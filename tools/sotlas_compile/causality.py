"""Source-stable causal queries over certified Flow plans and SIR evidence."""
from __future__ import annotations

from dataclasses import dataclass


class CausalityError(ValueError):
    """Raised when causal provenance is missing or inconsistent."""


@dataclass(frozen=True)
class CausalStep:
    producer_stage: str
    consumer_stage: str
    producer_function: str
    consumer_function: str
    argument_name: str
    type_name: str
    producer_effects: tuple[str, ...]
    consumer_effects: tuple[str, ...]


@dataclass(frozen=True)
class CausalExplanation:
    flow: str
    source_stage: str
    target_stage: str
    steps: tuple[CausalStep, ...]


def explain_flow_causality(plan, source_stage: str, target_stage: str) -> CausalExplanation:
    """Explain the deterministic dependency path between two checked stages."""
    if not isinstance(source_stage, str) or not source_stage:
        raise CausalityError("causal source stage must be a non-empty name")
    if not isinstance(target_stage, str) or not target_stage:
        raise CausalityError("causal target stage must be a non-empty name")
    stages = {stage.name: stage for stage in getattr(plan, "stages", ())}
    if len(stages) != len(getattr(plan, "stages", ())):
        raise CausalityError("causal Flow plan repeats stage names")
    if source_stage not in stages or target_stage not in stages:
        raise CausalityError("causal query references an unknown Flow stage")
    if source_stage == target_stage:
        return CausalExplanation(plan.name, source_stage, target_stage, ())

    consumers: dict[str, list[tuple[str, object]]] = {
        name: [] for name in stages
    }
    for consumer in plan.stages:
        for argument in consumer.arguments:
            producer = argument.value.producer_stage
            if producer not in stages:
                raise CausalityError(
                    f"causal edge references missing producer {producer!r}"
                )
            consumers[producer].append((consumer.name, argument))

    # Breadth-first traversal gives a shortest deterministic explanation.
    queue = [source_stage]
    previous: dict[str, tuple[str, object] | None] = {source_stage: None}
    for current in queue:
        for consumer, argument in sorted(
            consumers[current], key=lambda edge: (edge[0], edge[1].parameter_index)
        ):
            if consumer in previous:
                continue
            previous[consumer] = (current, argument)
            if consumer == target_stage:
                queue = []
                break
            queue.append(consumer)
        if target_stage in previous:
            break
    if target_stage not in previous:
        raise CausalityError(
            f"no causal dependency path from {source_stage!r} to {target_stage!r}"
        )

    edges = []
    cursor = target_stage
    while cursor != source_stage:
        item = previous[cursor]
        if item is None:
            raise CausalityError("causal predecessor chain is incomplete")
        producer, argument = item
        edges.append((producer, cursor, argument))
        cursor = producer
    edges.reverse()

    steps = tuple(
        CausalStep(
            producer,
            consumer,
            stages[producer].function,
            stages[consumer].function,
            argument.parameter_name,
            argument.type_name,
            tuple(stages[producer].effects),
            tuple(stages[consumer].effects),
        )
        for producer, consumer, argument in edges
    )
    return CausalExplanation(plan.name, source_stage, target_stage, steps)


def explain_sir_flow_causality(module, flow_name: str, source_stage: str, target_stage: str):
    """Query only canonical source Flow plans attached to SIR."""
    plans = tuple(getattr(module, "flow_plans", ()) or ())
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CausalityError(f"SIR has no unique checked Flow plan {flow_name!r}")
    return explain_flow_causality(matches[0], source_stage, target_stage)


__all__ = [
    "CausalityError", "CausalStep", "CausalExplanation",
    "explain_flow_causality", "explain_sir_flow_causality",
]
