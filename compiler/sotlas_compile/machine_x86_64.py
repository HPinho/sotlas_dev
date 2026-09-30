"""First executable Sotlas-owned x86-64 SysV machine backend slice.

This backend consumes canonical Target IR and the existing CFG liveness/register
allocation analysis. Unlike the inspection reports, the resulting physical
allocation is consumed by instruction selection and assembly emission.

The initial contract is deliberately narrow and fail-closed:
- x86-64 System V ABI;
- one linear basic block per function;
- up to six unsigned integer parameters;
- u8/u16/u32/u64/usize values;
- canonical alloc_stack/store/load local memory;
- integer constants and add/sub/mul;
- direct return (or void return);
- two caller-saved value registers (r10/r11) plus real stack spills.

Signed arithmetic remains rejected until Sotlas' checked/wrapping/saturating/
unchecked overflow semantics are selected explicitly at the language level.
"""
from __future__ import annotations

import re
from typing import Any

from .target_ir import (
    TargetIRLoweringError,
    allocate_target_ir_registers,
    lower_sir_to_target_ir,
)


class MachineBackendError(ValueError):
    """Raised when Target IR is outside the executable x86-64 backend slice."""


_VALUE_REGISTERS = ("r10", "r11")
_UNSIGNED_TYPES = {"u8": 8, "u16": 16, "u32": 32, "u64": 64, "usize": 64}
_ARG_REGISTERS = (
    {64: "rdi", 32: "edi", 16: "di", 8: "dil"},
    {64: "rsi", 32: "esi", 16: "si", 8: "sil"},
    {64: "rdx", 32: "edx", 16: "dx", 8: "dl"},
    {64: "rcx", 32: "ecx", 16: "cx", 8: "cl"},
    {64: "r8", 32: "r8d", 16: "r8w", 8: "r8b"},
    {64: "r9", 32: "r9d", 16: "r9w", 8: "r9b"},
)
_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def _require_unsigned(type_name: Any, *, context: str) -> int:
    if type_name in _UNSIGNED_TYPES:
        return _UNSIGNED_TYPES[type_name]
    if type_name in {"i8", "i16", "i32", "i64", "isize"}:
        raise MachineBackendError(
            f"{context}: signed integer lowering waits for Sotlas overflow-mode semantics"
        )
    raise MachineBackendError(
        f"{context}: x86-64 machine backend does not lower type {type_name!r}"
    )


