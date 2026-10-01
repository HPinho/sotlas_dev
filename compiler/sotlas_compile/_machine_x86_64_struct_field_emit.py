"""Machine emission for validated x86-64 struct field address projection."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError
from ._machine_x86_64_types import pointer_pointee


def emit_struct_field_address(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    value_types: dict[str, str],
    struct_layouts: dict[str, dict[str, Any]],
) -> None:
    name = function["name"]
    operands = instruction.get("operands", ())
    if len(operands) != 1:
        raise MachineBackendError(
            f"function {name!r}: field_address requires one struct pointer"
        )
    base = operands[0]
    attributes = instruction.get("attributes", {})
    struct_name = attributes.get("struct")
    field_name = attributes.get("field")
    field_type = attributes.get("field_type")
    if value_types.get(base) != f"{struct_name}*":
        raise MachineBackendError(
            f"function {name!r}: field_address base type does not match {struct_name!r}"
        )
    result_type = instruction.get("type")
    if pointer_pointee(result_type) != field_type:
        raise MachineBackendError(
            f"function {name!r}: field_address result type does not match field"
        )
    struct_plan = struct_layouts.get(struct_name)
    field_plan = (
        struct_plan.get("fields", {}).get(field_name)
        if struct_plan is not None else None
    )
    if field_plan is None or field_plan.get("type") != field_type:
        raise MachineBackendError(
            f"function {name!r}: field_address lacks a matching x86-64 layout field"
        )

    _core._load_value(lines, base, "rcx", locations)
    offset = field_plan["offset_bytes"]
    if offset:
        lines.append(f"    lea rax, [rcx+{offset}]")
    else:
        lines.append("    lea rax, [rcx]")
    _core._store_value(
        lines, instruction.get("result"), "rax", locations
    )


__all__ = ["emit_struct_field_address"]
