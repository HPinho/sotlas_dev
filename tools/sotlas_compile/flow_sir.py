"""Source-stable lowering records for checked Flow orchestration in SIR."""
from __future__ import annotations

from dataclasses import dataclass

from .flow_graph import certify_flow_graph


class FlowSIRError(ValueError):
    """Raised when typed Flow facts cannot be reconciled with generated SIR."""


@dataclass(frozen=True)
class FlowSIRValueRef:
    producer_stage: str
    producer_function: str
    type_name: str


@dataclass(frozen=True)
class FlowSIRArgument:
    parameter_index: int
    parameter_name: str
    type_name: str
    value: FlowSIRValueRef


@dataclass(frozen=True)
class FlowSIRStage:
    name: str
    function: str
    arguments: tuple[FlowSIRArgument, ...]
    result_type: str
    effects: tuple[str, ...]


@dataclass(frozen=True)
class FlowSIRPlan:
    name: str
    parallel_stages: tuple[tuple[str, ...], ...]
    stages: tuple[FlowSIRStage, ...]


def _source_type_name(type_info) -> str:
    name = getattr(type_info, "name", None)
    if not isinstance(name, str) or not name:
        raise FlowSIRError("Flow SIR lowering encountered a source type without a name")
    if getattr(type_info, "state_space", None) and getattr(type_info, "state_name", None):
        name = f"{name}<{type_info.state_name}>"
    if getattr(type_info, "pointer", False) or getattr(type_info, "is_reference", False):
        name += "*"
    return name