def plan_x86_64_sysv_allocation(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> dict[str, Any]:
    """Map canonical virtual allocation and local memory onto x86-64 locations."""

    if (
        not isinstance(register_count, int)
        or isinstance(register_count, bool)
        or register_count < 1
        or register_count > len(_VALUE_REGISTERS)
    ):
        raise MachineBackendError(
            "x86-64 SysV machine backend supports one or two value registers"
        )
    try:
        allocation = allocate_target_ir_registers(
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
                    "name": _VALUE_REGISTERS[index],
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
            physical_values.append(
                {
                    "value": value.get("value"),
                    "type": value.get("type"),
                    "location": location,
                    "interferes_with": list(value.get("interferes_with", ())),
                }
            )

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
                _require_unsigned(
                    type_name,
                    context=f"function {function_name!r} local {value_name!r}",
                )
                seen_local_values.add(value_name)
                local_index = len(local_slots)
                local_slots.append(
                    {
                        "value": value_name,
                        "type": type_name,
                        "source_name": instruction.get("attributes", {}).get("source_name"),
                        "slot": local_index,
                        "offset_bytes": -8 * (spill_slots + local_index + 1),
                    }
                )

        total_stack_slots = spill_slots + len(local_slots)
        functions.append(
            {
                "name": function_name,
                "values": physical_values,
                "spill_slots": spill_slots,
                "local_stack_slots": len(local_slots),
                "stack_slots": local_slots,
                "frame_size_bytes": _align(total_stack_slots * 8, 16),
            }
        )

    return {
        "schema": "sotlas.machine-allocation.x86_64-sysv.v1",
        "target": "x86_64-unknown-linux-gnu",
        "abi": "sysv",
        "value_registers": list(_VALUE_REGISTERS[:register_count]),
        "functions": functions,
    }


def _location_map(function_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    locations = {}
    for value in function_plan.get("values", ()):
        name = value.get("value")
        if not isinstance(name, str) or not name or name in locations:
            raise MachineBackendError("machine allocation contains invalid value names")
        locations[name] = value
    return locations


def _stack_slot_map(function_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    slots = {}
    for slot in function_plan.get("stack_slots", ()):
        name = slot.get("value")
        if not isinstance(name, str) or not name or name in slots:
            raise MachineBackendError("machine allocation contains invalid local stack slots")
        slots[name] = slot
    return slots


def _type_map(function: dict[str, Any]) -> dict[str, str]:
    types: dict[str, str] = {}
    for parameter in function.get("parameters", ()):
        name = parameter.get("name")
        type_name = parameter.get("type")
        if isinstance(name, str) and isinstance(type_name, str):
            types[name] = type_name
    for block in function.get("blocks", ()):
        for instruction in block.get("instructions", ()):
            result = instruction.get("result")
            type_name = instruction.get("type")
            if isinstance(result, str) and isinstance(type_name, str):
                types[result] = type_name
    return types


def _load_value(
    lines: list[str],
    value: str,
    destination: str,
    locations: dict[str, dict[str, Any]],
) -> None:
    entry = locations.get(value)
    if entry is None:
        raise MachineBackendError(f"machine backend has no allocation for {value!r}")
    location = entry["location"]
    if location["kind"] == "register":
        lines.append(f"    mov {destination}, {location['name']}")
        return
    offset = -int(location["offset_bytes"])
    lines.append(f"    mov {destination}, QWORD PTR [rbp-{offset}]")


def _store_value(
    lines: list[str],
    value: str,
    source: str,
    locations: dict[str, dict[str, Any]],
) -> None:
    entry = locations.get(value)
    if entry is None:
        raise MachineBackendError(f"machine backend has no allocation for {value!r}")
    location = entry["location"]
    if location["kind"] == "register":
        lines.append(f"    mov {location['name']}, {source}")
        return
    offset = -int(location["offset_bytes"])
    lines.append(f"    mov QWORD PTR [rbp-{offset}], {source}")


def _normalize_argument_to_rax(lines: list[str], type_name: str, index: int) -> None:
    bits = _require_unsigned(type_name, context=f"parameter {index + 1}")
    registers = _ARG_REGISTERS[index]
    if bits == 64:
        lines.append(f"    mov rax, {registers[64]}")
    elif bits == 32:
        lines.append(f"    mov eax, {registers[32]}")
    elif bits == 16:
        lines.append(f"    movzx eax, {registers[16]}")
    else:
        lines.append(f"    movzx eax, {registers[8]}")


def _truncate_rax(lines: list[str], bits: int) -> None:
    if bits == 8:
        lines.append("    and eax, 255")
    elif bits == 16:
        lines.append("    and eax, 65535")


def _validate_function_shape(function: dict[str, Any]) -> None:
    name = function.get("name")
    if not isinstance(name, str) or _SYMBOL_RE.fullmatch(name) is None:
        raise MachineBackendError(f"invalid x86-64 symbol name {name!r}")
    parameters = function.get("parameters", ())
    if len(parameters) > len(_ARG_REGISTERS):
        raise MachineBackendError(
            f"function {name!r} has more than six integer parameters"
        )
    blocks = function.get("blocks", ())
    if len(blocks) != 1:
        raise MachineBackendError(
            f"function {name!r}: x86-64 machine backend currently requires one linear block"
        )
    for parameter in parameters:
        _require_unsigned(
            parameter.get("type"),
            context=f"function {name!r} parameter {parameter.get('name')!r}",
        )
    return_type = function.get("return_type")
    if return_type != "void":
        _require_unsigned(return_type, context=f"function {name!r} return")


def emit_x86_64_sysv_assembly(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> str:
    """Select real x86-64 instructions from canonical Target IR."""

    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")
    plan = plan_x86_64_sysv_allocation(
        target_ir, register_count=register_count
    )
    plan_by_name = {
        function["name"]: function for function in plan.get("functions", ())
    }

    lines = [".intel_syntax noprefix", ".text"]
    for function in target_ir.get("functions", ()):
        _validate_function_shape(function)
        name = function["name"]
        function_plan = plan_by_name.get(name)
        if function_plan is None:
            raise MachineBackendError(f"missing allocation plan for {name!r}")
        locations = _location_map(function_plan)
        stack_slots = _stack_slot_map(function_plan)
        value_types = _type_map(function)
        frame_size = function_plan["frame_size_bytes"]

        lines.extend(
            [
                "",
                f".globl {name}",
                f".type {name}, @function",
                f"{name}:",
                "    push rbp",
                "    mov rbp, rsp",
            ]
        )
        if frame_size:
            lines.append(f"    sub rsp, {frame_size}")

        for index, parameter in enumerate(function.get("parameters", ())):
            parameter_name = parameter["name"]
            _normalize_argument_to_rax(lines, parameter["type"], index)
            _store_value(lines, parameter_name, "rax", locations)

        instructions = function["blocks"][0].get("instructions", ())
        for instruction in instructions:
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
                continue

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
                _load_value(lines, source, "rax", locations)
                _truncate_rax(
                    lines,
                    _require_unsigned(type_name, context=f"function {name!r} store"),
                )
                offset = -int(slot["offset_bytes"])
                lines.append(f"    mov QWORD PTR [rbp-{offset}], rax")
                continue

            if op == "load":
                result = instruction.get("result")
                operands = instruction.get("operands", ())
                if len(operands) != 1:
                    raise MachineBackendError(
                        f"function {name!r}: load requires one local stack slot"
                    )
                source = operands[0]
                slot = stack_slots.get(source)
                if slot is None:
                    raise MachineBackendError(
                        f"function {name!r}: load source is not a local stack slot"
                    )
                type_name = instruction.get("type")
                if slot.get("type") != type_name:
                    raise MachineBackendError(
                        f"function {name!r}: load type does not match local stack slot"
                    )
                offset = -int(slot["offset_bytes"])
                lines.append(f"    mov rax, QWORD PTR [rbp-{offset}]")
                _truncate_rax(
                    lines,
                    _require_unsigned(type_name, context=f"function {name!r} load"),
                )
                _store_value(lines, result, "rax", locations)
                continue

            if op == "const_int":
                result = instruction.get("result")
                type_name = instruction.get("type")
                bits = _require_unsigned(
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
                _truncate_rax(lines, bits)
                _store_value(lines, result, "rax", locations)
                continue

            if op in {"add", "sub", "mul"}:
                result = instruction.get("result")
                operands = instruction.get("operands", ())
                if len(operands) != 2:
                    raise MachineBackendError(
                        f"function {name!r}: {op} requires two operands"
                    )
                type_name = instruction.get("type")
                bits = _require_unsigned(
                    type_name, context=f"function {name!r} {op}"
                )
                left, right = operands
                if (
                    value_types.get(left) != type_name
                    or value_types.get(right) != type_name
                ):
                    raise MachineBackendError(
                        f"function {name!r}: {op} operand types do not match {type_name!r}"
                    )
                _load_value(lines, left, "rax", locations)
                _load_value(lines, right, "rcx", locations)
                mnemonic = {"add": "add", "sub": "sub", "mul": "imul"}[op]
                if bits == 64:
                    lines.append(f"    {mnemonic} rax, rcx")
                else:
                    lines.append(f"    {mnemonic} eax, ecx")
                    _truncate_rax(lines, bits)
                _store_value(lines, result, "rax", locations)
                continue

            if op == "return":
                operands = instruction.get("operands", ())
                return_type = function.get("return_type")
                if return_type == "void":
                    if operands:
                        raise MachineBackendError(
                            f"function {name!r}: void return carries a value"
                        )
                else:
                    if len(operands) != 1:
                        raise MachineBackendError(
                            f"function {name!r}: non-void return requires one value"
                        )
                    value = operands[0]
                    if value_types.get(value) != return_type:
                        raise MachineBackendError(
                            f"function {name!r}: return value type does not match {return_type!r}"
                        )
                    _load_value(lines, value, "rax", locations)
                    _truncate_rax(
                        lines,
                        _require_unsigned(
                            return_type, context=f"function {name!r} return"
                        ),
                    )
                if frame_size:
                    lines.append(f"    add rsp, {frame_size}")
                lines.extend(["    pop rbp", "    ret"])
                continue

            raise MachineBackendError(
                f"function {name!r}: x86-64 machine backend does not lower operation {op!r}"
            )

        if not instructions or instructions[-1].get("op") != "return":
            raise MachineBackendError(
                f"function {name!r}: linear machine block must end in return"
            )
        lines.append(f".size {name}, .-{name}")

    lines.extend(["", '.section .note.GNU-stack,"",@progbits', ""])
    return "\n".join(lines)


def compile_source_to_x86_64_sysv_assembly(
    source: str,
    filename: str = "<stdin>",
    *,
    register_count: int = 2,
) -> str:
    """Run the canonical checked pipeline and emit Sotlas-owned x86-64 assembly."""

    from .canonical_sir import build_canonical_checked_ownership_sir
    from .phase1_pipeline import analyze_source_phase1

    checked = analyze_source_phase1(source, filename=filename)
    checked_sir, _ = build_canonical_checked_ownership_sir(checked)
    module = checked_sir.module
    unlowered = tuple(getattr(module, "unlowered_functions", ()) or ())
    if unlowered:
        raise MachineBackendError(
            "x86-64 machine backend cannot lower source bodies for: "
            + ", ".join(sorted(unlowered))
        )
    target_ir = lower_sir_to_target_ir(module)
    return emit_x86_64_sysv_assembly(
        target_ir, register_count=register_count
    )


__all__ = [
    "MachineBackendError",
    "plan_x86_64_sysv_allocation",
    "emit_x86_64_sysv_assembly",
    "compile_source_to_x86_64_sysv_assembly",
]
