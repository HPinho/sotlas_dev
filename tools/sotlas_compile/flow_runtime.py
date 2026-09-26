"""Structured execution for certified Flow dependency graphs.

This runtime executes callable nodes by deterministic ready stages. It does not
parse Flow source or perform language-level type/effect checking.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import Event
from time import monotonic
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


class TransactionExecutionError(RuntimeError):
    """A transactional Flow failed, with any compensation failures retained."""

    def __init__(
        self, stage: str, cause: BaseException,
        rollback_errors=(), completed=(),
    ):
        self.stage = stage
        self.cause = cause
        self.rollback_errors = tuple(rollback_errors)
        self.completed_stages = tuple(completed)
        suffix = (
            f"; {len(self.rollback_errors)} compensation handler(s) also failed"
            if self.rollback_errors else ""
        )
        super().__init__(
            f"transaction Flow stage {stage!r} failed: {cause}{suffix}"
        )


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


class FlowCancellationToken:
    """Read-only cooperative cancellation signal supplied to opt-in actions."""

    def __init__(
        self,
        external_event: Event | None = None,
        stop_event: Event | None = None,
    ) -> None:
        self._external_event = external_event
        self._stop_event = stop_event or Event()

    def is_cancelled(self) -> bool:
        return self._stop_event.is_set() or (
            self._external_event is not None and self._external_event.is_set()
        )

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise FlowCancelledError("Flow cancellation was requested")

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for cancellation, returning False when the timeout expires."""
        if timeout is not None and (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout < 0
        ):
            raise ValueError("cancellation timeout must be non-negative")
        deadline = None if timeout is None else monotonic() + timeout
        while not self.is_cancelled():
            remaining = None if deadline is None else deadline - monotonic()
            if remaining is not None and remaining <= 0:
                return False
            self._stop_event.wait(
                0.02 if remaining is None else min(remaining, 0.02)
            )
        return True