def lower_typed_flows_to_sir(typed_flows, source_module, sir_module):
    """Attach validated orchestration records to a generated canonical SIR module.

    This represents stage calls and their data dependencies at module scope. It
    does not claim that a target runtime or backend can schedule the plan yet.
    """
    plans = tuple(typed_flows or ())
    if not plans:
        if tuple(getattr(source_module, "flows", ()) or ()):
            raise FlowSIRError(
                "source Flow declarations are missing their checked plans"
            )
        sir_module.flow_plans = ()
        return ()

    source_functions = {
        function.name: function for function in source_module.functions
    }
    source_flows = {
        flow.name: flow for flow in getattr(source_module, "flows", ())
    }
    if len(source_flows) != len(getattr(source_module, "flows", ())):
        raise FlowSIRError("source Flow module contains duplicate plan names")
    sir_functions = {function.name: function for function in sir_module.functions}
    if len(sir_functions) != len(sir_module.functions):
        raise FlowSIRError("Flow SIR module contains duplicate function names")

    lowered = []
    seen_plans = set()
    for plan in plans:
        if plan.name in seen_plans:
            raise FlowSIRError(f"Flow SIR repeats plan {plan.name!r}")
        seen_plans.add(plan.name)
        source_flow = source_flows.get(plan.name)
        if source_flow is None:
            raise FlowSIRError(
                f"Flow SIR plan {plan.name!r} has no source declaration"
            )
        try:
            graph = certify_flow_graph(plan.graph.nodes, plan.graph.dependencies)
        except ValueError as error:
            raise FlowSIRError(
                f"Flow SIR plan {plan.name!r} has an invalid graph: {error}"
            ) from error
        if graph != plan.graph:
            raise FlowSIRError(f"Flow SIR plan {plan.name!r} is not canonical")

        typed_by_name = {stage.name: stage for stage in plan.stages}
        if len(typed_by_name) != len(plan.stages):
            raise FlowSIRError(f"Flow SIR plan {plan.name!r} repeats a stage")
        if set(typed_by_name) != {node.name for node in graph.nodes}:
            raise FlowSIRError(
                f"Flow SIR plan {plan.name!r} stage set differs from its graph"
            )
        source_stages = {stage.name: stage for stage in source_flow.stages}
        if len(source_stages) != len(source_flow.stages):
            raise FlowSIRError(
                f"source Flow plan {plan.name!r} repeats a stage"
            )
        if set(source_stages) != set(typed_by_name):
            raise FlowSIRError(
                f"Flow SIR plan {plan.name!r} stage set differs from its source"
            )
        source_edges = tuple(
            (edge.producer, edge.consumer) for edge in graph.dependencies
        )
        declared_edges = tuple(
            (dependency, stage.name)
            for stage in source_flow.stages
            for dependency in stage.dependencies
        )
        if source_edges != declared_edges:
            raise FlowSIRError(
                f"Flow SIR plan {plan.name!r} dependencies differ from its source"
            )
        for stage_name, declaration in source_stages.items():
            stage = typed_by_name[stage_name]
            if (
                stage.function != declaration.function
                or stage.dependencies != declaration.dependencies
            ):
                raise FlowSIRError(
                    f"Flow SIR stage {stage_name!r} differs from its source declaration"
                )

        lowered_stages = []
        for stage_name in (node.name for node in graph.nodes):
            stage = typed_by_name[stage_name]
            source_function = source_functions.get(stage.function)
            sir_function = sir_functions.get(stage.function)
            if source_function is None or sir_function is None:
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} is missing its generated SIR function"
                )
            result_type = _source_type_name(source_function.result)
            if result_type != sir_function.return_type:
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} result type differs between source and SIR"
                )
            if result_type != _source_type_name(stage.result_type):
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} typed result fact is inconsistent"
                )
            if len(source_function.params) != len(stage.dependencies):
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} dependency arity changed after checking"
                )
            if len(stage.input_types) != len(stage.dependencies):
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} checked input count changed after checking"
                )
            if len(sir_function.parameters) != len(source_function.params):
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} parameter count differs between source and SIR"
                )

            arguments = []
            for index, ((parameter_name, source_type), dependency) in enumerate(
                zip(source_function.params, stage.dependencies)
            ):
                source_type_name = _source_type_name(source_type)
                sir_parameter = sir_function.parameters[index]
                if (
                    sir_parameter.name != parameter_name
                    or sir_parameter.type_name != source_type_name
                ):
                    raise FlowSIRError(
                        f"Flow stage {stage.name!r} parameter {index} differs between source and SIR"
                    )
                if _source_type_name(stage.input_types[index]) != source_type_name:
                    raise FlowSIRError(
                        f"Flow stage {stage.name!r} checked input type changed after checking"
                    )
                producer = typed_by_name.get(dependency)
                if producer is None:
                    raise FlowSIRError(
                        f"Flow stage {stage.name!r} references missing producer {dependency!r}"
                    )
                producer_type = _source_type_name(producer.result_type)
                if producer_type != source_type_name:
                    raise FlowSIRError(
                        f"Flow stage {stage.name!r} dependency type changed after checking"
                    )
                arguments.append(FlowSIRArgument(
                    index,
                    parameter_name,
                    source_type_name,
                    FlowSIRValueRef(
                        dependency, producer.function, producer_type
                    ),
                ))

            summary = getattr(sir_function, "source_effect_summary", None)
            effects = tuple(stage.effects)
            checked_summary = (
                getattr(source_module, "source_effect_summaries", {}) or {}
            ).get(stage.function)
            if checked_summary is None:
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} has no checked source effect summary"
                )
            if effects != tuple(checked_summary.transitive_effects):
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} effects differ from checked source"
                )
            if summary is None or effects != tuple(summary.transitive_effects):
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} effects differ between checked source and SIR"
                )
            if "unknown_call" in effects:
                raise FlowSIRError(
                    f"Flow stage {stage.name!r} has unresolved call effects"
                )
            lowered_stages.append(FlowSIRStage(
                stage.name,
                stage.function,
                tuple(arguments),
                result_type,
                effects,
            ))

        lowered.append(FlowSIRPlan(
            plan.name,
            graph.parallel_stages,
            tuple(lowered_stages),
        ))

    if seen_plans != set(source_flows):
        raise FlowSIRError(
            "checked Flow plans do not cover every source declaration"
        )
    canonical = tuple(lowered)
    existing = getattr(sir_module, "flow_plans", ())
    if existing and existing != canonical:
        raise FlowSIRError("generated SIR already contains conflicting Flow plans")
    sir_module.flow_plans = canonical
    return canonical


__all__ = [
    "FlowSIRError",
    "FlowSIRValueRef",
    "FlowSIRArgument",
    "FlowSIRStage",
    "FlowSIRPlan",
    "lower_typed_flows_to_sir",
]
