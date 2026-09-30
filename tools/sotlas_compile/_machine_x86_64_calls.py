"""M16.3a direct-call SysV ABI layer for the Sotlas-owned x86-64 backend.

The machine core owns scalar instruction selection, CFG validation and physical
allocation.  This layer adds only the first interprocedural contract:

- module-local direct calls only;
- up to six bool/unsigned scalar arguments in SysV integer registers;
- scalar return values in RAX;
- 16-byte aligned call sites;
- explicit preservation of the backend's caller-saved r10/r11 value registers;
- recursive call cycles remain fail-closed until their language/runtime contract
  is selected explicitly.

Stack-passed arguments, indirect calls, aggregate ABI classification, variadics,
foreign/system calls and general linkage remain later milestones.
"""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core


MachineBackendError = _core.MachineBackendError


def _module_signatures(target_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    signatures: dict[str, dict[str, Any]] = {}
    for function in target_ir.get("functions", ()):
        name = function.get("name")
        if not isinstance(name, str) or _core._SYMBOL_RE.fullmatch(name) is None:
            raise MachineBackendError(f"invalid x86-64 symbol name {name!r}")
        if name in signatures:
            raise MachineBackendError(f"duplicate machine function symbol {name!r}")
        signatures[name] = {
            "parameters": tuple(
                parameter.get("type") for parameter in function.get("parameters", ())
            ),
            "return_type": function.get("return_type"),
        }
    return signatures


def _validate_direct_calls(target_ir: dict[str, Any]) -> None:
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")

    signatures = _module_signatures(target_ir)
    call_graph: dict[str, set[str]] = {name: set() for name in signatures}

    for function in target_ir.get("functions", ()):
        caller = function["name"]
        value_types = _core._type_map(function)
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "call":
                    continue
                if instruction.get("semantic_only"):
                    raise MachineBackendError(
                        f"function {caller!r}: semantic call cannot reach machine ABI lowering"
                    )
                attributes = instruction.get("attributes", {})
                callee = attributes.get("callee")
                if not isinstance(callee, str) or _core._SYMBOL_RE.fullmatch(callee) is None:
                    raise MachineBackendError(
                        f"function {caller!r}: direct call has an invalid callee symbol"
                    )
                if attributes.get("system"):
                    raise MachineBackendError(
                        f"function {caller!r}: system/foreign call {callee!r} is outside M16.3a"
                    )
                signature = signatures.get(callee)
                if signature is None:
                    raise MachineBackendError(
                        f"function {caller!r}: direct call target {callee!r} is not a module function"
                    )
                call_graph[caller].add(callee)

                operands = tuple(instruction.get("operands", ()))
                parameters = signature["parameters"]
                if len(operands) != len(parameters):
                    raise MachineBackendError(
                        f"function {caller!r}: call to {callee!r} has the wrong argument count"
                    )
                if len(operands) > len(_core._ARG_REGISTERS):
                    raise MachineBackendError(
                        f"function {caller!r}: stack-passed call arguments are outside M16.3a"
                    )
                for index, (operand, parameter_type) in enumerate(
                    zip(operands, parameters, strict=True)
                ):
                    operand_type = value_types.get(operand)
                    if operand_type != parameter_type:
                        raise MachineBackendError(
                            f"function {caller!r}: call argument {index + 1} to {callee!r} "
                            f"has type {operand_type!r}, expected {parameter_type!r}"
                        )
                    _core._require_machine_scalar(
                        parameter_type,
                        context=f"function {caller!r} call argument {index + 1}",
                    )

                result = instruction.get("result")
                result_type = instruction.get("type")
                return_type = signature["return_type"]
                if return_type == "void":
                    if result is not None or result_type not in (None, "void"):
                        raise MachineBackendError(
                            f"function {caller!r}: void call to {callee!r} cannot produce a value"
                        )
                else:
                    _core._require_machine_scalar(
                        return_type,
                        context=f"function {caller!r} call return from {callee!r}",
                    )
                    if not isinstance(result, str) or not result:
                        raise MachineBackendError(
                            f"function {caller!r}: non-void call to {callee!r} requires a result"
                        )
                    if result_type != return_type or value_types.get(result) != return_type:
                        raise MachineBackendError(
                            f"function {caller!r}: call result type for {callee!r} must be {return_type!r}"
                        )

    # M16.3a defines recursion conservatively: it is rejected, not silently
    # accepted with an unbounded native stack contract.
    state = {name: 0 for name in call_graph}

    def visit(name: str) -> None:
        if state[name] == 1:
            raise MachineBackendError(
                "recursive direct calls remain outside the M16.3a machine contract"
            )
        if state[name] == 2:
            return
        state[name] = 1
        for callee in sorted(call_graph[name]):
            visit(callee)
        state[name] = 2

    for name in sorted(call_graph):
        if state[name] == 0:
            visit(name)


def plan_x86_64_sysv_allocation(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> dict[str, Any]:
    _validate_direct_calls(target_ir)
    return _core.plan_x86_64_sysv_allocation(
        target_ir, register_count=register_count
    )


def _move_call_argument_from_rax(
    lines: list[str], *, type_name: str, index: int
) -> None:
    bits = _core._require_machine_scalar(
        type_name, context=f"call argument {index + 1}"
    )
    registers = _core._ARG_REGISTERS[index]
    _core._truncate_rax(lines, bits)
    if bits == 64:
        lines.append(f"    mov {registers[64]}, rax")
    else:
        # Zero-extend all sub-64-bit scalar arguments in the 32-bit ABI register.
        # The callee still consumes only its declared low-width value.
        lines.append(f"    mov {registers[32]}, eax")


def _emit_direct_call(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
    signatures: dict[str, dict[str, Any]],
) -> None:
    caller = function["name"]
    callee = instruction.get("attributes", {}).get("callee")
    signature = signatures[callee]
    operands = tuple(instruction.get("operands", ()))

    # r10/r11 are the machine backend's physical value registers and both are
    # caller-saved under SysV. Reserve a full 16-byte area so RSP remains
    # 16-byte aligned immediately before CALL while preserving both values.
    lines.extend(
        [
            "    sub rsp, 16",
            "    mov QWORD PTR [rsp], r10",
            "    mov QWORD PTR [rsp+8], r11",
        ]
    )

    for index, (operand, parameter_type) in enumerate(
        zip(operands, signature["parameters"], strict=True)
    ):
        _core._load_value(lines, operand, "rax", locations)
        _move_call_argument_from_rax(
            lines, type_name=parameter_type, index=index
        )

    lines.append(f"    call {callee}")

    return_type = signature["return_type"]
    result = instruction.get("result")
    if return_type != "void":
        bits = _core._require_machine_scalar(
            return_type, context=f"function {caller!r} call return"
        )
        _core._truncate_rax(lines, bits)
        # Keep the return value outside r10/r11 while their pre-call contents
        # are restored. RDX is caller-saved and dead after the call setup.
        lines.append("    mov rdx, rax")

    lines.extend(
        [
            "    mov r10, QWORD PTR [rsp]",
            "    mov r11, QWORD PTR [rsp+8]",
            "    add rsp, 16",
        ]
    )
    if return_type != "void":
        _core._store_value(lines, result, "rdx", locations)


def emit_x86_64_sysv_assembly(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> str:
    """Emit the scalar machine subset plus M16.3a module-local direct calls."""
    _validate_direct_calls(target_ir)
    for function in target_ir.get("functions", ()):
        _core._validate_function_shape(function)

    plan = _core.plan_x86_64_sysv_allocation(
        target_ir, register_count=register_count
    )
    plan_by_name = {
        function["name"]: function for function in plan.get("functions", ())
    }
    signatures = _module_signatures(target_ir)

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
            _core._normalize_argument_to_rax(lines, parameter["type"], index)
            _core._store_value(lines, parameter_name, "rax", locations)

        for block in function.get("blocks", ()):
            lines.append(f"{block_labels[block['label']]}:")
            for instruction in block.get("instructions", ()):
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
                    _core._load_value(lines, source, "rax", locations)
                    _core._truncate_rax(
                        lines,
                        _core._require_machine_scalar(
                            type_name, context=f"function {name!r} store"
                        ),
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
                    _core._truncate_rax(
                        lines,
                        _core._require_machine_scalar(
                            type_name, context=f"function {name!r} load"
                        ),
                    )
                    _core._store_value(lines, result, "rax", locations)
                    continue

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
                    continue

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
                    continue

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
                    bits = _core._require_unsigned(
                        left_type, context=f"function {name!r} compare"
                    )
                    predicate = instruction.get("attributes", {}).get("predicate")
                    condition = _core._COMPARE_CONDITIONS.get(predicate)
                    if condition is None:
                        raise MachineBackendError(
                            f"function {name!r}: unsupported compare predicate {predicate!r}"
                        )
                    _core._load_value(lines, left, "rax", locations)
                    _core._load_value(lines, right, "rcx", locations)
                    lines.append("    cmp rax, rcx" if bits == 64 else "    cmp eax, ecx")
                    lines.append(f"    set{condition} al")
                    lines.append("    movzx eax, al")
                    _core._store_value(lines, result, "rax", locations)
                    continue

                if op == "call":
                    _emit_direct_call(
                        lines,
                        function=function,
                        instruction=instruction,
                        locations=locations,
                        value_types=value_types,
                        signatures=signatures,
                    )
                    continue

                if op == "branch":
                    target = instruction.get("targets", ())[0]
                    lines.append(f"    jmp {block_labels[target]}")
                    continue

                if op == "cond_branch":
                    condition_value = instruction.get("operands", ())[0]
                    true_target, false_target = instruction.get("targets", ())
                    _core._load_value(lines, condition_value, "rax", locations)
                    _core._truncate_rax(lines, 1)
                    lines.append("    test al, al")
                    lines.append(f"    jne {block_labels[true_target]}")
                    lines.append(f"    jmp {block_labels[false_target]}")
                    continue

                if op == "return":
                    _core._emit_return(
                        lines,
                        function=function,
                        instruction=instruction,
                        locations=locations,
                        value_types=value_types,
                        frame_size=frame_size,
                    )
                    continue

                if op == "phi":
                    raise MachineBackendError(
                        f"function {name!r}: phi lowering waits for the edge-copy milestone"
                    )

                raise MachineBackendError(
                    f"function {name!r}: x86-64 machine backend does not lower operation {op!r}"
                )

        lines.append(f".size {name}, .-{name}")

    lines.extend(["", '.section .note.GNU-stack,"",@progbits', ""])
    return "\n".join(lines)


__all__ = [
    "MachineBackendError",
    "plan_x86_64_sysv_allocation",
    "emit_x86_64_sysv_assembly",
]
