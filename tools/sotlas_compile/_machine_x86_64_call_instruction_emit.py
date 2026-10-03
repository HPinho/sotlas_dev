"""Instruction emission shared by the x86-64 SysV direct-call backend."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_abi import emit_direct_call
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import (
    pointer_pointee,
    require_abi_scalar,
    require_pointer_to,
)


def _emit_indirect_scalar_load(
    lines: list[str], *, bits: int, address_register: str = "rcx"
) -> None:
    if bits == 1 or bits == 8:
        lines.append(f"    movzx eax, BYTE PTR [{address_register}]")
        if bits == 1:
            lines.append("    and eax, 1")
    elif bits == 16:
        lines.append(f"    movzx eax, WORD PTR [{address_register}]")
    elif bits == 32:
        lines.append(f"    mov eax, DWORD PTR [{address_register}]")
    elif bits == 64:
        lines.append(f"    mov rax, QWORD PTR [{address_register}]")
    else:
        raise MachineBackendError(f"unsupported indirect scalar width {bits}")


def emit_instruction(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    stack_slots: dict[str, dict[str, Any]],
    value_types: dict[str, str],
    block_labels: dict[str, str],
    frame_size: int,
    signatures: dict[str, dict[str, Any]],
) -> None:
    name = function["name"]
    if instruction.get("semantic_only"):
        raise MachineBackendError(
            f"function {name!r}: semantic operation {instruction.get('op')!r} "
            "has no machine lowering yet"
        )
    op = instruction.get("op")

    if op == "alloc_stack":
        result = instruction.get("result")
        slot = stack_slots.get(result)
        if slot is None or slot.get("type") != instruction.get("type"):
            raise MachineBackendError(
                f"function {name!r}: alloc_stack has no matching local stack slot"
            )
        return

    if op == "address_of":
        result = instruction.get("result")
        operands = instruction.get("operands", ())
        if len(operands) != 1:
            raise MachineBackendError(
                f"function {name!r}: address_of requires one local stack slot"
            )
        source = operands[0]
        slot = stack_slots.get(source)
        if slot is None:
            raise MachineBackendError(
                f"function {name!r}: address_of source is not a local stack slot"
            )
        pointer_type = instruction.get("type")
        pointee = pointer_pointee(pointer_type)
        if pointee is None or pointee != slot.get("type"):
            raise MachineBackendError(
                f"function {name!r}: address_of result type does not match local stack slot"
            )
        offset = -int(slot["offset_bytes"])
        lines.append(f"    lea rax, [rbp-{offset}]")
        _core._store_value(lines, result, "rax", locations)
        return

    if op == "store":
        operands = instruction.get("operands", ())
        if len(operands) != 2:
            raise MachineBackendError(
                f"function {name!r}: store requires source and destination"
            )
        source, destination = operands
        slot = stack_slots.get(destination)
        if slot is None:
            raise MachineBackendError(
                f"function {name!r}: store destination is not a local stack slot"
            )
        type_name = slot["type"]
        if value_types.get(source) != type_name:
            raise MachineBackendError(
                f"function {name!r}: store source type does not match {type_name!r}"
            )
        _core._load_value(lines, source, "rax", locations)
        _core._truncate_rax(
            lines,
            require_abi_scalar(
                type_name, context=f"function {name!r} store"
            ),
        )
        offset = -int(slot["offset_bytes"])
        lines.append(f"    mov QWORD PTR [rbp-{offset}], rax")
        return

    if op == "load":
        result = instruction.get("result")
        operands = instruction.get("operands", ())
        if len(operands) != 1:
            raise MachineBackendError(
                f"function {name!r}: load requires one local stack slot"
            )
        source = operands[0]
        type_name = instruction.get("type")
        slot = stack_slots.get(source)
        if slot is not None:
            if slot.get("type") != type_name:
                raise MachineBackendError(
                    f"function {name!r}: load type does not match local stack slot"
                )
            offset = -int(slot["offset_bytes"])
            lines.append(f"    mov rax, QWORD PTR [rbp-{offset}]")
            _core._truncate_rax(
                lines,
                require_abi_scalar(
                    type_name, context=f"function {name!r} load"
                ),
            )
            _core._store_value(lines, result, "rax", locations)
            return

        source_type = value_types.get(source)
        bits = require_pointer_to(
            source_type,
            type_name,
            context=f"function {name!r} load",
        )
        _core._load_value(lines, source, "rcx", locations)
        _emit_indirect_scalar_load(lines, bits=bits)
        _core._store_value(lines, result, "rax", locations)
        return

    if op == "const_int":
        result = instruction.get("result")
        type_name = instruction.get("type")
        bits = _core._require_unsigned(
            type_name, context=f"function {name!r} constant"
        )
        value = instruction.get("attributes", {}).get("value")
        if not isinstance(value, int) or isinstance(value, bool):
            raise MachineBackendError(
                f"function {name!r}: integer constant is malformed"
            )
        if value < 0 or value >= (1 << bits):
            raise MachineBackendError(
                f"function {name!r}: constant {value} is out of range for {type_name}"
            )
        lines.append(f"    mov rax, {value}")
        _core._truncate_rax(lines, bits)
        _core._store_value(lines, result, "rax", locations)
        return

    if op in {"add", "sub", "mul"}:
        result = instruction.get("result")
        operands = instruction.get("operands", ())
        if len(operands) != 2:
            raise MachineBackendError(
                f"function {name!r}: {op} requires two operands"
            )
        type_name = instruction.get("type")
        bits = _core._require_unsigned(
            type_name, context=f"function {name!r} {op}"
        )
        left, right = operands
        if value_types.get(left) != type_name or value_types.get(right) != type_name:
            raise MachineBackendError(
                f"function {name!r}: {op} operand types do not match {type_name!r}"
            )
        _core._load_value(lines, left, "rax", locations)
        _core._load_value(lines, right, "rcx", locations)
        mnemonic = {"add": "add", "sub": "sub", "mul": "imul"}[op]
        if bits == 64:
            lines.append(f"    {mnemonic} rax, rcx")
        else:
            lines.append(f"    {mnemonic} eax, ecx")
            _core._truncate_rax(lines, bits)
        _core._store_value(lines, result, "rax", locations)
        return

    if op == "compare":
        result = instruction.get("result")
        operands = instruction.get("operands", ())
        if len(operands) != 2:
            raise MachineBackendError(
                f"function {name!r}: compare requires two operands"
            )
        if instruction.get("type") != "bool":
            raise MachineBackendError(
                f"function {name!r}: compare result must have type 'bool'"
            )
        left, right = operands
        left_type = value_types.get(left)
        right_type = value_types.get(right)
        if left_type != right_type:
            raise MachineBackendError(
                f"function {name!r}: compare operand types must match"
            )
        predicate = instruction.get("attributes", {}).get("predicate")
        bits, condition = _core._comparison_info(
            left_type, predicate, context=f"function {name!r} compare"
        )
        _core._load_value(lines, left, "rax", locations)
        _core._load_value(lines, right, "rcx", locations)
        if left_type in _core._SIGNED_TYPES:
            signed_registers = {
                8: ("al", "cl"),
                16: ("ax", "cx"),
                32: ("eax", "ecx"),
                64: ("rax", "rcx"),
            }
            left_register, right_register = signed_registers[bits]
            lines.append(f"    cmp {left_register}, {right_register}")
        else:
            lines.append("    cmp rax, rcx" if bits == 64 else "    cmp eax, ecx")
        lines.append(f"    set{condition} al")
        lines.append("    movzx eax, al")
        _core._store_value(lines, result, "rax", locations)
        return

    if op == "call":
        emit_direct_call(
            lines,
            function=function,
            instruction=instruction,
            locations=locations,
            signatures=signatures,
        )
        return

    if op == "system_op":
        attributes = instruction.get("attributes", {})
        symbol = attributes.get("symbol")
        intrinsic = {"__cli": "cli", "__sti": "sti"}.get(symbol)
        if intrinsic is not None:
            lines.append(f"    {intrinsic}")
            return
        operands = tuple(instruction.get("operands", ()))
        if symbol == "__outb" and len(operands) == 2:
            port, value = operands
            _core._load_value(lines, port, "rcx", locations)
            lines.append("    mov dx, cx")
            _core._load_value(lines, value, "rax", locations)
            _core._truncate_rax(lines, 8)
            lines.append("    out dx, al")
            return
        if symbol == "__inb" and len(operands) == 1:
            (port,) = operands
            _core._load_value(lines, port, "rcx", locations)
            lines.append("    mov dx, cx")
            lines.append("    in al, dx")
            lines.append("    movzx eax, al")
            _core._store_value(lines, instruction.get("result"), "rax", locations)
            return
        else:
            raise MachineBackendError(
                f"function {name!r}: x86-64 machine backend does not lower intrinsic {symbol!r}"
            )

    if op == "branch":
        target = instruction.get("targets", ())[0]
        lines.append(f"    jmp {block_labels[target]}")
        return

    if op == "cond_branch":
        condition_value = instruction.get("operands", ())[0]
        true_target, false_target = instruction.get("targets", ())
        _core._load_value(lines, condition_value, "rax", locations)
        _core._truncate_rax(lines, 1)
        lines.append("    test al, al")
        lines.append(f"    jne {block_labels[true_target]}")
        lines.append(f"    jmp {block_labels[false_target]}")
        return

    if op == "return":
        _core._emit_return(
            lines,
            function=function,
            instruction=instruction,
            locations=locations,
            value_types=value_types,
            frame_size=frame_size,
        )
        return

    if op == "phi":
        raise MachineBackendError(
            f"function {name!r}: phi lowering waits for the edge-copy milestone"
        )
    raise MachineBackendError(
        f"function {name!r}: x86-64 machine backend does not lower operation {op!r}"
    )


__all__ = ["emit_instruction"]
