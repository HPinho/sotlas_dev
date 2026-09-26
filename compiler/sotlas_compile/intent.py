"""Deterministic strategy selection over certified Flow plans in SIR."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .flow_sir import FlowSIRError, _source_type_name, validate_sir_flow_plans
from .flow_runtime import (
    FlowExecutionResult,
    execute_bound_sir_flow,
    execute_typed_flow,
)


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


@dataclass(frozen=True)
class IntentExecutionResult:
    intent: str
    selected_flow: str
    execution: FlowExecutionResult


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


def execute_sir_intent(
    checked_module,
    sir_module,
    intent: IntentPlan,
    actions: Mapping[str, object],
    *,
    max_workers: int | None = None,
    cancel_event=None,
) -> IntentExecutionResult:
    """Execute only the selected Flow after revalidating intent and SIR evidence."""
    if not isinstance(intent, IntentPlan):
        raise IntentError("intent execution requires a checked IntentPlan")
    reviews = tuple(intent.inspection)
    if any(
        not isinstance(item, IntentCandidateReview)
        or item.role not in {"prefer", "fallback"}
        or not isinstance(item.priority, int)
        or isinstance(item.priority, bool)
        for item in reviews
    ):
        raise IntentError("intent inspection contains malformed candidate evidence")
    ordered_reviews = tuple(sorted(reviews, key=lambda item: item.priority))
    preferred = tuple(item.flow for item in ordered_reviews if item.role == "prefer")
    fallbacks = tuple(item.flow for item in ordered_reviews if item.role == "fallback")
    try:
        canonical = plan_sir_intent(
            sir_module,
            intent.name,
            prefer=preferred,
            fallback=fallbacks,
            forbidden_effects=intent.forbidden_effects,
            unavailable_stages=dict(intent.unavailable_stages),
        )
    except (IntentError, TypeError, ValueError) as error:
        raise IntentError(f"intent plan no longer validates: {error}") from error
    if canonical != intent:
        raise IntentError("intent plan differs from the canonical SIR strategy")
    if intent.selected_flow is None:
        raise IntentError("intent has no eligible Flow to execute")
    try:
        sir_plans = validate_sir_flow_plans(sir_module)
    except FlowSIRError as error:
        raise IntentError(f"invalid canonical SIR Flow plan: {error}") from error
    sir_matches = tuple(plan for plan in sir_plans if plan.name == intent.selected_flow)
    typed_flows = tuple(getattr(checked_module, "flows", ()) or ())
    typed_matches = tuple(
        flow for flow in typed_flows if flow.name == intent.selected_flow
    )
    if len(sir_matches) != 1 or len(typed_matches) != 1:
        raise IntentError("selected Flow is not uniquely present in checked source and SIR")
    sir_plan = sir_matches[0]
    typed_plan = typed_matches[0]
    typed_stages = {stage.name: stage for stage in typed_plan.stages}
    sir_stages = {stage.name: stage for stage in sir_plan.stages}
    if len(typed_stages) != len(typed_plan.stages) or set(typed_stages) != set(sir_stages):
        raise IntentError("selected typed Flow stages differ from canonical SIR")
    for name, typed_stage in typed_stages.items():
        sir_stage = sir_stages[name]
        dependencies = tuple(
            argument.value.producer_stage for argument in sir_stage.arguments
        )
        input_types = tuple(_source_type_name(value) for value in typed_stage.input_types)
        if (
            typed_stage.function != sir_stage.function
            or _source_type_name(typed_stage.result_type) != sir_stage.result_type
            or tuple(typed_stage.dependencies) != dependencies
            or input_types != tuple(argument.type_name for argument in sir_stage.arguments)
            or tuple(typed_stage.effects) != tuple(sir_stage.effects)
        ):
            raise IntentError(
                f"selected typed Flow stage {name!r} differs from canonical SIR"
            )
    execution = execute_typed_flow(
        typed_plan, actions, max_workers=max_workers, cancel_event=cancel_event
    )
    return IntentExecutionResult(intent.name, intent.selected_flow, execution)


def execute_bound_sir_intent(
    sir_module,
    intent: IntentPlan,
    function_bindings: Mapping[str, object],
    *,
    max_workers: int | None = None,
    cancel_event=None,
) -> IntentExecutionResult:
    """Execute the selected strategy using only its reconciled canonical SIR plan."""
    if not isinstance(intent, IntentPlan):
        raise IntentError("SIR intent execution requires a checked IntentPlan")
    reviews = tuple(intent.inspection)
    if any(
        not isinstance(item, IntentCandidateReview)
        or item.role not in {"prefer", "fallback"}
        or not isinstance(item.priority, int)
        or isinstance(item.priority, bool)
        for item in reviews
    ):
        raise IntentError("intent inspection contains malformed candidate evidence")
    ordered_reviews = tuple(sorted(reviews, key=lambda item: item.priority))
    try:
        canonical = plan_sir_intent(
            sir_module,
            intent.name,
            prefer=tuple(item.flow for item in ordered_reviews if item.role == "prefer"),
            fallback=tuple(item.flow for item in ordered_reviews if item.role == "fallback"),
            forbidden_effects=intent.forbidden_effects,
            unavailable_stages=dict(intent.unavailable_stages),
        )
    except (IntentError, TypeError, ValueError) as error:
        raise IntentError(f"intent plan no longer validates: {error}") from error
    if canonical != intent:
        raise IntentError("intent plan differs from the canonical SIR strategy")
    if intent.selected_flow is None:
        raise IntentError("intent has no eligible Flow to execute")
    try:
        execution = execute_bound_sir_flow(
            sir_module,
            intent.selected_flow,
            function_bindings,
            max_workers=max_workers,
            cancel_event=cancel_event,
        )
    except (FlowSIRError, TypeError, ValueError) as error:
        raise IntentError(f"selected SIR Flow cannot execute: {error}") from error
    return IntentExecutionResult(intent.name, intent.selected_flow, execution)


__all__ = [
    "IntentError", "IntentCandidateReview", "IntentPlan", "IntentExecutionResult",
    "plan_sir_intent", "execute_sir_intent", "execute_bound_sir_intent",
]
