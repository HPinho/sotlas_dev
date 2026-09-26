"""Deterministic stage failure analysis over certified Sotlas Flow plans."""
from __future__ import annotations

from dataclasses import dataclass

from .flow_graph import certify_flow_graph
from .flow_sir import FlowSIRError, validate_sir_flow_plans
from .source_effects import EFFECT_ORDER, KNOWN_EFFECTS


class CounterfactualError(ValueError):
    """Raised when a stage availability scenario lacks canonical evidence."""


@dataclass(frozen=True)
class CounterfactualImpact:
    flow: str
    unavailable_stage: str
    affected_stages: tuple[str, ...]
    unaffected_stages: tuple[str, ...]
    affected_dependencies: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CounterfactualRecoveryCandidate:
    flow: str
    stage: str
    function: str
    result_type: str
    effects: tuple[str, ...]
    effects_added: tuple[str, ...]
    effects_removed: tuple[str, ...]
    semantic_equivalence_verified: bool = False
    effect_policy: tuple[str, ...] | None = None
    effects_disallowed: tuple[str, ...] = ()


@dataclass(frozen=True)
class CounterfactualRecoveryOptions:
    impact: CounterfactualImpact
    target_stage: str
    candidates: tuple[CounterfactualRecoveryCandidate, ...]


def _analyze(flow_name, graph, stage_names, unavailable_stage):
    if not isinstance(unavailable_stage, str) or not unavailable_stage:
        raise CounterfactualError("unavailable Flow stage must be a non-empty name")
    try:
        canonical = certify_flow_graph(graph.nodes, graph.dependencies)
    except (AttributeError, TypeError, ValueError) as error:
        raise CounterfactualError(f"invalid canonical Flow graph: {error}") from error
    if canonical != graph:
        raise CounterfactualError("Flow graph is not in canonical certified form")
    graph_names = tuple(node.name for node in canonical.nodes)
    if len(set(stage_names)) != len(stage_names) or set(stage_names) != set(graph_names):
        raise CounterfactualError("Flow stage facts differ from the certified graph")
    if unavailable_stage not in graph_names:
        raise CounterfactualError(f"unknown Flow stage {unavailable_stage!r}")

    successors = {name: [] for name in graph_names}
    for edge in canonical.dependencies:
        successors[edge.producer].append(edge.consumer)
    impacted = {unavailable_stage}
    pending = [unavailable_stage]
    while pending:
        current = pending.pop(0)
        for consumer in successors[current]:
            if consumer not in impacted:
                impacted.add(consumer)
                pending.append(consumer)
    affected = tuple(name for name in graph_names if name in impacted)
    unaffected = tuple(name for name in graph_names if name not in impacted)
    edges = tuple(
        (edge.producer, edge.consumer)
        for edge in canonical.dependencies
        if edge.consumer in impacted
    )
    return CounterfactualImpact(
        flow_name, unavailable_stage, affected, unaffected, edges
    )


def analyze_flow_stage_unavailability(plan, unavailable_stage: str) -> CounterfactualImpact:
    """Report transitive downstream impact without executing Flow actions."""
    if not isinstance(getattr(plan, "name", None), str) or not plan.name:
        raise CounterfactualError("Flow plan must have a name")
    return _analyze(
        plan.name, plan.graph, tuple(stage.name for stage in plan.stages),
        unavailable_stage,
    )


def analyze_sir_flow_stage_unavailability(
    module, flow_name: str, unavailable_stage: str,
) -> CounterfactualImpact:
    """Analyze one uniquely attached canonical Flow plan in SIR."""
    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise CounterfactualError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CounterfactualError(f"SIR has no unique checked Flow plan {flow_name!r}")
    plan = matches[0]
    # SIR stores source-stable arguments instead of the frontend graph record;
    # validation reconciles those references before reconstructing the graph.
    from .flow_graph import FlowDependency, FlowNode
    graph = certify_flow_graph(
        tuple(FlowNode(stage.name) for stage in plan.stages),
        tuple(
            FlowDependency(argument.value.producer_stage, stage.name)
            for stage in plan.stages for argument in stage.arguments
        ),
    )
    return _analyze(flow_name, graph, tuple(stage.name for stage in plan.stages), unavailable_stage)


