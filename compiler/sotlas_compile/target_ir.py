"""A small, explicit Target IR boundary for the checked SIR subset.

This is an inspection/lowering foundation. It deliberately does not perform
instruction selection, register allocation, or object emission.
"""
from __future__ import annotations

from typing import Any


class TargetIRLoweringError(ValueError):
    """Raised when checked SIR contains an operation outside Target IR v1."""


def _validate_phi_edges(
    function_name: str,
    blocks: list[dict[str, Any]],
    value_types: dict[str, str | None],
) -> None:
    predecessors = {block["label"]: set() for block in blocks}
    for block in blocks:
        terminator = block["instructions"][-1]
        for target in terminator.get("targets", ()):
            predecessors[target].add(block["label"])

    for block in blocks:
        seen_non_phi = False
        for instruction in block["instructions"]:
            if instruction["op"] != "phi":
                seen_non_phi = True
                continue
            if seen_non_phi:
                raise TargetIRLoweringError(
                    f"phi in {function_name!r}:{block['label']!r} must precede non-phi instructions"
                )
            incoming = instruction["incoming"]
            incoming_blocks = [item["block"] for item in incoming]
            if len(incoming_blocks) != len(set(incoming_blocks)):
                raise TargetIRLoweringError(
                    f"phi in {function_name!r}:{block['label']!r} has duplicate predecessor inputs"
                )
            if set(incoming_blocks) != predecessors[block["label"]]:
                raise TargetIRLoweringError(
                    f"phi in {function_name!r}:{block['label']!r} inputs do not match CFG predecessors"
                )
            result_type = instruction.get("type")
            for item in incoming:
                value_type = value_types.get(item["value"])
                if (
                    result_type is not None
                    and value_type is not None
                    and value_type != result_type
                ):
                    raise TargetIRLoweringError(
                        f"phi in {function_name!r}:{block['label']!r} has an input with a different type"
                    )


def _validate_ssa_dominance(
    function_name: str,
    blocks: list[dict[str, Any]],
    value_definitions: dict[str, tuple[str, int] | None],
) -> None:
    labels = [block["label"] for block in blocks]
    predecessors = {label: set() for label in labels}
    for block in blocks:
        for target in block["instructions"][-1].get("targets", ()):
            predecessors[target].add(block["label"])

    entry = labels[0]
    dominators = {
        label: ({label} if label == entry else set(labels))
        for label in labels
    }
    changed = True
    while changed:
        changed = False
        for label in labels[1:]:
            incoming = predecessors[label]
            common = (
                set.intersection(*(dominators[item] for item in incoming))
                if incoming else set()
            )
            updated = {label} | common
            if updated != dominators[label]:
                dominators[label] = updated
                changed = True

    def require_available(value: str, use_block: str, use_index: int) -> None:
        definition = value_definitions.get(value)
        if definition is None:
            return
        definition_block, definition_index = definition
        if definition_block == use_block:
            if definition_index >= use_index:
                raise TargetIRLoweringError(
                    f"SIR function {function_name!r} uses {value!r} before its definition"
                )
        elif definition_block not in dominators[use_block]:
            raise TargetIRLoweringError(
                f"SIR function {function_name!r} uses {value!r} outside its defining block's dominance"
            )

    for block in blocks:
        label = block["label"]
        for index, instruction in enumerate(block["instructions"]):
            if instruction["op"] == "phi":
                for item in instruction["incoming"]:
                    predecessor = item["block"]
                    require_available(
                        item["value"], predecessor,
                        len(next(candidate for candidate in blocks
                                 if candidate["label"] == predecessor)["instructions"]) - 1,
                    )
                continue
            for value in instruction.get("operands", ()):
                require_available(value, label, index)


def _value_name(value: Any, *, context: str) -> str:
    name = getattr(value, "name", None)
    if not isinstance(name, str) or not name:
        raise TargetIRLoweringError(f"{context} has an invalid SIR value")
    return name


