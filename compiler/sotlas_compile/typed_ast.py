"""Phase-1 Typed AST foundation.

This module is intentionally isolated from the production bootstrap pipeline.
It materializes the *declared* semantic types that already exist on the parsed
canonical AST. Function-body expression typing is not claimed here yet.

Maturity: DECLARATIONS_ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


MATURITY = "DECLARATIONS_ONLY"


class Phase1SemanticError(ValueError):
    """Raised by isolated Phase-1 semantic validators."""


class VarState(str, Enum):
    LIVE = "LIVE"
    MOVED = "MOVED"
    MAYBE_MOVED = "MAYBE_MOVED"
    BORROWED_IMMUT = "BORROWED_IMMUT"
    BORROWED_MUT = "BORROWED_MUT"


def sole_type_names(module: TypedModule) -> frozenset[str]:
    """Return declaration names that carry exclusive sole ownership."""
    return frozenset(item.name for item in module.structs if item.is_sole)


def is_sole_type(type_info: SemanticType, module: TypedModule) -> bool:
    """Resolve a semantic type against the module's sole declarations."""
    return (
        not type_info.pointer
        and not type_info.is_reference
        and type_info.name in sole_type_names(module)
    )


def initial_ownership_state(
    type_info: SemanticType, module: TypedModule
) -> VarState | None:
    """Create ownership tracking only for declarations that are actually sole."""
    return VarState.LIVE if is_sole_type(type_info, module) else None


def require_sole_transfer(
    name: str, type_info: SemanticType, module: TypedModule
) -> VarState:
    """Validate an explicit ownership transfer target from declaration facts."""
    state = initial_ownership_state(type_info, module)
    if state is None:
        raise Phase1SemanticError(
            f"handover target {name!r} is not a sole value"
        )
    return move_state(name, state)


@dataclass(frozen=True)
class OwnershipBinding:
    name: str
    type: SemanticType
    state: VarState


@dataclass(frozen=True)
class OwnershipEnv:
    bindings: tuple[OwnershipBinding, ...] = ()

    def state_of(self, name: str) -> VarState | None:
        for binding in reversed(self.bindings):
            if binding.name == name:
                return binding.state
        return None

    def type_of(self, name: str) -> SemanticType | None:
        for binding in reversed(self.bindings):
            if binding.name == name:
                return binding.type
        return None

    def declare(
        self, name: str, type_info: SemanticType, module: TypedModule
    ) -> "OwnershipEnv":
        state = initial_ownership_state(type_info, module)
        if state is None:
            return self
        if self.state_of(name) is not None:
            raise Phase1SemanticError(
                f"ownership binding {name!r} already declared"
            )
        return OwnershipEnv(
            self.bindings + (OwnershipBinding(name, type_info, state),)
        )

    def require_live(self, name: str) -> None:
        state = self.state_of(name)
        if state is None:
            raise Phase1SemanticError(
                f"ownership binding {name!r} is not tracked"
            )
        require_live(name, state)

    def move(self, name: str) -> "OwnershipEnv":
        state = self.state_of(name)
        if state is None:
            raise Phase1SemanticError(
                f"ownership binding {name!r} is not tracked"
            )
        next_state = move_state(name, state)
        updated = []
        replaced = False
        for binding in self.bindings:
            if binding.name == name and not replaced:
                updated.append(
                    OwnershipBinding(binding.name, binding.type, next_state)
                )
                replaced = True
            else:
                updated.append(binding)
        return OwnershipEnv(tuple(updated))

    def merge(self, other: "OwnershipEnv") -> "OwnershipEnv":
        left = {binding.name: binding for binding in self.bindings}
        right = {binding.name: binding for binding in other.bindings}
        if left.keys() != right.keys():
            raise Phase1SemanticError(
                "ownership environments have incompatible bindings"
            )
        merged = []
        for binding in self.bindings:
            peer = right[binding.name]
            if binding.type != peer.type:
                raise Phase1SemanticError(
                    f"ownership binding {binding.name!r} changed type across branches"
                )
            merged.append(
                OwnershipBinding(
                    binding.name,
                    binding.type,
                    merge_branch_states(binding.state, peer.state),
                )
            )
        return OwnershipEnv(tuple(merged))


