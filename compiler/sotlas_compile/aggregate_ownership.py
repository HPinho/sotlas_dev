"""Backend-neutral ownership facts for aggregate fields (M16.4h1a / h1d).

This layer consumes the checked Typed AST instead of re-deriving ownership from
source syntax. The initial slice records only direct by-value fields whose type
is a canonical exclusive ``sole`` declaration. Arrays, references, pointers,
shared aliases, domain handovers, enum payloads and runtime cleanup stay outside
this recut and therefore cannot be accidentally promoted by metadata alone.

M16.4h1d projects only ownership facts for struct declarations that actually
reached Target IR. The sidecar remains semantic: it carries no byte offsets,
sizes, alignments, ABI classes, register classes, cleanup actions, or moves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .typed_ast import OwnershipDomain, is_sole_type, ownership_domain


class AggregateOwnershipError(ValueError):
    """Raised when checked aggregate ownership facts are contradictory."""


@dataclass(frozen=True)
class StructFieldOwnershipFact:
    """One direct by-value ownership-bearing struct member."""

    struct_name: str
    field_name: str
    field_type: str
    domain: str
    storage: str = "by_value"


def _is_direct_value(type_info: Any) -> bool:
    return not any(
        bool(getattr(type_info, attribute, False))
        for attribute in ("pointer", "is_reference", "is_array")
    )


def collect_struct_field_ownership_facts(
    typed_module: Any,
) -> tuple[StructFieldOwnershipFact, ...]:
    """Collect canonical exclusive field owners from one checked TypedModule."""
    if typed_module is None:
        raise AggregateOwnershipError(
            "aggregate ownership collection requires a checked TypedModule"
        )

    facts: list[StructFieldOwnershipFact] = []
    seen: set[tuple[str, str]] = set()
    for struct in tuple(getattr(typed_module, "structs", ()) or ()):
        struct_name = getattr(struct, "name", None)
        if not isinstance(struct_name, str) or not struct_name:
            raise AggregateOwnershipError(
                "checked aggregate ownership contains an unnamed struct"
            )
        for field in tuple(getattr(struct, "fields", ()) or ()):
            field_name = getattr(field, "name", None)
            type_info = getattr(field, "type", None)
            type_name = getattr(type_info, "name", None)
            if (
                not isinstance(field_name, str)
                or not field_name
                or not isinstance(type_name, str)
                or not type_name
            ):
                raise AggregateOwnershipError(
                    f"struct {struct_name!r} has malformed checked field facts"
                )
            key = (struct_name, field_name)
            if key in seen:
                raise AggregateOwnershipError(
                    f"struct {struct_name!r} repeats field {field_name!r}"
                )
            seen.add(key)

            if not _is_direct_value(type_info):
                continue
            if not is_sole_type(type_info, typed_module):
                continue
            domain = ownership_domain(type_info, typed_module)
            if domain is not OwnershipDomain.EXCLUSIVE:
                continue
            facts.append(
                StructFieldOwnershipFact(
                    struct_name=struct_name,
                    field_name=field_name,
                    field_type=type_name,
                    domain=domain.value,
                )
            )

    return tuple(facts)


def attach_checked_struct_field_ownership(
    semantic: Any,
    sir_module: Any,
) -> tuple[StructFieldOwnershipFact, ...]:
    """Attach checked h1a ownership facts to SIR without changing move placement."""
    typed_module = getattr(semantic, "typed_module", None)
    facts = collect_struct_field_ownership_facts(typed_module)
    existing = tuple(getattr(sir_module, "aggregate_ownership_facts", ()) or ())
    if existing and existing != facts:
        raise AggregateOwnershipError(
            "canonical SIR already contains conflicting aggregate ownership facts"
        )
    sir_module.aggregate_ownership_facts = facts
    return facts


def _target_ir_struct_layouts(
    target_ir: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    layouts: dict[str, dict[str, dict[str, Any]]] = {}
    for layout in target_ir.get("struct_layouts", ()) or ():
        name = layout.get("name") if isinstance(layout, dict) else None
        fields = layout.get("fields") if isinstance(layout, dict) else None
        if not isinstance(name, str) or not name or name in layouts:
            raise AggregateOwnershipError(
                "Target IR aggregate ownership found an invalid or duplicate struct layout"
            )
        if not isinstance(fields, list) or not fields:
            raise AggregateOwnershipError(
                f"struct {name!r}: aggregate ownership requires declared fields"
            )
        field_map: dict[str, dict[str, Any]] = {}
        for field in fields:
            field_name = field.get("name") if isinstance(field, dict) else None
            if (
                not isinstance(field_name, str)
                or not field_name
                or field_name in field_map
            ):
                raise AggregateOwnershipError(
                    f"struct {name!r}: aggregate ownership found a malformed field declaration"
                )
            field_map[field_name] = field
        layouts[name] = field_map
    return layouts


def attach_target_ir_aggregate_ownership(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Preserve materialized SIR ownership-bearing struct members in Target IR.

    SIR ownership facts are module-wide, whereas ``struct_layouts`` is
    intentionally usage-driven. h1d therefore exports only facts whose owning
    struct declaration reached Target IR. Every exported fact must match a
    direct nominal by-value field and its nominal dependency must also be
    declared. No runtime cleanup or physical layout claim is inferred here.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise AggregateOwnershipError(
            "aggregate ownership bridge requires Target IR v1"
        )

    facts = tuple(getattr(sir_module, "aggregate_ownership_facts", ()) or ())
    layouts = _target_ir_struct_layouts(target_ir)
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for fact in facts:
        if not isinstance(fact, StructFieldOwnershipFact):
            raise AggregateOwnershipError(
                "canonical SIR contains malformed aggregate ownership facts"
            )
        key = (fact.struct_name, fact.field_name)
        if key in seen:
            raise AggregateOwnershipError(
                "canonical SIR contains duplicate aggregate ownership facts"
            )
        seen.add(key)
        if (
            not isinstance(fact.struct_name, str)
            or not fact.struct_name
            or not isinstance(fact.field_name, str)
            or not fact.field_name
            or not isinstance(fact.field_type, str)
            or not fact.field_type
            or fact.domain != OwnershipDomain.EXCLUSIVE.value
            or fact.storage != "by_value"
        ):
            raise AggregateOwnershipError(
                "canonical SIR contains unsupported aggregate ownership facts"
            )

        fields = layouts.get(fact.struct_name)
        if fields is None:
            continue

        field = fields.get(fact.field_name)
        if (
            field is None
            or field.get("type") != fact.field_type
            or field.get("representation") != "nominal_struct"
        ):
            raise AggregateOwnershipError(
                f"struct {fact.struct_name!r} field {fact.field_name!r}: "
                "ownership fact does not match a nominal Target IR field"
            )
        if fact.field_type not in layouts:
            raise AggregateOwnershipError(
                f"struct {fact.struct_name!r} field {fact.field_name!r}: "
                f"ownership type {fact.field_type!r} is not declared in Target IR"
            )

        normalized.append({
            "kind": "struct_field",
            "struct": fact.struct_name,
            "field": fact.field_name,
            "field_type": fact.field_type,
            "domain": fact.domain,
            "storage": fact.storage,
        })

    normalized.sort(key=lambda item: (item["struct"], item["field"]))
    existing = target_ir.get("aggregate_ownership_facts")
    if existing not in (None, [], normalized):
        raise AggregateOwnershipError(
            "Target IR already contains conflicting aggregate ownership facts"
        )
    if normalized:
        target_ir["aggregate_ownership_facts"] = normalized
    return target_ir


__all__ = [
    "AggregateOwnershipError",
    "StructFieldOwnershipFact",
    "attach_checked_struct_field_ownership",
    "attach_target_ir_aggregate_ownership",
    "collect_struct_field_ownership_facts",
]
