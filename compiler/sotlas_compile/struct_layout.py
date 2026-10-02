"""Backend-neutral struct declaration facts for M16.4c / M16.4h1c.

This module preserves source field order and canonical field types without
assigning byte offsets. M16.4h1c1 extends the declaration contract with direct
by-value nominal struct fields. M16.4h1c2 adds a narrowly scoped source-generation
context plus dependency closure so canonical SIR can preserve every nominal
struct declaration required by an actually lowered root layout.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Mapping


_SCALAR_FIELD_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})
_FIELD_REPRESENTATIONS = frozenset({"scalar", "nominal_struct"})
_ACTIVE_NOMINAL_STRUCT_NAMES: ContextVar[frozenset[str] | None] = ContextVar(
    "sotlas_active_nominal_struct_names",
    default=None,
)


class StructLayoutError(ValueError):
    """Raised when a source/SIR/Target-IR struct layout fact is malformed."""


@dataclass(frozen=True)
class StructFieldDecl:
    name: str
    type_name: str
    representation: str = "scalar"


@dataclass(frozen=True)
class StructLayoutDecl:
    name: str
    fields: tuple[StructFieldDecl, ...]


def _direct_by_value(type_info: Any) -> bool:
    return not any(
        bool(getattr(type_info, attribute, False))
        for attribute in ("pointer", "is_reference", "is_array")
    )


def _normalize_nominal_struct_names(names: Iterable[str]) -> frozenset[str]:
    normalized = frozenset(names)
    if any(not isinstance(name, str) or not name for name in normalized):
        raise StructLayoutError(
            "nominal struct layout names must be non-empty strings"
        )
    return normalized


@contextmanager
def nominal_struct_layout_scope(
    names: Iterable[str],
) -> Iterator[frozenset[str]]:
    """Temporarily expose checked source struct names to legacy layout callers.

    The original M16.4c source generator calls ``make_struct_layout_decl``
    without a nominal-name parameter. h1c2 keeps that generator intact and
    scopes the extra knowledge to one ``generate_from_ast`` call. ContextVar
    prevents state leaking between nested or concurrent compiler invocations.
    """
    normalized = _normalize_nominal_struct_names(names)
    token = _ACTIVE_NOMINAL_STRUCT_NAMES.set(normalized)
    try:
        yield normalized
    finally:
        _ACTIVE_NOMINAL_STRUCT_NAMES.reset(token)


def _effective_nominal_struct_names(
    names: Iterable[str] | None,
) -> frozenset[str]:
    if names is not None:
        return _normalize_nominal_struct_names(names)
    active = _ACTIVE_NOMINAL_STRUCT_NAMES.get()
    return active if active is not None else frozenset()


def make_struct_layout_decl(
    struct: Any,
    type_name: Callable[[Any], str],
    *,
    nominal_struct_names: Iterable[str] | None = None,
) -> StructLayoutDecl:
    """Build a backend-neutral scalar/nominal declaration from checked source.

    Scalar fields preserve the original M16.4c contract. A direct by-value field
    may additionally name another source struct only when that name is supplied
    explicitly or by the scoped h1c2 source-generation context. This records
    nominal identity only; no nested size, alignment, offset, flattening, or ABI
    class is inferred here.
    """
    name = getattr(struct, "name", None)
    if not isinstance(name, str) or not name:
        raise StructLayoutError("struct layout requires a named source struct")

    nominal_names = _effective_nominal_struct_names(nominal_struct_names)
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
                f"struct {name!r} bit-fields are outside M16.4h1c"
            )

        source_type = getattr(field, "type", None)
        rendered = type_name(source_type)
        representation = "scalar"
        if rendered not in _SCALAR_FIELD_TYPES:
            if (
                not isinstance(rendered, str)
                or not rendered
                or rendered not in nominal_names
                or not _direct_by_value(source_type)
            ):
                raise StructLayoutError(
                    f"struct {name!r} field {field_name!r} type {rendered!r} "
                    "is outside the M16.4h1c scalar/nominal declaration contract"
                )
            if rendered == name:
                raise StructLayoutError(
                    f"struct {name!r} cannot contain itself directly by value"
                )
            representation = "nominal_struct"

        seen.add(field_name)
        fields.append(
            StructFieldDecl(
                field_name,
                rendered,
                representation=representation,
            )
        )

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


def complete_sir_struct_layout_closure(
    sir_module: Any,
    struct_definitions: Mapping[str, Any],
    type_name: Callable[[Any], str],
) -> tuple[StructLayoutDecl, ...]:
    """Close already-used SIR layouts over direct nominal struct dependencies.

    Only declarations reachable from layouts that an existing source lowering
    actually attached are added. Unused source structs therefore do not pollute
    canonical SIR. Dependencies are validated from source definitions, cycles
    fail closed, and physical layout remains entirely deferred.
    """
    roots = tuple(getattr(sir_module, "struct_layouts", ()) or ())
    if not roots:
        return ()

    definitions = dict(struct_definitions)
    if any(
        not isinstance(name, str)
        or not name
        or getattr(struct, "name", None) != name
        for name, struct in definitions.items()
    ):
        raise StructLayoutError(
            "nominal struct closure requires canonical named source definitions"
        )
    nominal_names = _normalize_nominal_struct_names(definitions)
    visiting: set[str] = set()
    visited: set[str] = set()
    completed: list[StructLayoutDecl] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise StructLayoutError(
                f"canonical SIR nominal struct closure contains a by-value cycle at {name!r}"
            )
        source = definitions.get(name)
        if source is None:
            raise StructLayoutError(
                f"canonical SIR layout {name!r} has no matching source struct definition"
            )

        visiting.add(name)
        layout = make_struct_layout_decl(
            source,
            type_name,
            nominal_struct_names=nominal_names,
        )
        for field in layout.fields:
            if field.representation == "nominal_struct":
                visit(field.type_name)
        visiting.remove(name)
        visited.add(name)
        attach_sir_struct_layout(sir_module, layout)
        completed.append(layout)

    for root in roots:
        name = getattr(root, "name", None)
        if not isinstance(name, str) or not name:
            raise StructLayoutError(
                "canonical SIR contains an invalid root struct layout"
            )
        visit(name)

    return tuple(completed)


def _validated_layout_map(
    layouts: tuple[StructLayoutDecl, ...],
) -> dict[str, StructLayoutDecl]:
    by_name: dict[str, StructLayoutDecl] = {}
    for layout in layouts:
        if not isinstance(layout, StructLayoutDecl):
            raise StructLayoutError("canonical SIR contains malformed struct layout")
        if not isinstance(layout.name, str) or not layout.name or layout.name in by_name:
            raise StructLayoutError(
                "canonical SIR contains an invalid or duplicate struct layout name"
            )
        if not layout.fields:
            raise StructLayoutError(
                f"canonical SIR struct {layout.name!r} has no declared fields"
            )
        by_name[layout.name] = layout

    graph: dict[str, tuple[str, ...]] = {}
    for name, layout in by_name.items():
        field_names: set[str] = set()
        dependencies: list[str] = []
        for field in layout.fields:
            if (
                not isinstance(field, StructFieldDecl)
                or not isinstance(field.name, str)
                or not field.name
                or field.name in field_names
                or not isinstance(field.type_name, str)
                or not field.type_name
                or field.representation not in _FIELD_REPRESENTATIONS
            ):
                raise StructLayoutError(
                    f"canonical SIR struct {name!r} contains a malformed field"
                )
            field_names.add(field.name)
            if field.representation == "scalar":
                if field.type_name not in _SCALAR_FIELD_TYPES:
                    raise StructLayoutError(
                        f"canonical SIR struct {name!r} marks non-scalar field "
                        f"{field.name!r} as scalar"
                    )
                continue
            if field.type_name in _SCALAR_FIELD_TYPES:
                raise StructLayoutError(
                    f"canonical SIR struct {name!r} marks scalar field "
                    f"{field.name!r} as nominal"
                )
            if field.type_name not in by_name:
                raise StructLayoutError(
                    f"canonical SIR struct {name!r} field {field.name!r} "
                    f"references undeclared nominal struct {field.type_name!r}"
                )
            dependencies.append(field.type_name)
        graph[name] = tuple(dependencies)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise StructLayoutError(
                f"canonical SIR nominal struct declarations contain a by-value cycle at {name!r}"
            )
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(graph):
        visit(name)
    return by_name


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

    by_name = _validated_layout_map(layouts)
    normalized = []
    for name in sorted(by_name):
        layout = by_name[name]
        fields = []
        for field in layout.fields:
            item = {"name": field.name, "type": field.type_name}
            if field.representation == "nominal_struct":
                item["representation"] = "nominal_struct"
            fields.append(item)
        normalized.append({
            "name": layout.name,
            "fields": fields,
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
    "complete_sir_struct_layout_closure",
    "make_struct_layout_decl",
    "nominal_struct_layout_scope",
]