def execute_flow(
    plan: FlowGraphPlan,
    actions: Mapping[str, FlowAction],
    *,
    max_workers: int | None = None,
    cancel_event: Event | None = None,
    cooperative: bool = False,
) -> FlowExecutionResult:
    """Run each ready stage concurrently and commit outputs stage by stage.

    A node receives an immutable mapping containing only its direct
    dependencies. If a task fails or cancellation is requested, pending tasks
    are cancelled, already-running peers are joined, and no downstream stage
    is launched. With ``cooperative=True``, each action receives a second
    read-only ``FlowCancellationToken`` argument. Existing one-argument actions
    remain the default contract.
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
    if not isinstance(cooperative, bool):
        raise TypeError("cooperative must be a bool")

    committed: dict[str, object] = {}
    grouped: dict[str, list[str]] = {name: [] for name in names}
    for edge in plan.dependencies:
        grouped[edge.consumer].append(edge.producer)
    dependencies = {name: tuple(grouped[name]) for name in names}
    stop_event = Event()
    cancellation_token = FlowCancellationToken(cancel_event, stop_event)

    for stage in plan.parallel_stages:
        if cancel_event is not None and cancel_event.is_set():
            stop_event.set()
            raise FlowCancelledError("Flow cancelled before the next stage")
        stage_inputs = {
            name: MappingProxyType(
                {source: committed[source] for source in dependencies[name]}
            )
            for name in stage
        }
        stage_outputs: dict[str, object] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            def invoke(name: str):
                if cooperative:
                    return actions[name](stage_inputs[name], cancellation_token)
                return actions[name](stage_inputs[name])

            futures: dict[Future[object], str] = {
                executor.submit(invoke, name): name
                for name in stage
            }
            pending = set(futures)
            stage_order = {name: index for index, name in enumerate(stage)}
            failure: FlowExecutionError | FlowCancelledError | None = None
            while pending:
                if cancel_event is not None and cancel_event.is_set():
                    stop_event.set()
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
                    except FlowCancelledError as error:
                        stop_event.set()
                        failure = error
                        break
                    except BaseException as error:
                        stop_event.set()
                        failure = FlowExecutionError(name, error)
                        break
                if failure is not None:
                    break
            if (
                failure is None
                and cancel_event is not None
                and cancel_event.is_set()
            ):
                stop_event.set()
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
                    except FlowCancelledError:
                        # Cooperative peers may stop after another action fails.
                        continue
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
    cooperative: bool = False,
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

        def invoke(values, token=None, *, dependencies=dependencies, action=action):
            arguments = tuple(values[dependency] for dependency in dependencies)
            if cooperative:
                return action(*arguments, token)
            return action(*arguments)

        wrapped[name] = invoke
    return execute_flow(
        graph,
        wrapped,
        max_workers=max_workers,
        cancel_event=cancel_event,
        cooperative=cooperative,
    )


def execute_bound_sir_flow(
    sir_module,
    flow_name: str,
    function_bindings: Mapping[str, Callable[..., object]],
    *,
    max_workers: int | None = None,
    cancel_event: Event | None = None,
    cooperative: bool = False,
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

        def invoke(values, token=None, *, binding=binding, arguments=arguments):
            inputs = tuple(
                values[item.value.producer_stage] for item in arguments
            )
            if cooperative:
                return binding(*inputs, token)
            return binding(*inputs)

        actions[stage.name] = invoke
    return execute_flow(
        graph,
        actions,
        max_workers=max_workers,
        cancel_event=cancel_event,
        cooperative=cooperative,
    )


def execute_transactional_sir_flow(
    sir_module,
    flow_name: str,
    function_bindings: Mapping[str, Callable[..., object]],
    effect_policies: Mapping[str, str],
    compensation_handlers: Mapping[str, str] | None = None,
) -> FlowExecutionResult:
    """Execute a sequential checked SIR Flow and compensate completed stages.

    Compensators receive the output produced by the stage they compensate.
    This runtime deliberately rejects parallel schedules: the current SIR
    transaction journal records completed stages in a deterministic order.
    """
    from .flow_sir import FlowSIRError, validate_sir_flow_plans
    from .transactions import (
        TransactionError,
        analyze_sir_flow_transaction_effects,
    )

    plans = validate_sir_flow_plans(sir_module)
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowSIRError(
            "transaction SIR Flow runner requires exactly one plan named "
            f"{flow_name!r}"
        )
    plan = matches[0]
    audit = analyze_sir_flow_transaction_effects(
        sir_module,
        flow_name,
        dict(effect_policies),
        dict(compensation_handlers or {}),
    )
    if not audit.rollback_policy_satisfied:
        raise TransactionError(
            "transaction rollback policy is not satisfied: "
            + "; ".join(audit.blockers)
        )
    if any(len(batch) != 1 for batch in plan.parallel_stages):
        raise TransactionError(
            "transaction Flow execution currently requires a sequential schedule"
        )
    if not isinstance(function_bindings, Mapping):
        raise TypeError("transaction SIR bindings must be a mapping")
    required_stages = tuple(
        dict.fromkeys(stage.function for stage in plan.stages)
    )
    required_handlers = tuple(dict.fromkeys(
        record.compensation for record in audit.effects
        if record.compensation is not None
    ))
    required = tuple(dict.fromkeys((*required_stages, *required_handlers)))
    missing = tuple(name for name in required if name not in function_bindings)
    extra = tuple(name for name in function_bindings if name not in required)
    if missing or extra:
        raise ValueError(
            "transaction SIR bindings must match stage and compensation functions "
            f"(missing={missing}, extra={extra})"
        )
    if any(not callable(function_bindings[name]) for name in required):
        raise TypeError("Every transaction SIR binding must be callable")

    stage_by_name = {stage.name: stage for stage in plan.stages}
    committed: dict[str, object] = {}
    completed: list[str] = []
    effects_by_stage: dict[str, list[object]] = {}
    for record in audit.effects:
        effects_by_stage.setdefault(record.stage, []).append(record)
    for stage_name, in plan.parallel_stages:
        stage = stage_by_name[stage_name]
        arguments = tuple(
            committed[arg.value.producer_stage] for arg in stage.arguments
        )
        try:
            output = function_bindings[stage.function](*arguments)
        except BaseException as cause:
            rollback_errors = []
            for completed_name in reversed(completed):
                records = effects_by_stage.get(completed_name, ())
                for record in reversed(records):
                    if record.classification != "compensatable":
                        continue
                    try:
                        function_bindings[record.compensation](
                            committed[completed_name]
                        )
                    except BaseException as rollback_error:
                        rollback_errors.append((
                            completed_name, record.effect, rollback_error,
                        ))
            raise TransactionExecutionError(
                stage_name, cause, rollback_errors, completed
            ) from cause
        committed[stage_name] = output
        completed.append(stage_name)

    return FlowExecutionResult(MappingProxyType({
        stage.name: committed[stage.name] for stage in plan.stages
    }))


__all__ = [
    "FlowAction",
    "FlowExecutionError",
    "FlowCancelledError",
    "FlowExecutionResult",
    "execute_flow",
    "execute_typed_flow",
    "execute_bound_sir_flow",
    "TransactionExecutionError",
    "execute_transactional_sir_flow",
]