def _lower_instruction(instruction: Any, *, function: str) -> dict[str, Any]:
    kind = type(instruction).__name__
    context = f"{function}: {kind}"
    if kind == "AllocStackInst":
        return {
            "op": "alloc_stack",
            "result": _value_name(instruction.result, context=context),
            "type": instruction.type_name,
            "attributes": {"source_name": instruction.var_name},
        }
    if kind == "StoreInst":
        return {
            "op": "store",
            "operands": [
                _value_name(instruction.source, context=context),
                _value_name(instruction.destination, context=context),
            ],
        }
    if kind == "LoadInst":
        return {
            "op": "load",
            "result": _value_name(instruction.result, context=context),
            "operands": [_value_name(instruction.source, context=context)],
            "type": getattr(instruction.result, "type_name", None),
        }
    if kind == "ConstantIntInst":
        return {
            "op": "const_int",
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "attributes": {"value": instruction.value},
        }
    if kind == "BinaryOpInst":
        return {
            "op": instruction.operation,
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "operands": [
                _value_name(instruction.left, context=context),
                _value_name(instruction.right, context=context),
            ],
        }
    if kind == "CompareInst":
        return {
            "op": "compare",
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "operands": [
                _value_name(instruction.left, context=context),
                _value_name(instruction.right, context=context),
            ],
            "attributes": {"predicate": instruction.operation},
        }
    if kind == "PhiInst":
        incoming = getattr(instruction, "incoming", None)
        if not isinstance(incoming, list) or not incoming:
            raise TargetIRLoweringError(f"{context} has no incoming values")
        return {
            "op": "phi",
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "incoming": [
                {
                    "value": _value_name(value, context=context),
                    "block": str(block),
                }
                for value, block in incoming
            ],
        }
    if kind == "CallInst":
        result = getattr(instruction, "result", None)
        return {
            "op": "call",
            "result": _value_name(result, context=context) if result else None,
            "operands": [
                _value_name(value, context=context)
                for value in instruction.arguments
            ],
            "attributes": {
                "callee": instruction.callee,
                "system": bool(instruction.is_system),
            },
        }
    if kind == "BranchInst":
        return {
            "op": "branch",
            "targets": [str(instruction.target_block)],
            "attributes": {
                "point_id": getattr(instruction, "point_id", None),
                "control_kind": getattr(instruction, "control_kind", None),
            },
        }
    if kind == "CondBranchInst":
        return {
            "op": "cond_branch",
            "operands": [_value_name(instruction.condition, context=context)],
            "targets": [str(instruction.true_block), str(instruction.false_block)],
        }
    if kind == "ReturnInst":
        value = getattr(instruction, "value", None)
        return {
            "op": "return",
            "operands": [_value_name(value, context=context)] if value else [],
            "attributes": {"point_id": getattr(instruction, "point_id", None)},
        }
    if kind in {"DirectAccessInst", "WhisperBorrowInst"}:
        return {
            "op": "semantic.direct_borrow" if kind == "DirectAccessInst"
            else "semantic.whisper_borrow",
            "operands": [_value_name(instruction.source, context=context)],
            "semantic_only": True,
            "attributes": {
                "callee": instruction.callee,
                "parameter": instruction.parameter,
                "source_domain": instruction.source_domain,
                "point_id": instruction.point_id,
            },
        }
    if kind == "OwnershipDomainTransferInst":
        destination = getattr(instruction, "destination", None)
        return {
            "op": "semantic.ownership_transfer",
            "operands": [
                _value_name(instruction.source, context=context),
                *([_value_name(destination, context=context)] if destination else []),
            ],
            "semantic_only": True,
            "attributes": {
                "operation": instruction.operation,
                "source_domain": instruction.source_domain,
                "target_domain": instruction.target_domain,
                "point_id": instruction.point_id,
            },
        }
    if kind in {"ShareInst", "RetainInst", "ReleaseInst", "DestroyInst"}:
        value = getattr(instruction, "value", None)
        return {
            "op": "semantic." + {
                "ShareInst": "share", "RetainInst": "retain",
                "ReleaseInst": "release", "DestroyInst": "destroy",
            }[kind],
            "operands": [_value_name(value, context=context)],
            "semantic_only": True,
        }
    if kind in {"OwnershipDomainPointInst", "SharedOwnershipPointInst"}:
        return {
            "op": "semantic.ownership_point" if kind == "OwnershipDomainPointInst"
            else "semantic.shared_ownership_point",
            "semantic_only": True,
            "attributes": {
                key: getattr(instruction, key)
                for key in (
                    ("operation", "source_name", "destination_name", "point_id")
                    if kind == "OwnershipDomainPointInst"
                    else ("source_name", "alias_name", "point_id")
                )
            },
        }
    if kind == "DeferUseInst":
        return {
            "op": "semantic.defer_use",
            "operands": [_value_name(instruction.value, context=context)],
            "semantic_only": True,
            "attributes": {"point_id": instruction.defer_point_id},
        }
    if kind == "StateTransitionInst":
        return {
            "op": "semantic.state_transition",
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "operands": [_value_name(instruction.source, context=context)],
            "semantic_only": True,
            "attributes": {
                "space": instruction.space_name,
                "source_state": instruction.source_state,
                "target_state": instruction.target_state,
                "point_id": instruction.point_id,
            },
        }
    raise TargetIRLoweringError(
        f"Target IR v1 does not lower {kind} in function {function!r}"
    )


