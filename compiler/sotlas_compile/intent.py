"""Deterministic strategy selection over certified Flow plans in SIR."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .flow_sir import FlowSIRError, validate_sir_flow_plans


class IntentError(ValueError):
    """Raised when an intent strategy cannot be checked from canonical SIR."""


@dataclass(frozen=True)
class IntentCandidateReview:
    flow: str
    role: str
    priority: int
    eligible: bool
    effects: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IntentPlan:
    name: str
    selected_flow: str | None
    forbidden_effects: tuple[str, ...]
    unavailable_stages: tuple[tuple[str, tuple[str, ...]], ...]
    guarantees: tuple[str, ...]
    inspection: tuple[IntentCandidateReview, ...]


def _names(value, label: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise IntentError(f"intent {label} must be an ordered tuple or list")
    names = tuple(value)
    if any(not isinstance(name, str) or not name for name in names):
        raise IntentError(f"intent {label} contains an invalid name")
    if len(set(names)) != len(names):
        raise IntentError(f"intent {label} contains duplicates")
    return names


def plan_sir_intent(
    module,
    name: str,
    *,
    prefer: tuple[str, ...],
    fallback: tuple[str, ...] = (),
    forbidden_effects: tuple[str, ...] = (),
    unavailable_stages: Mapping[str, tuple[str, ...]] | None = None,
) -> IntentPlan:
    """Choose and explain the first eligible Flow strategy without executing it.

    The only guarantees checked in this initial subset are absence of explicitly
    forbidden effects and availability of every stage in the chosen Flow.
    """
    if not isinstance(name, str) or not name:
        raise IntentError("intent requires a non-empty name")
    preferred = _names(prefer, "preferred Flow list")
    fallbacks = _names(fallback, "fallback Flow list")
    ordered = preferred + fallbacks
    if not ordered:
        raise IntentError("intent requires at least one preferred or fallback Flow")
    if len(set(ordered)) != len(ordered):
        raise IntentError("intent repeats a Flow across preference lists")
    forbidden = _names(forbidden_effects, "forbidden-effects list")
    unavailable = unavailable_stages or {}
    if not isinstance(unavailable, Mapping):
        raise IntentError("intent unavailable stages must be a mapping by Flow name")
    unknown_availability = set(unavailable) - set(ordered)
    if unknown_availability:
        raise IntentError(
            "intent availability references a non-candidate Flow: "
            + ", ".join(sorted(unknown_availability))
        )

    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise IntentError(f"invalid canonical SIR Flow plan: {error}") from error
    by_name = {plan.name: plan for plan in plans}
    missing = tuple(flow for flow in ordered if flow not in by_name)
    if missing:
        raise IntentError("intent references unknown SIR Flow: " + ", ".join(missing))

    reviews = []
    selected = None
    availability_summary = []
    for priority, flow_name in enumerate(ordered):
        plan = by_name[flow_name]
        stage_names = tuple(stage.name for stage in plan.stages)
        unavailable_for_flow = _names(
            unavailable.get(flow_name, ()), f"unavailable stages for {flow_name}"
        )
        unknown_stages = tuple(
            stage for stage in unavailable_for_flow if stage not in stage_names
        )
        if unknown_stages:
            raise IntentError(
                f"intent availability for Flow {flow_name!r} references unknown "
                f"stages: {', '.join(unknown_stages)}"
            )
        availability_summary.append((flow_name, unavailable_for_flow))
        effects = tuple(dict.fromkeys(
            effect for stage in plan.stages for effect in stage.effects
        ))
        reasons = []
        rejected_effects = tuple(effect for effect in effects if effect in forbidden)
        if rejected_effects:
            reasons.append("forbidden effects: " + ", ".join(rejected_effects))
        if unavailable_for_flow:
            reasons.append(
                "unavailable stages: " + ", ".join(unavailable_for_flow)
            )
        eligible = not reasons
        role = "prefer" if priority < len(preferred) else "fallback"
        reviews.append(IntentCandidateReview(
            flow_name, role, priority, eligible, effects, tuple(reasons)
        ))
        if eligible and selected is None:
            selected = flow_name

    guarantees = (
        "forbidden_effects_absent",
        "all_selected_flow_stages_available",
    ) if selected is not None else ()
    return IntentPlan(
        name,
        selected,
        forbidden,
        tuple(availability_summary),
        guarantees,
        tuple(reviews),
    )


__all__ = [
    "IntentError", "IntentCandidateReview", "IntentPlan", "plan_sir_intent",
]
