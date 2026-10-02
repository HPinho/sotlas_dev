"""Backend-neutral ownership facts for aggregates (M16.4h1a / h1d / h2a).

This layer consumes the checked Typed AST instead of re-deriving ownership from
source syntax. h1 records direct by-value struct fields whose type is a canonical
exclusive ``sole`` declaration and projects only materialized struct facts into
Target IR. h2a adds the same backend-neutral ownership identity for direct enum
payloads, but deliberately keeps those enum payload facts SIR-only until enum
representation and tagged-union layout are extended in later h2 recuts.

The sidecars remain semantic: they carry no byte offsets, sizes, alignments, ABI
classes, register classes, cleanup actions, or moves.
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


@dataclass(frozen=True)
class EnumPayloadOwnershipFact:
    """One direct by-value ownership-bearing enum payload."""

    enum_name: str
    variant: str
    payload_type: str
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


def collect_enum_payload_ownership_facts(
    typed_module: Any,
) -> tuple[EnumPayloadOwnershipFact, ...]:
    """Collect direct exclusive enum payload owners from checked Typed AST.

    h2a records semantic ownership only. It does not make nominal payload enums
    executable and does not alter the scalar-only M16.4e3 enum representation.
    """
    if typed_module is None:
        raise AggregateOwnershipError(
            "aggregate ownership collection requires a checked TypedModule"
        )

    facts: list[EnumPayloadOwnershipFact] = []
    seen: set[tuple[str, str]] = set()
    for enum in tuple(getattr(typed_module, "enums", ()) or ()):
        enum_name = getattr(enum, "name", None)
        if not isinstance(enum_name, str) or not enum_name:
            raise AggregateOwnershipError(
                "checked aggregate ownership contains an unnamed enum"
            )
        variants = tuple(getattr(enum, "variants", ()) or ())
        if not variants:
            raise AggregateOwnershipError(
                f"enum {enum_name!r} has no checked variants"
            )
        for variant in variants:
            variant_name = getattr(variant, "name", None)
            if not isinstance(variant_name, str) or not variant_name:
                raise AggregateOwnershipError(
                    f"enum {enum_name!r} has a malformed checked variant"
                )
            key = (enum_name, variant_name)
            if key in seen:
                raise AggregateOwnershipError(
                    f"enum {enum_name!r} repeats variant {variant_name!r}"
                )
            seen.add(key)

            type_info = getattr(variant, "payload_type", None)
            if type_info is None or not _is_direct_value(type_info):
                continue
            type_name = getattr(type_info, "name", None)
            if not isinstance(type_name, str) or not type_name:
                raise AggregateOwnershipError(
                    f"enum {enum_name!r} variant {variant_name!r} has malformed payload type"
                )
            if not is_sole_type(type_info, typed_module):
                continue
            domain = ownership_domain(type_info, typed_module)
            if domain is not OwnershipDomain.EXCLUSIVE:
                continue
            facts.append(
                EnumPayloadOwnershipFact(
                    enum_name=enum_name,
                    variant=variant_name,
                    payload_type=type_name,
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


def attach_checked_enum_payload_ownership(
    semantic: Any,
    sir_module: Any,
) -> tuple[EnumPayloadOwnershipFact, ...]:
    """Attach h2a enum payload facts alongside any previously attached h1 facts."""
    typed_module = getattr(semantic, "typed_module", None)
    enum_facts = collect_enum_payload_ownership_facts(typed_module)
    existing = tuple(getattr(sir_module, "aggregate_ownership_facts", ()) or ())
    if any(isinstance(fact, EnumPayloadOwnershipFact) for fact in existing):
        existing_enum = tuple(
            fact for fact in existing if isinstance(fact, EnumPayloadOwnershipFact)
        )
        if existing_enum != enum_facts:
            raise AggregateOwnershipError(
                "canonical SIR already contains conflicting enum payload ownership facts"
            )
        return enum_facts

    sir_module.aggregate_ownership_facts = existing + enum_facts
    return enum_facts


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
    """Preserve materialized h1 struct ownership facts in Target IR.

    h2a enum payload facts remain SIR-only until nominal payload enum
    representation is certified. Encountering one here is therefore an explicit
    fail-closed boundary rather than a silent Target IR projection.
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
        if isinstance(fact, EnumPayloadOwnershipFact):
            if (
                not isinstance(fact.enum_name, str)
                or not fact.enum_name
                or not isinstance(fact.variant, str)
                or not fact.variant
                or not isinstance(fact.payload_type, str)
                or not fact.payload_type
                or fact.domain != OwnershipDomain.EXCLUSIVE.value
                or fact.storage != "by_value"
            ):
                raise AggregateOwnershipError(
                    "canonical SIR contains unsupported enum payload ownership facts"
                )
            raise AggregateOwnershipError(
                "owned enum payload Target IR projection waits for M16.4h2b"
            )

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
    "EnumPayloadOwnershipFact",
    "StructFieldOwnershipFact",
    "attach_checked_enum_payload_ownership",
    "attach_checked_struct_field_ownership",
    "attach_target_ir_aggregate_ownership",
    "collect_enum_payload_ownership_facts",
    "collect_struct_field_ownership_facts",
]
