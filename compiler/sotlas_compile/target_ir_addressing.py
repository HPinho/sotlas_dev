"""Backend-neutral address calculation contract for Target IR v1.

M16.4b admits exact local-slot ``address_of``. M16.4c adds typed struct field
projection as ``field_address`` while deliberately keeping target byte offsets
out of Target IR. Field identity and declaration order/types are validated here;
the selected machine backend owns physical layout.
"""
from __future__ import annotations

from typing import Any


_SCALAR_FIELD_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


class TargetIRAddressingError(ValueError):
    """Raised when Target IR addressing facts violate the M16.4 contract."""


def _struct_layout_map(
    target_ir: dict[str, Any],
) -> dict[str, dict[str, str]]:
    layouts: dict[str, dict[str, str]] = {}
    for layout in target_ir.get("struct_layouts", ()):
        name = layout.get("name") if isinstance(layout, dict) else None
        fields = layout.get("fields") if isinstance(layout, dict) else None
        if not isinstance(name, str) or not name or name in layouts:
            raise TargetIRAddressingError(
                "Target IR contains an invalid or duplicate struct layout"
            )
        if not isinstance(fields, list) or not fields:
            raise TargetIRAddressingError(
                f"struct {name!r}: Target IR layout requires fields"
            )
        field_map: dict[str, str] = {}
        for field in fields:
            field_name = field.get("name") if isinstance(field, dict) else None
            type_name = field.get("type") if isinstance(field, dict) else None
            if (
                not isinstance(field_name, str)
                or not field_name
                or field_name in field_map
                or type_name not in _SCALAR_FIELD_TYPES
            ):
                raise TargetIRAddressingError(
                    f"struct {name!r}: malformed M16.4c field declaration"
                )
            if any(
                key in field for key in ("offset_bytes", "size_bytes", "alignment_bytes")
            ):
                raise TargetIRAddressingError(
                    f"struct {name!r}: Target IR field declarations cannot carry target layout bytes"
                )
            field_map[field_name] = type_name
        layouts[name] = field_map
    return layouts


def _value_types(function: dict[str, Any]) -> dict[str, str]:
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


def validate_target_ir_addressing(target_ir: dict[str, Any]) -> None:
    """Validate exact local addresses and typed struct-field projections."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIRAddressingError("address calculation requires Target IR v1")

    layouts = _struct_layout_map(target_ir)
    for function in target_ir.get("functions", ()):
        name = function.get("name")
        value_types = _value_types(function)
        slots: dict[str, str] = {}
        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                if instruction.get("op") != "alloc_stack":
                    continue
                result = instruction.get("result")
                type_name = instruction.get("type")
                if not isinstance(result, str) or not result or result in slots:
                    raise TargetIRAddressingError(
                        f"function {name!r}: invalid or duplicate alloc_stack result"
                    )
                if not isinstance(type_name, str) or not type_name:
                    raise TargetIRAddressingError(
                        f"function {name!r}: alloc_stack has an invalid type"
                    )
                slots[result] = type_name

        for block in function.get("blocks", ()):
            for instruction in block.get("instructions", ()):
                op = instruction.get("op")
                if op == "address_of":
                    result = instruction.get("result")
                    operands = instruction.get("operands", ())
                    pointer_type = instruction.get("type")
                    if not isinstance(result, str) or not result:
                        raise TargetIRAddressingError(
                            f"function {name!r}: address_of requires a result"
                        )
                    if len(operands) != 1:
                        raise TargetIRAddressingError(
                            f"function {name!r}: address_of requires one local stack slot"
                        )
                    source = operands[0]
                    slot_type = slots.get(source)
                    if slot_type is None:
                        raise TargetIRAddressingError(
                            f"function {name!r}: address_of source is not a local stack slot"
                        )
                    if "*" in slot_type:
                        raise TargetIRAddressingError(
                            f"function {name!r}: pointer-to-pointer address calculation is not supported"
                        )
                    if pointer_type != f"{slot_type}*":
                        raise TargetIRAddressingError(
                            f"function {name!r}: address_of result type must be {slot_type + '*'!r}"
                        )
                    offset = instruction.get("attributes", {}).get("offset_bytes", 0)
                    if offset != 0:
                        raise TargetIRAddressingError(
                            f"function {name!r}: address_of byte offsets wait for aggregate layout"
                        )
                    continue

                if op != "field_address":
                    continue
                result = instruction.get("result")
                operands = instruction.get("operands", ())
                attributes = instruction.get("attributes", {})
                struct_name = attributes.get("struct")
                field_name = attributes.get("field")
                field_type = attributes.get("field_type")
                point_id = attributes.get("source_point_id")
                if not isinstance(result, str) or not result:
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address requires a result"
                    )
                if len(operands) != 1:
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address requires one struct pointer"
                    )
                if (
                    not isinstance(struct_name, str) or not struct_name
                    or not isinstance(field_name, str) or not field_name
                    or field_type not in _SCALAR_FIELD_TYPES
                ):
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address contains malformed field identity"
                    )
                if "offset_bytes" in attributes:
                    raise TargetIRAddressingError(
                        f"function {name!r}: Target IR field_address cannot carry a target byte offset"
                    )
                declared = layouts.get(struct_name, {}).get(field_name)
                if declared is None or declared != field_type:
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address does not match a declared struct field"
                    )
                if value_types.get(operands[0]) != f"{struct_name}*":
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address base must be {struct_name + '*'!r}"
                    )
                if instruction.get("type") != f"{field_type}*":
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address result type must be {field_type + '*'!r}"
                    )
                if not isinstance(point_id, str) or not point_id.startswith("field_address@"):
                    raise TargetIRAddressingError(
                        f"function {name!r}: field_address lacks source-stable identity"
                    )


__all__ = ["TargetIRAddressingError", "validate_target_ir_addressing"]
