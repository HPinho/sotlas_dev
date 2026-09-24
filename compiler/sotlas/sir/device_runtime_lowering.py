"""Backend-neutral lowering contract for validated DEVICE runtime calls.

This module freezes the *logical* ABI shape a future executable backend must
honor after ``DeviceRuntimeCallRequirementPlan`` has already proved lifecycle,
symbol, dependency, function and queue identity.

The value roles below are deliberately abstract.  They are not C types, LLVM
types, pointer layouts, register assignments, DMA descriptors or hardware
handles.  In particular ``COMPLETION_SET`` does not choose whether a physical
ABI will use a pointer/count pair, slice, array, descriptor or another
representation.

A backend may not emit DEVICE runtime calls merely because this plan exists.
Physical ABI layout, concrete runtime implementation and target lowering still
have to be defined and validated separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .device_runtime_calls import DeviceRuntimeCallRequirementPlan


class DeviceRuntimeLoweringPlanError(ValueError):
    """Raised when a DEVICE call plan cannot become an honest lowering plan."""


class DeviceRuntimeABIValueRole(str, Enum):
    """Abstract semantic roles crossing the future DEVICE runtime boundary."""

    QUEUE = "queue"
    HOST_OWNER = "host_owner"
    DEVICE_OWNER = "device_owner"
    SUBMISSION = "submission"
    COMPLETION = "completion"
    COMPLETION_SET = "completion_set"
    SYNC_FENCE = "sync_fence"


@dataclass(frozen=True)
class DeviceRuntimeABISignature:
    """Logical operation signature; intentionally independent of physical ABI."""

    operation: str
    parameters: tuple[DeviceRuntimeABIValueRole, ...]
    results: tuple[DeviceRuntimeABIValueRole, ...]


CANONICAL_DEVICE_RUNTIME_SIGNATURES: dict[str, DeviceRuntimeABISignature] = {
    "submit": DeviceRuntimeABISignature(
        operation="submit",
        parameters=(
            DeviceRuntimeABIValueRole.QUEUE,
            DeviceRuntimeABIValueRole.HOST_OWNER,
        ),
        results=(
            DeviceRuntimeABIValueRole.DEVICE_OWNER,
            DeviceRuntimeABIValueRole.SUBMISSION,
        ),
    ),
    "complete": DeviceRuntimeABISignature(
        operation="complete",
        parameters=(
            DeviceRuntimeABIValueRole.QUEUE,
            DeviceRuntimeABIValueRole.SUBMISSION,
        ),
        results=(DeviceRuntimeABIValueRole.COMPLETION,),
    ),
    "synchronize": DeviceRuntimeABISignature(
        operation="synchronize",
        parameters=(
            DeviceRuntimeABIValueRole.QUEUE,
            DeviceRuntimeABIValueRole.COMPLETION_SET,
        ),
        results=(DeviceRuntimeABIValueRole.SYNC_FENCE,),
    ),
    "reacquire": DeviceRuntimeABISignature(
        operation="reacquire",
        parameters=(
            DeviceRuntimeABIValueRole.QUEUE,
            DeviceRuntimeABIValueRole.DEVICE_OWNER,
            DeviceRuntimeABIValueRole.SYNC_FENCE,
        ),
        results=(DeviceRuntimeABIValueRole.HOST_OWNER,),
    ),
}


@dataclass(frozen=True)
class DeviceRuntimeLoweringRequirement:
    """One future backend call together with its canonical logical signature."""

    operation: str
    point_id: str
    symbol: str
    binding: str | None
    depends_on: tuple[str, ...]
    signature: DeviceRuntimeABISignature


@dataclass(frozen=True)
class DeviceRuntimeLoweringPlan:
    """Validated logical lowering schedule; contains no executable call IR."""

    abi_name: str
    abi_version: int
    function: str
    queue: str
    calls: tuple[DeviceRuntimeLoweringRequirement, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(call.point_id for call in self.calls)

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(call.symbol for call in self.calls)


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimeLoweringPlanError(
            f"{label} requires a non-empty source-stable identity"
        )
    return value


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    result = tuple(values)
    if not result:
        raise DeviceRuntimeLoweringPlanError(f"{label} requires at least one item")
    return result


def plan_device_runtime_lowering(
    call_plan: DeviceRuntimeCallRequirementPlan,
) -> DeviceRuntimeLoweringPlan:
    """Freeze logical DEVICE ABI signatures without choosing physical lowering."""
    abi_name = _required_text(
        getattr(call_plan, "abi_name", None), label="DEVICE runtime ABI name"
    )
    abi_version = getattr(call_plan, "abi_version", None)
    if (
        not isinstance(abi_version, int)
        or isinstance(abi_version, bool)
        or abi_version <= 0
    ):
        raise DeviceRuntimeLoweringPlanError(
            "DEVICE runtime ABI version must remain a positive integer"
        )
    function = _required_text(
        getattr(call_plan, "function", None), label="DEVICE runtime function"
    )
    queue = _required_text(
        getattr(call_plan, "queue", None), label="DEVICE runtime queue"
    )
    calls = _materialize(
        getattr(call_plan, "calls", ()) or (), label="DEVICE runtime calls"
    )

    operations = tuple(getattr(call, "operation", None) for call in calls)
    owner_count = operations.count("submit")
    if owner_count == 0:
        raise DeviceRuntimeLoweringPlanError(
            "DEVICE lowering requires at least one submitted owner"
        )
    expected_operations = (
        ("submit",) * owner_count
        + ("complete",) * owner_count
        + ("synchronize",)
        + ("reacquire",) * owner_count
    )
    if operations != expected_operations:
        raise DeviceRuntimeLoweringPlanError(
            "DEVICE lowering operation order diverges from the canonical lifecycle"
        )

    point_ids = tuple(
        _required_text(
            getattr(call, "point_id", None), label="DEVICE lowering lifecycle point"
        )
        for call in calls
    )
    if len(set(point_ids)) != len(point_ids):
        raise DeviceRuntimeLoweringPlanError(
            "DEVICE lowering lifecycle point identities must remain globally unique"
        )

    submissions = point_ids[:owner_count]
    completions = point_ids[owner_count : owner_count * 2]
    sync_index = owner_count * 2
    sync_point = point_ids[sync_index]
    reacquisitions = point_ids[sync_index + 1 :]
    if len(reacquisitions) != owner_count:
        raise DeviceRuntimeLoweringPlanError(
            "DEVICE lowering requires one reacquisition per submitted owner"
        )

    submit_bindings: list[str] = []
    operation_symbols: dict[str, str] = {}
    symbol_operations: dict[str, str] = {}
    lowered: list[DeviceRuntimeLoweringRequirement] = []

    for index, call in enumerate(calls):
        operation = operations[index]
        if operation not in CANONICAL_DEVICE_RUNTIME_SIGNATURES:
            raise DeviceRuntimeLoweringPlanError(
                f"DEVICE lowering received unsupported operation {operation!r}"
            )

        symbol = _required_text(
            getattr(call, "symbol", None), label="DEVICE lowering runtime symbol"
        )
        previous_symbol = operation_symbols.get(operation)
        if previous_symbol is not None and previous_symbol != symbol:
            raise DeviceRuntimeLoweringPlanError(
                "DEVICE lowering symbol drifts within one operation"
            )
        previous_operation = symbol_operations.get(symbol)
        if previous_operation is not None and previous_operation != operation:
            raise DeviceRuntimeLoweringPlanError(
                "DEVICE lowering symbol is reused by different operations"
            )
        operation_symbols[operation] = symbol
        symbol_operations[symbol] = operation

        dependencies = tuple(getattr(call, "depends_on", ()) or ())
        binding = getattr(call, "binding", None)

        if operation == "submit":
            if dependencies:
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE submit cannot depend on a later lifecycle point"
                )
            submit_bindings.append(
                _required_text(
                    binding, label=f"DEVICE lowering submission binding {index}"
                )
            )
        elif operation == "complete":
            owner_index = index - owner_count
            if dependencies != (submissions[owner_index],):
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE completion dependency diverges from its submission"
                )
            if binding != submit_bindings[owner_index]:
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE completion binding diverges from its submission"
                )
        elif operation == "synchronize":
            if dependencies != completions:
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE synchronization dependency set diverges from completions"
                )
            if binding is not None:
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE synchronization must cover the batch, not one binding"
                )
        elif operation == "reacquire":
            owner_index = index - (sync_index + 1)
            if dependencies != (sync_point,):
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE reacquisition dependency diverges from synchronization"
                )
            if binding != submit_bindings[owner_index]:
                raise DeviceRuntimeLoweringPlanError(
                    "DEVICE reacquisition binding diverges from its submission"
                )

        lowered.append(
            DeviceRuntimeLoweringRequirement(
                operation=operation,
                point_id=point_ids[index],
                symbol=symbol,
                binding=binding,
                depends_on=dependencies,
                signature=CANONICAL_DEVICE_RUNTIME_SIGNATURES[operation],
            )
        )

    if set(operation_symbols) != set(CANONICAL_DEVICE_RUNTIME_SIGNATURES):
        raise DeviceRuntimeLoweringPlanError(
            "DEVICE lowering plan does not cover every canonical runtime operation"
        )

    return DeviceRuntimeLoweringPlan(
        abi_name=abi_name,
        abi_version=abi_version,
        function=function,
        queue=queue,
        calls=tuple(lowered),
    )
