"""Backend-neutral call requirements for a validated DEVICE runtime ABI.

This module is deliberately one step before executable lowering.  It combines
an already-validated ``DeviceRuntimeSIRBridgePlan`` with a structurally bound
runtime ABI plan and freezes which ABI symbol would be required at each
source-stable DEVICE lifecycle point.

The result is *not* a call instruction stream.  No symbol is invoked, no queue
is touched, no DMA/hardware work is submitted, and no C11/LLVM DEVICE support
is enabled.  Future backend lowering must consume this plan rather than
reconstructing lifecycle order or ABI identity independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .device_runtime import DeviceRuntimeSIRBridgePlan


class DeviceRuntimeCallPlanError(ValueError):
    """Raised when a bound ABI no longer matches the validated DEVICE proof."""


class _RequirementLike(Protocol):
    operation: Any
    function: str
    point_id: str
    binding: str | None
    queue: str | None
    depends_on: tuple[str, ...]


class _BoundRequirementLike(Protocol):
    requirement: _RequirementLike
    symbol: str


class _BoundPlanLike(Protocol):
    abi_name: str
    abi_version: int
    function: str
    queue: str
    requirements: tuple[_BoundRequirementLike, ...]


@dataclass(frozen=True)
class DeviceRuntimeCallRequirement:
    """One validated future runtime call obligation; still non-executable."""

    operation: str
    point_id: str
    symbol: str
    binding: str | None
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class DeviceRuntimeCallRequirementPlan:
    """Exact ABI/lifecycle schedule a future backend must lower honestly."""

    abi_name: str
    abi_version: int
    function: str
    queue: str
    calls: tuple[DeviceRuntimeCallRequirement, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(call.point_id for call in self.calls)


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimeCallPlanError(f"{label} requires a non-empty identity")
    return value


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    result = tuple(values)
    if not result:
        raise DeviceRuntimeCallPlanError(f"{label} requires at least one item")
    return result


def _operation_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None


def plan_bound_device_runtime_calls(
    bridge: DeviceRuntimeSIRBridgePlan,
    bound_plan: _BoundPlanLike,
) -> DeviceRuntimeCallRequirementPlan:
    """Freeze exact future call obligations without performing call lowering."""
    function = _required_text(bridge.function, label="DEVICE bridge function")
    queue = _required_text(bridge.queue, label="DEVICE bridge queue")
    abi_name = _required_text(
        getattr(bound_plan, "abi_name", None), label="DEVICE runtime ABI name"
    )
    abi_version = getattr(bound_plan, "abi_version", None)
    if (
        not isinstance(abi_version, int)
        or isinstance(abi_version, bool)
        or abi_version <= 0
    ):
        raise DeviceRuntimeCallPlanError(
            "DEVICE runtime ABI version must remain a positive integer"
        )
    if getattr(bound_plan, "function", None) != function:
        raise DeviceRuntimeCallPlanError(
            "DEVICE bound runtime plan crosses function identity"
        )
    if getattr(bound_plan, "queue", None) != queue:
        raise DeviceRuntimeCallPlanError(
            "DEVICE bound runtime plan crosses queue identity"
        )

    submissions = tuple(bridge.submission_point_ids)
    completions = tuple(bridge.completion_point_ids)
    reacquisitions = tuple(bridge.reacquisition_point_ids)
    sync_point = _required_text(
        bridge.synchronization_point_id,
        label="DEVICE bridge synchronization point",
    )
    owner_count = len(submissions)
    if owner_count == 0:
        raise DeviceRuntimeCallPlanError(
            "DEVICE runtime call plan requires at least one submission"
        )
    if len(completions) != owner_count or len(reacquisitions) != owner_count:
        raise DeviceRuntimeCallPlanError(
            "DEVICE bridge no longer has one completion/reacquisition per submission"
        )

    expected_runtime_points = (
        submissions + completions + (sync_point,) + reacquisitions
    )
    if tuple(bridge.runtime_point_ids) != expected_runtime_points:
        raise DeviceRuntimeCallPlanError(
            "DEVICE bridge runtime point order is internally inconsistent"
        )
    expected_sir_points = completions + (sync_point,) + reacquisitions
    if tuple(bridge.sir_point_ids) != expected_sir_points:
        raise DeviceRuntimeCallPlanError(
            "DEVICE bridge SIR point order is internally inconsistent"
        )
    if len(set(expected_runtime_points)) != len(expected_runtime_points):
        raise DeviceRuntimeCallPlanError(
            "DEVICE bridge lifecycle point identities must remain globally unique"
        )

    bound_requirements = _materialize(
        getattr(bound_plan, "requirements", ()) or (),
        label="DEVICE bound runtime requirements",
    )
    if len(bound_requirements) != len(expected_runtime_points):
        raise DeviceRuntimeCallPlanError(
            "DEVICE bound runtime plan must cover the exact lifecycle point set"
        )

    expected_operations = (
        ("submit",) * owner_count
        + ("complete",) * owner_count
        + ("synchronize",)
        + ("reacquire",) * owner_count
    )
    expected_dependencies = (
        ((),) * owner_count
        + tuple((point,) for point in submissions)
        + (completions,)
        + ((sync_point,),) * owner_count
    )

    calls: list[DeviceRuntimeCallRequirement] = []
    operation_symbols: dict[str, str] = {}
    symbol_operations: dict[str, str] = {}
    submit_bindings: list[str] = []

    for index, (bound, expected_point, expected_operation, expected_deps) in enumerate(
        zip(
            bound_requirements,
            expected_runtime_points,
            expected_operations,
            expected_dependencies,
            strict=True,
        )
    ):
        requirement = getattr(bound, "requirement", None)
        if requirement is None:
            raise DeviceRuntimeCallPlanError(
                "DEVICE bound runtime entry is missing its semantic requirement"
            )
        operation = _operation_value(getattr(requirement, "operation", None))
        if operation != expected_operation:
            raise DeviceRuntimeCallPlanError(
                "DEVICE bound runtime operation order diverges from the validated bridge"
            )
        if getattr(requirement, "point_id", None) != expected_point:
            raise DeviceRuntimeCallPlanError(
                "DEVICE bound runtime point order diverges from the validated bridge"
            )
        if getattr(requirement, "function", None) != function:
            raise DeviceRuntimeCallPlanError(
                "DEVICE bound runtime requirement crosses function identity"
            )
        if getattr(requirement, "queue", None) != queue:
            raise DeviceRuntimeCallPlanError(
                "DEVICE bound runtime requirement crosses queue identity"
            )
        dependencies = tuple(getattr(requirement, "depends_on", ()) or ())
        if dependencies != expected_deps:
            raise DeviceRuntimeCallPlanError(
                "DEVICE bound runtime dependency graph diverges from the validated bridge"
            )

        binding = getattr(requirement, "binding", None)
        if operation == "submit":
            submit_binding = _required_text(
                binding, label=f"DEVICE submission binding {index}"
            )
            submit_bindings.append(submit_binding)
        elif operation == "complete":
            owner_index = index - owner_count
            if binding != submit_bindings[owner_index]:
                raise DeviceRuntimeCallPlanError(
                    "DEVICE completion binding diverges from its submission"
                )
        elif operation == "synchronize":
            if binding is not None:
                raise DeviceRuntimeCallPlanError(
                    "DEVICE synchronization call must cover the batch, not one binding"
                )
        elif operation == "reacquire":
            owner_index = index - (owner_count * 2 + 1)
            if binding != submit_bindings[owner_index]:
                raise DeviceRuntimeCallPlanError(
                    "DEVICE reacquisition binding diverges from its submission"
                )

        symbol = _required_text(
            getattr(bound, "symbol", None), label="DEVICE runtime ABI symbol"
        )
        previous_symbol = operation_symbols.get(operation)
        if previous_symbol is not None and previous_symbol != symbol:
            raise DeviceRuntimeCallPlanError(
                "DEVICE runtime ABI symbol drifts within one operation"
            )
        previous_operation = symbol_operations.get(symbol)
        if previous_operation is not None and previous_operation != operation:
            raise DeviceRuntimeCallPlanError(
                "DEVICE runtime ABI symbol is reused by different operations"
            )
        operation_symbols[operation] = symbol
        symbol_operations[symbol] = operation

        calls.append(
            DeviceRuntimeCallRequirement(
                operation=operation,
                point_id=expected_point,
                symbol=symbol,
                binding=binding,
                depends_on=dependencies,
            )
        )

    if set(operation_symbols) != {"submit", "complete", "synchronize", "reacquire"}:
        raise DeviceRuntimeCallPlanError(
            "DEVICE runtime ABI call plan does not cover every lifecycle operation"
        )

    return DeviceRuntimeCallRequirementPlan(
        abi_name=abi_name,
        abi_version=abi_version,
        function=function,
        queue=queue,
        calls=tuple(calls),
    )