def lower_sir_to_target_ir(module: Any) -> dict[str, Any]:
    """Lower the checked SIR operation subset into deterministic Target IR v1."""
    functions = []
    seen_functions: set[str] = set()
    for function in tuple(getattr(module, "functions", ()) or ()):
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name or name in seen_functions:
            raise TargetIRLoweringError("SIR module has an invalid function name")
        seen_functions.add(name)
        parameters = tuple(getattr(function, "parameters", ()) or ())
        blocks = tuple(getattr(function, "blocks", ()) or ())
        labels = [str(getattr(block, "label", "")) for block in blocks]
        if not blocks or any(not label for label in labels) or len(set(labels)) != len(labels):
            raise TargetIRLoweringError(
                f"SIR function {name!r} has invalid or duplicate blocks"
            )
        lowered_blocks = []
        for block in blocks:
            label = str(block.label)
            instructions = [
                _lower_instruction(instruction, function=name)
                for instruction in tuple(getattr(block, "instructions", ()) or ())
            ]
            if not instructions:
                raise TargetIRLoweringError(
                    f"SIR block {label!r} in {name!r} is empty"
                )
            for instruction in instructions:
                if instruction["op"] in {"branch", "cond_branch"}:
                    missing = set(instruction.get("targets", ())) - set(labels)
                    if missing:
                        raise TargetIRLoweringError(
                            f"SIR block {label!r} in {name!r} targets missing blocks"
                        )
            lowered_blocks.append({"label": label, "instructions": instructions})
        definitions = {
            _value_name(parameter, context=f"{name}: parameter")
            for parameter in parameters
        }
        value_types = {
            _value_name(parameter, context=f"{name}: parameter"):
                getattr(parameter, "type_name", None)
            for parameter in parameters
        }
        value_definitions = {
            _value_name(parameter, context=f"{name}: parameter"): None
            for parameter in parameters
        }
        references: list[str] = []
        for block in lowered_blocks:
            instructions = block["instructions"]
            terminators = [
                index for index, instruction in enumerate(instructions)
                if instruction["op"] in {"return", "branch", "cond_branch"}
            ]
            if terminators != [len(instructions) - 1]:
                raise TargetIRLoweringError(
                    f"SIR block {block['label']!r} in {name!r} must end in one terminator"
                )
            for index, instruction in enumerate(instructions):
                result = instruction.get("result")
                if result is not None:
                    if result in definitions:
                        raise TargetIRLoweringError(
                            f"SIR function {name!r} defines {result!r} more than once"
                        )
                    definitions.add(result)
                    value_types[result] = instruction.get("type")
                    value_definitions[result] = (block["label"], index)
                references.extend(instruction.get("operands", ()))
                references.extend(
                    incoming["value"]
                    for incoming in instruction.get("incoming", ())
                )
        missing_values = sorted(set(references) - definitions)
        if missing_values:
            raise TargetIRLoweringError(
                f"SIR function {name!r} uses undefined values: "
                + ", ".join(missing_values)
            )
        _validate_phi_edges(name, lowered_blocks, value_types)
        _validate_ssa_dominance(name, lowered_blocks, value_definitions)
        functions.append({
            "name": name,
            "parameters": [
                {
                    "name": _value_name(parameter, context=f"{name}: parameter"),
                    "type": getattr(parameter, "type_name", None),
                }
                for parameter in parameters
            ],
            "return_type": getattr(function, "return_type", None),
            "blocks": lowered_blocks,
        })
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": getattr(module, "name", None),
        "functions": functions,
        "limitations": [
            "No target instruction selection or register allocation is performed.",
            "Native code emission still uses the selected existing backend.",
            "Semantic ownership and state operations are annotations, not runtime lowering.",
        ],
    }


