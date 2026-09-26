"""Typed source declarations for the synchronous Sotlas Flow subset."""
from __future__ import annotations

from dataclasses import dataclass

from .flow_graph import (
    FlowDependency,
    FlowGraphPlan,
    FlowNode,
    certify_flow_graph,
)


class FlowFrontendError(ValueError):
    """Raised when source Flow declarations cannot be certified."""


@dataclass(frozen=True)
class TypedFlowStage:
    name: str
    function: str
    dependencies: tuple[str, ...]
    input_types: tuple[object, ...]
    result_type: object
    effects: tuple[str, ...]


@dataclass(frozen=True)
class TypedFlowPlan:
    name: str
    graph: FlowGraphPlan
    stages: tuple[TypedFlowStage, ...]


def plan_source_flows(module, bootstrap) -> tuple[TypedFlowPlan, ...]:
    """Validate source Flow DAGs and type each stage's dependency values."""
    flows = tuple(getattr(module, "flows", ()))
    if not flows:
        return ()
    functions = {function.name: function for function in module.functions}
    plans = []
    seen_flows: set[str] = set()
    for flow in flows:
        if flow.name in seen_flows:
            raise FlowFrontendError(f"flow {flow.name!r} is declared more than once")
        seen_flows.add(flow.name)
        stage_names = [stage.name for stage in flow.stages]
        if len(set(stage_names)) != len(stage_names):
            raise FlowFrontendError(f"flow {flow.name!r} repeats a stage name")
        stage_declarations = {stage.name: stage for stage in flow.stages}
        try:
            graph = certify_flow_graph(
                tuple(FlowNode(name) for name in stage_names),
                tuple(
                    FlowDependency(producer, stage.name)
                    for stage in flow.stages
                    for producer in stage.dependencies
                ),
            )
        except ValueError as error:
            raise FlowFrontendError(f"flow {flow.name!r}: {error}") from error

        typed_stages = []
        for stage in flow.stages:
            function = functions.get(stage.function)
            if function is None:
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} references unknown function "
                    f"{stage.function!r}"
                )
            if not function.body:
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} requires a source function body"
                )
            if function.result.name == "void":
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} must return a value"
                )
            if len(function.params) != len(stage.dependencies):
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} has {len(stage.dependencies)} "
                    f"dependencies but function {stage.function!r} accepts "
                    f"{len(function.params)} parameters"
                )
            input_types = []
            for dependency, (_, parameter_type) in zip(
                stage.dependencies, function.params
            ):
                producer = stage_declarations.get(dependency)
                if producer is None:
                    raise FlowFrontendError(
                        f"flow stage {stage.name!r} references unknown "
                        f"dependency {dependency!r}"
                    )
                producer_function = functions.get(producer.function)
                if producer_function is None:
                    # The graph reports the same missing function with context
                    # when its stage is visited; fail before reading its type.
                    continue
                if not bootstrap.same_type(
                    producer_function.result, parameter_type
                ):
                    raise FlowFrontendError(
                        f"flow stage {stage.name!r} parameter type does not "
                        f"match dependency {dependency!r} result"
                    )
                input_types.append(parameter_type)
            summary = (getattr(module, "source_effect_summaries", {}) or {}).get(
                stage.function
            )
            effects = tuple(
                getattr(summary, "transitive_effects", ())
            )
            if "unknown_call" in effects:
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} has unresolved call effects"
                )
            typed_stages.append(TypedFlowStage(
                stage.name, stage.function, stage.dependencies,
                tuple(input_types), function.result, effects,
            ))
        plans.append(TypedFlowPlan(flow.name, graph, tuple(typed_stages)))
    return tuple(plans)


def install(bootstrap) -> None:
    original_check = bootstrap.check
    original_compile_module = bootstrap.compile_module

    def check_with_flows(module, *args, **kwargs):
        result = original_check(module, *args, **kwargs)
        try:
            module.typed_flows = plan_source_flows(module, bootstrap)
        except FlowFrontendError as error:
            raise bootstrap.SotlasBootstrapError(
                str(error), 1, 1, module.filename, module.source
            ) from error
        return result

    bootstrap.check = check_with_flows

    def compile_without_flow_lowering(module, *args, **kwargs):
        generated = original_compile_module(module, *args, **kwargs)
        if tuple(getattr(module, "flows", ())):
            raise bootstrap.SotlasBootstrapError(
                "C11 backend does not lower source Flow declarations yet",
                1, 1, module.filename, module.source,
            )
        return generated

    bootstrap.compile_module = compile_without_flow_lowering


__all__ = [
    "FlowFrontendError",
    "TypedFlowStage",
    "TypedFlowPlan",
    "plan_source_flows",
    "install",
]
