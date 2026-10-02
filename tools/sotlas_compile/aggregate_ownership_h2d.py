"""M16.4h2d1 explicit Target IR ownership projection for nominal enum payloads."""
from __future__ import annotations

from typing import Any

from .aggregate_ownership import AggregateOwnershipError, EnumPayloadOwnershipFact
from .aggregate_ownership_h2c2b import (
    attach_target_ir_aggregate_ownership_with_nominal_enums,
)


def _enum_ownership_projection(
    sir_module: Any,
) -> list[dict[str, str]]:
    facts = tuple(getattr(sir_module, "aggregate_ownership_facts", ()) or ())
    projected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for fact in facts:
        if not isinstance(fact, EnumPayloadOwnershipFact):
            continue
        key = (fact.enum_name, fact.variant)
        if key in seen:
            raise AggregateOwnershipError(
                "canonical SIR contains duplicate enum payload ownership facts"
            )
        seen.add(key)
        projected.append({
            "kind": "enum_payload",
            "enum": fact.enum_name,
            "variant": fact.variant,
            "payload_type": fact.payload_type,
            "domain": fact.domain,
            "storage": fact.storage,
        })

    projected.sort(key=lambda item: (item["enum"], item["variant"]))
    return projected


def attach_target_ir_enum_payload_ownership(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Project h2 enum ownership only after h2c2b nominal identity validation.

    The h2c2b bridge remains the source of truth for:
    - validating each enum ownership fact against ``nominal_enum_payloads``;
    - preserving h1 struct ownership facts.

    h2d1 adds only semantic ``enum_payload`` entries. It does not add byte
    layout, ABI, cleanup, move, drop, or machine-execution claims.
    """
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise AggregateOwnershipError(
            "enum payload ownership bridge requires Target IR v1"
        )

    # Recompute the h1/h2c2b semantic baseline on a scratch mapping so a
    # pre-existing h2d result can be validated idempotently.
    scratch = dict(target_ir)
    scratch.pop("aggregate_ownership_facts", None)
    attach_target_ir_aggregate_ownership_with_nominal_enums(scratch, sir_module)

    struct_projection = list(
        tuple(scratch.get("aggregate_ownership_facts", ()) or ())
    )
    enum_projection = _enum_ownership_projection(sir_module)
    combined = struct_projection + enum_projection

    existing = target_ir.get("aggregate_ownership_facts")
    if existing not in (None, [], combined):
        raise AggregateOwnershipError(
            "Target IR already contains conflicting aggregate ownership facts"
        )

    if combined:
        target_ir["aggregate_ownership_facts"] = combined
    else:
        target_ir.pop("aggregate_ownership_facts", None)
    return target_ir


__all__ = ["attach_target_ir_enum_payload_ownership"]
