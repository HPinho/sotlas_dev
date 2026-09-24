"""Validation boundary between logical DEVICE ABI and physical backend ABI.

The logical lowering plan deliberately says nothing about C/LLVM types or how
multiple results are transported.  This module lets one concrete backend
declare those choices and validates that the declaration is a faithful physical
representation of the already-proven logical ABI.

Validation still does not emit a call.  A physical contract may choose a return
value or out-parameter for logical results, but it may not add, remove, reorder
or reinterpret logical DEVICE roles.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .device_runtime_lowering import (
    DeviceRuntimeABIValueRole,
    DeviceRuntimeLoweringPlan,
    DeviceRuntimeLoweringRequirement,
)


class DeviceRuntimePhysicalABIError(ValueError):
    """Raised when a physical runtime ABI weakens the logical DEVICE contract."""


class DeviceRuntimeResultTransport(str, Enum):
    """How one logical result crosses a concrete backend call boundary."""

    RETURN_VALUE = "return_value"
    OUT_PARAMETER = "out_parameter"


@dataclass(frozen=True)
class DeviceRuntimePhysicalParameter:
    role: DeviceRuntimeABIValueRole
    type_name: str


@dataclass(frozen=True)
class DeviceRuntimePhysicalResult:
    role: DeviceRuntimeABIValueRole
    type_name: str
    transport: DeviceRuntimeResultTransport


@dataclass(frozen=True)
class DeviceRuntimePhysicalOperationABI:
    operation: str
    parameters: tuple[DeviceRuntimePhysicalParameter, ...]
    results: tuple[DeviceRuntimePhysicalResult, ...]


@dataclass(frozen=True)
class DeviceRuntimePhysicalABIContract:
    abi_name: str
    abi_version: int
    backend: str
    calling_convention: str
    operations: tuple[DeviceRuntimePhysicalOperationABI, ...]


@dataclass(frozen=True)
class BoundDeviceRuntimePhysicalCall:
    logical: DeviceRuntimeLoweringRequirement
    physical: DeviceRuntimePhysicalOperationABI


@dataclass(frozen=True)
class BoundDeviceRuntimePhysicalABIPlan:
    abi_name: str
    abi_version: int
    backend: str
    calling_convention: str
    function: str
    queue: str
    calls: tuple[BoundDeviceRuntimePhysicalCall, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(call.logical.point_id for call in self.calls)


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimePhysicalABIError(f"{label} requires a non-empty identity")
    return value


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    result = tuple(values)
    if not result:
        raise DeviceRuntimePhysicalABIError(f"{label} requires at least one item")
    return result


def bind_device_runtime_physical_abi(
    logical_plan: DeviceRuntimeLoweringPlan,
    contract: DeviceRuntimePhysicalABIContract,
) -> BoundDeviceRuntimePhysicalABIPlan:
    """Validate one backend's physical ABI without emitting executable calls."""
    abi_name = _required_text(
        getattr(contract, "abi_name", None), label="DEVICE physical ABI name"
    )
    if abi_name != logical_plan.abi_name:
        raise DeviceRuntimePhysicalABIError(
            "DEVICE physical ABI name diverges from the logical runtime ABI"
        )

    abi_version = getattr(contract, "abi_version", None)
    if (
        not isinstance(abi_version, int)
        or isinstance(abi_version, bool)
        or abi_version <= 0
    ):
        raise DeviceRuntimePhysicalABIError(
            "DEVICE physical ABI version must be a positive integer"
        )
    if abi_version != logical_plan.abi_version:
        raise DeviceRuntimePhysicalABIError(
            "DEVICE physical ABI version diverges from the logical runtime ABI"
        )

    backend = _required_text(
        getattr(contract, "backend", None), label="DEVICE physical ABI backend"
    )
    calling_convention = _required_text(
        getattr(contract, "calling_convention", None),
        label="DEVICE physical ABI calling convention",
    )
    logical_calls = _materialize(
        getattr(logical_plan, "calls", ()) or (), label="DEVICE logical lowering calls"
    )
    physical_operations = _materialize(
        getattr(contract, "operations", ()) or (), label="DEVICE physical ABI operations"
    )

    operation_map: dict[str, DeviceRuntimePhysicalOperationABI] = {}
    for physical in physical_operations:
        if not isinstance(physical, DeviceRuntimePhysicalOperationABI):
            raise DeviceRuntimePhysicalABIError(
                "DEVICE physical ABI contains an invalid operation declaration"
            )
        operation = _required_text(
            physical.operation, label="DEVICE physical ABI operation"
        )
        if operation in operation_map:
            raise DeviceRuntimePhysicalABIError(
                f"DEVICE physical ABI declares {operation} more than once"
            )
        operation_map[operation] = physical

    logical_operations = {call.operation for call in logical_calls}
    if set(operation_map) != logical_operations:
        missing = sorted(logical_operations - set(operation_map))
        extra = sorted(set(operation_map) - logical_operations)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise DeviceRuntimePhysicalABIError(
            "DEVICE physical ABI must cover the exact logical operation set"
            + (": " + "; ".join(details) if details else "")
        )

    for operation, physical in operation_map.items():
        logical_for_operation = next(
            call for call in logical_calls if call.operation == operation
        )
        signature = logical_for_operation.signature

        parameters = tuple(physical.parameters)
        parameter_roles = tuple(parameter.role for parameter in parameters)
        if parameter_roles != signature.parameters:
            raise DeviceRuntimePhysicalABIError(
                f"DEVICE physical {operation} parameter roles diverge from logical ABI"
            )
        for parameter in parameters:
            if not isinstance(parameter, DeviceRuntimePhysicalParameter):
                raise DeviceRuntimePhysicalABIError(
                    f"DEVICE physical {operation} contains an invalid parameter"
                )
            _required_text(
                parameter.type_name,
                label=f"DEVICE physical {operation} parameter type",
            )

        results = tuple(physical.results)
        result_roles = tuple(result.role for result in results)
        if result_roles != signature.results:
            raise DeviceRuntimePhysicalABIError(
                f"DEVICE physical {operation} result roles diverge from logical ABI"
            )
        return_value_count = 0
        for result in results:
            if not isinstance(result, DeviceRuntimePhysicalResult):
                raise DeviceRuntimePhysicalABIError(
                    f"DEVICE physical {operation} contains an invalid result"
                )
            _required_text(
                result.type_name,
                label=f"DEVICE physical {operation} result type",
            )
            if not isinstance(result.transport, DeviceRuntimeResultTransport):
                raise DeviceRuntimePhysicalABIError(
                    f"DEVICE physical {operation} result has invalid transport"
                )
            if result.transport is DeviceRuntimeResultTransport.RETURN_VALUE:
                return_value_count += 1
        if return_value_count > 1:
            raise DeviceRuntimePhysicalABIError(
                f"DEVICE physical {operation} cannot have multiple direct return values"
            )

    bound_calls = tuple(
        BoundDeviceRuntimePhysicalCall(
            logical=call,
            physical=operation_map[call.operation],
        )
        for call in logical_calls
    )
    if tuple(call.logical.point_id for call in bound_calls) != logical_plan.point_ids:
        raise DeviceRuntimePhysicalABIError(
            "DEVICE physical ABI binding changed lifecycle point order"
        )

    return BoundDeviceRuntimePhysicalABIPlan(
        abi_name=abi_name,
        abi_version=abi_version,
        backend=backend,
        calling_convention=calling_convention,
        function=logical_plan.function,
        queue=logical_plan.queue,
        calls=bound_calls,
    )
