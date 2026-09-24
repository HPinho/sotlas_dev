"""Backend-neutral ABI requirements for DEVICE ownership execution.

This module does *not* implement a runtime, submit work to hardware, wait on a
queue, perform DMA, or make DEVICE ownership executable.  It freezes the
minimum runtime contract that a future backend/runtime must satisfy before the
already-proven semantic DEVICE lifecycle can be lowered honestly.

For every synchronized ownership batch the required dependency chain is:

    submit -> completion -> synchronization fence -> reacquisition

The result is a source-stable requirement DAG.  A concrete runtime ABI may be
bound to that DAG only when it declares one unique symbol for every required
operation.  Binding is validation only; it performs no call lowering.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .device_ownership import DeviceTransferState
from .device_sync import DeviceSyncState
from .typed_ast import Phase1SemanticError


class DeviceRuntimeABIError(Phase1SemanticError):
    """Raised when a DEVICE runtime contract would weaken semantic proof."""


class DeviceRuntimeOperation(str, Enum):
    SUBMIT = "submit"
    COMPLETE = "complete"
    SYNCHRONIZE = "synchronize"
    REACQUIRE = "reacquire"


@dataclass(frozen=True)
class DeviceRuntimeRequirement:
    operation: DeviceRuntimeOperation
    function: str
    point_id: str
    binding: str | None = None
    queue: str | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceRuntimeRequirementPlan:
    function: str
    queue: str
    requirements: tuple[DeviceRuntimeRequirement, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(requirement.point_id for requirement in self.requirements)

    def requirements_for(
        self, operation: DeviceRuntimeOperation
    ) -> tuple[DeviceRuntimeRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.operation is operation
        )


@dataclass(frozen=True)
class DeviceRuntimeABISymbol:
    operation: DeviceRuntimeOperation
    symbol: str


@dataclass(frozen=True)
class DeviceRuntimeABIContract:
    name: str
    version: int
    symbols: tuple[DeviceRuntimeABISymbol, ...]


@dataclass(frozen=True)
class BoundDeviceRuntimeRequirement:
    requirement: DeviceRuntimeRequirement
    symbol: str


@dataclass(frozen=True)
class BoundDeviceRuntimePlan:
    abi_name: str
    abi_version: int
    function: str
    queue: str
    requirements: tuple[BoundDeviceRuntimeRequirement, ...]


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimeABIError(
            f"{label} requires a non-empty source-stable identity"
        )
    return value


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    materialized = tuple(values)
    if not materialized:
        raise DeviceRuntimeABIError(f"{label} requires at least one item")
    return materialized


def _enum_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None


def plan_device_runtime_requirements(
    tokens: Iterable[Any],
    batch: Any,
) -> DeviceRuntimeRequirementPlan:
    """Freeze the exact runtime obligations for one synchronized DEVICE batch."""
    semantic_tokens = _materialize(tokens, label="DEVICE runtime tokens")
    fence = getattr(batch, "fence", None)
    plans = _materialize(
        getattr(batch, "plans", ()) or (),
        label="DEVICE runtime reacquisition plans",
    )
    if len(plans) != len(semantic_tokens):
        raise DeviceRuntimeABIError(
            "DEVICE runtime requirements need one reacquisition plan per token"
        )

    fence_state = _enum_value(getattr(fence, "state", None))
    if fence_state != DeviceSyncState.SYNCHRONIZED.value:
        raise DeviceRuntimeABIError(
            "DEVICE runtime requirements require a SYNCHRONIZED fence"
        )

    function = _required_text(
        getattr(fence, "function", None), label="DEVICE runtime function"
    )
    queue = _required_text(
        getattr(fence, "queue", None), label="DEVICE runtime queue"
    )
    sync_point = _required_text(
        getattr(fence, "sync_point_id", None), label="DEVICE runtime sync point"
    )

    fence_submissions = tuple(
        getattr(fence, "submission_point_ids", ()) or ()
    )
    fence_completions = tuple(
        getattr(fence, "completion_point_ids", ()) or ()
    )
    if (
        not fence_submissions
        or len(fence_submissions) != len(semantic_tokens)
        or len(fence_completions) != len(semantic_tokens)
    ):
        raise DeviceRuntimeABIError(
            "DEVICE runtime fence must cover the exact synchronized token set"
        )

    submissions: list[DeviceRuntimeRequirement] = []
    completions: list[DeviceRuntimeRequirement] = []
    reacquisitions: list[DeviceRuntimeRequirement] = []

    for index, (token, plan) in enumerate(zip(semantic_tokens, plans, strict=True)):
        state = _enum_value(getattr(token, "state", None))
        if state != DeviceTransferState.COMPLETED.value:
            raise DeviceRuntimeABIError(
                f"DEVICE runtime plan requires COMPLETED token, got {state!r}"
            )
        token_function = _required_text(
            getattr(token, "function", None), label="DEVICE token function"
        )
        binding = _required_text(
            getattr(token, "binding", None), label="DEVICE token binding"
        )
        if token_function != function:
            raise DeviceRuntimeABIError(
                "DEVICE runtime tokens cannot cross function boundaries"
            )
        if getattr(plan, "function", None) != function:
            raise DeviceRuntimeABIError(
                "DEVICE runtime reacquisition plan has a different function"
            )
        if getattr(plan, "binding", None) != binding:
            raise DeviceRuntimeABIError(
                "DEVICE runtime token and reacquisition binding differ"
            )

        submission_point = _required_text(
            getattr(token, "submission_point_id", None),
            label="DEVICE runtime submission point",
        )
        completion_point = _required_text(
            getattr(token, "completion_point_id", None),
            label="DEVICE runtime completion point",
        )
        reacquisition_point = _required_text(
            getattr(plan, "reacquisition_point_id", None),
            label="DEVICE runtime reacquisition point",
        )
        if submission_point != fence_submissions[index]:
            raise DeviceRuntimeABIError(
                "DEVICE runtime submission identity diverges from sync fence"
            )
        if completion_point != fence_completions[index]:
            raise DeviceRuntimeABIError(
                "DEVICE runtime completion identity diverges from sync fence"
            )
        if getattr(plan, "submission_point_id", None) != submission_point:
            raise DeviceRuntimeABIError(
                "DEVICE runtime reacquisition lost its submission identity"
            )
        if getattr(plan, "completion_point_id", None) != completion_point:
            raise DeviceRuntimeABIError(
                "DEVICE runtime reacquisition lost its completion identity"
            )

        submissions.append(
            DeviceRuntimeRequirement(
                operation=DeviceRuntimeOperation.SUBMIT,
                function=function,
                binding=binding,
                queue=queue,
                point_id=submission_point,
            )
        )
        completions.append(
            DeviceRuntimeRequirement(
                operation=DeviceRuntimeOperation.COMPLETE,
                function=function,
                binding=binding,
                queue=queue,
                point_id=completion_point,
                depends_on=(submission_point,),
            )
        )
        reacquisitions.append(
            DeviceRuntimeRequirement(
                operation=DeviceRuntimeOperation.REACQUIRE,
                function=function,
                binding=binding,
                queue=queue,
                point_id=reacquisition_point,
                depends_on=(sync_point,),
            )
        )

    sync_requirement = DeviceRuntimeRequirement(
        operation=DeviceRuntimeOperation.SYNCHRONIZE,
        function=function,
        queue=queue,
        point_id=sync_point,
        depends_on=tuple(requirement.point_id for requirement in completions),
    )
    requirements = tuple(submissions + completions + [sync_requirement] + reacquisitions)

    point_ids = tuple(requirement.point_id for requirement in requirements)
    if len(set(point_ids)) != len(point_ids):
        raise DeviceRuntimeABIError(
            "DEVICE runtime lifecycle point identities must be globally unique"
        )
    known_points = set(point_ids)
    for requirement in requirements:
        if requirement.point_id in requirement.depends_on:
            raise DeviceRuntimeABIError(
                "DEVICE runtime requirement cannot depend on itself"
            )
        missing = tuple(
            point for point in requirement.depends_on if point not in known_points
        )
        if missing:
            raise DeviceRuntimeABIError(
                "DEVICE runtime requirement depends on an unknown lifecycle point"
            )

    return DeviceRuntimeRequirementPlan(
        function=function,
        queue=queue,
        requirements=requirements,
    )


def bind_device_runtime_abi(
    plan: DeviceRuntimeRequirementPlan,
    contract: DeviceRuntimeABIContract,
) -> BoundDeviceRuntimePlan:
    """Validate an ABI declaration against a proven plan without executing it."""
    abi_name = _required_text(contract.name, label="DEVICE runtime ABI name")
    if not isinstance(contract.version, int) or isinstance(contract.version, bool) or contract.version <= 0:
        raise DeviceRuntimeABIError("DEVICE runtime ABI version must be positive")

    symbols = tuple(contract.symbols)
    if not symbols:
        raise DeviceRuntimeABIError("DEVICE runtime ABI declares no operations")

    by_operation: dict[DeviceRuntimeOperation, str] = {}
    seen_symbols: set[str] = set()
    for entry in symbols:
        if not isinstance(entry, DeviceRuntimeABISymbol):
            raise DeviceRuntimeABIError(
                "DEVICE runtime ABI contains an invalid symbol declaration"
            )
        symbol = _required_text(entry.symbol, label="DEVICE runtime ABI symbol")
        if entry.operation in by_operation:
            raise DeviceRuntimeABIError(
                f"DEVICE runtime ABI declares {entry.operation.value} more than once"
            )
        if symbol in seen_symbols:
            raise DeviceRuntimeABIError(
                "DEVICE runtime ABI symbols must be unique per operation"
            )
        by_operation[entry.operation] = symbol
        seen_symbols.add(symbol)

    required_operations = {
        requirement.operation for requirement in plan.requirements
    }
    missing_operations = required_operations - set(by_operation)
    if missing_operations:
        missing = ", ".join(
            operation.value
            for operation in sorted(missing_operations, key=lambda item: item.value)
        )
        raise DeviceRuntimeABIError(
            f"DEVICE runtime ABI is missing required operations: {missing}"
        )

    bound = tuple(
        BoundDeviceRuntimeRequirement(
            requirement=requirement,
            symbol=by_operation[requirement.operation],
        )
        for requirement in plan.requirements
    )
    return BoundDeviceRuntimePlan(
        abi_name=abi_name,
        abi_version=contract.version,
        function=plan.function,
        queue=plan.queue,
        requirements=bound,
    )
