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


_C11_FLOW_SCALAR_TYPES = frozenset({
    "bool", "i8", "i16", "i32", "i64", "isize",
    "u8", "u16", "u32", "u64", "usize",
    "f32", "f64",
})


def _emit_c11_flow_entrypoints(module, bootstrap) -> str:
    """Emit C-callable entrypoints for verified pure scalar Flow plans.

    C11 currently uses a deterministic serial fallback for independent stages.
    The source and reference scheduler retain the parallel layers; because every
    accepted stage is proven pure, evaluating one layer in canonical order
    preserves the result while the backend lacks a native task runtime.
    """
    plans = tuple(getattr(module, "typed_flows", ()) or ())
    if not plans:
        return ""
    functions = {function.name: function for function in module.functions}
    summaries = getattr(module, "source_effect_summaries", None) or {}
    globals_ = {item.name for item in module.globals}
    emitted = []
    used_names = set(functions)
    generated_names: set[str] = set()

    for plan in plans:
        layers = tuple(plan.graph.parallel_stages)
        if not layers or any(not layer for layer in layers):
            raise FlowFrontendError(
                f"C11 Flow lowering found an invalid stage schedule for "
                f"Flow {plan.name!r}"
            )
        order = tuple(stage for layer in layers for stage in layer)
        stages = {stage.name: stage for stage in plan.stages}
        if set(order) != set(stages) or len(order) != len(stages):
            raise FlowFrontendError(
                f"C11 Flow lowering found an inconsistent stage schedule for "
                f"{plan.name!r}"
            )
        final_stage = stages[order[-1]]

        entry_name = bootstrap._c_ident(
            f"sotlas_flow_{module.name}_{plan.name}"
        )
        outputs_name = f"{entry_name}_outputs"
        if entry_name in generated_names:
            raise FlowFrontendError(
                f"multiple Flow plans map to generated C11 symbol {entry_name!r}"
            )
        generated_names.add(entry_name)
        if outputs_name in generated_names or outputs_name in used_names:
            raise FlowFrontendError(
                f"generated C11 Flow outputs symbol {outputs_name!r} collides "
                "with a function or another Flow plan"
            )
        generated_names.add(outputs_name)
        declaration = functions.get(entry_name)
        if declaration is not None:
            if (
                declaration.body
                or "@extern(C)" not in declaration.attributes
                or declaration.params
                or not bootstrap.same_type(declaration.result, final_stage.result_type)
            ):
                raise FlowFrontendError(
                    f"generated C11 Flow entrypoint {entry_name!r} collides with an "
                    "incompatible function declaration"
                )
        else:
            if entry_name in used_names:
                raise FlowFrontendError(
                    f"generated C11 Flow entrypoint {entry_name!r} collides with a function"
                )
            used_names.add(entry_name)

        output_names: dict[str, str] = {}
        output_parameters = []
        body = []
        outputs_body = []
        for stage_name in order:
            stage = stages[stage_name]
            function = functions.get(stage.function)
            if function is None:
                raise FlowFrontendError(
                    f"C11 Flow stage {stage.name!r} has no source function"
                )
            if stage.result_type.name not in _C11_FLOW_SCALAR_TYPES or any(
                item.name not in _C11_FLOW_SCALAR_TYPES
                for item in stage.input_types
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not support value type in stage "
                    f"{stage.name!r}"
                )
            summary = summaries.get(stage.function)
            if (
                summary is None
                or tuple(getattr(summary, "transitive_effects", ()))
                or tuple(getattr(summary, "unresolved_calls", ()))
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering requires a proven pure stage function "
                    f"{stage.function!r}"
                )
            if _flow_function_reaches_global_access(
                function, functions, globals_, bootstrap
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not yet verify global access in "
                    f"stage function {stage.function!r}"
                )
            if any(
                attribute in {"@system", "@extern(C)"}
                for attribute in function.attributes
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not call system or foreign stage "
                    f"function {stage.function!r}"
                )
            if (
                getattr(function, "requires", None) is not None
                or getattr(function, "ensures", None) is not None
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not yet integrate contracts on "
                    f"stage function {stage.function!r}"
                )
            if len(function.params) != len(stage.dependencies):
                raise FlowFrontendError(
                    f"C11 Flow stage {stage.name!r} parameter count changed"
                )

            arguments = []
            for dependency in stage.dependencies:
                value_name = output_names.get(dependency)
                if value_name is None:
                    raise FlowFrontendError(
                        f"C11 Flow stage {stage.name!r} reads a dependency "
                        f"{dependency!r} before it is produced"
                    )
                arguments.append(value_name)

            value_name = bootstrap._c_ident(
                f"sotlas_flow_value_{plan.name}_{stage.name}"
            )
            call = f"{bootstrap._c_ident(stage.function)}({', '.join(arguments)})"
            body.append(
                f"    {stage.result_type.c()} {value_name} = {call};"
            )
            outputs_body.append(
                f"    {stage.result_type.c()} {value_name} = {call};"
            )
            output_names[stage.name] = value_name
            output_parameter = f"out_{bootstrap._c_ident(stage.name)}"
            output_parameters.append((stage.result_type.c(), output_parameter))
            outputs_body.append(f"    *{output_parameter} = {value_name};")

        outputs_signature = ", ".join(
            f"{kind} *{name}" for kind, name in output_parameters
        )
        emitted.extend([
            f"int32_t {outputs_name}({outputs_signature}) {{",
            *[
                f"    if ({name} == 0) return 0;"
                for _, name in output_parameters
            ],
            *outputs_body,
            "    return 1;",
            "}",
            "",
            f"{final_stage.result_type.c()} {entry_name}(void) {{",
            *body,
            f"    return {output_names[final_stage.name]};",
            "}",
            "",
        ])
    return "\n".join(emitted)


def _flow_function_reaches_global_access(function, functions, globals_, bootstrap):
    """Fail closed on globals, including through directly called helpers.

    The current source effect pass does not classify global reads and writes,
    so its empty summary alone is not a sufficient purity proof for Flow.
    """
    pending = [function]
    visited = set()

    def children(value):
        if isinstance(value, (bootstrap.Expr, bootstrap.Stmt)):
            return tuple(vars(value).values())
        if isinstance(value, (tuple, list)):
            return tuple(value)
        return ()

    while pending:
        current = pending.pop()
        if current.name in visited:
            continue
        visited.add(current.name)
        stack = list(current.body)
        while stack:
            value = stack.pop()
            if isinstance(value, bootstrap.Name) and value.value in globals_:
                return True
            if type(value).__name__ == "MethodCall":
                # Method resolution is not yet part of the Flow purity proof.
                return True
            if isinstance(value, bootstrap.Call) and value.callee in functions:
                pending.append(functions[value.callee])
            stack.extend(children(value))
    return False


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

    def compile_serial_scalar_flows(module, *args, **kwargs):
        generated = original_compile_module(module, *args, **kwargs)
        try:
            flow_c = _emit_c11_flow_entrypoints(module, bootstrap)
        except FlowFrontendError as error:
            raise bootstrap.SotlasBootstrapError(
                str(error), 1, 1, module.filename, module.source
            ) from error
        return generated + ("\n" + flow_c if flow_c else "")

    bootstrap.compile_module = compile_serial_scalar_flows


__all__ = [
    "FlowFrontendError",
    "TypedFlowStage",
    "TypedFlowPlan",
    "plan_source_flows",
    "install",
]