def _declared_local_type(statement) -> SemanticType | None:
    """Resolve a local declaration type without running a second typechecker.

    Explicit annotations are authoritative. For an unannotated local, the only
    inference admitted at this Phase-1 slice is a direct struct literal, whose
    declared struct name is syntactically unambiguous.
    """
    if type(statement).__name__ != "Let":
        return None
    explicit = getattr(statement, "type", None)
    if explicit is not None:
        return semantic_type(explicit)
    value = getattr(statement, "value", None)
    if type(value).__name__ == "StructLit":
        return SemanticType(getattr(value, "struct_name"))
    return None


def seed_function_ownership(
    parsed_module, typed_module: TypedModule, function_name: str
) -> OwnershipEnv:
    """Seed sole ownership for parameters and top-level locals of one function.

    This is intentionally an isolated Phase-1 adapter. It does not mutate the
    parsed module, does not walk control flow, and does not replace semantic
    checking. Nested-block dataflow is a later slice.
    """
    parsed_function = next(
        (item for item in parsed_module.functions if item.name == function_name),
        None,
    )
    typed_function = next(
        (item for item in typed_module.functions if item.name == function_name),
        None,
    )
    if parsed_function is None or typed_function is None:
        raise Phase1SemanticError(
            f"function {function_name!r} not found for ownership seeding"
        )

    env = OwnershipEnv()
    for param in typed_function.params:
        env = env.declare(param.name, param.type, typed_module)

    for statement in parsed_function.body:
        local_type = _declared_local_type(statement)
        if local_type is None:
            continue
        env = env.declare(statement.name, local_type, typed_module)
    return env


@dataclass(frozen=True)
class OwnershipEvent:
    kind: str
    name: str
    via: str


@dataclass(frozen=True)
class OwnershipTrace:
    final_env: OwnershipEnv
    events: tuple[OwnershipEvent, ...]


def _typed_function_map(module: TypedModule) -> dict[str, TypedFunction]:
    return {item.name: item for item in module.functions}


def _root_owned_name(expr) -> str | None:
    """Return the tracked owner whose field/index access depends on this expr."""
    kind = type(expr).__name__
    if kind == "Name":
        return getattr(expr, "value", None)
    if kind in ("Member", "Index"):
        return _root_owned_name(getattr(expr, "target", None))
    return None


def require_expr_ownership_live(env: OwnershipEnv, expr) -> None:
    """Reject reads through a moved or maybe-moved sole owner."""
    if expr is None:
        return
    owner = _root_owned_name(expr)
    if owner is not None and env.state_of(owner) is not None:
        env.require_live(owner)
        return

    kind = type(expr).__name__
    if kind == "Binary":
        require_expr_ownership_live(env, getattr(expr, "left", None))
        require_expr_ownership_live(env, getattr(expr, "right", None))
    elif kind == "Unary":
        require_expr_ownership_live(env, getattr(expr, "value", None))
    elif kind == "Cast":
        require_expr_ownership_live(env, getattr(expr, "expr", None))
    elif kind == "Call":
        for argument in getattr(expr, "args", ()):
            require_expr_ownership_live(env, argument)


