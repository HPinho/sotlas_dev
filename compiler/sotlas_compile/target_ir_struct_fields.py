"""Target IR extension for canonical aggregate address projection.

The base Target IR v1 path remains untouched for modules without the M16.4c
``StructFieldAddressInst``, M16.4d2 ``FixedArrayElementAddressInst``, or
M16.4d3b ``DynamicFixedArrayElementAddressInst``. Modules that contain one of
those proven SIR operations use the extended lowering below; all existing
instruction lowering and CFG/SSA validation is still delegated to the canonical
Target IR helpers.
"""
from __future__ import annotations

from typing import Any

from . import target_ir as _base


_FIELD_INST = "StructFieldAddressInst"
_ARRAY_INST = "FixedArrayElementAddressInst"
_DYNAMIC_ARRAY_INST = "DynamicFixedArrayElementAddressInst"
_SCALAR_ARRAY_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


def _contains_extended_addressing(module: Any) -> bool:
    return any(
        type(instruction).__name__ in {
            _FIELD_INST,
            _ARRAY_INST,
            _DYNAMIC_ARRAY_INST,
        }
        for function in tuple(getattr(module, "functions", ()) or ())
        for block in tuple(getattr(function, "blocks", ()) or ())
        for instruction in tuple(getattr(block, "instructions", ()) or ())
    )


def _lower_instruction(instruction: Any, *, function: str) -> dict[str, Any]:
    kind = type(instruction).__name__
    if kind not in {_FIELD_INST, _ARRAY_INST, _DYNAMIC_ARRAY_INST}:
        return _base._lower_instruction(instruction, function=function)

    if kind == _ARRAY_INST:
        context = f"{function}: {_ARRAY_INST}"
        base = _base._value_name(instruction.base, context=context)
        result = _base._value_name(instruction.result, context=context)
        result_type = getattr(instruction.result, "type_name", None)
        element_type = getattr(instruction, "element_type", None)
        length = getattr(instruction, "length", None)
        index = getattr(instruction, "index", None)
        point_id = getattr(instruction, "point_id", None)
        if (
            element_type not in _SCALAR_ARRAY_TYPES
            or not isinstance(length, int)
            or isinstance(length, bool)
            or length < 1
            or not isinstance(index, int)
            or isinstance(index, bool)
            or index < 0
            or index >= length
            or result_type != f"{element_type}*"
            or not isinstance(point_id, str)
            or not point_id.startswith("array_address@")
        ):
            raise _base.TargetIRLoweringError(
                f"{context} contains malformed fixed-array projection facts"
            )
        return {
            "op": "array_address",
            "result": result,
            "type": result_type,
            "operands": [base],
            "attributes": {
                "element_type": element_type,
                "length": length,
                "index": index,
                "source_point_id": point_id,
            },
        }

    if kind == _DYNAMIC_ARRAY_INST:
        context = f"{function}: {_DYNAMIC_ARRAY_INST}"
        base = _base._value_name(instruction.base, context=context)
        index = _base._value_name(instruction.index, context=context)
        result = _base._value_name(instruction.result, context=context)
        result_type = getattr(instruction.result, "type_name", None)
        index_type = getattr(instruction.index, "type_name", None)
        element_type = getattr(instruction, "element_type", None)
        length = getattr(instruction, "length", None)
        bounds_policy = getattr(instruction, "bounds_policy", None)
        point_id = getattr(instruction, "point_id", None)
        if (
            element_type not in _SCALAR_ARRAY_TYPES
            or not isinstance(length, int)
            or isinstance(length, bool)
            or length < 1
            or index_type != "usize"
            or bounds_policy != "trap"
            or result_type != f"{element_type}*"
            or not isinstance(point_id, str)
            or not point_id.startswith("array_address_dynamic@")
        ):
            raise _base.TargetIRLoweringError(
                f"{context} contains malformed dynamic fixed-array projection facts"
            )
        return {
            "op": "array_address_dynamic",
            "result": result,
            "type": result_type,
            "operands": [base, index],
            "attributes": {
                "element_type": element_type,
                "length": length,
                "bounds_policy": "trap",
                "source_point_id": point_id,
            },
        }

    context = f"{function}: {_FIELD_INST}"
    base = _base._value_name(instruction.base, context=context)
    result = _base._value_name(instruction.result, context=context)
    result_type = getattr(instruction.result, "type_name", None)
    struct_name = getattr(instruction, "struct_name", None)
    field_name = getattr(instruction, "field_name", None)
    field_type = getattr(instruction, "field_type", None)
    point_id = getattr(instruction, "point_id", None)
    if (
        not isinstance(struct_name, str) or not struct_name
        or not isinstance(field_name, str) or not field_name
        or not isinstance(field_type, str) or not field_type
        or result_type != f"{field_type}*"
        or not isinstance(point_id, str)
        or not point_id.startswith("field_address@")
    ):
        raise _base.TargetIRLoweringError(
            f"{context} contains malformed struct field projection facts"
        )
    return {
        "op": "field_address",
        "result": result,
        "type": result_type,
        "operands": [base],
        "attributes": {
            "struct": struct_name,
            "field": field_name,
            "field_type": field_type,
            "source_point_id": point_id,
        },
    }


def lower_sir_to_target_ir_with_struct_fields(module: Any) -> dict[str, Any]:
    """Lower canonical SIR, extending Target IR only for proven M16.4 projections."""
    if not _contains_extended_addressing(module):
        return _base.lower_sir_to_target_ir(module)

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
        if not blocks or any(not label for label in labels) or len(set(labels)) != len(labels):
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


__all__ = ["lower_sir_to_target_ir_with_struct_fields"]
