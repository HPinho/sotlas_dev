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
        attributes = {"value": instruction.value}
        source_point_id = getattr(instruction, "source_point_id", None)
        if isinstance(source_point_id, str) and source_point_id:
            attributes["source_point_id"] = source_point_id
        return {
            "op": "const_int",
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "attributes": attributes,
        }
    if kind == "BinaryOpInst":
        attributes = {}
        source_point_id = getattr(instruction, "source_point_id", None)
        if isinstance(source_point_id, str) and source_point_id:
            attributes["source_point_id"] = source_point_id
        return {
            "op": instruction.operation,
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "operands": [
                _value_name(instruction.left, context=context),
                _value_name(instruction.right, context=context),
            ],
            "attributes": attributes,
        }
    if kind == "CompareInst":
        attributes = {"predicate": instruction.operation}
        source_point_id = getattr(instruction, "source_point_id", None)
        if isinstance(source_point_id, str) and source_point_id:
            attributes["source_point_id"] = source_point_id
        return {
            "op": "compare",
            "result": _value_name(instruction.result, context=context),
            "type": getattr(instruction.result, "type_name", None),
            "operands": [
                _value_name(instruction.left, context=context),
                _value_name(instruction.right, context=context),
            ],
            "attributes": attributes,
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
                "source_point_id": getattr(instruction, "source_point_id", None),
                "defer_point_id": getattr(instruction, "defer_point_id", None),
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
    """Produce an inspection-only graph-coloring allocation for scalar CFG IR.

    This report consumes the CFG liveness/interference analysis, including phi
    edge uses. It remains a preview and does not impose ABI constraints or
    generate moves, spill code, or machine instructions.
    """
    if not isinstance(register_count, int) or isinstance(register_count, bool) or register_count < 1:
        raise TargetIRLoweringError("register_count must be a positive integer")
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRLoweringError("register allocation requires Target IR v1")

    scalar_types = {
        "bool", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64",
        "usize", "f32", "f64",
    }

    def is_allocatable_scalar(type_name: Any) -> bool:
        if type_name in scalar_types:
            return True
        return (
            isinstance(type_name, str)
            and type_name.count("*") == 1
            and type_name.endswith("*")
            and type_name[:-1] in scalar_types
        )

    liveness = analyze_target_ir_liveness(target_ir)
    liveness_by_name = {
        item["name"]: item for item in liveness["functions"]
    }
    functions = []
    for function in target_ir.get("functions", ()):
        name = function.get("name")
        live_function = liveness_by_name.get(name)
        if live_function is None:
            raise TargetIRLoweringError(
                f"register allocation preview has no liveness result for {name!r}"
            )

        allocatable: dict[str, dict[str, Any]] = {}
        for parameter in function.get("parameters", ()):
            value = parameter.get("name")
            type_name = parameter.get("type")
            if not is_allocatable_scalar(type_name):
                raise TargetIRLoweringError(
                    f"register allocation preview does not support type {type_name!r}"
                )
            allocatable[value] = {"value": value, "type": type_name}
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                value = instruction.get("result")
                if (
                    value is None or instruction.get("op") == "alloc_stack"
                    or instruction.get("semantic_only")
                ):
                    continue
                type_name = instruction.get("type")
                if not is_allocatable_scalar(type_name):
                    raise TargetIRLoweringError(
                        f"register allocation preview does not support type {type_name!r}"
                    )
                allocatable[value] = {"value": value, "type": type_name}

        graph = {value: set() for value in allocatable}
        for left, right in live_function["interference_edges"]:
            if left in graph and right in graph:
                graph[left].add(right)
                graph[right].add(left)
        interference_edges = [
            [left, right]
            for left in sorted(graph)
            for right in sorted(graph[left])
            if left < right
        ]

        # Deterministic greedy coloring: choose the most constrained value
        # first, then its source-stable name. Uncolored values receive unique
        # spill slots; no claim is made about spill reuse or target registers.
        coloring_order = sorted(
            graph, key=lambda value: (-len(graph[value]), value)
        )
        locations: dict[str, dict[str, Any]] = {}
        next_spill = 0
        for value in coloring_order:
            unavailable = {
                locations[neighbor]["index"]
                for neighbor in graph[value]
                if locations.get(neighbor, {}).get("kind") == "register"
            }
            register = next(
                (candidate for candidate in range(register_count)
                 if candidate not in unavailable),
                None,
            )
            if register is None:
                locations[value] = {"kind": "spill", "slot": next_spill}
                next_spill += 1
            else:
                locations[value] = {"kind": "register", "index": register}

        functions.append({
            "name": name,
            "blocks": live_function["blocks"],
            "interference_edges": interference_edges,
            "values": [
                {**allocatable[value], "location": locations[value],
                 "interferes_with": sorted(graph[value])}
                for value in sorted(allocatable)
            ],
            "spill_slots": next_spill,
        })
    return {
        "schema": "sotlas.register-allocation-preview.v1",
        "algorithm": "greedy_cfg_graph_coloring",
        "register_count": register_count,
        "functions": functions,
        "limitations": [
            "Inspection only; this allocation is not consumed by a code generator.",
            "Scalar values only; register classes, ABI constraints, coalescing, spill reuse/code, and machine instructions are not modeled.",
        ],
    }


def layout_target_ir_stack(
    target_ir: dict[str, Any], *, stack_alignment: int = 16
) -> dict[str, Any]:
    """Lay out scalar alloc_stack slots using a target-neutral frame model."""
    if (
        not isinstance(stack_alignment, int)
        or isinstance(stack_alignment, bool)
        or stack_alignment < 1
        or stack_alignment & (stack_alignment - 1)
    ):
        raise TargetIRLoweringError("stack_alignment must be a positive power of two")
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRLoweringError("stack layout requires Target IR v1")

    type_layout = {
        "bool": (1, 1), "i8": (1, 1), "u8": (1, 1),
        "i16": (2, 2), "u16": (2, 2),
        "i32": (4, 4), "u32": (4, 4), "f32": (4, 4),
        "i64": (8, 8), "u64": (8, 8), "usize": (8, 8), "f64": (8, 8),
    }


    functions = []
    for function in target_ir.get("functions", ()):
        slots = []
        cursor = 0
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "alloc_stack":
                    continue
                type_name = instruction.get("type")
                if type_name not in type_layout:
                    raise TargetIRLoweringError(
                        f"stack layout preview does not support type {type_name!r}"
                    )
                size, alignment = type_layout[type_name]
                cursor = (cursor + alignment - 1) & -alignment
                slots.append({
                    "value": instruction.get("result"),
                    "source_name": instruction.get("attributes", {}).get("source_name"),
                    "type": type_name,
                    "offset_bytes": cursor,
                    "size_bytes": size,
                    "alignment_bytes": alignment,
                })
                cursor += size
        frame_size = (cursor + stack_alignment - 1) & -stack_alignment
        functions.append({
            "name": function.get("name"),
            "slots": slots,
            "raw_size_bytes": cursor,
            "frame_size_bytes": frame_size,
            "frame_alignment_bytes": stack_alignment,
        })
    return {
        "schema": "sotlas.stack-layout-preview.v1",
        "model": "target_neutral_local_slots",
        "functions": functions,
        "limitations": [
            "Local scalar slots only; parameters, spills, saved registers, and outgoing arguments are not included.",
            "Offsets are relative to an abstract frame base and do not describe a platform ABI or emitted machine stack frame.",
        ],
    }


def analyze_target_ir_liveness(target_ir: dict[str, Any]) -> dict[str, Any]:
    """Compute CFG liveness and SSA interference for the checked Target IR."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRLoweringError("liveness analysis requires Target IR v1")

    functions = []
    for function in target_ir.get("functions", ()):
        blocks = function.get("blocks", ())
        labels = [block.get("label") for block in blocks]
        successors: dict[str, set[str]] = {label: set() for label in labels}
        instructions_by_block = {
            block["label"]: block.get("instructions", ()) for block in blocks
        }
        definitions: dict[str, dict[str, Any]] = {}
        for parameter in function.get("parameters", ()):
            definitions[parameter["name"]] = {
                "value": parameter["name"], "type": parameter.get("type"),
                "kind": "parameter",
            }
        uses: dict[str, set[str]] = {}
        defs: dict[str, set[str]] = {}
        phi_defs: dict[str, set[str]] = {}
        phi_edge_uses: dict[tuple[str, str], set[str]] = {}

        for block in blocks:
            label = block["label"]
            block_use: set[str] = set()
            block_defs: set[str] = set()
            block_phi_defs: set[str] = set()
            for instruction in instructions_by_block[label]:
                for target in instruction.get("targets", ()):
                    successors[label].add(target)
                result = instruction.get("result")
                if result is not None:
                    definitions[result] = {
                        "value": result, "type": instruction.get("type"),
                        "kind": "value",
                    }
                    block_defs.add(result)
                    if instruction.get("op") == "phi":
                        block_phi_defs.add(result)
                if instruction.get("op") == "phi":
                    for incoming in instruction.get("incoming", ()):
                        phi_edge_uses.setdefault(
                            (incoming["block"], label), set()
                        ).add(incoming["value"])
                    continue
                if instruction.get("semantic_only"):
                    continue
                for operand in instruction.get("operands", ()):
                    if operand not in block_defs:
                        block_use.add(operand)
            uses[label] = block_use
            defs[label] = block_defs
            phi_defs[label] = block_phi_defs

        live_in = {label: set() for label in labels}
        live_out = {label: set() for label in labels}
        changed = True
        while changed:
            changed = False
            for label in reversed(labels):
                outgoing = set()
                for successor in successors[label]:
                    outgoing.update(live_in[successor] - phi_defs[successor])
                    outgoing.update(phi_edge_uses.get((label, successor), ()))
                incoming = uses[label] | (outgoing - defs[label])
                if outgoing != live_out[label] or incoming != live_in[label]:
                    live_out[label] = outgoing
                    live_in[label] = incoming
                    changed = True

        interference: set[tuple[str, str]] = set()

        def add_live_clique(values: set[str]) -> None:
            ordered = sorted(values)
            for index, first in enumerate(ordered):
                for second in ordered[index + 1:]:
                    interference.add((first, second))

        for label in labels:
            live = set(live_out[label])
            add_live_clique(live)
            for instruction in reversed(instructions_by_block[label]):
                if instruction.get("semantic_only"):
                    continue
                result = instruction.get("result")
                if result is not None:
                    for value in live:
                        if result != value:
                            interference.add(tuple(sorted((result, value))))
                    live.discard(result)
                if instruction.get("op") != "phi":
                    live.update(instruction.get("operands", ()))
                add_live_clique(live)

        functions.append({
            "name": function.get("name"),
            "blocks": [
                {
                    "label": label,
                    "successors": sorted(successors[label]),
                    "live_in": sorted(live_in[label]),
                    "live_out": sorted(live_out[label]),
                }
                for label in labels
            ],
            "values": [definitions[name] for name in sorted(definitions)],
            "interference_edges": [list(edge) for edge in sorted(interference)],
        })
    return {
        "schema": "sotlas.target-ir-liveness.v1",
        "analysis": "backward_dataflow_with_phi_edge_uses",
        "functions": functions,
        "limitations": [
            "Semantic-only ownership/state annotations do not participate as machine-value uses.",
            "Interference is analysis output only; no target register classes, ABI constraints, coalescing, spill code, or machine instructions are produced.",
        ],
    }


def map_target_ir_source_points(target_ir: dict[str, Any]) -> dict[str, Any]:
    """Index the source-stable point IDs already carried by Target IR.

    This is deliberately a partial mapping: ordinary arithmetic instructions
    do not yet carry source spans, so each function reports mapping coverage.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRLoweringError("source mapping requires Target IR v1")

    functions = []
    total_instructions = 0
    mapped_instructions = 0
    for function in target_ir.get("functions", ()):
        mappings = []
        instruction_count = 0
        for block in function.get("blocks", ()):
            for index, instruction in enumerate(block.get("instructions", ())):
                instruction_count += 1
                attributes = instruction.get("attributes", {})
                point_id = next((
                    attributes.get(key)
                    for key in ("source_point_id", "point_id", "defer_point_id")
                    if isinstance(attributes.get(key), str)
                    and attributes.get(key)
                ), None)
                if point_id is None:
                    continue
                source_kind, separator, location = point_id.rpartition("@")
                line = column = None
                if separator:
                    line_text, colon, column_text = location.partition(":")
                    if colon:
                        try:
                            line, column = int(line_text), int(column_text)
                        except ValueError:
                            line = column = None
                mappings.append({
                    "source_id": point_id,
                    "source_kind": source_kind if separator else None,
                    "line": line,
                    "column": column,
                    "block": block.get("label"),
                    "instruction_index": index,
                    "operation": instruction.get("op"),
                    "result": instruction.get("result"),
                    "operands": instruction.get("operands", []),
                })
        total_instructions += instruction_count
        mapped_instructions += len(mappings)
        functions.append({
            "name": function.get("name"),
            "instruction_count": instruction_count,
            "mapped_instruction_count": len(mappings),
            "coverage": (
                len(mappings) / instruction_count if instruction_count else 1.0
            ),
            "mappings": mappings,
        })
    return {
        "schema": "sotlas.target-ir-source-map.v1",
        "representation": "source_stable_point_ids_and_expression_spans",
        "instruction_count": total_instructions,
        "mapped_instruction_count": mapped_instructions,
        "coverage": (
            mapped_instructions / total_instructions
            if total_instructions else 1.0
        ),
        "functions": functions,
        "limitations": [
            "Only instructions with source-stable point IDs or expression spans are mapped; unsupported SIR operations may remain unmapped.",
            "Mappings describe pre-selection Target IR positions and do not identify emitted machine instructions.",
        ],
    }


__all__ = [
    "TargetIRLoweringError", "allocate_target_ir_registers",
    "analyze_target_ir_liveness", "map_target_ir_source_points",
    "layout_target_ir_stack", "lower_sir_to_target_ir",
]
