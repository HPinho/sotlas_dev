"""Source-stable causal queries over certified Flow plans and SIR evidence."""
from __future__ import annotations

from dataclasses import dataclass

from . import bootstrap
from .flow_sir import FlowSIRError, validate_sir_flow_plans


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


@dataclass(frozen=True)
class SourceCallStep:
    caller_function: str
    callee_function: str
    line: int
    column: int
    argument_count: int
    callee_parameters: tuple[str, ...]
    caller_effects: tuple[str, ...]
    callee_effects: tuple[str, ...]


@dataclass(frozen=True)
class SourceCallExplanation:
    source_function: str
    target_function: str
    steps: tuple[SourceCallStep, ...]


def _source_calls(value):
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _source_calls(item)
        return
    if not isinstance(value, (bootstrap.Expr, bootstrap.Stmt)):
        return
    if isinstance(value, bootstrap.Call):
        yield value
    for name, child in vars(value).items():
        if name in {"token", "type", "target_type"}:
            continue
        if isinstance(child, dict):
            yield from _source_calls(tuple(child.values()))
        else:
            yield from _source_calls(child)


def explain_source_call_causality(
    checked_module, source_function: str, target_function: str
) -> SourceCallExplanation:
    """Explain a deterministic source call chain outside Flow orchestration."""
    if not isinstance(source_function, str) or not source_function:
        raise CausalityError("causal source function must be a non-empty name")
    if not isinstance(target_function, str) or not target_function:
        raise CausalityError("causal target function must be a non-empty name")
    parsed = getattr(checked_module, "parsed_module", None)
    summaries = getattr(checked_module, "source_effects", None)
    if parsed is None or not isinstance(summaries, dict):
        raise CausalityError("causal call query requires a checked source module")
    functions = tuple(getattr(parsed, "functions", ()) or ())
    by_name = {function.name: function for function in functions}
    if len(by_name) != len(functions):
        raise CausalityError("checked source module repeats function names")
    if source_function not in by_name or target_function not in by_name:
        raise CausalityError("causal call query references an unknown function")
    if source_function == target_function:
        return SourceCallExplanation(source_function, target_function, ())

    calls: dict[str, list[tuple[str, object]]] = {name: [] for name in by_name}
    for caller, function in by_name.items():
        for call in _source_calls(function.body):
            if call.callee in by_name:
                calls[caller].append((call.callee, call))

    queue = [source_function]
    previous: dict[str, tuple[str, object] | None] = {source_function: None}
    for current in queue:
        for callee, call in sorted(
            calls[current],
            key=lambda edge: (
                edge[0], edge[1].token.line, edge[1].token.column
            ),
        ):
            if callee in previous:
                continue
            previous[callee] = (current, call)
            if callee == target_function:
                queue = []
                break
            queue.append(callee)
        if target_function in previous:
            break
    if target_function not in previous:
        raise CausalityError(
            f"no source call path from {source_function!r} to {target_function!r}"
        )

    edges = []
    cursor = target_function
    while cursor != source_function:
        predecessor = previous[cursor]
        if predecessor is None:
            raise CausalityError("source call predecessor chain is incomplete")
        caller, call = predecessor
        edges.append((caller, cursor, call))
        cursor = caller
    edges.reverse()
    steps = tuple(
        SourceCallStep(
            caller,
            callee,
            call.token.line,
            call.token.column,
            len(call.args),
            tuple(parameter for parameter, _ in by_name[callee].params),
            tuple(summaries[caller].transitive_effects),
            tuple(summaries[callee].transitive_effects),
        )
        for caller, callee, call in edges
    )
    return SourceCallExplanation(source_function, target_function, steps)


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
    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise CausalityError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CausalityError(f"SIR has no unique checked Flow plan {flow_name!r}")
    return explain_flow_causality(matches[0], source_stage, target_stage)


__all__ = [
    "CausalityError", "CausalStep", "CausalExplanation",
    "SourceCallStep", "SourceCallExplanation", "explain_source_call_causality",
    "explain_flow_causality", "explain_sir_flow_causality",
]
