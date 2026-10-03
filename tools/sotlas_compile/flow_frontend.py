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

    def __init__(self, message: str, token=None) -> None:
        super().__init__(message)
        self.token = token


@dataclass(frozen=True)
class TypedFlowStage:
    name: str
    function: str
    dependencies: tuple[str, ...]
    input_types: tuple[object, ...]
    result_type: object
    effects: tuple[str, ...]
    token: object | None = None


@dataclass(frozen=True)
class TypedFlowPlan:
    name: str
    graph: FlowGraphPlan
    stages: tuple[TypedFlowStage, ...]
    token: object | None = None


_C11_FLOW_SCALAR_TYPES = frozenset({
    "bool", "i8", "i16", "i32", "i64", "isize",
    "u8", "u16", "u32", "u64", "usize",
    "f32", "f64",
})


def _c11_flow_value_type(type_obj, module, visiting=frozenset()) -> bool:
    """Return whether a type has a plain, ownership-free C11 Flow ABI value."""
    if (
        getattr(type_obj, "name", None) in _C11_FLOW_SCALAR_TYPES
        and not getattr(type_obj, "pointer", False)
        and not getattr(type_obj, "is_array", False)
        and not getattr(type_obj, "is_reference", False)
        and not getattr(type_obj, "is_fn_ptr", False)
        and getattr(type_obj, "ownership_domain", None) is None
    ):
        return True
    if (
        type_obj is None
        or getattr(type_obj, "pointer", False)
        or getattr(type_obj, "is_array", False)
        or getattr(type_obj, "is_reference", False)
        or getattr(type_obj, "is_fn_ptr", False)
        or getattr(type_obj, "ownership_domain", None) is not None
    ):
        return False
    name = getattr(type_obj, "name", None)
    if not isinstance(name, str) or name in visiting:
        return False
    struct = next(
        (item for item in getattr(module, "structs", ()) if item.name == name),
        None,
    )
    if (
        struct is None
        or getattr(struct, "is_sole", False)
        or getattr(struct, "is_register", False)
        or "@repr(C)" not in tuple(getattr(struct, "attributes", ()))
        or not getattr(struct, "fields", ())
        or any(
            getattr(field, "bit_width", None) is not None
            for field in struct.fields
        )
        or any(
            attribute == "@packed" or attribute.startswith("@aligned(")
            for attribute in tuple(getattr(struct, "attributes", ()))
        )
    ):
        return False
    return all(
        _c11_flow_value_type(field.type, module, visiting | {name})
        for field in struct.fields
    )


def _c11_flow_trivial_owner_type(type_obj, module, visiting=frozenset()) -> bool:
    """Allow a linear sole record only when its representation is inert POD."""
    if (
        type_obj is None
        or getattr(type_obj, "pointer", False)
        or getattr(type_obj, "is_array", False)
        or getattr(type_obj, "is_reference", False)
        or getattr(type_obj, "is_fn_ptr", False)
        or getattr(type_obj, "ownership_domain", None) is not None
    ):
        return False
    name = getattr(type_obj, "name", None)
    if not isinstance(name, str) or name in visiting:
        return False
    struct = next(
        (item for item in getattr(module, "structs", ()) if item.name == name),
        None,
    )
    attributes = tuple(getattr(struct, "attributes", ())) if struct else ()
    methods = tuple(getattr(struct, "methods", ()) or ()) if struct else ()
    if (
        struct is None
        or not getattr(struct, "is_sole", False)
        or "@repr(C)" not in attributes
        or not getattr(struct, "fields", ())
        or any(
            getattr(method, "name", None) in {"deinit", f"{name}_deinit"}
            for method in methods
        )
        or any(
            getattr(field, "bit_width", None) is not None
            for field in struct.fields
        )
        or any(
            attribute == "@packed" or attribute.startswith("@aligned(")
            for attribute in attributes
        )
    ):
        return False
    return all(
        _c11_flow_abi_value_type(field.type, module, visiting | {name})
        for field in struct.fields
    )


def _c11_flow_abi_value_type(type_obj, module, visiting=frozenset()) -> bool:
    """Return whether a Flow value has a certified by-value C11 ABI."""
    return _c11_flow_value_type(type_obj, module, visiting) or _c11_flow_trivial_owner_type(
        type_obj, module, visiting
    )


