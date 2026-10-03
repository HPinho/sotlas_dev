"""Executable Sotlas-owned x86-64 SysV machine backend slice.

This backend consumes canonical Target IR and the existing CFG liveness/register
allocation analysis. Unlike the inspection reports, the resulting physical
allocation is consumed by instruction selection and assembly emission.

The current deliberately narrow fail-closed contract supports:
- x86-64 System V ABI;
- acyclic multi-block CFG plus explicitly proven bounded-loop backedges;
- up to six bool/unsigned integer parameters;
- bool, signed/unsigned integer parameters and returns;
- canonical alloc_stack/store/load local memory;
- integer constants and unsigned add/sub/mul;
- signed and unsigned EQ/NEQ/LT/LTE/GT/GTE comparisons with canonical bool results;
- unconditional and conditional branches over canonical bool conditions;
- direct return (or void return) from any supported block;
- two caller-saved value registers (r10/r11) plus real stack spills.

Signed arithmetic remains rejected until Sotlas' checked/wrapping/saturating/
unchecked overflow semantics are selected explicitly at the language level.
Signed comparisons use the signed x86 condition codes and do not depend on
arithmetic overflow semantics. Phi destruction is performed by the public
orchestration layer; this core independently proves the narrow bounded-loop
shape before any cyclic CFG reaches allocation or instruction selection.
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
_SIGNED_TYPES = {"i8": 8, "i16": 16, "i32": 32, "i64": 64, "isize": 64}
_BOOL_TYPES = {"bool"}
_COMPARE_CONDITIONS = {
    "EQ": "e",
    "NEQ": "ne",
    "LT": "b",
    "LTE": "be",
    "GT": "a",
    "GTE": "ae",
}
_SIGNED_COMPARE_CONDITIONS = {
    "EQ": "e",
    "NEQ": "ne",
    "LT": "l",
    "LTE": "le",
    "GT": "g",
    "GTE": "ge",
}
_ARG_REGISTERS = (
    {64: "rdi", 32: "edi", 16: "di", 8: "dil"},
    {64: "rsi", 32: "esi", 16: "si", 8: "sil"},
    {64: "rdx", 32: "edx", 16: "dx", 8: "dl"},
    {64: "rcx", 32: "ecx", 16: "cx", 8: "cl"},
    {64: "r8", 32: "r8d", 16: "r8w", 8: "r8b"},
    {64: "r9", 32: "r9d", 16: "r9w", 8: "r9b"},
)
_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TERMINATORS = {"return", "branch", "cond_branch"}


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


def _require_machine_scalar(type_name: Any, *, context: str) -> int:
    if type_name in _BOOL_TYPES:
        return 1
    if type_name in _SIGNED_TYPES:
        return _SIGNED_TYPES[type_name]
    return _require_unsigned(type_name, context=context)


def _comparison_info(
    type_name: Any, predicate: Any, *, context: str
) -> tuple[int, str]:
    if type_name in _SIGNED_TYPES:
        bits = _SIGNED_TYPES[type_name]
        conditions = _SIGNED_COMPARE_CONDITIONS
    else:
        bits = _require_unsigned(type_name, context=context)
        conditions = _COMPARE_CONDITIONS
    condition = conditions.get(predicate)
    if condition is None:
        raise MachineBackendError(
            f"{context}: unsupported compare predicate {predicate!r}"
        )
    return bits, condition


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


def _block_label_map(function: dict[str, Any]) -> dict[str, str]:
    name = function["name"]
    labels: dict[str, str] = {}
    for index, block in enumerate(function.get("blocks", ())):
        label = block.get("label")
        if not isinstance(label, str) or not label:
            raise MachineBackendError(
                f"function {name!r}: machine CFG has an invalid block label"
            )
        if label in labels:
            raise MachineBackendError(
                f"function {name!r}: machine CFG has duplicate block label {label!r}"
            )
        labels[label] = f".L{name}_bb{index}"
    return labels



def _cyclic_components(
    successors: dict[str, tuple[str, ...]]
) -> list[set[str]]:
    """Return cyclic SCCs in deterministic Tarjan order."""
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(label: str) -> None:
        nonlocal index
        indices[label] = index
        lowlinks[label] = index
        index += 1
        stack.append(label)
        on_stack.add(label)
        for target in successors.get(label, ()):
            if target not in indices:
                visit(target)
                lowlinks[label] = min(lowlinks[label], lowlinks[target])
            elif target in on_stack:
                lowlinks[label] = min(lowlinks[label], indices[target])
        if lowlinks[label] != indices[label]:
            return
        component: set[str] = set()
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == label:
                break
        if len(component) > 1 or any(
            member in successors.get(member, ()) for member in component
        ):
            components.append(component)

    for label in successors:
        if label not in indices:
            visit(label)
    return components


def _prove_bounded_loop_backedges(
    function: dict[str, Any],
    *,
    successors: dict[str, tuple[str, ...]],
    value_types: dict[str, str],
) -> frozenset[tuple[str, str]]:
    """Prove stack-lowered unsigned counted loops before accepting backedges.

    M16.2c leaves machine-lowering metadata on phi loads/stores. M16.2d uses
    those facts to identify the induction variable and accepts only recurrences
    that cannot wrap while the loop condition remains true.
    """
    components = _cyclic_components(successors)
    if not components:
        return frozenset()

    name = function.get("name")
    blocks = function.get("blocks", ())
    block_by_label = {block["label"]: block for block in blocks}
    predecessors = {label: set() for label in block_by_label}
    definitions: dict[str, tuple[str, dict[str, Any]] | None] = {}
    constants: dict[str, int] = {}
    for parameter in function.get("parameters", ()):
        parameter_name = parameter.get("name")
        if isinstance(parameter_name, str):
            definitions[parameter_name] = None
    for block in blocks:
        label = block["label"]
        for target in successors.get(label, ()):
            predecessors[target].add(label)
        for instruction in block.get("instructions", ()):
            result = instruction.get("result")
            if isinstance(result, str):
                definitions[result] = (label, instruction)
                if instruction.get("op") == "const_int":
                    constant = instruction.get("attributes", {}).get("value")
                    if isinstance(constant, int) and not isinstance(constant, bool):
                        constants[result] = constant

    proved: set[tuple[str, str]] = set()
    for component in components:
        if len(component) != 2:
            raise MachineBackendError(
                f"function {name!r}: cyclic CFG is outside the bounded-loop machine subset"
            )

        header_candidates: list[tuple[str, str]] = []
        for label in component:
            instructions = block_by_label[label].get("instructions", ())
            if not instructions or instructions[-1].get("op") != "cond_branch":
                continue
            targets = tuple(instructions[-1].get("targets", ()))
            inside = [target for target in targets if target in component]
            outside = [target for target in targets if target not in component]
            if len(inside) == 1 and len(outside) == 1:
                header_candidates.append((label, inside[0]))
        if len(header_candidates) != 1:
            raise MachineBackendError(
                f"function {name!r}: cyclic CFG lacks one canonical counted-loop header"
            )
        header_label, body_label = header_candidates[0]
        body_instructions = block_by_label[body_label].get("instructions", ())
        if (
            not body_instructions
            or body_instructions[-1].get("op") != "branch"
            or tuple(body_instructions[-1].get("targets", ())) != (header_label,)
        ):
            raise MachineBackendError(
                f"function {name!r}: loop body does not have one canonical backedge"
            )

        outside_predecessors = predecessors[header_label] - component
        if predecessors[header_label] != {body_label, *outside_predecessors} or len(
            outside_predecessors
        ) != 1:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop header has non-canonical predecessors"
            )
        preheader_label = next(iter(outside_predecessors))

        header_instructions = block_by_label[header_label].get("instructions", ())
        terminator = header_instructions[-1]
        condition_operands = tuple(terminator.get("operands", ()))
        if len(condition_operands) != 1:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop header has an invalid condition"
            )
        condition_value = condition_operands[0]
        comparison = next(
            (
                instruction for instruction in header_instructions[:-1]
                if instruction.get("op") == "compare"
                and instruction.get("result") == condition_value
            ),
            None,
        )
        if comparison is None:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop condition is not a canonical comparison"
            )
        compare_operands = tuple(comparison.get("operands", ()))
        if len(compare_operands) != 2:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop comparison is malformed"
            )
        counter_value, bound_value = compare_operands
        counter_type = value_types.get(counter_value)
        bits = _require_unsigned(
            counter_type, context=f"function {name!r} bounded loop counter"
        )
        if value_types.get(bound_value) != counter_type:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop limit type does not match the counter"
            )

        counter_load = next(
            (
                instruction for instruction in header_instructions[:-1]
                if instruction.get("op") == "load"
                and instruction.get("result") == counter_value
                and instruction.get("attributes", {}).get("machine_lowering")
                == "phi_edge_copy"
            ),
            None,
        )
        if counter_load is None:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop counter is not a lowered phi value"
            )
        load_operands = tuple(counter_load.get("operands", ()))
        if len(load_operands) != 1:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop counter load is malformed"
            )
        counter_slot = load_operands[0]

        def phi_store(block_label: str) -> dict[str, Any] | None:
            return next(
                (
                    instruction
                    for instruction in block_by_label[block_label].get("instructions", ())
                    if instruction.get("op") == "store"
                    and tuple(instruction.get("operands", ()))[1:] == (counter_slot,)
                    and instruction.get("attributes", {}).get("machine_lowering")
                    == "phi_edge_copy"
                    and instruction.get("attributes", {}).get("phi_target")
                    == header_label
                    and instruction.get("attributes", {}).get("phi_result")
                    == counter_value
                ),
                None,
            )

        preheader_store = phi_store(preheader_label)
        body_store = phi_store(body_label)
        if preheader_store is None or body_store is None:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop counter lacks canonical phi edge stores"
            )
        body_store_operands = tuple(body_store.get("operands", ()))
        if len(body_store_operands) != 2:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop backedge store is malformed"
            )
        next_counter = body_store_operands[0]
        counter_update = next(
            (
                instruction for instruction in body_instructions[:-1]
                if instruction.get("result") == next_counter
            ),
            None,
        )
        if (
            counter_update is None
            or counter_update.get("op") not in {"add", "sub"}
            or counter_update.get("type") != counter_type
        ):
            raise MachineBackendError(
                f"function {name!r}: bounded-loop counter update is not add/sub"
            )
        update_operands = tuple(counter_update.get("operands", ()))
        if len(update_operands) != 2 or update_operands[0] != counter_value:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop counter update must use the current counter"
            )
        step_value = update_operands[1]
        step_definition = definitions.get(step_value)
        if (
            step_definition is None
            or step_definition[0] != body_label
            or step_definition[1].get("op") != "const_int"
            or value_types.get(step_value) != counter_type
        ):
            raise MachineBackendError(
                f"function {name!r}: bounded-loop step must be a body-local unsigned constant"
            )
        step = constants.get(step_value)
        if not isinstance(step, int) or step <= 0:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop step must be positive"
            )

        if bound_value not in definitions:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop limit is undefined"
            )
        bound_definition = definitions[bound_value]
        if bound_definition is not None and bound_definition[0] != preheader_label:
            raise MachineBackendError(
                f"function {name!r}: bounded-loop limit must be a parameter or preheader constant"
            )
        bound_constant = constants.get(bound_value)
        predicate = comparison.get("attributes", {}).get("predicate")
        maximum = (1 << bits) - 1
        operation = counter_update["op"]

        safe = False
        if operation == "add" and predicate == "LT":
            safe = (
                step == 1 if bound_constant is None
                else bound_constant == 0
                or bound_constant <= maximum - step + 1
            )
        elif operation == "add" and predicate == "LTE":
            safe = (
                bound_constant is not None
                and bound_constant <= maximum - step
            )
        elif operation == "sub" and predicate == "GT":
            safe = (
                step == 1 if bound_constant is None
                else bound_constant >= step - 1
            )
        elif operation == "sub" and predicate == "GTE":
            safe = (
                bound_constant is not None
                and bound_constant >= step
            )
        if not safe:
            raise MachineBackendError(
                f"function {name!r}: loop is not proven bounded without unsigned counter wrap"
            )
        proved.add((body_label, header_label))

    return frozenset(proved)


def _validate_function_shape(function: dict[str, Any]) -> None:
    name = function.get("name")
    if not isinstance(name, str) or _SYMBOL_RE.fullmatch(name) is None:
        raise MachineBackendError(f"invalid x86-64 symbol name {name!r}")

    parameters = function.get("parameters", ())
    if len(parameters) > len(_ARG_REGISTERS):
        raise MachineBackendError(
            f"function {name!r} has more than six scalar parameters"
        )
    for parameter in parameters:
        _require_machine_scalar(
            parameter.get("type"),
            context=f"function {name!r} parameter {parameter.get('name')!r}",
        )

    return_type = function.get("return_type")
    if return_type != "void":
        _require_machine_scalar(return_type, context=f"function {name!r} return")

    blocks = function.get("blocks", ())
    if not blocks:
        raise MachineBackendError(f"function {name!r}: machine CFG has no blocks")
    labels = _block_label_map(function)
    value_types = _type_map(function)
    successors: dict[str, tuple[str, ...]] = {}

    for block in blocks:
        label = block["label"]
        instructions = block.get("instructions", ())
        if not instructions:
            raise MachineBackendError(
                f"function {name!r}: block {label!r} is empty"
            )
        terminators = [
            index
            for index, instruction in enumerate(instructions)
            if instruction.get("op") in _TERMINATORS
        ]
        if terminators != [len(instructions) - 1]:
            raise MachineBackendError(
                f"function {name!r}: block {label!r} must end in exactly one terminator"
            )

        for instruction in instructions:
            if instruction.get("op") == "phi":
                raise MachineBackendError(
                    f"function {name!r}: phi lowering waits for the edge-copy milestone"
                )

        terminator = instructions[-1]
        op = terminator.get("op")
        if op == "branch":
            targets = terminator.get("targets", ())
            if len(targets) != 1 or targets[0] not in labels:
                raise MachineBackendError(
                    f"function {name!r}: branch has an invalid target"
                )
            successors[label] = (targets[0],)
        elif op == "cond_branch":
            operands = terminator.get("operands", ())
            targets = terminator.get("targets", ())
            if len(operands) != 1:
                raise MachineBackendError(
                    f"function {name!r}: cond_branch requires one condition"
                )
            if value_types.get(operands[0]) != "bool":
                raise MachineBackendError(
                    f"function {name!r}: cond_branch condition must have type 'bool'"
                )
            if len(targets) != 2 or any(target not in labels for target in targets):
                raise MachineBackendError(
                    f"function {name!r}: cond_branch has invalid targets"
                )
            successors[label] = tuple(targets)
        else:
            successors[label] = ()

    allowed_backedges = _prove_bounded_loop_backedges(
        function, successors=successors, value_types=value_types
    )

    visit_state = {label: 0 for label in labels}

    def visit(label: str) -> None:
        if visit_state[label] == 2:
            return
        if visit_state[label] == 1:
            raise MachineBackendError(
                f"function {name!r}: CFG backedge lacks a bounded-loop proof"
            )
        visit_state[label] = 1
        for target in successors.get(label, ()):
            if visit_state[target] == 1:
                if (label, target) not in allowed_backedges:
                    raise MachineBackendError(
                        f"function {name!r}: CFG backedge lacks a bounded-loop proof"
                    )
                continue
            visit(target)
        visit_state[label] = 2

    for label in labels:
        if visit_state[label] == 0:
            visit(label)


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
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")

    for function in target_ir.get("functions", ()):
        _validate_function_shape(function)

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
                _require_machine_scalar(
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
    bits = _require_machine_scalar(type_name, context=f"parameter {index + 1}")
    registers = _ARG_REGISTERS[index]
    if bits == 64:
        lines.append(f"    mov rax, {registers[64]}")
    elif bits == 32:
        lines.append(f"    mov eax, {registers[32]}")
    elif bits == 16:
        lines.append(f"    movzx eax, {registers[16]}")
    else:
        lines.append(f"    movzx eax, {registers[8]}")
        if bits == 1:
            lines.append("    and eax, 1")


def _truncate_rax(lines: list[str], bits: int) -> None:
    if bits == 1:
        lines.append("    and eax, 1")
    elif bits == 8:
        lines.append("    and eax, 255")
    elif bits == 16:
        lines.append("    and eax, 65535")


def _emit_return(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
    frame_size: int,
) -> None:
    name = function["name"]
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
            _require_machine_scalar(
                return_type, context=f"function {name!r} return"
            ),
        )
    if frame_size:
        lines.append(f"    add rsp, {frame_size}")
    lines.extend(["    pop rbp", "    ret"])


def emit_x86_64_sysv_assembly(
    target_ir: dict[str, Any], *, register_count: int = 2
) -> str:
    """Select real x86-64 instructions from canonical Target IR."""

    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise MachineBackendError("x86-64 machine backend requires Target IR v1")

    for function in target_ir.get("functions", ()):
        _validate_function_shape(function)
    plan = plan_x86_64_sysv_allocation(
        target_ir, register_count=register_count
    )
    plan_by_name = {
        function["name"]: function for function in plan.get("functions", ())
    }

    lines = [".intel_syntax noprefix", ".text"]
    for function in target_ir.get("functions", ()):
        name = function["name"]
        function_plan = plan_by_name.get(name)
        if function_plan is None:
            raise MachineBackendError(f"missing allocation plan for {name!r}")
        locations = _location_map(function_plan)
        stack_slots = _stack_slot_map(function_plan)
        value_types = _type_map(function)
        block_labels = _block_label_map(function)
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
                    _load_value(lines, source, "rax", locations)
                    _truncate_rax(
                        lines,
                        _require_machine_scalar(
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
                    _truncate_rax(
                        lines,
                        _require_machine_scalar(
                            type_name, context=f"function {name!r} load"
                        ),
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
                    bits, condition = _comparison_info(
                        left_type, predicate, context=f"function {name!r} compare"
                    )
                    _load_value(lines, left, "rax", locations)
                    _load_value(lines, right, "rcx", locations)
                    if left_type in _SIGNED_TYPES:
                        signed_registers = {
                            8: ("al", "cl"),
                            16: ("ax", "cx"),
                            32: ("eax", "ecx"),
                            64: ("rax", "rcx"),
                        }
                        left_register, right_register = signed_registers[bits]
                        lines.append(
                            f"    cmp {left_register}, {right_register}"
                        )
                    elif bits == 64:
                        lines.append("    cmp rax, rcx")
                    else:
                        lines.append("    cmp eax, ecx")
                    lines.append(f"    set{condition} al")
                    lines.append("    movzx eax, al")
                    _store_value(lines, result, "rax", locations)
                    continue

                if op == "branch":
                    target = instruction.get("targets", ())[0]
                    lines.append(f"    jmp {block_labels[target]}")
                    continue

                if op == "cond_branch":
                    condition_value = instruction.get("operands", ())[0]
                    true_target, false_target = instruction.get("targets", ())
                    _load_value(lines, condition_value, "rax", locations)
                    _truncate_rax(lines, 1)
                    lines.append("    test al, al")
                    lines.append(f"    jne {block_labels[true_target]}")
                    lines.append(f"    jmp {block_labels[false_target]}")
                    continue

                if op == "return":
                    _emit_return(
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
