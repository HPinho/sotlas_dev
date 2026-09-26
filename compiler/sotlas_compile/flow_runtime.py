"""Structured execution for certified Flow dependency graphs.

This runtime executes callable nodes by deterministic ready stages. It does not
parse Flow source or perform language-level type/effect checking.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import Event
from types import MappingProxyType
from typing import Callable, Mapping

from .flow_graph import (
    FlowDependency,
    FlowGraphPlan,
    FlowNode,
    certify_flow_graph,
)


class FlowExecutionError(RuntimeError):
    """A Flow node failed; no later stage is started."""

    def __init__(self, node: str, cause: BaseException):
        self.node = node
        self.cause = cause
        super().__init__(f"Flow node {node!r} failed: {cause}")


class FlowCancelledError(RuntimeError):
    """Execution was cancelled between or during ready stages."""


@dataclass(frozen=True)
class FlowExecutionResult:
    """Successful node outputs in the graph's declared source order."""

    outputs: Mapping[str, object]

    def output(self, node: str) -> object:
        try:
            return self.outputs[node]
        except KeyError as error:
            raise KeyError(f"Flow has no output for node {node!r}") from error


FlowAction = Callable[[Mapping[str, object]], object]


def execute_flow(
    plan: FlowGraphPlan,
    actions: Mapping[str, FlowAction],
    *,
    max_workers: int | None = None,
    cancel_event: Event | None = None,
) -> FlowExecutionResult:
    """Run each ready stage concurrently and commit outputs stage by stage.

    A node receives an immutable mapping containing only its direct
    dependencies. If a task fails or cancellation is requested, pending tasks
    are cancelled, already-running peers are joined, and no downstream stage
    is launched.
    """
    if not isinstance(plan, FlowGraphPlan):
        raise TypeError("Flow execution requires a certified FlowGraphPlan")
    canonical = certify_flow_graph(plan.nodes, plan.dependencies)
    if canonical != plan:
        raise ValueError("Flow execution plan is not in canonical stage order")
    if not isinstance(actions, Mapping):
        raise TypeError("Flow actions must be a mapping keyed by node name")
    names = tuple(node.name for node in plan.nodes)
    missing = tuple(name for name in names if name not in actions)
    extra = tuple(name for name in actions if name not in names)
    if missing or extra:
        raise ValueError(
            f"Flow actions must match graph nodes (missing={missing}, extra={extra})"
        )
    if any(not callable(actions[name]) for name in names):
        raise TypeError("Every Flow action must be callable")
    if max_workers is not None and (
        not isinstance(max_workers, int)
        or isinstance(max_workers, bool)
        or max_workers <= 0
    ):
        raise ValueError("max_workers must be a positive integer")
    if cancel_event is not None and not callable(
        getattr(cancel_event, "is_set", None)
    ):
        raise TypeError("cancel_event must provide is_set()")

    committed: dict[str, object] = {}
    grouped: dict[str, list[str]] = {name: [] for name in names}
    for edge in plan.dependencies:
        grouped[edge.consumer].append(edge.producer)
    dependencies = {name: tuple(grouped[name]) for name in names}

    for stage in plan.parallel_stages:
        if cancel_event is not None and cancel_event.is_set():
            raise FlowCancelledError("Flow cancelled before the next stage")
        stage_inputs = {
            name: MappingProxyType(
                {source: committed[source] for source in dependencies[name]}
            )
            for name in stage
        }
        stage_outputs: dict[str, object] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Future[object], str] = {
                executor.submit(actions[name], stage_inputs[name]): name
                for name in stage
            }
            pending = set(futures)
            stage_order = {name: index for index, name in enumerate(stage)}
            failure: FlowExecutionError | FlowCancelledError | None = None
            while pending:
                if cancel_event is not None and cancel_event.is_set():
                    failure = FlowCancelledError("Flow cancelled during a stage")
                    break
                completed, pending = wait(
                    pending, timeout=0.02, return_when=FIRST_COMPLETED
                )
                for future in sorted(
                    completed, key=lambda item: stage_order[futures[item]]
                ):
                    name = futures[future]
                    try:
                        stage_outputs[name] = future.result()
                    except BaseException as error:
                        failure = FlowExecutionError(name, error)
                        break
                if failure is not None:
                    break
            if (
                failure is None
                and cancel_event is not None
                and cancel_event.is_set()
            ):
                failure = FlowCancelledError("Flow cancelled during a stage")
            if failure is not None:
                for future in pending:
                    future.cancel()
                # Join every peer before returning so no task escapes the flow.
                task_failures = [failure] if isinstance(
                    failure, FlowExecutionError
                ) else []
                for future, name in futures.items():
                    if future.cancelled():
                        continue
                    try:
                        future.result()
                    except BaseException as error:
                        task_failures.append(FlowExecutionError(name, error))
                if task_failures:
                    failure = min(
                        task_failures,
                        key=lambda item: stage_order[item.node],
                    )
                if isinstance(failure, FlowExecutionError):
                    raise failure from failure.cause
                raise failure
        committed.update(stage_outputs)

    return FlowExecutionResult(
        MappingProxyType({name: committed[name] for name in names})
    )


