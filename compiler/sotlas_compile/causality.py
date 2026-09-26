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
class SourceCallArgument:
    parameter_index: int
    parameter_name: str
    expression: str
    source_bindings: tuple[str, ...]
    causal_origins: tuple[str, ...] = ()
    causal_expression: str | None = None


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
    arguments: tuple[SourceCallArgument, ...]


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


def _causal_expression(value, aliases=None, origins=None) -> str:
    """Render a stable, bounded description of a checked call argument."""
    aliases = aliases or {}
    origins = origins or {}
    if isinstance(value, bootstrap.Name):
        name = value.value
        seen = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return origins.get(name, name)
    if isinstance(value, bootstrap.Number):
        return value.value
    if isinstance(value, bootstrap.Boolean):
        return "true" if value.value else "false"
    if isinstance(value, bootstrap.StringLit):
        return repr(value.value)
    if isinstance(value, bootstrap.CharLit):
        return repr(value.value)
    if isinstance(value, bootstrap.NullLit):
        return "null"
    if type(value).__name__ in {"MoveExpr", "ShareExpr"}:
        operation = "move" if type(value).__name__ == "MoveExpr" else "share"
        return f"{operation}({_causal_expression(value.value, aliases, origins)})"
    if isinstance(value, bootstrap.Unary):
        return f"{value.op}{_causal_expression(value.value, aliases, origins)}"
    if isinstance(value, bootstrap.Binary):
        return (
            f"({_causal_expression(value.left, aliases, origins)} {value.op} "
            f"{_causal_expression(value.right, aliases, origins)})"
        )
    if isinstance(value, bootstrap.Member):
        return f"{_causal_expression(value.target, aliases, origins)}.{value.field}"
    if isinstance(value, bootstrap.Index):
        return (
            f"{_causal_expression(value.target, aliases, origins)}"
            f"[{_causal_expression(value.index, aliases, origins)}]"
        )
    if isinstance(value, bootstrap.Call):
        args = ", ".join(
            _causal_expression(item, aliases, origins) for item in value.args
        )
        return f"{value.callee}({args})"
    if isinstance(value, bootstrap.MethodCall):
        args = ", ".join(
            _causal_expression(item, aliases, origins) for item in value.args
        )
        return f"{_causal_expression(value.target, aliases, origins)}.{value.method}({args})"
    if isinstance(value, bootstrap.Cast):
        target_name = getattr(value.target_type, "name", "<type>")
        return f"{_causal_expression(value.expr, aliases, origins)} as {target_name}"
    return f"<{type(value).__name__}>"


def _immutable_aliases_before_call(function, target_call) -> dict[str, str]:
    """Resolve simple immutable local aliases that dominate a top-level call."""
    aliases: dict[str, str] = {}
    for statement in tuple(getattr(function, "body", ()) or ()):
        if any(call is target_call for call in _source_calls(statement)):
            if type(statement).__name__ in {"Return", "Expression"}:
                return aliases
            return {}
        if type(statement).__name__ != "Let":
            # Calls under branches/loops and aliases crossing arbitrary
            # statements require CFG-sensitive reaching definitions.
            aliases.clear()
            continue
        name = getattr(statement, "name", None)
        if not isinstance(name, str) or not name:
            aliases.clear()
            continue
        aliases.pop(name, None)
        value = getattr(statement, "value", None)
        if not getattr(statement, "is_mut", False) and isinstance(
            value, bootstrap.Name
        ):
            aliases[name] = aliases.get(value.value, value.value)
    return {}


def _source_bindings(value, aliases: dict[str, str] | None = None) -> tuple[str, ...]:
    names: set[str] = set()
    aliases = aliases or {}

    def resolve(name: str) -> str:
        seen = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return name

    def visit(node):
        if isinstance(node, (tuple, list)):
            for item in node:
                visit(item)
            return
        if isinstance(node, bootstrap.Name):
            names.add(resolve(node.value))
            return
        if not isinstance(node, (bootstrap.Expr, bootstrap.Stmt)):
            return
        for field_name, child in vars(node).items():
            if field_name not in {"token", "type", "target_type"}:
                visit(child)

    visit(value)
    return tuple(sorted(names))


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
    for caller, callee, call in edges:
        parameters = by_name[callee].params
        if len(call.args) != len(parameters):
            raise CausalityError(
                f"checked call {caller!r} -> {callee!r} changed arity"
            )
        if caller not in summaries or callee not in summaries:
            raise CausalityError(
                f"checked call {caller!r} -> {callee!r} lost effect provenance"
            )
    incoming_origins = {
        source_function: {
            parameter: (parameter,)
            for parameter, _ in by_name[source_function].params
        }
    }
    incoming_expressions = {
        source_function: {
            parameter: parameter
            for parameter, _ in by_name[source_function].params
        }
    }
    steps = []
    for caller, callee, call in edges:
        caller_origins = incoming_origins.get(caller, {})
        caller_expressions = incoming_expressions.get(caller, {})
        aliases = _immutable_aliases_before_call(by_name[caller], call)
        arguments = []
        callee_origins = {}
        callee_expressions = {}
        for index, (argument, (parameter_name, _)) in enumerate(zip(
            call.args, by_name[callee].params
        )):
            bindings = _source_bindings(argument, aliases)
            origins = tuple(sorted({
                origin
                for binding in bindings
                for origin in caller_origins.get(binding, (binding,))
            }))
            causal_expression = _causal_expression(
                argument, aliases, caller_expressions
            )
            arguments.append(SourceCallArgument(
                index,
                parameter_name,
                _causal_expression(argument),
                bindings,
                origins,
                causal_expression,
            ))
            callee_origins[parameter_name] = origins
            callee_expressions[parameter_name] = causal_expression
        incoming_origins[callee] = callee_origins
        incoming_expressions[callee] = callee_expressions
        steps.append(SourceCallStep(
            caller,
            callee,
            call.token.line,
            call.token.column,
            len(call.args),
            tuple(parameter for parameter, _ in by_name[callee].params),
            tuple(summaries[caller].transitive_effects),
            tuple(summaries[callee].transitive_effects),
            tuple(arguments),
        ))
    return SourceCallExplanation(source_function, target_function, tuple(steps))


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


def render_source_call_causality_mermaid(
    explanation: SourceCallExplanation,
) -> str:
    """Render a deterministic Mermaid graph for editor/IDE causal views."""
    if not isinstance(explanation, SourceCallExplanation):
        raise CausalityError("causal graph rendering requires a source explanation")
    names = {explanation.source_function, explanation.target_function}
    for step in explanation.steps:
        names.add(step.caller_function)
        names.add(step.callee_function)
    identifiers = {name: f"fn{index}" for index, name in enumerate(sorted(names))}

    def label(value: str) -> str:
        return value.replace("\r", " ").replace("\n", " ").replace('"', "&quot;")

    lines = ["flowchart LR"]
    lines.extend(
        f'  {identifiers[name]}["{label(name)}"]'
        for name in sorted(names)
    )
    lines.extend(
        f"  {identifiers[step.caller_function]} -->|{step.line}:{step.column}| "
        f"{identifiers[step.callee_function]}"
        for step in explanation.steps
    )
    return "\n".join(lines)


__all__ = [
    "CausalityError", "CausalStep", "CausalExplanation",
    "SourceCallArgument", "SourceCallStep", "SourceCallExplanation",
    "explain_source_call_causality",
    "explain_flow_causality", "explain_sir_flow_causality",
    "render_source_call_causality_mermaid",
]