def analyze_sir_flow_recovery_options(
    module, flow_name: str, unavailable_stage: str, target_stage: str,
    *, allowed_effects: tuple[str, ...] | None = None,
) -> CounterfactualRecoveryOptions:
    """Find type-compatible alternate Flow implementations for an impacted stage.

    Candidates are structural only: matching stage names and result types do not
    prove that two functions compute equivalent values.
    """
    if not isinstance(target_stage, str) or not target_stage:
        raise CounterfactualError("recovery target stage must be a non-empty name")
    if allowed_effects is not None:
        if not isinstance(allowed_effects, tuple) or any(
            not isinstance(effect, str) for effect in allowed_effects
        ):
            raise CounterfactualError(
                "allowed recovery effects must be a tuple of effect names"
            )
        if len(set(allowed_effects)) != len(allowed_effects):
            raise CounterfactualError("allowed recovery effects repeat an effect")
        unknown = set(allowed_effects) - KNOWN_EFFECTS
        if unknown:
            raise CounterfactualError(
                "unknown allowed recovery effects: "
                + ", ".join(sorted(unknown))
            )
        allowed_effects = tuple(
            effect for effect in EFFECT_ORDER if effect in allowed_effects
        )
    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise CounterfactualError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CounterfactualError(f"SIR has no unique checked Flow plan {flow_name!r}")
    failed_plan = matches[0]
    failed_stages = {stage.name: stage for stage in failed_plan.stages}
    if target_stage not in failed_stages:
        raise CounterfactualError(f"unknown recovery target stage {target_stage!r}")
    impact = analyze_sir_flow_stage_unavailability(
        module, flow_name, unavailable_stage
    )
    if target_stage not in impact.affected_stages:
        return CounterfactualRecoveryOptions(impact, target_stage, ())

    target = failed_stages[target_stage]
    failed_effects = tuple(target.effects)
    candidates = []
    for plan in plans:
        if plan.name == flow_name:
            continue
        stage_by_name = {stage.name: stage for stage in plan.stages}
        replacement = stage_by_name.get(target_stage)
        if replacement is None or replacement.result_type != target.result_type:
            continue
        # Follow the replacement's transitive dependency ancestry. A candidate
        # that still consumes the failed stage cannot recover the requested output.
        producers = {
            stage.name: tuple(
                argument.value.producer_stage for argument in stage.arguments
            )
            for stage in plan.stages
        }
        ancestry = set()
        pending = [target_stage]
        while pending:
            current = pending.pop()
            for producer in producers.get(current, ()):
                if producer not in ancestry:
                    ancestry.add(producer)
                    pending.append(producer)
        if unavailable_stage in ancestry:
            continue
        candidate_effects = tuple(replacement.effects)
        effects_disallowed = (
            tuple(effect for effect in candidate_effects if effect not in allowed_effects)
            if allowed_effects is not None else ()
        )
        candidates.append(CounterfactualRecoveryCandidate(
            plan.name,
            target_stage,
            replacement.function,
            replacement.result_type,
            candidate_effects,
            tuple(effect for effect in candidate_effects if effect not in failed_effects),
            tuple(effect for effect in failed_effects if effect not in candidate_effects),
            effect_policy=allowed_effects,
            effects_disallowed=effects_disallowed,
        ))
    candidates.sort(key=lambda candidate: (candidate.flow, candidate.function))
    return CounterfactualRecoveryOptions(impact, target_stage, tuple(candidates))


__all__ = [
    "CounterfactualError", "CounterfactualImpact",
    "CounterfactualRecoveryCandidate", "CounterfactualRecoveryOptions",
    "analyze_flow_stage_unavailability",
    "analyze_sir_flow_stage_unavailability",
    "analyze_sir_flow_recovery_options",
]
