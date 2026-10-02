"""Function/module assembly emission for the x86-64 SysV call ABI."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_aggregate_allocation import (
    plan_x86_64_sysv_aggregate_allocation,
)
from ._machine_x86_64_aggregate_param_emit import (
    emit_aggregate_incoming_parameters,
    validate_aggregate_entry_emission_scope,
)
from ._machine_x86_64_call_abi import load_incoming_parameter_to_rax
from ._machine_x86_64_call_instruction_emit import emit_instruction
from ._machine_x86_64_call_validation import (
    MachineBackendError,
    function_linkage,
    module_signatures,
    validate_abi_function_shape,
    validate_direct_calls,
)
from ._machine_x86_64_enum_emit import emit_enum_const
from ._machine_x86_64_fixed_array_emit import (
    emit_fixed_array_address,
    emit_fixed_array_dynamic_address,
)
from ._machine_x86_64_struct_field_emit import emit_struct_field_address
from ._machine_x86_64_struct_layout import plan_x86_64_sysv_struct_layouts
from .target_ir_enums import validate_target_ir_enum_representation


def emit_x86_64_sysv_assembly(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> str:
    validate_aggregate_entry_emission_scope(target_ir)
    validate_direct_calls(target_ir)
    validate_target_ir_enum_representation(target_ir)
    for function in target_ir.get("functions", ()):
        validate_abi_function_shape(function)
    plan = plan_x86_64_sysv_aggregate_allocation(
        target_ir,
        register_count=register_count,
    )
    struct_layouts = plan_x86_64_sysv_struct_layouts(target_ir)
    enum_layouts = target_ir.get("enum_layouts", {})
    plan_by_name = {
        function["name"]: function for function in plan.get("functions", ())
    }
    signatures = module_signatures(target_ir)

    lines = [".intel_syntax noprefix", ".text"]
    for function in target_ir.get("functions", ()):
        name = function["name"]
        linkage = function_linkage(function)
        function_plan = plan_by_name.get(name)
        if function_plan is None:
            raise MachineBackendError(f"missing allocation plan for {name!r}")
        locations = _core._location_map(function_plan)
        stack_slots = _core._stack_slot_map(function_plan)
        value_types = _core._type_map(function)
        block_labels = _core._block_label_map(function)
        frame_size = function_plan["frame_size_bytes"]

        lines.append("")
        lines.append(
            f".globl {name}" if linkage == "external" else f".local {name}"
        )
        lines.extend([
            f".type {name}, @function",
            f"{name}:",
            "    push rbp",
            "    mov rbp, rsp",
        ])
        if frame_size:
            lines.append(f"    sub rsp, {frame_size}")

        if "abi_transport" in function_plan:
            emit_aggregate_incoming_parameters(
                lines,
                function=function,
                function_plan=function_plan,
                locations=locations,
            )
        else:
            for index, parameter in enumerate(function.get("parameters", ())):
                load_incoming_parameter_to_rax(
                    lines, type_name=parameter["type"], index=index
                )
                _core._store_value(
                    lines, parameter["name"], "rax", locations
                )

        for block in function.get("blocks", ()):
            lines.append(f"{block_labels[block['label']]}:")
            for instruction in block.get("instructions", ()):
                if instruction.get("op") == "field_address":
                    emit_struct_field_address(
                        lines,
                        function=function,
                        instruction=instruction,
                        locations=locations,
                        value_types=value_types,
                        struct_layouts=struct_layouts,
                    )
                    continue
                if instruction.get("op") == "array_address":
                    emit_fixed_array_address(
                        lines,
                        function=function,
                        instruction=instruction,
                        locations=locations,
                        value_types=value_types,
                    )
                    continue
                if instruction.get("op") == "array_address_dynamic":
                    emit_fixed_array_dynamic_address(
                        lines,
                        function=function,
                        instruction=instruction,
                        locations=locations,
                        value_types=value_types,
                    )
                    continue
                if instruction.get("op") == "enum_const":
                    emit_enum_const(
                        lines,
                        function=function,
                        instruction=instruction,
                        locations=locations,
                        enum_layouts=enum_layouts,
                    )
                    continue
                emit_instruction(
                    lines,
                    function=function,
                    instruction=instruction,
                    locations=locations,
                    stack_slots=stack_slots,
                    value_types=value_types,
                    block_labels=block_labels,
                    frame_size=frame_size,
                    signatures=signatures,
                )
        lines.append(f".size {name}, .-{name}")

    lines.extend(["", '.section .note.GNU-stack,"",@progbits', ""])
    return "\n".join(lines)


__all__ = ["emit_x86_64_sysv_assembly"]
