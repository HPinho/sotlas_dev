"""x86-64 SysV scalar/nominal struct layout for the M16.4c / M16.4h1c3 slice."""
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
    """Derive source-order natural scalar/nominal field offsets for x86-64 SysV.

    M16.4h1c3 recursively derives size/alignment for direct by-value nominal
    struct fields only when the complete declaration closure is present. Target
    IR still carries no physical bytes. This function deliberately does not
    flatten nested declarations or decide function argument/return transport;
    it computes memory layout for already-certified aggregate declarations.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise _core.MachineBackendError(
            "x86-64 struct layout requires Target IR v1"
        )

    declarations: dict[str, list[dict[str, Any]]] = {}
    for layout in target_ir.get("struct_layouts", ()):
        name = layout.get("name") if isinstance(layout, dict) else None
        fields = layout.get("fields") if isinstance(layout, dict) else None
        if not isinstance(name, str) or not name or name in declarations:
            raise _core.MachineBackendError(
                "x86-64 struct layout contains an invalid or duplicate struct name"
            )
        if not isinstance(fields, list) or not fields:
            raise _core.MachineBackendError(
                f"struct {name!r}: x86-64 layout requires declared fields"
            )
        declarations[name] = fields

    planned: dict[str, dict[str, Any]] = {}
    visiting: set[str] = set()

    def plan(name: str) -> dict[str, Any]:
        existing = planned.get(name)
        if existing is not None:
            return existing
        if name in visiting:
            raise _core.MachineBackendError(
                f"x86-64 nominal struct layout contains a by-value cycle at {name!r}"
            )
        fields = declarations.get(name)
        if fields is None:
            raise _core.MachineBackendError(
                f"x86-64 nominal struct layout references undeclared struct {name!r}"
            )

        visiting.add(name)
        cursor = 0
        max_alignment = 1
        field_plan: dict[str, dict[str, Any]] = {}
        ordered_fields = []
        for field in fields:
            field_name = field.get("name") if isinstance(field, dict) else None
            type_name = field.get("type") if isinstance(field, dict) else None
            representation = (
                field.get("representation", "scalar")
                if isinstance(field, dict)
                else None
            )
            if (
                not isinstance(field_name, str)
                or not field_name
                or field_name in field_plan
                or not isinstance(type_name, str)
                or not type_name
            ):
                raise _core.MachineBackendError(
                    f"struct {name!r}: field layout is outside the M16.4h1c3 scalar/nominal slice"
                )

            if representation == "scalar":
                scalar_layout = _SCALAR_LAYOUT.get(type_name)
                if scalar_layout is None:
                    raise _core.MachineBackendError(
                        f"struct {name!r}: field layout is outside the M16.4h1c3 scalar/nominal slice"
                    )
                size, alignment = scalar_layout
            elif representation == "nominal_struct":
                if type_name in _SCALAR_LAYOUT or type_name == name:
                    raise _core.MachineBackendError(
                        f"struct {name!r}: invalid nominal field {field_name!r}"
                    )
                nested = plan(type_name)
                size = nested["size_bytes"]
                alignment = nested["alignment_bytes"]
            else:
                raise _core.MachineBackendError(
                    f"struct {name!r}: unsupported field representation {representation!r}"
                )

            cursor = _align(cursor, alignment)
            item = {
                "name": field_name,
                "type": type_name,
                "offset_bytes": cursor,
                "size_bytes": size,
                "alignment_bytes": alignment,
            }
            if representation == "nominal_struct":
                item["representation"] = "nominal_struct"
            field_plan[field_name] = item
            ordered_fields.append(item)
            cursor += size
            max_alignment = max(max_alignment, alignment)

        size_bytes = _align(cursor, max_alignment)
        result = {
            "name": name,
            "size_bytes": size_bytes,
            "alignment_bytes": max_alignment,
            "fields": field_plan,
            "ordered_fields": ordered_fields,
        }
        visiting.remove(name)
        planned[name] = result
        return result

    for name in declarations:
        plan(name)
    return planned


__all__ = ["plan_x86_64_sysv_struct_layouts"]
