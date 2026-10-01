"""x86-64 SysV scalar struct layout for the M16.4c native backend slice."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core


_SCALAR_LAYOUT = {
    "u8": (1, 1),
    "u16": (2, 2),
    "u32": (4, 4),
    "u64": (8, 8),
    "usize": (8, 8),
}


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def plan_x86_64_sysv_struct_layouts(
    target_ir: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Derive source-order natural scalar field offsets for x86-64 SysV.

    This deliberately does not classify aggregates for argument/return ABI use.
    It only computes memory layout for field projection through an existing
    pointer to a source struct.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise _core.MachineBackendError(
            "x86-64 struct layout requires Target IR v1"
        )

    planned: dict[str, dict[str, Any]] = {}
    for layout in target_ir.get("struct_layouts", ()):
        name = layout.get("name") if isinstance(layout, dict) else None
        fields = layout.get("fields") if isinstance(layout, dict) else None
        if not isinstance(name, str) or not name or name in planned:
            raise _core.MachineBackendError(
                "x86-64 struct layout contains an invalid or duplicate struct name"
            )
        if not isinstance(fields, list) or not fields:
            raise _core.MachineBackendError(
                f"struct {name!r}: x86-64 layout requires declared fields"
            )

        cursor = 0
        max_alignment = 1
        field_plan: dict[str, dict[str, Any]] = {}
        ordered_fields = []
        for field in fields:
            field_name = field.get("name") if isinstance(field, dict) else None
            type_name = field.get("type") if isinstance(field, dict) else None
            if (
                not isinstance(field_name, str) or not field_name
                or field_name in field_plan
                or type_name not in _SCALAR_LAYOUT
            ):
                raise _core.MachineBackendError(
                    f"struct {name!r}: field layout is outside the M16.4c scalar slice"
                )
            size, alignment = _SCALAR_LAYOUT[type_name]
            cursor = _align(cursor, alignment)
            item = {
                "name": field_name,
                "type": type_name,
                "offset_bytes": cursor,
                "size_bytes": size,
                "alignment_bytes": alignment,
            }
            field_plan[field_name] = item
            ordered_fields.append(item)
            cursor += size
            max_alignment = max(max_alignment, alignment)

        size_bytes = _align(cursor, max_alignment)
        planned[name] = {
            "name": name,
            "size_bytes": size_bytes,
            "alignment_bytes": max_alignment,
            "fields": field_plan,
            "ordered_fields": ordered_fields,
        }
    return planned


__all__ = ["plan_x86_64_sysv_struct_layouts"]