def allocate_target_ir_registers(
    target_ir: dict[str, Any], *, register_count: int = 4
) -> dict[str, Any]:
    """Produce an inspection-only linear-scan allocation for straight-line IR.

    This deliberately rejects control flow and non-scalar values: linear block
    order is not a sound substitute for CFG-aware liveness or ABI lowering.
    """
    if not isinstance(register_count, int) or isinstance(register_count, bool) or register_count < 1:
        raise TargetIRLoweringError("register_count must be a positive integer")
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRLoweringError("register allocation requires Target IR v1")

    scalar_types = {
        "bool", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64",
        "usize", "f32", "f64",
    }
    functions = []
    for function in target_ir.get("functions", ()):
        blocks = function.get("blocks", ())
        if len(blocks) != 1:
            raise TargetIRLoweringError(
                f"register allocation preview requires one straight-line block in {function.get('name')!r}"
            )
        instructions = blocks[0].get("instructions", ())
        if any(item.get("op") in {"branch", "cond_branch", "phi"} for item in instructions):
            raise TargetIRLoweringError("register allocation preview does not support CFG or phi nodes")
        supported_ops = {
            "alloc_stack", "load", "store", "const_int", "add", "sub", "mul",
            "compare", "call", "return",
        }
        unsupported_ops = sorted({item.get("op") for item in instructions} - supported_ops)
        if unsupported_ops:
            raise TargetIRLoweringError(
                "register allocation preview does not support operations: "
                + ", ".join(str(item) for item in unsupported_ops)
            )

        intervals: dict[str, dict[str, Any]] = {}
        for parameter in function.get("parameters", ()):
            name, type_name = parameter.get("name"), parameter.get("type")
            if type_name not in scalar_types:
                raise TargetIRLoweringError(
                    f"register allocation preview does not support type {type_name!r}"
                )
            intervals[name] = {"value": name, "type": type_name, "start": 0, "end": 0}

        for index, instruction in enumerate(instructions):
            result = instruction.get("result")
            if result is not None and instruction.get("op") != "alloc_stack":
                type_name = instruction.get("type")
                if type_name not in scalar_types:
                    raise TargetIRLoweringError(
                        f"register allocation preview does not support type {type_name!r}"
                    )
                intervals[result] = {
                    "value": result, "type": type_name, "start": index, "end": index,
                }
            operands = instruction.get("operands", ())
            if instruction.get("op") == "load":
                operands = ()  # The stack address is not an allocatable scalar.
            elif instruction.get("op") == "store":
                operands = operands[:1]  # Only the stored scalar has a live interval.
            for operand in operands:
                if operand in intervals:
                    intervals[operand]["end"] = max(intervals[operand]["end"], index)

        ordered = sorted(intervals.values(), key=lambda item: (item["start"], item["value"]))
        active: list[tuple[int, str, int]] = []
        free_registers = list(range(register_count))
        locations: dict[str, dict[str, Any]] = {}
        next_spill = 0
        for interval in ordered:
            still_active = []
            for end, value, register in active:
                if end < interval["start"]:
                    free_registers.append(register)
                else:
                    still_active.append((end, value, register))
            active = still_active
            free_registers.sort()
            if free_registers:
                register = free_registers.pop(0)
                locations[interval["value"]] = {"kind": "register", "index": register}
                active.append((interval["end"], interval["value"], register))
                active.sort()
            else:
                locations[interval["value"]] = {"kind": "spill", "slot": next_spill}
                next_spill += 1

        functions.append({
            "name": function.get("name"),
            "block": blocks[0].get("label"),
            "intervals": [
                {**interval, "location": locations[interval["value"]]}
                for interval in ordered
            ],
            "spill_slots": next_spill,
        })
    return {
        "schema": "sotlas.register-allocation-preview.v1",
        "algorithm": "linear_scan_straight_line",
        "register_count": register_count,
        "functions": functions,
        "limitations": [
            "Inspection only; this allocation is not consumed by a code generator.",
            "Only single-block scalar functions are supported; CFG liveness, ABI, stack layout, and spill code are not modeled.",
        ],
    }


__all__ = [
    "TargetIRLoweringError", "allocate_target_ir_registers",
    "lower_sir_to_target_ir",
]
