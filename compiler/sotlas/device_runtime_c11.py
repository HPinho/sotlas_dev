"""Reference C11 declaration boundary for the Sotlas DEVICE runtime ABI.

This module is intentionally declaration-only.  It chooses one concrete C11
representation for the already-validated logical/physical DEVICE ABI and
produces prototypes plus a source-stable map of physical operand slots.

No runtime call is emitted here.  No queue is touched, no ownership transition
is executed, and no hardware transfer is enabled.  Executable C11 lowering must
consume this plan rather than reconstructing ABI details independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sir.device_runtime_lowering import (
    CANONICAL_DEVICE_RUNTIME_SIGNATURES,
    DeviceRuntimeABIValueRole,
    DeviceRuntimeLoweringRequirement,
)
from .sir.device_runtime_physical_abi import (
    BoundDeviceRuntimePhysicalABIPlan,
    DeviceRuntimePhysicalABIContract,
    DeviceRuntimePhysicalOperationABI,
    DeviceRuntimePhysicalParameter,
    DeviceRuntimePhysicalResult,
    DeviceRuntimeResultTransport,
)


class DeviceRuntimeC11ABIError(ValueError):
    """Raised when a bound DEVICE plan cannot use the reference C11 ABI."""


REFERENCE_C11_DEVICE_ABI_NAME = "sotlas.device.reference"
REFERENCE_C11_DEVICE_ABI_VERSION = 1
REFERENCE_C11_DEVICE_BACKEND = "c11-reference"
REFERENCE_C11_CALLING_CONVENTION = "c"

CANONICAL_C11_DEVICE_SYMBOLS = {
    "submit": "sotlas_device_submit",
    "complete": "sotlas_device_complete",
    "synchronize": "sotlas_device_sync",
    "reacquire": "sotlas_device_reacquire",
}

_REFERENCE_C11_TYPE_NAMES = {
    "sotlas_device_queue_t",
    "sotlas_device_submission_t",
    "sotlas_device_completion_t",
    "sotlas_device_fence_t",
    "uintptr_t",
    "size_t",
    "const sotlas_device_completion_t *",
}


@dataclass(frozen=True)
class C11DeviceRuntimeOperandSlot:
    """One physical C11 operand/result slot; still not a concrete expression."""

    role: DeviceRuntimeABIValueRole
    component: str | None
    c_type: str
    name: str
    direction: str


@dataclass(frozen=True)
class C11DeviceRuntimePrototype:
    operation: str
    symbol: str
    return_type: str
    parameters: tuple[C11DeviceRuntimeOperandSlot, ...]

    @property
    def declaration(self) -> str:
        rendered = ", ".join(
            f"{parameter.c_type} {parameter.name}" for parameter in self.parameters
        ) or "void"
        return f"{self.return_type} {self.symbol}({rendered});"


@dataclass(frozen=True)
class C11DeviceRuntimeCallLayout:
    """Physical operand layout for one source-stable future runtime call."""

    operation: str
    point_id: str
    symbol: str
    inputs: tuple[C11DeviceRuntimeOperandSlot, ...]
    outputs: tuple[C11DeviceRuntimeOperandSlot, ...]
    direct_result: C11DeviceRuntimeOperandSlot | None


@dataclass(frozen=True)
class C11DeviceRuntimeDeclarationPlan:
    abi_name: str
    abi_version: int
    function: str
    queue: str
    includes: tuple[str, ...]
    typedefs: tuple[str, ...]
    prototypes: tuple[C11DeviceRuntimePrototype, ...]
    calls: tuple[C11DeviceRuntimeCallLayout, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(call.point_id for call in self.calls)

    def render_declarations(self) -> str:
        sections = [*self.includes, "", *self.typedefs, ""]
        sections.extend(prototype.declaration for prototype in self.prototypes)
        return "\n".join(sections).rstrip() + "\n"


def reference_c11_device_runtime_contract() -> DeviceRuntimePhysicalABIContract:
    """Return the exact v1 physical ABI declaration for the reference C11 backend."""
    role = DeviceRuntimeABIValueRole
    parameter = DeviceRuntimePhysicalParameter
    result = DeviceRuntimePhysicalResult
    transport = DeviceRuntimeResultTransport
    operation = DeviceRuntimePhysicalOperationABI

    return DeviceRuntimePhysicalABIContract(
        abi_name=REFERENCE_C11_DEVICE_ABI_NAME,
        abi_version=REFERENCE_C11_DEVICE_ABI_VERSION,
        backend=REFERENCE_C11_DEVICE_BACKEND,
        calling_convention=REFERENCE_C11_CALLING_CONVENTION,
        operations=(
            operation(
                "submit",
                (
                    parameter(role.QUEUE, "sotlas_device_queue_t"),
                    parameter(role.HOST_OWNER, "uintptr_t", "address"),
                    parameter(role.HOST_OWNER, "size_t", "extent"),
                ),
                (
                    result(
                        role.DEVICE_OWNER,
                        "uintptr_t",
                        transport.OUT_PARAMETER,
                        "address",
                    ),
                    result(
                        role.DEVICE_OWNER,
                        "size_t",
                        transport.OUT_PARAMETER,
                        "extent",
                    ),
                    result(
                        role.SUBMISSION,
                        "sotlas_device_submission_t",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                "complete",
                (
                    parameter(role.QUEUE, "sotlas_device_queue_t"),
                    parameter(role.SUBMISSION, "sotlas_device_submission_t"),
                ),
                (
                    result(
                        role.COMPLETION,
                        "sotlas_device_completion_t",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                "synchronize",
                (
                    parameter(role.QUEUE, "sotlas_device_queue_t"),
                    parameter(
                        role.COMPLETION_SET,
                        "const sotlas_device_completion_t *",
                        "data",
                    ),
                    parameter(role.COMPLETION_SET, "size_t", "count"),
                ),
                (
                    result(
                        role.SYNC_FENCE,
                        "sotlas_device_fence_t",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                "reacquire",
                (
                    parameter(role.QUEUE, "sotlas_device_queue_t"),
                    parameter(role.DEVICE_OWNER, "uintptr_t", "address"),
                    parameter(role.DEVICE_OWNER, "size_t", "extent"),
                    parameter(role.SYNC_FENCE, "sotlas_device_fence_t"),
                ),
                (
                    result(
                        role.HOST_OWNER,
                        "uintptr_t",
                        transport.OUT_PARAMETER,
                        "address",
                    ),
                    result(
                        role.HOST_OWNER,
                        "size_t",
                        transport.OUT_PARAMETER,
                        "extent",
                    ),
                ),
            ),
        ),
    )


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimeC11ABIError(f"{label} requires a non-empty identity")
    return value


def _operand_name(
    role: DeviceRuntimeABIValueRole,
    component: str | None,
    *,
    output: bool,
) -> str:
    bases = {
        DeviceRuntimeABIValueRole.QUEUE: "queue",
        DeviceRuntimeABIValueRole.HOST_OWNER: "host",
        DeviceRuntimeABIValueRole.DEVICE_OWNER: "device",
        DeviceRuntimeABIValueRole.SUBMISSION: "submission",
        DeviceRuntimeABIValueRole.COMPLETION: "completion",
        DeviceRuntimeABIValueRole.COMPLETION_SET: "completions",
        DeviceRuntimeABIValueRole.SYNC_FENCE: "fence",
    }
    base = bases[role]
    if component:
        if role is DeviceRuntimeABIValueRole.COMPLETION_SET and component == "data":
            base = "completions"
        elif role is DeviceRuntimeABIValueRole.COMPLETION_SET and component == "count":
            base = "completion_count"
        else:
            base = f"{base}_{component}"
    return f"out_{base}" if output else base


def _validated_type_name(value: str, *, operation: str) -> str:
    c_type = _required_text(value, label=f"DEVICE C11 {operation} type")
    if c_type not in _REFERENCE_C11_TYPE_NAMES:
        raise DeviceRuntimeC11ABIError(
            f"DEVICE C11 {operation} uses non-reference physical type {c_type!r}"
        )
    return c_type


def _out_parameter_type(c_type: str) -> str:
    if c_type.endswith("*"):
        return c_type + "*"
    return c_type + " *"


def plan_reference_c11_device_runtime(
    bound_plan: BoundDeviceRuntimePhysicalABIPlan,
) -> C11DeviceRuntimeDeclarationPlan:
    """Validate and render declarations/operand slots; never emit a runtime call."""
    if not isinstance(bound_plan, BoundDeviceRuntimePhysicalABIPlan):
        raise DeviceRuntimeC11ABIError(
            "DEVICE C11 declarations require a validated physical ABI plan"
        )
    if bound_plan.abi_name != REFERENCE_C11_DEVICE_ABI_NAME:
        raise DeviceRuntimeC11ABIError("DEVICE C11 ABI name is not the reference ABI")
    if bound_plan.abi_version != REFERENCE_C11_DEVICE_ABI_VERSION:
        raise DeviceRuntimeC11ABIError("DEVICE C11 ABI version is not supported")
    if bound_plan.backend != REFERENCE_C11_DEVICE_BACKEND:
        raise DeviceRuntimeC11ABIError("DEVICE C11 physical backend identity diverges")
    if bound_plan.calling_convention != REFERENCE_C11_CALLING_CONVENTION:
        raise DeviceRuntimeC11ABIError("DEVICE C11 calling convention diverges")

    function = _required_text(bound_plan.function, label="DEVICE C11 function")
    queue = _required_text(bound_plan.queue, label="DEVICE C11 queue")
    if not bound_plan.calls:
        raise DeviceRuntimeC11ABIError("DEVICE C11 plan requires lifecycle calls")

    logical_calls: list[DeviceRuntimeLoweringRequirement] = []
    for bound in bound_plan.calls:
        if not isinstance(bound.logical, DeviceRuntimeLoweringRequirement):
            raise DeviceRuntimeC11ABIError(
                "DEVICE C11 plan contains an invalid logical call requirement"
            )
        logical_calls.append(bound.logical)

    operations = tuple(call.operation for call in logical_calls)
    owner_count = operations.count("submit")
    if owner_count == 0:
        raise DeviceRuntimeC11ABIError(
            "DEVICE C11 lifecycle requires at least one submitted owner"
        )
    expected_operations = (
        ("submit",) * owner_count
        + ("complete",) * owner_count
        + ("synchronize",)
        + ("reacquire",) * owner_count
    )
    if operations != expected_operations:
        raise DeviceRuntimeC11ABIError(
            "DEVICE C11 lifecycle operation order diverges from canonical ordering"
        )

    points = tuple(
        _required_text(call.point_id, label="DEVICE C11 lifecycle point")
        for call in logical_calls
    )
    if len(set(points)) != len(points):
        raise DeviceRuntimeC11ABIError(
            "DEVICE C11 lifecycle point identities must remain globally unique"
        )
    submissions = points[:owner_count]
    completions = points[owner_count : owner_count * 2]
    sync_index = owner_count * 2
    sync_point = points[sync_index]

    submit_bindings: list[str] = []
    for index, logical in enumerate(logical_calls):
        dependencies = tuple(logical.depends_on)
        binding = logical.binding
        if logical.operation == "submit":
            if dependencies:
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 submit cannot depend on a later lifecycle point"
                )
            submit_bindings.append(
                _required_text(
                    binding, label=f"DEVICE C11 submission binding {index}"
                )
            )
        elif logical.operation == "complete":
            owner_index = index - owner_count
            if dependencies != (submissions[owner_index],):
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 completion dependency diverges from submission"
                )
            if binding != submit_bindings[owner_index]:
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 completion binding diverges from submission"
                )
        elif logical.operation == "synchronize":
            if dependencies != completions:
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 synchronization dependencies diverge from completions"
                )
            if binding is not None:
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 synchronization must cover the batch"
                )
        elif logical.operation == "reacquire":
            owner_index = index - (sync_index + 1)
            if dependencies != (sync_point,):
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 reacquisition dependency diverges from synchronization"
                )
            if binding != submit_bindings[owner_index]:
                raise DeviceRuntimeC11ABIError(
                    "DEVICE C11 reacquisition binding diverges from submission"
                )

    reference_operations = {
        operation.operation: operation
        for operation in reference_c11_device_runtime_contract().operations
    }
    prototypes_by_operation: dict[str, C11DeviceRuntimePrototype] = {}
    calls: list[C11DeviceRuntimeCallLayout] = []

    for bound, logical in zip(bound_plan.calls, logical_calls, strict=True):
        operation = _required_text(logical.operation, label="DEVICE C11 operation")
        canonical_signature = CANONICAL_DEVICE_RUNTIME_SIGNATURES.get(operation)
        if canonical_signature is None or logical.signature != canonical_signature:
            raise DeviceRuntimeC11ABIError(
                f"DEVICE C11 {operation} logical signature is not canonical"
            )
        expected_physical = reference_operations.get(operation)
        if expected_physical is None or bound.physical != expected_physical:
            raise DeviceRuntimeC11ABIError(
                f"DEVICE C11 {operation} physical ABI diverges from reference v1"
            )
        expected_symbol = CANONICAL_C11_DEVICE_SYMBOLS[operation]
        if logical.symbol != expected_symbol:
            raise DeviceRuntimeC11ABIError(
                f"DEVICE C11 {operation} symbol diverges from reference v1"
            )

        input_slots: list[C11DeviceRuntimeOperandSlot] = []
        parameter_slots: list[C11DeviceRuntimeOperandSlot] = []
        for parameter in bound.physical.parameters:
            c_type = _validated_type_name(parameter.type_name, operation=operation)
            name = _operand_name(parameter.role, parameter.component, output=False)
            slot = C11DeviceRuntimeOperandSlot(
                role=parameter.role,
                component=parameter.component,
                c_type=c_type,
                name=name,
                direction="input",
            )
            input_slots.append(slot)
            parameter_slots.append(slot)

        outputs: list[C11DeviceRuntimeOperandSlot] = []
        direct_result: C11DeviceRuntimeOperandSlot | None = None
        return_type = "void"
        for result in bound.physical.results:
            c_type = _validated_type_name(result.type_name, operation=operation)
            if result.transport is DeviceRuntimeResultTransport.OUT_PARAMETER:
                slot = C11DeviceRuntimeOperandSlot(
                    role=result.role,
                    component=result.component,
                    c_type=_out_parameter_type(c_type),
                    name=_operand_name(result.role, result.component, output=True),
                    direction="output",
                )
                outputs.append(slot)
                parameter_slots.append(slot)
            elif result.transport is DeviceRuntimeResultTransport.RETURN_VALUE:
                if direct_result is not None:
                    raise DeviceRuntimeC11ABIError(
                        f"DEVICE C11 {operation} has multiple direct return values"
                    )
                direct_result = C11DeviceRuntimeOperandSlot(
                    role=result.role,
                    component=result.component,
                    c_type=c_type,
                    name=_operand_name(result.role, result.component, output=False),
                    direction="return",
                )
                return_type = c_type
            else:
                raise DeviceRuntimeC11ABIError(
                    f"DEVICE C11 {operation} uses unsupported result transport"
                )

        names = tuple(slot.name for slot in parameter_slots)
        if len(set(names)) != len(names):
            raise DeviceRuntimeC11ABIError(
                f"DEVICE C11 {operation} produces duplicate physical parameter names"
            )

        prototype = C11DeviceRuntimePrototype(
            operation=operation,
            symbol=expected_symbol,
            return_type=return_type,
            parameters=tuple(parameter_slots),
        )
        previous = prototypes_by_operation.get(operation)
        if previous is not None and previous != prototype:
            raise DeviceRuntimeC11ABIError(
                f"DEVICE C11 {operation} prototype drifts across lifecycle calls"
            )
        prototypes_by_operation[operation] = prototype
        calls.append(
            C11DeviceRuntimeCallLayout(
                operation=operation,
                point_id=logical.point_id,
                symbol=expected_symbol,
                inputs=tuple(input_slots),
                outputs=tuple(outputs),
                direct_result=direct_result,
            )
        )

    canonical_operation_order = tuple(CANONICAL_C11_DEVICE_SYMBOLS)
    if tuple(prototypes_by_operation) != canonical_operation_order:
        raise DeviceRuntimeC11ABIError(
            "DEVICE C11 declarations do not cover canonical operations in order"
        )
    if tuple(call.point_id for call in calls) != points:
        raise DeviceRuntimeC11ABIError(
            "DEVICE C11 declaration planning changed lifecycle point order"
        )

    return C11DeviceRuntimeDeclarationPlan(
        abi_name=bound_plan.abi_name,
        abi_version=bound_plan.abi_version,
        function=function,
        queue=queue,
        includes=("#include <stddef.h>", "#include <stdint.h>"),
        typedefs=(
            "typedef uintptr_t sotlas_device_queue_t;",
            "typedef uintptr_t sotlas_device_submission_t;",
            "typedef uintptr_t sotlas_device_completion_t;",
            "typedef uintptr_t sotlas_device_fence_t;",
        ),
        prototypes=tuple(
            prototypes_by_operation[operation]
            for operation in canonical_operation_order
        ),
        calls=tuple(calls),
    )
