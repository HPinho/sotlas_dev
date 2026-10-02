"""h2c2b bridge: validate nominal enum ownership without projecting it yet."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .aggregate_ownership import (
    AggregateOwnershipError,
    EnumPayloadOwnershipFact,
    attach_target_ir_aggregate_ownership,
)
from .typed_ast import OwnershipDomain


def _nominal_payload_variant(
    target_ir: dict[str, Any],
    enum_name: str,
    variant_name: str,
) -> dict[str, Any] | None:
    declarations = target_ir.get("nominal_enum_payloads", {})
    if not isinstance(declarations, dict):
        raise AggregateOwnershipError(
            "Target IR nominal enum payload ownership requires a declaration mapping"
        )
    declaration = declarations.get(enum_name)
    if declaration is None:
        return None
    if not isinstance(declaration, dict):
        raise AggregateOwnershipError(
            f"enum {enum_name!r}: nominal payload declaration is malformed"
        )
    if declaration.get("tag_type") != "u32" or declaration.get("storage") != "tagged_union":
        raise AggregateOwnershipError(
            f"enum {enum_name!r}: ownership requires canonical nominal tagged_union storage"
        )
    variants = declaration.get("variants")
    if not isinstance(variants, list) or not variants:
        raise AggregateOwnershipError(
            f"enum {enum_name!r}: ownership requires nominal payload variants"
        )
    matches = [
        item
        for item in variants
        if isinstance(item, dict) and item.get("name") == variant_name
    ]
    if len(matches) > 1:
        raise AggregateOwnershipError(
            f"enum {enum_name!r}: nominal payload declaration repeats variant {variant_name!r}"
        )
    return matches[0] if matches else None


def _validate_enum_fact(target_ir: dict[str, Any], fact: EnumPayloadOwnershipFact) -> None:
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

    variant = _nominal_payload_variant(target_ir, fact.enum_name, fact.variant)
    if (
        variant is None
        or variant.get("payload_type") != fact.payload_type
        or variant.get("payload_representation") != "nominal_struct"
    ):
        raise AggregateOwnershipError(
            f"enum {fact.enum_name!r} variant {fact.variant!r}: "
            "ownership fact does not match a nominal Target IR payload"
        )


def attach_target_ir_aggregate_ownership_with_nominal_enums(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Preserve h1 struct ownership and validate h2 enum ownership for h2d.

    h2c2b makes nominal enum payload identity visible in full Target IR, but
    enum ownership itself remains SIR-authoritative until h2d.  Every enum
    ownership fact must therefore match the logical nominal sidecar exactly,
    then it is intentionally omitted from ``aggregate_ownership_facts``.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise AggregateOwnershipError(
            "aggregate ownership bridge requires Target IR v1"
        )

    facts = tuple(getattr(sir_module, "aggregate_ownership_facts", ()) or ())
    enum_seen: set[tuple[str, str]] = set()
    struct_facts = []
    for fact in facts:
        if not isinstance(fact, EnumPayloadOwnershipFact):
            struct_facts.append(fact)
            continue
        key = (fact.enum_name, fact.variant)
        if key in enum_seen:
            raise AggregateOwnershipError(
                "canonical SIR contains duplicate enum payload ownership facts"
            )
        enum_seen.add(key)
        _validate_enum_fact(target_ir, fact)

    proxy = SimpleNamespace(aggregate_ownership_facts=tuple(struct_facts))
    return attach_target_ir_aggregate_ownership(target_ir, proxy)


__all__ = ["attach_target_ir_aggregate_ownership_with_nominal_enums"]
