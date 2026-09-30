"""Function/module assembly emission for the x86-64 SysV call ABI."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_abi import load_incoming_parameter_to_rax
from ._machine_x86_64_call_instruction_emit import emit_instruction
from ._machine_x86_64_call_plan import plan_x86_64_sysv_allocation
from ._machine_x86_64_call_validation import (
    MachineBackendError,
    module_signatures,
    validate_abi_function_shape,
    validate_direct_calls,
)


def emit_x86_64_sysv_assembly(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> str:
    validate_direct_calls(target_ir)
    for function in target_ir.get("functions", ()):
        validate_abi_function_shape(function)
    plan = plan_x86_64_sysv_allocation(target_ir, register_count=register_count)
    plan_by_name = {
        function["name"]: function for function in plan.get("functions", ())
    }
    signatures = module_signatures(target_ir)

    lines = [".intel_syntax noprefix", ".text"]
    for function in target_ir.get("functions", ()):
        name = function["name"]
        function_plan = plan_by_name.get(name)
        if function_plan is None:
            raise MachineBackendError(f"missing allocation plan for {name!r}")
        locations = _core._location_map(function_plan)
        stack_slots = _core._stack_slot_map(function_plan)
        value_types = _core._type_map(function)
        block_labels = _core._block_label_map(function)
        frame_size = function_plan["frame_size_bytes"]

        lines.extend([
            "",
            f".globl {name}",
            f".type {name}, @function",
            f"{name}:",
            "    push rbp",
            "    mov rbp, rsp",
        ])
        if frame_size:
            lines.append(f"    sub rsp, {frame_size}")

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