def _move_call_arguments(
    env: OwnershipEnv,
    call,
    typed_module: TypedModule,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    callee = _typed_function_map(typed_module).get(getattr(call, "callee", ""))
    if callee is None:
        return env
    result = env
    for argument, parameter in zip(getattr(call, "args", ()), callee.params):
        if is_sole_type(parameter.type, typed_module):
            if type(argument).__name__ == "Name":
                name = argument.value
                result = result.move(name)
                events.append(OwnershipEvent("move", name, f"call:{callee.name}"))
                continue
        require_expr_ownership_live(result, argument)
    return result


def analyze_linear_function_ownership(
    parsed_module, typed_module: TypedModule, function_name: str
) -> OwnershipTrace:
    """Analyze the first SRG milestone: straight-line sole ownership.

    Supported events are parameter ownership, local sole construction,
    assignment-style moves through a let destination/source pair, by-value
    calls to known module functions, and return of a sole value. Control-flow
    statements are deliberately not consumed here; branch/loop integration is
    a later SRG milestone.
    """
    parsed_function = next(
        (item for item in parsed_module.functions if item.name == function_name),
        None,
    )
    typed_function = next(
        (item for item in typed_module.functions if item.name == function_name),
        None,
    )
    if parsed_function is None or typed_function is None:
        raise Phase1SemanticError(
            f"function {function_name!r} not found for linear ownership analysis"
        )

    env = OwnershipEnv()
    events: list[OwnershipEvent] = []
    for param in typed_function.params:
        before = env
        env = env.declare(param.name, param.type, typed_module)
        if env != before:
            events.append(OwnershipEvent("declare", param.name, "parameter"))

    for statement in parsed_function.body:
        kind = type(statement).__name__

        if kind == "Let":
            local_type = _declared_local_type(statement)
            value = getattr(statement, "value", None)
            if type(value).__name__ == "Name":
                source_name = value.value
                source_type = env.type_of(source_name)
                if source_type is not None:
                    env = env.move(source_name)
                    events.append(
                        OwnershipEvent("move", source_name, f"let:{statement.name}")
                    )
                    if local_type is None:
                        local_type = source_type
            if type(value).__name__ == "Call":
                env = _move_call_arguments(env, value, typed_module, events)
            if type(value).__name__ not in ("Name", "Call"):
                require_expr_ownership_live(env, value)
            if local_type is not None:
                before = env
                env = env.declare(statement.name, local_type, typed_module)
                if env != before:
                    events.append(
                        OwnershipEvent("declare", statement.name, "local")
                    )
            continue

        if kind == "Expression":
            value = getattr(statement, "value", None)
            if type(value).__name__ == "Call":
                env = _move_call_arguments(env, value, typed_module, events)
            continue

        if kind == "Return":
            value = getattr(statement, "value", None)
            if (
                value is not None
                and type(value).__name__ == "Name"
                and is_sole_type(typed_function.result, typed_module)
            ):
                env = env.move(value.value)
                events.append(
                    OwnershipEvent("move", value.value, "return")
                )
            continue

        if kind in ("If", "While", "Loop", "For"):
            events.append(
                OwnershipEvent("deferred-control-flow", function_name, kind)
            )

    return OwnershipTrace(env, tuple(events))


def _project_ownership_env(
    env: OwnershipEnv, names: tuple[str, ...]
) -> OwnershipEnv:
    wanted = set(names)
    return OwnershipEnv(
        tuple(binding for binding in env.bindings if binding.name in wanted)
    )


def _analyze_block_ownership(
    statements,
    env: OwnershipEnv,
    typed_module: TypedModule,
    typed_function: TypedFunction,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    """Analyze ownership events for a canonical AST block.

    Branch-local bindings are allowed while analyzing a branch but are dropped
    at the merge boundary; only bindings visible on entry participate in the
    ownership join.
    """
    result = env
    for statement in statements:
        kind = type(statement).__name__

        if kind == "Let":
            local_type = _declared_local_type(statement)
            value = getattr(statement, "value", None)
            if type(value).__name__ == "Name":
                source_name = value.value
                source_type = result.type_of(source_name)
                if source_type is not None:
                    result = result.move(source_name)
                    events.append(
                        OwnershipEvent("move", source_name, f"let:{statement.name}")
                    )
                    if local_type is None:
                        local_type = source_type
                else:
                    require_expr_ownership_live(result, value)
            elif type(value).__name__ == "Call":
                result = _move_call_arguments(
                    result, value, typed_module, events
                )
            if local_type is not None:
                before = result
                result = result.declare(
                    statement.name, local_type, typed_module
                )
                if result != before:
                    events.append(
                        OwnershipEvent("declare", statement.name, "local")
                    )
            continue

        if kind == "Expression":
            value = getattr(statement, "value", None)
            if type(value).__name__ == "Call":
                result = _move_call_arguments(
                    result, value, typed_module, events
                )
            else:
                require_expr_ownership_live(result, value)
            continue

        if kind == "Return":
            value = getattr(statement, "value", None)
            if (
                value is not None
                and type(value).__name__ == "Name"
                and is_sole_type(typed_function.result, typed_module)
            ):
                result = result.move(value.value)
                events.append(
                    OwnershipEvent("move", value.value, "return")
                )
            else:
                require_expr_ownership_live(result, value)
            continue

        if kind == "If":
            visible = tuple(binding.name for binding in result.bindings)
            then_events: list[OwnershipEvent] = []
            else_events: list[OwnershipEvent] = []
            then_env = _analyze_block_ownership(
                getattr(statement, "then_body", ()),
                result,
                typed_module,
                typed_function,
                then_events,
            )
            else_env = _analyze_block_ownership(
                getattr(statement, "else_body", ()),
                result,
                typed_module,
                typed_function,
                else_events,
            )
            then_env = _project_ownership_env(then_env, visible)
            else_env = _project_ownership_env(else_env, visible)
            result = then_env.merge(else_env)
            events.append(
                OwnershipEvent("branch", typed_function.name, "if")
            )
            events.extend(then_events)
            events.extend(else_events)
            continue

        if kind in ("While", "Loop", "For"):
            if kind == "While":
                require_expr_ownership_live(
                    result, getattr(statement, "condition", None)
                )
            elif kind == "For":
                require_expr_ownership_live(
                    result, getattr(statement, "start", None)
                )
                require_expr_ownership_live(
                    result, getattr(statement, "end", None)
                )

            visible = tuple(binding.name for binding in result.bindings)
            body_events: list[OwnershipEvent] = []
            body_env = _analyze_block_ownership(
                getattr(statement, "body", ()),
                result,
                typed_module,
                typed_function,
                body_events,
            )
            body_env = _project_ownership_env(body_env, visible)

            for name in visible:
                before = result.state_of(name)
                after = body_env.state_of(name)
                if before != after:
                    raise Phase1SemanticError(
                        f"sole value {name!r} moved inside loop without reinitialization"
                    )

            events.append(
                OwnershipEvent("loop", typed_function.name, kind)
            )
            events.extend(body_events)
            continue

    return result


def analyze_function_ownership(
    parsed_module, typed_module: TypedModule, function_name: str
) -> OwnershipTrace:
    """Analyze linear, conditional, field and loop sole ownership from the canonical AST."""
    parsed_function = next(
        (item for item in parsed_module.functions if item.name == function_name),
        None,
    )
    typed_function = next(
        (item for item in typed_module.functions if item.name == function_name),
        None,
    )
    if parsed_function is None or typed_function is None:
        raise Phase1SemanticError(
            f"function {function_name!r} not found for ownership analysis"
        )

    env = OwnershipEnv()
    events: list[OwnershipEvent] = []
    for param in typed_function.params:
        before = env
        env = env.declare(param.name, param.type, typed_module)
        if env != before:
            events.append(
                OwnershipEvent("declare", param.name, "parameter")
            )

    env = _analyze_block_ownership(
        parsed_function.body, env, typed_module, typed_function, events
    )
    return OwnershipTrace(env, tuple(events))


@dataclass(frozen=True)
class OwnershipParamContract:
    name: str
    takes_ownership: bool


@dataclass(frozen=True)
class OwnershipFunctionSummary:
    name: str
    params: tuple[OwnershipParamContract, ...]
    returns_sole: bool
    calls: tuple[str, ...]


@dataclass(frozen=True)
class OwnershipModuleAnalysis:
    summaries: tuple[OwnershipFunctionSummary, ...]
    traces: tuple[tuple[str, OwnershipTrace], ...]


def _collect_calls_from_expr(expr, calls: list[str]) -> None:
    if expr is None:
        return
    kind = type(expr).__name__
    if kind == "Call":
        callee = getattr(expr, "callee", None)
        if isinstance(callee, str):
            calls.append(callee)
        for argument in getattr(expr, "args", ()):
            _collect_calls_from_expr(argument, calls)
        return
    if kind == "Binary":
        _collect_calls_from_expr(getattr(expr, "left", None), calls)
        _collect_calls_from_expr(getattr(expr, "right", None), calls)
    elif kind == "Unary":
        _collect_calls_from_expr(getattr(expr, "value", None), calls)
    elif kind == "Cast":
        _collect_calls_from_expr(getattr(expr, "expr", None), calls)
    elif kind == "Index":
        _collect_calls_from_expr(getattr(expr, "target", None), calls)
        _collect_calls_from_expr(getattr(expr, "index", None), calls)
    elif kind == "Member":
        _collect_calls_from_expr(getattr(expr, "target", None), calls)


def _collect_calls_from_statements(statements, calls: list[str]) -> None:
    for statement in statements:
        kind = type(statement).__name__
        if kind in ("Let", "Expression", "Return"):
            _collect_calls_from_expr(getattr(statement, "value", None), calls)
        elif kind == "If":
            _collect_calls_from_expr(getattr(statement, "condition", None), calls)
            _collect_calls_from_statements(
                getattr(statement, "then_body", ()), calls
            )
            _collect_calls_from_statements(
                getattr(statement, "else_body", ()), calls
            )
        elif kind in ("While", "Loop", "For"):
            _collect_calls_from_expr(
                getattr(statement, "condition", None), calls
            )
            _collect_calls_from_expr(getattr(statement, "start", None), calls)
            _collect_calls_from_expr(getattr(statement, "end", None), calls)
            _collect_calls_from_statements(
                getattr(statement, "body", ()), calls
            )


def summarize_module_ownership(
    parsed_module, typed_module: TypedModule
) -> tuple[OwnershipFunctionSummary, ...]:
    """Build explicit ownership contracts and call edges for module functions."""
    parsed_functions = {item.name: item for item in parsed_module.functions}
    summaries = []
    for function in typed_module.functions:
        calls: list[str] = []
        parsed = parsed_functions.get(function.name)
        if parsed is not None:
            _collect_calls_from_statements(parsed.body, calls)
        summaries.append(
            OwnershipFunctionSummary(
                name=function.name,
                params=tuple(
                    OwnershipParamContract(
                        param.name,
                        is_sole_type(param.type, typed_module),
                    )
                    for param in function.params
                ),
                returns_sole=is_sole_type(function.result, typed_module),
                calls=tuple(calls),
            )
        )
    return tuple(summaries)


def analyze_module_ownership(
    parsed_module, typed_module: TypedModule
) -> OwnershipModuleAnalysis:
    """Run isolated ownership analysis across every canonical module function."""
    summaries = summarize_module_ownership(parsed_module, typed_module)
    traces = tuple(
        (
            function.name,
            analyze_function_ownership(
                parsed_module, typed_module, function.name
            ),
        )
        for function in typed_module.functions
    )
    return OwnershipModuleAnalysis(summaries, traces)


@dataclass(frozen=True)
class TypedExprNode:
    kind: str
    type: SemanticType
    label: str | None = None


@dataclass(frozen=True)
class TypedStmtNode:
    kind: str
    name: str | None
    type: SemanticType | None
    expr: TypedExprNode | None


@dataclass(frozen=True)
class TypedFunctionBody:
    name: str
    statements: tuple[TypedStmtNode, ...]
    maturity: str = "LINEAR_BODY_TYPES"


def _number_type(value: str) -> SemanticType:
    integer_suffixes = (
        "usize", "isize", "u64", "i64", "u32", "i32",
        "u16", "i16", "u8", "i8",
    )
    float_suffixes = ("f32", "f64")
    for suffix in integer_suffixes + float_suffixes:
        if value.endswith(suffix):
            return SemanticType(suffix)
    if "." in value or "e" in value.lower():
        return SemanticType("f64")
    return SemanticType("i64")


def infer_expression_type(
    expr,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> TypedExprNode:
    """Infer a conservative semantic type for a canonical expression.

    This intentionally covers only declarations whose type is locally
    demonstrable. Unsupported expressions fail closed instead of fabricating
    a type.
    """
    kind = type(expr).__name__

    if kind == "Name":
        name = getattr(expr, "value")
        if name in env:
            return TypedExprNode(kind, env[name], name)
        for item in typed_module.globals:
            if item.name == name:
                return TypedExprNode(kind, item.type, name)
        raise Phase1SemanticError(f"cannot type unresolved name {name!r}")

    if kind == "Number":
        value = getattr(expr, "value")
        return TypedExprNode(kind, _number_type(value), value)

    if kind == "Boolean":
        return TypedExprNode(kind, SemanticType("bool"), str(getattr(expr, "value")))

    if kind == "StringLit":
        return TypedExprNode(kind, SemanticType("str", pointer=True), None)

    if kind == "StructLit":
        name = getattr(expr, "struct_name")
        known = {item.name for item in typed_module.structs}
        if name not in known:
            raise Phase1SemanticError(f"unknown struct literal type {name!r}")
        return TypedExprNode(kind, SemanticType(name), name)

    if kind == "Cast":
        return TypedExprNode(
            kind,
            semantic_type(getattr(expr, "target_type")),
            None,
        )

    if kind == "Member":
        target = infer_expression_type(
            getattr(expr, "target"), env, typed_module
        )
        struct = next(
            (item for item in typed_module.structs if item.name == target.type.name),
            None,
        )
        if struct is None:
            raise Phase1SemanticError(
                f"member access requires known struct type, got {target.type.name}"
            )
        field_name = getattr(expr, "field")
        field = next(
            (item for item in struct.fields if item.name == field_name),
            None,
        )
        if field is None:
            raise Phase1SemanticError(
                f"struct {struct.name!r} has no field {field_name!r}"
            )
        return TypedExprNode(kind, field.type, field_name)

    if kind == "Call":
        callee = getattr(expr, "callee")
        function = next(
            (item for item in typed_module.functions if item.name == callee),
            None,
        )
        if function is None:
            raise Phase1SemanticError(f"cannot type unknown call {callee!r}")
        if len(getattr(expr, "args", ())) != len(function.params):
            raise Phase1SemanticError(
                f"call {callee!r} has wrong argument count"
            )
        for argument, parameter in zip(getattr(expr, "args", ()), function.params):
            argument_type = infer_expression_type(
                argument, env, typed_module
            ).type
            if argument_type != parameter.type:
                raise Phase1SemanticError(
                    f"call {callee!r} argument type mismatch: "
                    f"expected {parameter.type.name}, got {argument_type.name}"
                )
        return TypedExprNode(kind, function.result, callee)

    if kind == "Binary":
        left = infer_expression_type(getattr(expr, "left"), env, typed_module)
        right = infer_expression_type(getattr(expr, "right"), env, typed_module)
        op = getattr(expr, "op")
        if op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
            return TypedExprNode(kind, SemanticType("bool"), op)
        if left.type != right.type:
            raise Phase1SemanticError(
                f"binary operator {op!r} type mismatch: "
                f"{left.type.name} vs {right.type.name}"
            )
        return TypedExprNode(kind, left.type, op)

    raise Phase1SemanticError(
        f"expression typing not implemented for {kind}"
    )


def build_linear_typed_body(
    parsed_module, typed_module: TypedModule, function_name: str
) -> TypedFunctionBody:
    """Materialize typed facts for top-level straight-line statements only."""
    parsed_function = next(
        (item for item in parsed_module.functions if item.name == function_name),
        None,
    )
    typed_function = next(
        (item for item in typed_module.functions if item.name == function_name),
        None,
    )
    if parsed_function is None or typed_function is None:
        raise Phase1SemanticError(
            f"function {function_name!r} not found for body typing"
        )

    env = {param.name: param.type for param in typed_function.params}
    statements: list[TypedStmtNode] = []

    for statement in parsed_function.body:
        kind = type(statement).__name__
        if kind == "Let":
            expr = infer_expression_type(
                getattr(statement, "value"), env, typed_module
            )
            explicit = getattr(statement, "type", None)
            declared = semantic_type(explicit) if explicit is not None else expr.type
            if declared != expr.type:
                raise Phase1SemanticError(
                    f"let {statement.name!r} type mismatch: "
                    f"declared {declared.name}, got {expr.type.name}"
                )
            env[statement.name] = declared
            statements.append(
                TypedStmtNode("Let", statement.name, declared, expr)
            )
            continue

        if kind == "Return":
            value = getattr(statement, "value", None)
            expr = (
                infer_expression_type(value, env, typed_module)
                if value is not None
                else None
            )
            actual = expr.type if expr is not None else SemanticType("void")
            if actual != typed_function.result:
                raise Phase1SemanticError(
                    f"return type mismatch in {function_name!r}: "
                    f"expected {typed_function.result.name}, got {actual.name}"
                )
            statements.append(
                TypedStmtNode("Return", None, actual, expr)
            )
            continue

        if kind == "Expression":
            expr = infer_expression_type(
                getattr(statement, "value"), env, typed_module
            )
            statements.append(
                TypedStmtNode("Expression", None, expr.type, expr)
            )
            continue

        raise Phase1SemanticError(
            f"body typing not implemented for statement {kind}"
        )

    return TypedFunctionBody(function_name, tuple(statements))


def apply_ownership_moves(
    env: OwnershipEnv, names: tuple[str, ...] | list[str]
) -> OwnershipEnv:
    """Apply a deterministic sequence of sole transfers to an environment."""
    result = env
    for name in names:
        result = result.move(name)
    return result


def merge_conditional_ownership(
    base: OwnershipEnv,
    then_moves: tuple[str, ...] | list[str],
    else_moves: tuple[str, ...] | list[str] = (),
) -> OwnershipEnv:
    """Model an if/else ownership join from an immutable incoming state."""
    then_env = apply_ownership_moves(base, then_moves)
    else_env = apply_ownership_moves(base, else_moves)
    return then_env.merge(else_env)


def validate_loop_ownership(
    base: OwnershipEnv, body_moves: tuple[str, ...] | list[str]
) -> OwnershipEnv:
    """Reject a sole move that could repeat on a subsequent loop iteration.

    Phase 1 currently has no reinitialization model, so any tracked move in a
    repeating body is rejected rather than unsafely pretending the next
    iteration starts LIVE.
    """
    probe = base
    for name in body_moves:
        state = probe.state_of(name)
        if state is None:
            raise Phase1SemanticError(
                f"ownership binding {name!r} is not tracked"
            )
        require_live(name, state)
        raise Phase1SemanticError(
            f"sole value {name!r} moved inside loop without reinitialization"
        )
    return base


def require_live(name: str, state: VarState) -> None:
    """Reject uses of values whose ownership is no longer definitely live."""
    if state is VarState.LIVE:
        return
    if state is VarState.MOVED:
        raise Phase1SemanticError(
            f"use of sole value {name!r} after move"
        )
    if state is VarState.MAYBE_MOVED:
        raise Phase1SemanticError(
            f"use of sole value {name!r} after conditional move"
        )
    raise Phase1SemanticError(
        f"use of sole value {name!r} while borrowed as {state.value}"
    )


def move_state(name: str, state: VarState) -> VarState:
    """Apply one ownership transfer to a sole variable state."""
    require_live(name, state)
    return VarState.MOVED


def merge_branch_states(left: VarState, right: VarState) -> VarState:
    """Join ownership facts at an if/else convergence point."""
    if left is right:
        return left
    moved_like = {VarState.MOVED, VarState.MAYBE_MOVED}
    if left in moved_like or right in moved_like:
        return VarState.MAYBE_MOVED
    if {left, right} == {VarState.BORROWED_IMMUT, VarState.LIVE}:
        return VarState.LIVE
    if {left, right} == {VarState.BORROWED_MUT, VarState.LIVE}:
        return VarState.LIVE
    if left in (VarState.BORROWED_IMMUT, VarState.BORROWED_MUT) or right in (
        VarState.BORROWED_IMMUT, VarState.BORROWED_MUT
    ):
        raise Phase1SemanticError(
            f"incompatible ownership branch states: {left.value} vs {right.value}"
        )
    return VarState.LIVE


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int


@dataclass(frozen=True)
class SemanticType:
    name: str
    pointer: bool = False
    mutable: bool = False
    is_array: bool = False
    array_size: int | str = 0
    is_reference: bool = False


@dataclass(frozen=True)
class TypedField:
    name: str
    type: SemanticType


@dataclass(frozen=True)
class TypedStruct:
    name: str
    fields: tuple[TypedField, ...]
    public: bool
    attributes: tuple[str, ...]
    is_sole: bool


@dataclass(frozen=True)
class TypedParam:
    name: str
    type: SemanticType


@dataclass(frozen=True)
class TypedFunction:
    name: str
    params: tuple[TypedParam, ...]
    result: SemanticType
    public: bool
    attributes: tuple[str, ...]


@dataclass(frozen=True)
class TypedGlobal:
    name: str
    type: SemanticType
    public: bool
    is_const: bool
    is_mut: bool


@dataclass(frozen=True)
class TypedModule:
    name: str
    structs: tuple[TypedStruct, ...]
    globals: tuple[TypedGlobal, ...]
    functions: tuple[TypedFunction, ...]
    filename: str | None
    maturity: str = MATURITY


def semantic_type(type_obj) -> SemanticType:
    """Freeze a canonical bootstrap Type without changing the source AST."""
    return SemanticType(
        name=type_obj.name,
        pointer=bool(type_obj.pointer),
        mutable=bool(type_obj.mutable),
        is_array=bool(type_obj.is_array),
        array_size=type_obj.array_size,
        is_reference=bool(getattr(type_obj, "is_reference", False)),
    )


_INTEGER_WIDTHS = {
    "u8": (8, False), "u16": (16, False), "u32": (32, False),
    "u64": (64, False), "usize": (64, False),
    "i8": (8, True), "i16": (16, True), "i32": (32, True),
    "i64": (64, True), "isize": (64, True),
}


def integer_bounds(type_info: SemanticType) -> tuple[int, int]:
    """Return the inclusive range for a fixed-width Sotlas integer type."""
    try:
        width, signed = _INTEGER_WIDTHS[type_info.name]
    except KeyError as error:
        raise Phase1SemanticError(
            f"integer type expected, got {type_info.name}"
        ) from error
    if signed:
        limit = 1 << (width - 1)
        return -limit, limit - 1
    return 0, (1 << width) - 1


def validate_integer_value(value: int, type_info: SemanticType) -> None:
    """Reject a compile-time integer value that cannot fit its declared type."""
    lower, upper = integer_bounds(type_info)
    if value < lower or value > upper:
        raise Phase1SemanticError(
            f"integer value {value} out of range for {type_info.name} "
            f"[{lower}, {upper}]"
        )


def validate_no_recursive_value_types(module: TypedModule) -> None:
    """Reject infinitely-sized struct cycles while allowing indirection.

    Only by-value struct fields participate in the dependency graph. Raw
    pointers and references break the size cycle and are therefore permitted.
    Fixed arrays remain by-value and keep their element-type dependency.
    """
    structs = {item.name: item for item in module.structs}
    edges: dict[str, tuple[str, ...]] = {}
    for item in module.structs:
        deps = []
        for field in item.fields:
            type_info = field.type
            if type_info.pointer or type_info.is_reference:
                continue
            if type_info.name in structs:
                deps.append(type_info.name)
        edges[item.name] = tuple(deps)

    visiting: list[str] = []
    active: set[str] = set()
    done: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name in active:
            start = visiting.index(name)
            cycle = visiting[start:] + [name]
            raise Phase1SemanticError(
                "recursive value type: " + " -> ".join(cycle)
            )
        active.add(name)
        visiting.append(name)
        for dependency in edges.get(name, ()):
            visit(dependency)
        visiting.pop()
        active.remove(name)
        done.add(name)

    for name in edges:
        visit(name)


def build_declaration_typed_ast(module) -> TypedModule:
    """Build the Phase-1 declaration snapshot from an already parsed module.

    Callers remain responsible for running the canonical semantic checker first.
    This function neither calls nor replaces bootstrap.check and never mutates
    the production AST.
    """
    return TypedModule(
        name=module.name,
        structs=tuple(
            TypedStruct(
                name=item.name,
                fields=tuple(
                    TypedField(field.name, semantic_type(field.type))
                    for field in item.fields
                ),
                public=bool(item.public),
                attributes=tuple(item.attributes),
                is_sole=bool(getattr(item, "is_sole", False)),
            )
            for item in module.structs
        ),
        globals=tuple(
            TypedGlobal(
                name=item.name,
                type=semantic_type(item.type),
                public=bool(item.public),
                is_const=bool(item.is_const),
                is_mut=bool(item.is_mut),
            )
            for item in module.globals
        ),
        functions=tuple(
            TypedFunction(
                name=item.name,
                params=tuple(
                    TypedParam(name, semantic_type(type_obj))
                    for name, type_obj in item.params
                ),
                result=semantic_type(item.result),
                public=bool(item.public),
                attributes=tuple(item.attributes),
            )
            for item in module.functions
        ),
        filename=module.filename,
    )


__all__ = [
    "MATURITY", "Phase1SemanticError", "VarState", "sole_type_names", "is_sole_type",
    "initial_ownership_state", "require_sole_transfer", "OwnershipBinding", "OwnershipEnv",
    "seed_function_ownership", "OwnershipEvent", "OwnershipTrace",
    "require_expr_ownership_live",
    "analyze_linear_function_ownership", "analyze_function_ownership",
    "OwnershipParamContract", "OwnershipFunctionSummary",
    "OwnershipModuleAnalysis", "summarize_module_ownership",
    "analyze_module_ownership", "TypedExprNode", "TypedStmtNode",
    "TypedFunctionBody", "infer_expression_type", "build_linear_typed_body",
    "apply_ownership_moves", "merge_conditional_ownership",
    "validate_loop_ownership", "require_live", "move_state", "merge_branch_states",
    "SourceSpan", "SemanticType",
    "TypedField", "TypedStruct",
    "TypedParam", "TypedFunction", "TypedGlobal", "TypedModule",
    "semantic_type", "integer_bounds", "validate_integer_value",
    "validate_no_recursive_value_types",
    "build_declaration_typed_ast",
]