"""Backend-neutral struct declaration facts for M16.4c.

This module preserves source field order and canonical field types without
assigning byte offsets. Target-specific layout is deliberately deferred to the
machine ABI layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_SCALAR_FIELD_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})


class StructLayoutError(ValueError):
    """Raised when a source/SIR/Target-IR struct layout fact is malformed."""


@dataclass(frozen=True)
class StructFieldDecl:
    name: str
    type_name: str


@dataclass(frozen=True)
class StructLayoutDecl:
    name: str
    fields: tuple[StructFieldDecl, ...]


def make_struct_layout_decl(
    struct: Any,
    type_name: Callable[[Any], str],
) -> StructLayoutDecl:
    """Build the narrow scalar M16.4c declaration fact from checked source."""
    name = getattr(struct, "name", None)
    if not isinstance(name, str) or not name:
        raise StructLayoutError("struct layout requires a named source struct")

    fields: list[StructFieldDecl] = []
    seen: set[str] = set()
    for field in tuple(getattr(struct, "fields", ()) or ()):
        field_name = getattr(field, "name", None)
        if not isinstance(field_name, str) or not field_name or field_name in seen:
            raise StructLayoutError(
                f"struct {name!r} has an invalid or duplicate field name"
            )
        if getattr(field, "bit_width", None) is not None:
            raise StructLayoutError(
                f"struct {name!r} bit-fields are outside M16.4c"
            )
        rendered = type_name(getattr(field, "type", None))
        if rendered not in _SCALAR_FIELD_TYPES:
            raise StructLayoutError(
                f"struct {name!r} field {field_name!r} type {rendered!r} "
                "is outside the M16.4c scalar layout slice"
            )
        seen.add(field_name)
        fields.append(StructFieldDecl(field_name, rendered))

    if not fields:
        raise StructLayoutError(f"struct {name!r} has no fields to lay out")
    return StructLayoutDecl(name=name, fields=tuple(fields))


def attach_sir_struct_layout(sir_module: Any, layout: StructLayoutDecl) -> None:
    """Attach one canonical declaration fact, rejecting contradictory repeats."""
    existing = tuple(getattr(sir_module, "struct_layouts", ()) or ())
    by_name = {item.name: item for item in existing}
    previous = by_name.get(layout.name)
    if previous is not None:
        if previous != layout:
            raise StructLayoutError(
                f"canonical SIR has conflicting layout facts for {layout.name!r}"
            )
        return
    sir_module.struct_layouts = existing + (layout,)


def attach_target_ir_struct_layouts(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Copy SIR-proven declarations into Target IR without assigning offsets."""
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise StructLayoutError("struct layout bridge requires Target IR v1")

    layouts = tuple(getattr(sir_module, "struct_layouts", ()) or ())
    if not layouts:
        return target_ir

    normalized = []
    seen: set[str] = set()
    for layout in sorted(layouts, key=lambda item: item.name):
        if not isinstance(layout, StructLayoutDecl):
            raise StructLayoutError("canonical SIR contains malformed struct layout")
        if layout.name in seen:
            raise StructLayoutError(
                f"canonical SIR repeats struct layout {layout.name!r}"
            )
        seen.add(layout.name)
        normalized.append({
            "name": layout.name,
            "fields": [
                {"name": field.name, "type": field.type_name}
                for field in layout.fields
            ],
        })

    existing = target_ir.get("struct_layouts")
    if existing not in (None, [], normalized):
        raise StructLayoutError("Target IR already contains conflicting struct layouts")
    target_ir["struct_layouts"] = normalized
    return target_ir


__all__ = [
    "StructFieldDecl",
    "StructLayoutDecl",
    "StructLayoutError",
    "attach_sir_struct_layout",
    "attach_target_ir_struct_layouts",
    "make_struct_layout_decl",
]
