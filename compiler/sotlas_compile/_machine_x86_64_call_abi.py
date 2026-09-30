"""SysV register/stack transport for Sotlas direct calls."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError


_REGISTER_ARGUMENT_COUNT = len(_core._ARG_REGISTERS)
_STACK_SLOT_BYTES = 8
_CALLER_SAVE_BYTES = 16


def load_incoming_parameter_to_rax(
    lines: list[str], *, type_name: str, index: int
) -> None:
    if index < _REGISTER_ARGUMENT_COUNT:
        _core._normalize_argument_to_rax(lines, type_name, index)
        return
    bits = _core._require_machine_scalar(
        type_name, context=f"parameter {index + 1}"
    )
    offset = 16 + _STACK_SLOT_BYTES * (index - _REGISTER_ARGUMENT_COUNT)
    lines.append(f"    mov rax, QWORD PTR [rbp+{offset}]")
    _core._truncate_rax(lines, bits)


def _move_register_argument(lines: list[str], *, type_name: str, index: int) -> None:
    if index >= _REGISTER_ARGUMENT_COUNT:
        raise MachineBackendError("stack call argument passed to register mover")
    bits = _core._require_machine_scalar(
        type_name, context=f"call argument {index + 1}"
    )
    registers = _core._ARG_REGISTERS[index]
    _core._truncate_rax(lines, bits)
    if bits == 64:
        lines.append(f"    mov {registers[64]}, rax")
    else:
        lines.append(f"    mov {registers[32]}, eax")


def call_stack_layout(argument_count: int) -> tuple[int, int, int]:
    """Return stack-argument count, aligned outgoing bytes and save offset."""
    stack_count = max(0, argument_count - _REGISTER_ARGUMENT_COUNT)
    stack_bytes = stack_count * _STACK_SLOT_BYTES
    total_bytes = _core._align(stack_bytes + _CALLER_SAVE_BYTES, 16)
    return stack_count, total_bytes, total_bytes - _CALLER_SAVE_BYTES


def _rsp_qword(offset: int) -> str:
    return "QWORD PTR [rsp]" if offset == 0 else f"QWORD PTR [rsp+{offset}]"


def emit_direct_call(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    signatures: dict[str, dict[str, Any]],
) -> None:
    caller = function["name"]
    callee = instruction.get("attributes", {}).get("callee")
    signature = signatures[callee]
    operands = tuple(instruction.get("operands", ()))
    _, call_area_bytes, save_offset = call_stack_layout(len(operands))

    lines.extend([
        f"    sub rsp, {call_area_bytes}",
        f"    mov {_rsp_qword(save_offset)}, r10",
        f"    mov {_rsp_qword(save_offset + 8)}, r11",
    ])

    for index in range(_REGISTER_ARGUMENT_COUNT, len(operands)):
        operand = operands[index]
        parameter_type = signature["parameters"][index]
        _core._load_value(lines, operand, "rax", locations)
        bits = _core._require_machine_scalar(
            parameter_type, context=f"call argument {index + 1}"
        )
        _core._truncate_rax(lines, bits)
        offset = _STACK_SLOT_BYTES * (index - _REGISTER_ARGUMENT_COUNT)
        lines.append(f"    mov {_rsp_qword(offset)}, rax")

    for index in range(min(len(operands), _REGISTER_ARGUMENT_COUNT)):
        _core._load_value(lines, operands[index], "rax", locations)
        _move_register_argument(
            lines, type_name=signature["parameters"][index], index=index
        )

    lines.append(f"    call {callee}")
    return_type = signature["return_type"]
    result = instruction.get("result")
    if return_type != "void":
        bits = _core._require_machine_scalar(
            return_type, context=f"function {caller!r} call return"
        )
        _core._truncate_rax(lines, bits)
        lines.append("    mov rdx, rax")

    lines.extend([
        f"    mov r10, {_rsp_qword(save_offset)}",
        f"    mov r11, {_rsp_qword(save_offset + 8)}",
        f"    add rsp, {call_area_bytes}",
    ])
    if return_type != "void":
        _core._store_value(lines, result, "rdx", locations)


__all__ = [
    "call_stack_layout",
    "emit_direct_call",
    "load_incoming_parameter_to_rax",
]