def _emit_c11_flow_entrypoints(module, bootstrap) -> str:
    """Emit C-callable entrypoints for verified pure Flow plans.

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
                f"Flow {plan.name!r}",
                plan.token,
            )
        order = tuple(stage for layer in layers for stage in layer)
        stages = {stage.name: stage for stage in plan.stages}
        if set(order) != set(stages) or len(order) != len(stages):
            raise FlowFrontendError(
                f"C11 Flow lowering found an inconsistent stage schedule for "
                f"{plan.name!r}", plan.token
            )
        final_stage = stages[order[-1]]

        entry_name = bootstrap._c_ident(
            f"sotlas_flow_{module.name}_{plan.name}"
        )
        outputs_name = f"{entry_name}_outputs"
        cancelable_name = f"{entry_name}_cancelable"
        dispatch_name = f"{entry_name}_dispatch"
        if entry_name in generated_names:
            raise FlowFrontendError(
                    f"multiple Flow plans map to generated C11 symbol {entry_name!r}",
                    plan.token,
            )
        generated_names.add(entry_name)
        if outputs_name in generated_names or outputs_name in used_names:
            raise FlowFrontendError(
                f"generated C11 Flow outputs symbol {outputs_name!r} collides "
                    "with a function or another Flow plan", plan.token
            )
        generated_names.add(outputs_name)
        if cancelable_name in generated_names or cancelable_name in used_names:
            raise FlowFrontendError(
                f"generated C11 Flow cancellation symbol {cancelable_name!r} "
                    "collides with a function or another Flow plan", plan.token
            )
        generated_names.add(cancelable_name)
        if dispatch_name in generated_names or dispatch_name in used_names:
            raise FlowFrontendError(
                f"generated C11 Flow dispatch symbol {dispatch_name!r} "
                    "collides with a function or another Flow plan", plan.token
            )
        generated_names.add(dispatch_name)
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
                    "incompatible function declaration", plan.token
                )
        else:
            if entry_name in used_names:
                raise FlowFrontendError(
                    f"generated C11 Flow entrypoint {entry_name!r} collides with a function",
                    plan.token,
                )
            used_names.add(entry_name)

        output_names: dict[str, str] = {}
        dispatch_output_names: dict[str, str] = {}
        output_parameters = []
        body = []
        outputs_body = []
        cancelable_body = []
        cancelable_publish = []
        dispatch_body = []
        for stage_index, stage_name in enumerate(order):
            stage = stages[stage_name]
            function = functions.get(stage.function)
            if function is None:
                raise FlowFrontendError(
                    f"C11 Flow stage {stage.name!r} has no source function",
                    stage.token,
                )
            if not _c11_flow_abi_value_type(stage.result_type, module) or any(
                not _c11_flow_abi_value_type(item, module)
                for item in stage.input_types
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not support value type in stage "
                    f"{stage.name!r}", stage.token
                )
            summary = summaries.get(stage.function)
            if (
                summary is None
                or tuple(getattr(summary, "transitive_effects", ()))
                or tuple(getattr(summary, "unresolved_calls", ()))
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering requires a proven pure stage function "
                    f"{stage.function!r}", stage.token
                )
            if _flow_function_reaches_global_access(
                function, functions, globals_, bootstrap
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not yet verify global access in "
                    f"stage function {stage.function!r}", stage.token
                )
            if any(
                attribute in {"@system", "@extern(C)"}
                for attribute in function.attributes
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not call system or foreign stage "
                    f"function {stage.function!r}", stage.token
                )
            if (
                getattr(function, "requires", None) is not None
                or getattr(function, "ensures", None) is not None
            ):
                raise FlowFrontendError(
                    f"C11 Flow lowering does not yet integrate contracts on "
                    f"stage function {stage.function!r}", stage.token
                )
            if len(function.params) != len(stage.dependencies):
                raise FlowFrontendError(
                    f"C11 Flow stage {stage.name!r} parameter count changed",
                    stage.token,
                )

            arguments = []
            for dependency in stage.dependencies:
                value_name = output_names.get(dependency)
                if value_name is None:
                    raise FlowFrontendError(
                        f"C11 Flow stage {stage.name!r} reads a dependency "
                        f"{dependency!r} before it is produced", stage.token
                    )
                arguments.append(value_name)

            value_name = bootstrap._c_ident(
                f"sotlas_flow_value_{plan.name}_{stage.name}"
            )
            call = f"{bootstrap._c_ident(stage.function)}({', '.join(arguments)})"
            dispatch_arguments = []
            for dependency in stage.dependencies:
                dispatch_dependency = dispatch_output_names.get(dependency)
                if dispatch_dependency is None:
                    raise FlowFrontendError(
                        f"C11 Flow dispatch stage {stage.name!r} reads a dependency "
                        f"{dependency!r} before it is produced", stage.token
                    )
                dispatch_arguments.append(dispatch_dependency)
            dispatch_inputs_name = bootstrap._c_ident(
                f"sotlas_flow_inputs_{plan.name}_{stage.name}"
            )
            dispatch_input_types_name = bootstrap._c_ident(
                f"sotlas_flow_input_types_{plan.name}_{stage.name}"
            )
            if dispatch_arguments:
                dispatch_body.append(
                    f"    const void *{dispatch_inputs_name}[] = {{ "
                    + ", ".join(
                        f"(const void *)&{name}" for name in dispatch_arguments
                    )
                    + " };"
                )
                dispatch_body.append(
                    f"    const char *{dispatch_input_types_name}[] = {{ "
                    + ", ".join(
                        f'\"{item.name}\"' for item in stage.input_types
                    )
                    + " };"
                )
                dispatch_inputs = dispatch_inputs_name
                dispatch_input_types = dispatch_input_types_name
            else:
                dispatch_inputs = "0"
                dispatch_input_types = "0"
            dispatch_value = bootstrap._c_ident(
                f"sotlas_flow_dispatch_value_{plan.name}_{stage.name}"
            )
            dispatch_status = bootstrap._c_ident(
                f"sotlas_flow_dispatch_status_{plan.name}_{stage.name}"
            )
            dispatch_body.extend([
                "    if (is_cancelled != 0 && is_cancelled(context)) {",
                f"        if (stopped_stage != 0) *stopped_stage = {stage_index};",
                "        return 2;",
                "    }",
                f"    {stage.result_type.c()} {dispatch_value};",
                f"    int32_t {dispatch_status} = dispatch_stage(context, "
                f"{stage_index}u, \"{stage.name}\", \"{stage.result_type.name}\", "
                f"{dispatch_input_types}, {dispatch_inputs}, "
                f"{len(dispatch_arguments)}u, "
                f"(void *)&{dispatch_value});",
                f"    if ({dispatch_status} != 0) {{",
                f"        if (stopped_stage != 0) *stopped_stage = {stage_index};",
                f"        if (stage_status != 0) *stage_status = {dispatch_status};",
                "        return 3;",
                "    }",
            ])
            dispatch_output_names[stage.name] = dispatch_value
            cancelable_body.extend([
                "    if (is_cancelled != 0 && is_cancelled(context)) {",
                f"        if (cancelled_stage != 0) *cancelled_stage = {stage_index};",
                "        return 2;",
                "    }",
            ])
            cancelable_body.append(
                f"    {stage.result_type.c()} {value_name} = {call};"
            )
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
            cancelable_publish.append(f"    *{output_parameter} = {value_name};")

        outputs_signature = ", ".join(
            f"{kind} *{name}" for kind, name in output_parameters
        )
        cancelable_signature = ", ".join([
            "int32_t (*is_cancelled)(void *)",
            "void *context",
            "int32_t *cancelled_stage",
            *(
                f"{kind} *{name}"
                for kind, name in output_parameters
            ),
        ])
        dispatch_signature = ", ".join([
            "int32_t (*dispatch_stage)(void *, uint32_t, "
            "const char *, const char *, const char *const *, "
            "const void *const *, uint32_t, void *)",
            "void *context",
            "int32_t (*is_cancelled)(void *)",
            "int32_t *stopped_stage",
            "int32_t *stage_status",
            *(
                f"{kind} *{name}"
                for kind, name in output_parameters
            ),
        ])
        emitted.extend([
            f"int32_t {dispatch_name}({dispatch_signature}) {{",
            *[
                f"    if ({name} == 0) return 1;"
                for _, name in output_parameters
            ],
            "    if (dispatch_stage == 0) return 4;",
            "    if (stopped_stage != 0) *stopped_stage = -1;",
            "    if (stage_status != 0) *stage_status = 0;",
            *dispatch_body,
            *[
                f"    *out_{bootstrap._c_ident(stage.name)} = "
                f"{dispatch_output_names[stage.name]};"
                for stage in (stages[item] for item in order)
            ],
            "    return 0;",
            "}",
            "",
            f"int32_t {cancelable_name}({cancelable_signature}) {{",
            *[
                f"    if ({name} == 0) return 1;"
                for _, name in output_parameters
            ],
            "    if (cancelled_stage != 0) *cancelled_stage = -1;",
            *cancelable_body,
            *cancelable_publish,
            "    return 0;",
            "}",
            "",
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


def validate_flow_execution_source(
    module, flow_name: str, bootstrap_module=None
) -> None:
    """Require source proofs used by both executable Flow backends.

    Typed Flow plans also support analysis of effectful/transactional graphs.
    Execution has the narrower pure-stage contract, so this check belongs at
    the runner boundary rather than in source planning.
    """
    if bootstrap_module is None:
        from . import bootstrap as bootstrap_module
    bootstrap = bootstrap_module

    plans = tuple(getattr(module, "typed_flows", ()) or ())
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise FlowFrontendError(
            f"Flow execution requires exactly one checked plan named {flow_name!r}"
        )
    functions = {function.name: function for function in module.functions}
    globals_ = {item.name for item in getattr(module, "globals", ())}
    summaries = getattr(module, "source_effect_summaries", {}) or {}
    for stage in matches[0].stages:
        function = functions.get(stage.function)
        if function is None:
            raise FlowFrontendError(
                f"Flow stage {stage.name!r} has no source function"
            )
        if any(
            attribute in {"@system", "@extern(C)"}
            for attribute in function.attributes
        ):
            raise FlowFrontendError(
                f"Flow stage {stage.name!r} cannot execute a system or foreign function"
            )
        summary = summaries.get(stage.function)
        if summary is None:
            # The older tools/ package installs the same Flow checker without
            # the production source-effects pass. Prove the small executable
            # subset directly and fail closed on constructs whose effects
            # cannot be established here.
            def children(value):
                if isinstance(value, (bootstrap.Expr, bootstrap.Stmt)):
                    return tuple(vars(value).values())
                if isinstance(value, (tuple, list)):
                    return tuple(value)
                return ()

            pending = [function]
            visited: set[str] = set()
            while pending:
                current = pending.pop()
                if current.name in visited:
                    continue
                visited.add(current.name)
                if any(
                    attribute in {"@system", "@extern(C)"}
                    for attribute in current.attributes
                ):
                    raise FlowFrontendError(
                        f"Flow stage {stage.name!r} reaches a system or foreign function"
                    )
                if (
                    getattr(current, "requires", None) is not None
                    or getattr(current, "ensures", None) is not None
                ):
                    raise FlowFrontendError(
                        f"Flow stage {stage.name!r} reaches a function with unproven contracts"
                    )
                if _flow_function_reaches_global_access(
                    current, functions, globals_, bootstrap
                ):
                    raise FlowFrontendError(
                        f"Flow stage {stage.name!r} reads or writes global state"
                    )
                stack = list(current.body)
                while stack:
                    value = stack.pop()
                    if isinstance(value, bootstrap.MethodCall) or type(value).__name__ in {
                        "Asm", "Unsafe", "Defer"
                    }:
                        raise FlowFrontendError(
                            f"Flow stage {stage.name!r} uses a construct whose effects "
                            "cannot be proven by this compiler path"
                        )
                    if isinstance(value, bootstrap.Call):
                        callee = functions.get(value.callee)
                        if callee is None:
                            raise FlowFrontendError(
                                f"Flow stage {stage.name!r} reaches unresolved call "
                                f"{value.callee!r}"
                            )
                        pending.append(callee)
                    stack.extend(children(value))
            continue
        if (
            tuple(getattr(summary, "transitive_effects", ()))
            or tuple(getattr(summary, "unresolved_calls", ()))
        ):
            raise FlowFrontendError(
                f"Flow stage {stage.name!r} requires a proven pure function"
            )
        if _flow_function_reaches_global_access(
            function, functions, globals_, bootstrap
        ):
            raise FlowFrontendError(
                f"Flow stage {stage.name!r} reads or writes global state"
            )
        if (
            getattr(function, "requires", None) is not None
            or getattr(function, "ensures", None) is not None
        ):
            raise FlowFrontendError(
                f"Flow stage {stage.name!r} has contracts not yet proven by Flow"
            )


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
            raise FlowFrontendError(
                f"flow {flow.name!r} is declared more than once", flow.token
            )
        seen_flows.add(flow.name)
        stage_names = [stage.name for stage in flow.stages]
        if len(set(stage_names)) != len(stage_names):
            seen_stage_names: set[str] = set()
            duplicate = None
            for stage in flow.stages:
                if stage.name in seen_stage_names:
                    duplicate = stage
                    break
                seen_stage_names.add(stage.name)
            raise FlowFrontendError(
                f"flow {flow.name!r} repeats a stage name",
                getattr(duplicate, "token", flow.token),
            )
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
            raise FlowFrontendError(
                f"flow {flow.name!r}: {error}", flow.token
            ) from error

        typed_stages = []
        for stage in flow.stages:
            function = functions.get(stage.function)
            if function is None:
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} references unknown function "
                    f"{stage.function!r}", stage.token
                )
            if not function.body:
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} requires a source function body",
                    stage.token,
                )
            if function.result.name == "void":
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} must return a value", stage.token
                )
            if len(function.params) != len(stage.dependencies):
                raise FlowFrontendError(
                    f"flow stage {stage.name!r} has {len(stage.dependencies)} "
                    f"dependencies but function {stage.function!r} accepts "
                    f"{len(function.params)} parameters",
                    stage.token,
                )
            input_types = []
            for dependency, (_, parameter_type) in zip(
                stage.dependencies, function.params
            ):
                producer = stage_declarations.get(dependency)
                if producer is None:
                    raise FlowFrontendError(
                        f"flow stage {stage.name!r} references unknown "
                        f"dependency {dependency!r}", stage.token
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
                        f"match dependency {dependency!r} result", stage.token
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
                    f"flow stage {stage.name!r} has unresolved call effects",
                    stage.token,
                )
            typed_stages.append(TypedFlowStage(
                stage.name, stage.function, stage.dependencies,
                tuple(input_types), function.result, effects, stage.token,
            ))
        plans.append(TypedFlowPlan(
            flow.name, graph, tuple(typed_stages), flow.token
        ))
    return tuple(plans)


def install(bootstrap) -> None:
    original_check = bootstrap.check
    original_compile_module = bootstrap.compile_module

    def check_with_flows(module, *args, **kwargs):
        result = original_check(module, *args, **kwargs)
        try:
            module.typed_flows = plan_source_flows(module, bootstrap)
        except FlowFrontendError as error:
            token = error.token
            raise bootstrap.SotlasBootstrapError(
                str(error),
                getattr(token, "line", 1),
                getattr(token, "column", 1),
                module.filename,
                module.source,
            ) from error
        return result

    bootstrap.check = check_with_flows

    def compile_serial_scalar_flows(module, *args, **kwargs):
        generated = original_compile_module(module, *args, **kwargs)
        try:
            flow_c = _emit_c11_flow_entrypoints(module, bootstrap)
        except FlowFrontendError as error:
            token = error.token
            raise bootstrap.SotlasBootstrapError(
                str(error),
                getattr(token, "line", 1),
                getattr(token, "column", 1),
                module.filename,
                module.source,
            ) from error
        return generated + ("\n" + flow_c if flow_c else "")

    bootstrap.compile_module = compile_serial_scalar_flows


__all__ = [
    "FlowFrontendError",
    "validate_flow_execution_source",
    "TypedFlowStage",
    "TypedFlowPlan",
    "plan_source_flows",
    "install",
]