def execute_typed_flow(
    plan,
    actions: Mapping[str, Callable[..., object]],
    *,
    max_workers: int | None = None,
    cancel_event: Event | None = None,
) -> FlowExecutionResult:
    """Execute a checked source Flow plan using stage-name callables.

    Each callable receives dependency outputs as positional arguments in the
    source declaration order. The typed plan is reconciled with its certified
    graph before any user action runs.
    """
    graph = getattr(plan, "graph", None)
    stages = getattr(plan, "stages", None)
    if not isinstance(graph, FlowGraphPlan) or not isinstance(stages, tuple):
        raise TypeError("Typed Flow execution requires a checked source plan")
    canonical = certify_flow_graph(graph.nodes, graph.dependencies)
    if canonical != graph:
        raise ValueError("Typed Flow graph is not in canonical stage order")
    stage_names = tuple(node.name for node in graph.nodes)
    by_name = {getattr(stage, "name", None): stage for stage in stages}
    if len(by_name) != len(stages) or set(by_name) != set(stage_names):
        raise ValueError("Typed Flow stages do not match its certified graph")
    expected_dependencies: dict[str, list[str]] = {
        name: [] for name in stage_names
    }
    for edge in graph.dependencies:
        expected_dependencies[edge.consumer].append(edge.producer)
    for name in stage_names:
        stage = by_name[name]
        dependencies = getattr(stage, "dependencies", None)
        input_types = getattr(stage, "input_types", None)
        function = getattr(stage, "function", None)
        if dependencies != tuple(expected_dependencies[name]):
            raise ValueError(
                f"Typed Flow stage {name!r} dependencies differ from its graph"
            )
        if not isinstance(input_types, tuple) or len(input_types) != len(dependencies):
            raise ValueError(
                f"Typed Flow stage {name!r} input types differ from its dependencies"
            )
        if not isinstance(function, str) or not function:
            raise ValueError(f"Typed Flow stage {name!r} has no function symbol")
    if not isinstance(actions, Mapping):
        raise TypeError("Typed Flow actions must be a mapping keyed by stage name")
    missing = tuple(name for name in stage_names if name not in actions)
    extra = tuple(name for name in actions if name not in stage_names)
    if missing or extra:
        raise ValueError(
            f"Typed Flow actions must match stages (missing={missing}, extra={extra})"
        )
    if any(not callable(actions[name]) for name in stage_names):
        raise TypeError("Every typed Flow stage action must be callable")

    wrapped: dict[str, FlowAction] = {}
    for name in stage_names:
        stage = by_name[name]
        dependencies = stage.dependencies
        action = actions[name]

        def invoke(values, *, dependencies=dependencies, action=action):
            return action(*(values[dependency] for dependency in dependencies))

        wrapped[name] = invoke
    return execute_flow(
        graph, wrapped, max_workers=max_workers, cancel_event=cancel_event
    )


def execute_bound_sir_flow(
    sir_module,
    flow_name: str,
    function_bindings: Mapping[str, Callable[..., object]],
    *,
    max_workers: int | None = None,
    cancel_event: Event | None = None,
) -> FlowExecutionResult:
    """Schedule a validated SIR Flow plan using explicit host function bindings.

    Bindings supply execution for stage bodies; this runner does not interpret
    or compile SIR instructions. The canonical SIR plan is authoritative for
    stage order, function identity, and producer-to-parameter data flow.
    """
    from .flow_sir import FlowSIRError, validate_sir_flow_plans

    plans = validate_sir_flow_plans(sir_module)
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowSIRError(
            f"SIR Flow runner requires exactly one plan named {flow_name!r}"
        )
    plan = matches[0]
    if not isinstance(function_bindings, Mapping):
        raise TypeError("SIR Flow function bindings must be a mapping")
    required = tuple(dict.fromkeys(stage.function for stage in plan.stages))
    missing = tuple(name for name in required if name not in function_bindings)
    extra = tuple(name for name in function_bindings if name not in required)
    if missing or extra:
        raise ValueError(
            "SIR Flow function bindings must match referenced functions "
            f"(missing={missing}, extra={extra})"
        )
    if any(not callable(function_bindings[name]) for name in required):
        raise TypeError("Every SIR Flow function binding must be callable")

    graph = certify_flow_graph(
        tuple(FlowNode(stage.name) for stage in plan.stages),
        tuple(
            FlowDependency(argument.value.producer_stage, stage.name)
            for stage in plan.stages
            for argument in stage.arguments
        ),
    )
    if graph.parallel_stages != plan.parallel_stages:
        raise FlowSIRError(
            f"SIR Flow plan {flow_name!r} schedule changed after validation"
        )

    actions: dict[str, FlowAction] = {}
    for stage in plan.stages:
        binding = function_bindings[stage.function]
        arguments = tuple(stage.arguments)

        def invoke(values, *, binding=binding, arguments=arguments):
            return binding(*(values[item.value.producer_stage] for item in arguments))

        actions[stage.name] = invoke
    return execute_flow(
        graph, actions, max_workers=max_workers, cancel_event=cancel_event
    )


__all__ = [
    "FlowAction",
    "FlowExecutionError",
    "FlowCancelledError",
    "FlowExecutionResult",
    "execute_flow",
    "execute_typed_flow",
    "execute_bound_sir_flow",
]
