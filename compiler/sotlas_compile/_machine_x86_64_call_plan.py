"""Physical allocation bridge for the x86-64 SysV call ABI."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import (
    MachineBackendError,
    validate_abi_function_shape,
    validate_direct_calls,
)
from ._machine_x86_64_register_view import allocate_x86_64_register_view
from ._machine_x86_64_struct_layout import plan_x86_64_sysv_struct_layouts
from ._machine_x86_64_types import require_abi_scalar
from .target_ir import TargetIRLoweringError
from .target_ir_addressing import (
    TargetIRAddressingError,
    validate_target_ir_addressing,
)


_REGISTER_ARGUMENT_COUNT = len(_core._ARG_REGISTERS)


def plan_x86_64_sysv_allocation(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> dict[str, Any]:
    validate_direct_calls(target_ir)
    if (
        not isinstance(register_count, int)
        or isinstance(register_count, bool)
        or register_count < 1
        or register_count > len(_core._VALUE_REGISTERS)
    ):
        raise MachineBackendError(
            "x86-64 SysV machine backend supports one or two value registers"
        )
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")
    try:
        validate_target_ir_addressing(target_ir)
    except TargetIRAddressingError as error:
        raise MachineBackendError(str(error)) from error
    plan_x86_64_sysv_struct_layouts(target_ir)
    for function in target_ir.get("functions", ()):
        validate_abi_function_shape(function)

    try:
        allocation = allocate_x86_64_register_view(
            target_ir, register_count=register_count
        )
    except TargetIRLoweringError as error:
        raise MachineBackendError(str(error)) from error

    source_functions = {
        function.get("name"): function
        for function in target_ir.get("functions", ())
        if isinstance(function, dict)
    }
    functions = []
    for function in allocation.get("functions", ()):
        function_name = function.get("name")
        source_function = source_functions.get(function_name)
        if source_function is None:
            raise MachineBackendError(
                f"missing Target IR function for allocation {function_name!r}"
            )
        physical_values = []
        for value in function.get("values", ()):
            logical = value.get("location", {})
            if logical.get("kind") == "register":
                index = logical.get("index")
                if not isinstance(index, int) or not 0 <= index < register_count:
                    raise MachineBackendError(
                        f"invalid virtual register assignment for {value.get('value')!r}"
                    )
                location = {
                    "kind": "register",
                    "name": _core._VALUE_REGISTERS[index],
                    "index": index,
                }
            elif logical.get("kind") == "spill":
                slot = logical.get("slot")
                if not isinstance(slot, int) or slot < 0:
                    raise MachineBackendError(
                        f"invalid spill assignment for {value.get('value')!r}"
                    )
                location = {
                    "kind": "stack",
                    "slot": slot,
                    "offset_bytes": -8 * (slot + 1),
                }
            else:
                raise MachineBackendError(
                    f"unknown allocation location for {value.get('value')!r}"
                )
            physical_values.append({
                "value": value.get("value"),
                "type": value.get("type"),
                "location": location,
                "interferes_with": list(value.get("interferes_with", ())),
            })

        spill_slots = function.get("spill_slots", 0)
        if not isinstance(spill_slots, int) or spill_slots < 0:
            raise MachineBackendError("invalid spill slot count")
        local_slots = []
        seen_local_values: set[str] = set()
        for block in source_function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "alloc_stack":
                    continue
                value_name = instruction.get("result")
                type_name = instruction.get("type")
                if (
                    not isinstance(value_name, str)
                    or not value_name
                    or value_name in seen_local_values
                ):
                    raise MachineBackendError(
                        f"function {function_name!r}: invalid or duplicate alloc_stack result"
                    )
                require_abi_scalar(
                    type_name,
                    context=f"function {function_name!r} local {value_name!r}",
                )
                seen_local_values.add(value_name)
                local_index = len(local_slots)
                local_slots.append({
                    "value": value_name,
                    "type": type_name,
                    "source_name": instruction.get("attributes", {}).get("source_name"),
                    "slot": local_index,
                    "offset_bytes": -8 * (spill_slots + local_index + 1),
                })

        total_stack_slots = spill_slots + len(local_slots)
        incoming_stack_arguments = max(
            0,
            len(tuple(source_function.get("parameters", ()))) - _REGISTER_ARGUMENT_COUNT,
        )
        functions.append({
            "name": function_name,
            "values": physical_values,
            "spill_slots": spill_slots,
            "local_stack_slots": len(local_slots),
            "stack_slots": local_slots,
            "incoming_stack_arguments": incoming_stack_arguments,
            "frame_size_bytes": _core._align(total_stack_slots * 8, 16),
        })

    return {
        "schema": "sotlas.machine-allocation.x86_64-sysv.v1",
        "target": "x86_64-unknown-linux-gnu",
        "abi": "sysv",
        "value_registers": list(_core._VALUE_REGISTERS[:register_count]),
        "functions": functions,
    }


__all__ = ["plan_x86_64_sysv_allocation"]
