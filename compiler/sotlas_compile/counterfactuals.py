"""Deterministic stage failure analysis over certified Sotlas Flow plans."""
from __future__ import annotations

from dataclasses import dataclass

from .flow_graph import FlowDependency, FlowNode, certify_flow_graph


class CounterfactualError(ValueError):
    """Raised when a stage availability scenario lacks canonical evidence."""


@dataclass(frozen=True)
class CounterfactualImpact:
    flow: str
    unavailable_stage: str
    affected_stages: tuple[str, ...]
    unaffected_stages: tuple[str, ...]
    affected_dependencies: tuple[tuple[str, str], ...]


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
    plans = tuple(getattr(module, "flow_plans", ()) or ())
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CounterfactualError(f"SIR has no unique checked Flow plan {flow_name!r}")
    plan = matches[0]
    try:
        graph = certify_flow_graph(
            tuple(FlowNode(stage.name) for stage in plan.stages),
            tuple(
                FlowDependency(argument.value.producer_stage, stage.name)
                for stage in plan.stages for argument in stage.arguments
            ),
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise CounterfactualError(f"invalid SIR Flow provenance: {error}") from error
    if graph.parallel_stages != tuple(plan.parallel_stages):
        raise CounterfactualError("SIR Flow parallel stages are not canonical")
    # SIR stores source-stable arguments instead of the frontend graph record.
    # Reconstruct and certify the graph from those preserved dependencies.
    return _analyze(flow_name, graph, tuple(stage.name for stage in plan.stages), unavailable_stage)


__all__ = [
    "CounterfactualError", "CounterfactualImpact",
    "analyze_flow_stage_unavailability",
    "analyze_sir_flow_stage_unavailability",
]
