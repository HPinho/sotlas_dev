"""Backend-neutral ownership facts for aggregate fields (M16.4h1a).

This layer consumes the checked Typed AST instead of re-deriving ownership from
source syntax. The initial slice records only direct by-value fields whose type
is a canonical exclusive ``sole`` declaration. Arrays, references, pointers,
shared aliases, domain handovers, enum payloads and runtime cleanup stay outside
this recut and therefore cannot be accidentally promoted by metadata alone.
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


__all__ = [
    "AggregateOwnershipError",
    "StructFieldOwnershipFact",
    "attach_checked_struct_field_ownership",
    "collect_struct_field_ownership_facts",
]
