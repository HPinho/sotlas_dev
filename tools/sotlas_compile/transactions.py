"""Static transactional-effect audits for canonical Flow plans in SIR."""
from __future__ import annotations

from dataclasses import dataclass

from .flow_sir import FlowSIRError, validate_sir_flow_plans


class TransactionError(ValueError):
    """Raised when a transaction audit lacks canonical SIR evidence."""


_CLASSIFICATIONS = frozenset({"reversible", "compensatable", "irreversible"})


@dataclass(frozen=True)
class TransactionEffect:
    stage: str
    function: str
    effect: str
    classification: str
    compensation: str | None


@dataclass(frozen=True)
class TransactionAudit:
    flow: str
    effects: tuple[TransactionEffect, ...]
    rollback_policy_satisfied: bool
    blockers: tuple[str, ...]
    compensation_stage_order: tuple[tuple[str, ...], ...] = ()


def analyze_sir_flow_transaction_effects(
    module,
    flow_name: str,
    effect_policies: dict[str, str],
    compensation_handlers: dict[str, str] | None = None,
) -> TransactionAudit:
    """Audit a checked Flow's effects against an explicit rollback policy.

    This is analysis only: it does not run stages, apply mutations, or claim
    that an external compensating action has executed.
    """
    if not isinstance(effect_policies, dict):
        raise TransactionError("transaction effect policies must be a mapping")
    handlers = compensation_handlers or {}
    if not isinstance(handlers, dict):
        raise TransactionError("transaction compensation handlers must be a mapping")
    for effect, classification in effect_policies.items():
        if not isinstance(effect, str) or not effect:
            raise TransactionError("transaction policy contains an invalid effect name")
        if not isinstance(classification, str) or classification not in _CLASSIFICATIONS:
            raise TransactionError(
                f"invalid transaction classification for effect {effect!r}"
            )
    for effect, handler in handlers.items():
        if not isinstance(effect, str) or not effect or not isinstance(handler, str) or not handler:
            raise TransactionError("transaction compensation mapping is invalid")

    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise TransactionError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise TransactionError(f"SIR has no unique checked Flow plan {flow_name!r}")
    plan = matches[0]
    functions = {function.name: function for function in getattr(module, "functions", ())}
    if len(functions) != len(getattr(module, "functions", ())):
        raise TransactionError("SIR contains duplicate function names")

    records = []
    blockers = []
    observed = set()
    for stage in plan.stages:
        if stage.function not in functions:
            raise TransactionError(
                f"transaction stage {stage.name!r} has no SIR function"
            )
        for effect in stage.effects:
            observed.add(effect)
            classification = effect_policies.get(effect)
            if classification is None:
                classification = "unclassified"
                blockers.append(f"{stage.name}: effect {effect} has no transaction policy")
            compensation = None
            if classification == "compensatable":
                compensation = handlers.get(effect)
                if compensation is None:
                    blockers.append(
                        f"{stage.name}: effect {effect} requires a compensation handler"
                    )
                elif compensation not in functions:
                    raise TransactionError(
                        f"compensation handler {compensation!r} is not present in SIR"
                    )
            elif classification == "irreversible":
                blockers.append(f"{stage.name}: effect {effect} is irreversible")
            records.append(TransactionEffect(
                stage.name, stage.function, effect, classification, compensation
            ))

    unused = set(effect_policies) - observed
    if unused:
        raise TransactionError(
            "transaction policies reference effects absent from the Flow: "
            + ", ".join(sorted(unused))
        )
    policy_satisfied = not blockers
    compensation_stages = {
        record.stage for record in records
        if record.classification == "compensatable" and record.compensation is not None
    }
    compensation_order = (
        tuple(
            tuple(stage for stage in batch if stage in compensation_stages)
            for batch in reversed(plan.parallel_stages)
            if any(stage in compensation_stages for stage in batch)
        )
        if policy_satisfied else ()
    )
    return TransactionAudit(
        plan.name, tuple(records), policy_satisfied, tuple(blockers),
        compensation_order,
    )


__all__ = [
    "TransactionError", "TransactionEffect", "TransactionAudit",
    "analyze_sir_flow_transaction_effects",
]
