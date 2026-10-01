"""Target IR lowering for checked logical slice indexing (M16.4f3b)."""
from __future__ import annotations

from typing import Any

from . import target_ir as _base
from . import target_ir_struct_fields as _aggregate


_BOUNDS_CHECK_INST = "BoundsCheckInst"
_SLICE_ADDRESS_INST = "SliceElementAddressInst"
_SLICE_ELEMENT_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _contains_slice_indexing(module: Any) -> bool:
    return any(
        type(instruction).__name__ in {_BOUNDS_CHECK_INST, _SLICE_ADDRESS_INST}
        for function in tuple(getattr(module, "functions", ()) or ())
        for block in tuple(getattr(function, "blocks", ()) or ())
        for instruction in tuple(getattr(block, "instructions", ()) or ())
    )


def _lower_instruction(instruction: Any, *, function: str) -> dict[str, Any]:
    kind = type(instruction).__name__
    if kind == _BOUNDS_CHECK_INST:
        context = f"{function}: {_BOUNDS_CHECK_INST}"
        index = _base._value_name(instruction.index, context=context)
        length = _base._value_name(instruction.length, context=context)
        index_type = getattr(instruction.index, "type_name", None)
        length_type = getattr(instruction.length, "type_name", None)
        can_eliminate = getattr(instruction, "can_eliminate", None)
        if (
            index_type != "usize"
            or length_type != "usize"
            or not isinstance(can_eliminate, bool)
        ):
            raise _base.TargetIRLoweringError(
                f"{context} contains malformed slice bounds proof"
            )
        return {
            "op": "bounds_check",
            "operands": [index, length],
            "attributes": {"can_eliminate": can_eliminate},
        }

    if kind == _SLICE_ADDRESS_INST:
        context = f"{function}: {_SLICE_ADDRESS_INST}"
        base = _base._value_name(instruction.base, context=context)
        index = _base._value_name(instruction.index, context=context)
        length = _base._value_name(instruction.length, context=context)
        result = _base._value_name(instruction.result, context=context)
        base_type = getattr(instruction.base, "type_name", None)
        index_type = getattr(instruction.index, "type_name", None)
        length_type = getattr(instruction.length, "type_name", None)
        result_type = getattr(instruction.result, "type_name", None)
        element_type = getattr(instruction, "element_type", None)
        bounds_policy = getattr(instruction, "bounds_policy", None)
        point_id = getattr(instruction, "point_id", None)
        if (
            element_type not in _SLICE_ELEMENT_TYPES
            or base_type != f"{element_type}*"
            or index_type != "usize"
            or length_type != "usize"
            or result_type != f"{element_type}*"
            or bounds_policy != "checked"
            or not isinstance(point_id, str)
            or not point_id.startswith("slice_address@")
        ):
            raise _base.TargetIRLoweringError(
                f"{context} contains malformed slice projection facts"
            )
        return {
            "op": "slice_address",
            "result": result,
            "type": result_type,
            "operands": [base, index, length],
            "attributes": {
                "element_type": element_type,
                "bounds_policy": "checked",
                "source_point_id": point_id,
            },
        }

    return _aggregate._lower_instruction(instruction, function=function)


def _validate_bounds_proofs(
    function_name: str,
    lowered_blocks: list[dict[str, Any]],
) -> None:
    """Require a same-block dominating proof for every logical slice address."""
    for block in lowered_blocks:
        proven: set[tuple[str, str]] = set()
        for instruction in block["instructions"]:
            op = instruction.get("op")
            operands = instruction.get("operands", ())
            if op == "bounds_check":
                if len(operands) != 2:
                    raise _base.TargetIRLoweringError(
                        f"slice bounds proof in {function_name!r} is malformed"
                    )
                proven.add((operands[0], operands[1]))
                continue
            if op != "slice_address":
                continue
            if len(operands) != 3 or (operands[1], operands[2]) not in proven:
                raise _base.TargetIRLoweringError(
                    f"slice address in {function_name!r} lacks a dominating bounds proof"
                )


def lower_sir_to_target_ir_with_slice_indexing(module: Any) -> dict[str, Any]:
    """Lower f3b slice checks/projections while retaining Target IR v1 SSA gates."""
    if not _contains_slice_indexing(module):
        return _aggregate.lower_sir_to_target_ir_with_struct_fields(module)

    functions = []
    seen_functions: set[str] = set()
    for function in tuple(getattr(module, "functions", ()) or ()):
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name or name in seen_functions:
            raise _base.TargetIRLoweringError("SIR module has an invalid function name")
        seen_functions.add(name)
        parameters = tuple(getattr(function, "parameters", ()) or ())
        blocks = tuple(getattr(function, "blocks", ()) or ())
        labels = [str(getattr(block, "label", "")) for block in blocks]
        if (
            not blocks
            or any(not label for label in labels)
            or len(set(labels)) != len(labels)
        ):
            raise _base.TargetIRLoweringError(
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
                raise _base.TargetIRLoweringError(
                    f"SIR block {label!r} in {name!r} is empty"
                )
            for instruction in instructions:
                if instruction["op"] in {"branch", "cond_branch"}:
                    missing = set(instruction.get("targets", ())) - set(labels)
                    if missing:
                        raise _base.TargetIRLoweringError(
                            f"SIR block {label!r} in {name!r} targets missing blocks"
                        )
            lowered_blocks.append({"label": label, "instructions": instructions})

        _validate_bounds_proofs(name, lowered_blocks)

        definitions = {
            _base._value_name(parameter, context=f"{name}: parameter")
            for parameter in parameters
        }
        value_types = {
            _base._value_name(parameter, context=f"{name}: parameter"):
                getattr(parameter, "type_name", None)
            for parameter in parameters
        }
        value_definitions = {
            _base._value_name(parameter, context=f"{name}: parameter"): None
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
                raise _base.TargetIRLoweringError(
                    f"SIR block {block['label']!r} in {name!r} must end in one terminator"
                )
            for index, instruction in enumerate(instructions):
                result = instruction.get("result")
                if result is not None:
                    if result in definitions:
                        raise _base.TargetIRLoweringError(
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
            raise _base.TargetIRLoweringError(
                f"SIR function {name!r} uses undefined values: "
                + ", ".join(missing_values)
            )
        _base._validate_phi_edges(name, lowered_blocks, value_types)
        _base._validate_ssa_dominance(name, lowered_blocks, value_definitions)
        functions.append({
            "name": name,
            "parameters": [
                {
                    "name": _base._value_name(
                        parameter, context=f"{name}: parameter"
                    ),
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


__all__ = ["lower_sir_to_target_ir_with_slice_indexing"]
