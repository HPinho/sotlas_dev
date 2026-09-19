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


def _referenced_owned_names(
    env: OwnershipEnv, expr
) -> frozenset[str]:
    """Collect tracked sole owners referenced by an expression."""
    if expr is None:
        return frozenset()

    names: set[str] = set()
    owner = _root_owned_name(expr)
    if owner is not None and env.state_of(owner) is not None:
        names.add(owner)

    kind = type(expr).__name__
    if kind == "Binary":
        children = (
            getattr(expr, "left", None),
            getattr(expr, "right", None),
        )
    elif kind in ("Unary", "MoveExpr", "UnsafeExpr"):
        children = (getattr(expr, "value", None),)
    elif kind == "Cast":
        children = (getattr(expr, "expr", None),)
    elif kind == "Index":
        children = (
            getattr(expr, "target", None),
            getattr(expr, "index", None),
        )
    elif kind == "Member":
        children = (getattr(expr, "target", None),)
    elif kind == "Call":
        children = tuple(getattr(expr, "args", ()))
    elif kind == "MethodCall":
        children = (
            getattr(expr, "target", None),
            *tuple(getattr(expr, "args", ())),
        )
    elif kind == "ArrayLit":
        children = tuple(getattr(expr, "elements", ()))
    elif kind == "StructLit":
        children = tuple(
            value for _, value in getattr(expr, "fields", ())
        )
    elif kind == "IfExpr":
        children = (
            getattr(expr, "condition", None),
            getattr(expr, "then_expr", None),
            getattr(expr, "else_expr", None),
        )
    elif kind == "TryExpr":
        children = (getattr(expr, "expr", None),)
    else:
        children = ()

    for child in children:
        names.update(_referenced_owned_names(env, child))
    return frozenset(names)


def _statement_referenced_owned_names(
    env: OwnershipEnv, statement
) -> frozenset[str]:
    """Collect outer sole owners captured by a statement tree."""
    if statement is None:
        return frozenset()

    kind = type(statement).__name__
    names: set[str] = set()

    if kind in ("Let", "Return", "Expression"):
        names.update(
            _referenced_owned_names(env, getattr(statement, "value", None))
        )
    elif kind == "Assign":
        names.update(
            _referenced_owned_names(env, getattr(statement, "target", None))
        )
        names.update(
            _referenced_owned_names(env, getattr(statement, "value", None))
        )
    elif kind in ("If", "While"):
        names.update(
            _referenced_owned_names(env, getattr(statement, "condition", None))
        )
    elif kind == "For":
        names.update(
            _referenced_owned_names(env, getattr(statement, "start", None))
        )
        names.update(
            _referenced_owned_names(env, getattr(statement, "end", None))
        )
    elif kind == "Asm":
        for expr in getattr(statement, "outputs", ()):
            names.update(_referenced_owned_names(env, expr))
        for expr in getattr(statement, "inputs", ()):
            names.update(_referenced_owned_names(env, expr))
    elif kind == "Defer":
        deferred = getattr(statement, "value", None)
        if type(deferred).__name__ == "Assign":
            names.update(_statement_referenced_owned_names(env, deferred))
        else:
            names.update(_referenced_owned_names(env, deferred))

    body_attrs = {
        "If": ("then_body", "else_body"),
        "While": ("body",),
        "Loop": ("body",),
        "For": ("body",),
        "Unsafe": ("body",),
        "Defer": ("body",),
    }
    for attr in body_attrs.get(kind, ()):
        for nested in getattr(statement, attr, ()) or ():
            names.update(_statement_referenced_owned_names(env, nested))

    return frozenset(names)


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
    elif kind in ("Unary", "MoveExpr"):
        require_expr_ownership_live(env, getattr(expr, "value", None))
    elif kind == "Cast":
        require_expr_ownership_live(env, getattr(expr, "expr", None))
    elif kind == "TryExpr":
        require_expr_ownership_live(env, getattr(expr, "expr", None))
    elif kind == "Call":
        for argument in getattr(expr, "args", ()):
            require_expr_ownership_live(env, argument)
    elif kind == "MethodCall":
        require_expr_ownership_live(env, getattr(expr, "target", None))
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
            moved_argument = argument
            if type(argument).__name__ == "MoveExpr":
                moved_argument = getattr(argument, "value", None)
            if type(moved_argument).__name__ == "Name":
                name = moved_argument.value
                result = result.move(name)
                events.append(OwnershipEvent("move", name, f"call:{callee.name}"))
                continue
        require_expr_ownership_live(result, argument)
    return result


def _move_method_call_arguments(
    env: OwnershipEnv,
    call,
    typed_module: TypedModule,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    target_type = getattr(call, "target_type", None)
    owner_name = getattr(target_type, "name", None)
    method_name = getattr(call, "method", "")
    if not owner_name or not method_name:
        require_expr_ownership_live(env, getattr(call, "target", None))
        for argument in getattr(call, "args", ()):
            require_expr_ownership_live(env, argument)
        return env

    callee_name = f"{owner_name}_{method_name}"
    callee = _typed_function_map(typed_module).get(callee_name)
    if callee is None:
        require_expr_ownership_live(env, getattr(call, "target", None))
        for argument in getattr(call, "args", ()):
            require_expr_ownership_live(env, argument)
        return env

    result = env
    require_expr_ownership_live(result, getattr(call, "target", None))
    user_params = callee.params[1:] if callee.params else ()
    for argument, parameter in zip(getattr(call, "args", ()), user_params):
        if is_sole_type(parameter.type, typed_module):
            moved_argument = argument
            if type(argument).__name__ == "MoveExpr":
                moved_argument = getattr(argument, "value", None)
            if type(moved_argument).__name__ == "Name":
                name = moved_argument.value
                result = result.move(name)
                events.append(
                    OwnershipEvent("move", name, f"method:{callee.name}")
                )
                continue
        require_expr_ownership_live(result, argument)
    return result


def _move_try_wrapped_call_arguments(
    env: OwnershipEnv,
    expr,
    typed_module: TypedModule,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    """Apply call ownership effects hidden behind one or more try operators."""
    inner = expr
    while type(inner).__name__ == "TryExpr":
        inner = getattr(inner, "expr", None)

    if type(inner).__name__ == "Call":
        return _move_call_arguments(env, inner, typed_module, events)
    if type(inner).__name__ == "MethodCall":
        return _move_method_call_arguments(env, inner, typed_module, events)

    require_expr_ownership_live(env, expr)
    return env


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
            moved_value = (
                getattr(value, "value", None)
                if type(value).__name__ == "MoveExpr"
                else value
            )
            if type(moved_value).__name__ == "Name":
                source_name = moved_value.value
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
            elif type(value).__name__ == "MethodCall":
                env = _move_method_call_arguments(
                    env, value, typed_module, events
                )
            if type(value).__name__ not in (
                "Name", "MoveExpr", "Call", "MethodCall"
            ):
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
            elif type(value).__name__ == "MethodCall":
                env = _move_method_call_arguments(
                    env, value, typed_module, events
                )
            else:
                require_expr_ownership_live(env, value)
            continue

        if kind == "Return":
            value = getattr(statement, "value", None)
            if (
                value is not None
                and type(
                    getattr(value, "value", None)
                    if type(value).__name__ == "MoveExpr"
                    else value
                ).__name__ == "Name"
                and is_sole_type(typed_function.result, typed_module)
            ):
                moved_value = (
                    getattr(value, "value")
                    if type(value).__name__ == "MoveExpr"
                    else value
                )
                env = env.move(moved_value.value)
                events.append(
                    OwnershipEvent("move", moved_value.value, "return")
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


def _statement_definitely_terminates(statement) -> bool:
    """Return whether one statement prevents fallthrough in its block."""
    kind = type(statement).__name__
    if kind in ("Return", "Break", "Continue"):
        return True
    if kind == "Unsafe":
        return _block_definitely_terminates(
            getattr(statement, "body", ())
        )
    if kind == "If":
        else_body = getattr(statement, "else_body", ())
        return bool(else_body) and _block_definitely_terminates(
            getattr(statement, "then_body", ())
        ) and _block_definitely_terminates(else_body)
    return False


def _block_definitely_terminates(statements) -> bool:
    """Return whether control cannot fall through the canonical AST block."""
    for statement in statements:
        if _statement_definitely_terminates(statement):
            return True
    return False


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
            moved_value = (
                getattr(value, "value", None)
                if type(value).__name__ == "MoveExpr"
                else value
            )
            if type(moved_value).__name__ == "Name":
                source_name = moved_value.value
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
            elif type(value).__name__ == "MethodCall":
                result = _move_method_call_arguments(
                    result, value, typed_module, events
                )
            elif type(value).__name__ == "TryExpr":
                result = _move_try_wrapped_call_arguments(
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
            elif type(value).__name__ == "MethodCall":
                result = _move_method_call_arguments(
                    result, value, typed_module, events
                )
            elif type(value).__name__ == "TryExpr":
                result = _move_try_wrapped_call_arguments(
                    result, value, typed_module, events
                )
            else:
                require_expr_ownership_live(result, value)
            continue

        if kind == "Assign":
            target = getattr(statement, "target", None)
            value = getattr(statement, "value", None)
            target_name = (
                getattr(target, "value", None)
                if type(target).__name__ == "Name"
                else None
            )
            target_is_owned = (
                target_name is not None
                and result.state_of(target_name) is not None
            )

            if target_is_owned:
                result.require_live(target_name)
            elif type(target).__name__ in ("Member", "Index"):
                require_expr_ownership_live(result, target)

            moved_value = (
                getattr(value, "value", None)
                if type(value).__name__ == "MoveExpr"
                else value
            )
            if type(moved_value).__name__ == "Name":
                source_name = moved_value.value
                source_type = result.type_of(source_name)
                if source_type is not None:
                    if not target_is_owned:
                        raise Phase1SemanticError(
                            "sole assignment requires a direct owned target"
                        )
                    if source_name == target_name:
                        raise Phase1SemanticError(
                            f"sole value {source_name!r} cannot be assigned to itself"
                        )
                    result = result.move(source_name)
                    events.append(
                        OwnershipEvent(
                            "move", source_name, f"assign:{target_name}"
                        )
                    )
                else:
                    require_expr_ownership_live(result, value)
            elif type(value).__name__ == "Call":
                result = _move_call_arguments(
                    result, value, typed_module, events
                )
            elif type(value).__name__ == "MethodCall":
                result = _move_method_call_arguments(
                    result, value, typed_module, events
                )
            elif type(value).__name__ == "TryExpr":
                result = _move_try_wrapped_call_arguments(
                    result, value, typed_module, events
                )
            else:
                require_expr_ownership_live(result, value)
            continue

        if kind == "Return":
            value = getattr(statement, "value", None)
            if (
                value is not None
                and type(
                    getattr(value, "value", None)
                    if type(value).__name__ == "MoveExpr"
                    else value
                ).__name__ == "Name"
                and is_sole_type(typed_function.result, typed_module)
            ):
                moved_value = (
                    getattr(value, "value")
                    if type(value).__name__ == "MoveExpr"
                    else value
                )
                result = result.move(moved_value.value)
                events.append(
                    OwnershipEvent("move", moved_value.value, "return")
                )
            elif type(value).__name__ == "Call":
                result = _move_call_arguments(
                    result, value, typed_module, events
                )
            elif type(value).__name__ == "MethodCall":
                result = _move_method_call_arguments(
                    result, value, typed_module, events
                )
            elif type(value).__name__ == "TryExpr":
                result = _move_try_wrapped_call_arguments(
                    result, value, typed_module, events
                )
            else:
                require_expr_ownership_live(result, value)
            break

        if kind in ("Break", "Continue"):
            events.append(
                OwnershipEvent(
                    "control",
                    typed_function.name,
                    kind.lower(),
                )
            )
            break

        if kind == "If":
            visible = tuple(binding.name for binding in result.bindings)
            then_body = getattr(statement, "then_body", ())
            else_body = getattr(statement, "else_body", ())
            then_events: list[OwnershipEvent] = []
            else_events: list[OwnershipEvent] = []
            then_env = _analyze_block_ownership(
                then_body,
                result,
                typed_module,
                typed_function,
                then_events,
            )
            else_env = _analyze_block_ownership(
                else_body,
                result,
                typed_module,
                typed_function,
                else_events,
            )
            then_env = _project_ownership_env(then_env, visible)
            else_env = _project_ownership_env(else_env, visible)
            then_terminates = _block_definitely_terminates(then_body)
            else_terminates = _block_definitely_terminates(else_body)

            if then_terminates and not else_terminates:
                result = else_env
            elif else_terminates and not then_terminates:
                result = then_env
            else:
                result = then_env.merge(else_env)

            events.append(
                OwnershipEvent("branch", typed_function.name, "if")
            )
            events.extend(then_events)
            events.extend(else_events)
            if then_terminates and else_terminates:
                break
            continue

        if kind == "Unsafe":
            visible = tuple(binding.name for binding in result.bindings)
            body_events: list[OwnershipEvent] = []
            body_env = _analyze_block_ownership(
                getattr(statement, "body", ()),
                result,
                typed_module,
                typed_function,
                body_events,
            )
            result = _project_ownership_env(body_env, visible)
            events.append(
                OwnershipEvent("unsafe", typed_function.name, "block")
            )
            events.extend(body_events)
            continue

        if kind == "Asm":
            operands = (
                *tuple(getattr(statement, "outputs", ())),
                *tuple(getattr(statement, "inputs", ())),
            )
            for operand in operands:
                if (
                    type(operand).__name__ == "MoveExpr"
                    and _referenced_owned_names(result, operand)
                ):
                    raise Phase1SemanticError(
                        "inline asm cannot transfer sole ownership"
                    )
                require_expr_ownership_live(result, operand)

            events.append(
                OwnershipEvent("asm", typed_function.name, "operands")
            )
            continue

        if kind == "Defer":
            visible = tuple(binding.name for binding in result.bindings)
            captured = _statement_referenced_owned_names(result, statement)
            deferred_body = getattr(statement, "body", None)
            deferred_value = getattr(statement, "value", None)
            deferred_events: list[OwnershipEvent] = []

            if deferred_body is not None:
                deferred_env = _analyze_block_ownership(
                    deferred_body,
                    result,
                    typed_module,
                    typed_function,
                    deferred_events,
                )
                deferred_env = _project_ownership_env(
                    deferred_env, visible
                )
                via = "block"
            elif type(deferred_value).__name__ == "Assign":
                deferred_env = _analyze_block_ownership(
                    (deferred_value,),
                    result,
                    typed_module,
                    typed_function,
                    deferred_events,
                )
                via = "assign"
            elif type(deferred_value).__name__ == "Call":
                deferred_env = _move_call_arguments(
                    result,
                    deferred_value,
                    typed_module,
                    deferred_events,
                )
                via = "call"
            elif type(deferred_value).__name__ == "MethodCall":
                deferred_env = _move_method_call_arguments(
                    result,
                    deferred_value,
                    typed_module,
                    deferred_events,
                )
                via = "method"
            elif type(deferred_value).__name__ == "TryExpr":
                deferred_env = _move_try_wrapped_call_arguments(
                    result,
                    deferred_value,
                    typed_module,
                    deferred_events,
                )
                via = "try"
            else:
                require_expr_ownership_live(result, deferred_value)
                deferred_env = result
                via = "expression"

            for name in captured:
                before = result.state_of(name)
                after = deferred_env.state_of(name)
                if before is after:
                    raise Phase1SemanticError(
                        f"defer captures sole value {name!r} without ownership transfer"
                    )

            result = deferred_env
            events.append(
                OwnershipEvent("defer", typed_function.name, via)
            )
            events.extend(deferred_events)
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
    elif kind in ("Unary", "MoveExpr"):
        _collect_calls_from_expr(getattr(expr, "value", None), calls)
    elif kind == "Cast":
        _collect_calls_from_expr(getattr(expr, "expr", None), calls)
    elif kind == "TryExpr":
        _collect_calls_from_expr(getattr(expr, "expr", None), calls)
    elif kind == "Index":
        _collect_calls_from_expr(getattr(expr, "target", None), calls)
        _collect_calls_from_expr(getattr(expr, "index", None), calls)
    elif kind == "Member":
        _collect_calls_from_expr(getattr(expr, "target", None), calls)
    elif kind == "MethodCall":
        target_type = getattr(expr, "target_type", None)
        owner_name = getattr(target_type, "name", None)
        method_name = getattr(expr, "method", None)
        if owner_name and method_name:
            calls.append(f"{owner_name}_{method_name}")
        _collect_calls_from_expr(getattr(expr, "target", None), calls)
        for argument in getattr(expr, "args", ()):
            _collect_calls_from_expr(argument, calls)


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
    body: tuple["TypedStmtNode", ...] = ()
    else_body: tuple["TypedStmtNode", ...] = ()
    extra_expr: TypedExprNode | None = None


@dataclass(frozen=True)
class TypedFunctionBody:
    name: str
    statements: tuple[TypedStmtNode, ...]
    maturity: str = "STRUCTURED_BODY_TYPES"


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


def _integer_constant_value(expr) -> int | None:
    """Return a compile-time integer value for simple literal expressions."""
    kind = type(expr).__name__
    if kind == "Number":
        raw = getattr(expr, "value")
        suffixes = (
            "usize", "isize", "u64", "i64", "u32", "i32",
            "u16", "i16", "u8", "i8", "f32", "f64",
        )
        for suffix in suffixes:
            if raw.endswith(suffix):
                raw = raw[:-len(suffix)]
                break
        if "." in raw or "e" in raw.lower():
            return None
        try:
            return int(raw, 0)
        except ValueError:
            return None
    if kind == "Unary" and getattr(expr, "op", None) == "-":
        inner = _integer_constant_value(getattr(expr, "value", None))
        return -inner if inner is not None else None
    return None


def _is_unsuffixed_integer_literal_expr(expr) -> bool:
    kind = type(expr).__name__
    if kind == "Unary" and getattr(expr, "op", None) == "-":
        expr = getattr(expr, "value", None)
        kind = type(expr).__name__
    if kind != "Number":
        return False
    raw = getattr(expr, "value")
    suffixes = (
        "usize", "isize", "u64", "i64", "u32", "i32",
        "u16", "i16", "u8", "i8", "f32", "f64",
    )
    return (
        not any(raw.endswith(suffix) for suffix in suffixes)
        and "." not in raw
        and "e" not in raw.lower()
    )


def _contextual_integer_literal(
    expr,
    inferred: TypedExprNode,
    expected: SemanticType,
) -> TypedExprNode:
    """Contextualize an unsuffixed integer literal to an expected integer type.

    Explicit suffixes remain authoritative. Contextual conversion is accepted
    only when the literal value fits the destination type exactly.
    """
    if inferred.type == expected:
        return inferred
    if expected.pointer or expected.is_array or expected.name not in _INTEGER_WIDTHS:
        return inferred
    if not _is_unsuffixed_integer_literal_expr(expr):
        return inferred

    value = _integer_constant_value(expr)
    if value is None:
        return inferred
    validate_integer_value(value, expected)
    return TypedExprNode(inferred.kind, expected, inferred.label)


def _contextualize_expression(
    expr,
    inferred: TypedExprNode,
    expected: SemanticType,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> TypedExprNode:
    """Apply only explicit Phase-1 contextual typing rules."""
    integer = _contextual_integer_literal(expr, inferred, expected)
    if integer.type == expected:
        return integer

    if type(expr).__name__ != "ArrayLit" or not expected.is_array:
        return inferred

    elements = tuple(getattr(expr, "elements", ()))
    expected_elem = expected.elem_type or SemanticType(
        expected.name,
        pointer=expected.pointer,
        mutable=expected.mutable,
    )
    actual_size = (
        getattr(expr, "repeat_size")
        if getattr(expr, "is_repeat", False)
        else len(elements)
    )
    if str(actual_size) != str(expected.array_size):
        raise Phase1SemanticError(
            f"array length mismatch: expected {expected.array_size}, got {actual_size}"
        )

    if not elements:
        raise Phase1SemanticError(
            "cannot contextualize empty array literal"
        )

    for element in elements:
        element_type = infer_expression_type(
            element, env, typed_module
        )
        contextual = _contextual_integer_literal(
            element, element_type, expected_elem
        )
        if contextual.type != expected_elem:
            raise Phase1SemanticError(
                f"array element type mismatch: expected {expected_elem.name}, "
                f"got {contextual.type.name}"
            )

    return TypedExprNode("ArrayLit", expected, "array")


_TRY_RESULT_PAYLOADS = {
    "ResultU32": "u32",
    "ResultI32": "i32",
}


def _try_payload_type(type_info: SemanticType) -> SemanticType:
    """Resolve the payload type of the concrete pre-generic Result ABI.

    Phase 1 recognizes only Result wrappers that exist in stdlib/core/result.sotlas.
    Unknown shapes fail closed instead of inheriting bootstrap's legacy u32 fallback.
    """
    if type_info.pointer or type_info.is_array or type_info.is_reference:
        raise Phase1SemanticError(
            f"try operator requires Result value, got {type_info.name}"
        )
    payload_name = _TRY_RESULT_PAYLOADS.get(type_info.name)
    if payload_name is None:
        raise Phase1SemanticError(
            f"try operator requires Result value, got {type_info.name}"
        )
    return SemanticType(payload_name)


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

    if kind == "CharLit":
        return TypedExprNode(kind, SemanticType("u8"), getattr(expr, "value"))

    if kind == "NullLit":
        return TypedExprNode(kind, SemanticType("null", pointer=True), None)

    if kind == "StringLit":
        return TypedExprNode(kind, SemanticType("str", pointer=True), None)

    if kind == "UnsafeExpr":
        inner = infer_expression_type(
            getattr(expr, "value"), env, typed_module
        )
        return TypedExprNode(kind, inner.type, inner.label)

    if kind == "MoveExpr":
        inner_expr = getattr(expr, "value")
        inner = infer_expression_type(inner_expr, env, typed_module)
        if not is_sole_type(inner.type, typed_module):
            raise Phase1SemanticError(
                f"move requires sole value, got {inner.type.name}"
            )
        if type(inner_expr).__name__ != "Name":
            raise Phase1SemanticError(
                "move currently requires a direct sole binding"
            )
        return TypedExprNode(kind, inner.type, getattr(inner_expr, "value"))

    if kind == "EnumAccess":
        enum_name = getattr(expr, "enum_name")
        variant_name = getattr(expr, "variant")
        enum = next(
            (item for item in typed_module.enums if item.name == enum_name),
            None,
        )
        if enum is None:
            raise Phase1SemanticError(
                f"unknown enum type {enum_name!r}"
            )
        if not any(item.name == variant_name for item in enum.variants):
            raise Phase1SemanticError(
                f"enum {enum_name!r} has no variant {variant_name!r}"
            )
        return TypedExprNode(
            kind,
            SemanticType(enum_name),
            f"{enum_name}::{variant_name}",
        )

    if kind == "Unary":
        inner = infer_expression_type(
            getattr(expr, "value"), env, typed_module
        )
        op = getattr(expr, "op")
        if op == "*":
            if not inner.type.pointer:
                raise Phase1SemanticError(
                    f"cannot dereference non-pointer type {inner.type.name}"
                )
            return TypedExprNode(
                kind,
                SemanticType(
                    inner.type.name,
                    pointer=False,
                    mutable=False,
                    is_reference=False,
                ),
                op,
            )
        if op == "&":
            return TypedExprNode(
                kind,
                SemanticType(
                    inner.type.name,
                    pointer=True,
                    mutable=inner.type.mutable,
                ),
                op,
            )
        if op == "!":
            if inner.type != SemanticType("bool"):
                raise Phase1SemanticError(
                    f"logical not requires bool, got {inner.type.name}"
                )
            return TypedExprNode(kind, SemanticType("bool"), op)
        if op == "~":
            if inner.type.pointer or inner.type.name not in _INTEGER_WIDTHS:
                raise Phase1SemanticError(
                    f"bitwise not requires integer, got {inner.type.name}"
                )
            return TypedExprNode(kind, inner.type, op)
        if op == "-":
            signed_numeric_types = {
                "i8", "i16", "i32", "i64", "isize", "f32", "f64"
            }
            if (
                inner.type.pointer
                or inner.type.name not in signed_numeric_types
            ):
                raise Phase1SemanticError(
                    "unary minus requires signed integer or float, got "
                    f"{inner.type.name}"
                )
            return TypedExprNode(kind, inner.type, op)
        raise Phase1SemanticError(f"unsupported unary operator {op!r}")

    if kind == "ArrayLit":
        elements = tuple(getattr(expr, "elements", ()))
        if not elements:
            raise Phase1SemanticError(
                "cannot infer type of empty array literal"
            )
        first = infer_expression_type(elements[0], env, typed_module)
        for element in elements[1:]:
            current = infer_expression_type(element, env, typed_module)
            if current.type != first.type:
                raise Phase1SemanticError(
                    f"array literal element type mismatch: "
                    f"{first.type.name} vs {current.type.name}"
                )
        size = (
            getattr(expr, "repeat_size")
            if getattr(expr, "is_repeat", False)
            else len(elements)
        )
        array_type = SemanticType(
            first.type.name,
            pointer=first.type.pointer,
            mutable=first.type.mutable,
            is_array=True,
            array_size=size,
            is_reference=False,
            elem_type=first.type,
        )
        return TypedExprNode(kind, array_type, "array")

    if kind == "Index":
        target = infer_expression_type(
            getattr(expr, "target"), env, typed_module
        )
        index = infer_expression_type(
            getattr(expr, "index"), env, typed_module
        )
        integer_types = {
            "u8", "u16", "u32", "u64", "usize",
            "i8", "i16", "i32", "i64", "isize",
        }
        if index.type.pointer or index.type.name not in integer_types:
            raise Phase1SemanticError(
                f"array index must be integer, got {index.type.name}"
            )

        if target.type.is_array:
            element_type = target.type.elem_type
            if element_type is None:
                element_type = SemanticType(
                    target.type.name,
                    pointer=target.type.pointer,
                    mutable=target.type.mutable,
                )
            index_expr = getattr(expr, "index")
            if isinstance(target.type.array_size, int):
                value = _integer_constant_value(index_expr)
                if value is not None and (
                    value < 0 or value >= target.type.array_size
                ):
                    raise Phase1SemanticError(
                        f"array index {value} out of bounds for length "
                        f"{target.type.array_size}"
                    )
            return TypedExprNode(kind, element_type, "index")

        if target.type.pointer:
            return TypedExprNode(
                kind,
                SemanticType(
                    target.type.name,
                    mutable=target.type.mutable,
                ),
                "index",
            )

        raise Phase1SemanticError(
            f"indexing requires array or pointer, got {target.type.name}"
        )

    if kind == "IfExpr":
        condition = infer_expression_type(
            getattr(expr, "condition"), env, typed_module
        )
        if condition.type != SemanticType("bool"):
            raise Phase1SemanticError(
                f"if expression condition must be bool, got {condition.type.name}"
            )
        then_expr = infer_expression_type(
            getattr(expr, "then_expr"), env, typed_module
        )
        else_expr = infer_expression_type(
            getattr(expr, "else_expr"), env, typed_module
        )
        if then_expr.type != else_expr.type:
            raise Phase1SemanticError(
                f"if expression branch type mismatch: "
                f"{then_expr.type.name} vs {else_expr.type.name}"
            )
        return TypedExprNode(kind, then_expr.type, "if")

    if kind == "StructLit":
        name = getattr(expr, "struct_name")
        struct = next(
            (item for item in typed_module.structs if item.name == name),
            None,
        )
        if struct is None:
            raise Phase1SemanticError(f"unknown struct literal type {name!r}")

        declared_fields = {field.name for field in struct.fields}
        seen_fields: set[str] = set()
        for field_name, field_expr in getattr(expr, "fields", ()):
            if field_name in seen_fields:
                raise Phase1SemanticError(
                    f"duplicate field {field_name!r} in struct literal {name!r}"
                )
            if field_name not in declared_fields:
                raise Phase1SemanticError(
                    f"unknown field {field_name!r} in struct literal {name!r}"
                )
            seen_fields.add(field_name)
            field = next(item for item in struct.fields if item.name == field_name)
            inferred = infer_expression_type(field_expr, env, typed_module)
            contextual = _contextualize_expression(
                field_expr, inferred, field.type, env, typed_module
            )
            if contextual.type != field.type:
                raise Phase1SemanticError(
                    f"struct literal {name!r} field {field_name!r} type mismatch: "
                    f"expected {field.type.name}, got {contextual.type.name}"
                )

        missing = declared_fields - seen_fields
        if missing:
            ordered = ", ".join(sorted(missing))
            raise Phase1SemanticError(
                f"missing field(s) in struct literal {name!r}: {ordered}"
            )
        return TypedExprNode(kind, SemanticType(name), name)

    if kind == "Cast":
        source = infer_expression_type(
            getattr(expr, "expr"), env, typed_module
        )
        target = semantic_type(getattr(expr, "target_type"))

        if source.type == target:
            return TypedExprNode(kind, target, "cast")

        integer_names = set(_INTEGER_WIDTHS)
        numeric_names = integer_names | {"f32", "f64"}
        source_numeric = (
            not source.type.pointer
            and not source.type.is_array
            and source.type.name in numeric_names
        )
        target_numeric = (
            not target.pointer
            and not target.is_array
            and target.name in numeric_names
        )
        if source_numeric and target_numeric:
            return TypedExprNode(kind, target, "cast")

        if source.type.name == "null" and target.pointer:
            return TypedExprNode(kind, target, "cast")

        if source.type.pointer and target.pointer:
            return TypedExprNode(kind, target, "cast")

        source_integer = (
            not source.type.pointer
            and not source.type.is_array
            and source.type.name in integer_names
        )
        target_integer = (
            not target.pointer
            and not target.is_array
            and target.name in integer_names
        )
        if (source_integer and target.pointer) or (
            source.type.pointer and target_integer
        ):
            # Legality and safety are separate. The canonical safety pass still
            # requires lexical unsafe for creating a raw pointer from an integer
            # or reference; this node only records that the explicit cast shape
            # is a supported systems conversion.
            return TypedExprNode(kind, target, "cast")

        raise Phase1SemanticError(
            f"invalid cast from {source.type.name} to {target.name}"
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

    if kind == "MethodCall":
        target_expr = getattr(expr, "target")
        target = infer_expression_type(target_expr, env, typed_module)
        method_name = getattr(expr, "method")
        owner_name = target.type.name
        method = next(
            (
                item for item in typed_module.functions
                if item.name == f"{owner_name}_{method_name}"
            ),
            None,
        )
        if method is None:
            raise Phase1SemanticError(
                f"cannot type unknown method {owner_name}.{method_name}"
            )

        params = method.params
        if not params:
            raise Phase1SemanticError(
                f"method {owner_name}.{method_name} has no self parameter"
            )

        self_param = params[0].type
        if self_param.name != owner_name:
            raise Phase1SemanticError(
                f"method {owner_name}.{method_name} has incompatible self type "
                f"{self_param.name}"
            )
        if target.type.pointer and not self_param.pointer:
            raise Phase1SemanticError(
                f"method {owner_name}.{method_name} expects value self, got pointer"
            )

        arguments = tuple(getattr(expr, "args", ()))
        user_params = params[1:]
        if len(arguments) != len(user_params):
            raise Phase1SemanticError(
                f"method {owner_name}.{method_name} has wrong argument count"
            )

        for argument, parameter in zip(arguments, user_params):
            inferred = infer_expression_type(argument, env, typed_module)
            contextual = _contextualize_expression(
                argument, inferred, parameter.type, env, typed_module
            )
            if contextual.type != parameter.type:
                raise Phase1SemanticError(
                    f"method {owner_name}.{method_name} argument type mismatch: "
                    f"expected {parameter.type.name}, got {contextual.type.name}"
                )

        return TypedExprNode(
            kind,
            method.result,
            f"{owner_name}.{method_name}",
        )

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
            inferred = infer_expression_type(argument, env, typed_module)
            contextual = _contextualize_expression(
                argument, inferred, parameter.type, env, typed_module
            )
            if contextual.type != parameter.type:
                raise Phase1SemanticError(
                    f"call {callee!r} argument type mismatch: "
                    f"expected {parameter.type.name}, got {contextual.type.name}"
                )
        return TypedExprNode(kind, function.result, callee)

    if kind == "TryExpr":
        inner = infer_expression_type(
            getattr(expr, "expr"), env, typed_module
        )
        payload = _try_payload_type(inner.type)
        return TypedExprNode(kind, payload, "?")

    if kind == "Binary":
        left_expr = getattr(expr, "left")
        right_expr = getattr(expr, "right")
        left = infer_expression_type(left_expr, env, typed_module)
        right = infer_expression_type(right_expr, env, typed_module)
        op = getattr(expr, "op")

        if left.type != right.type:
            right = _contextual_integer_literal(
                right_expr, right, left.type
            )
        if left.type != right.type:
            left = _contextual_integer_literal(
                left_expr, left, right.type
            )

        integer_names = set(_INTEGER_WIDTHS)
        numeric_names = integer_names | {"f32", "f64"}

        if op in ("&&", "||"):
            if left.type != SemanticType("bool") or right.type != SemanticType("bool"):
                raise Phase1SemanticError(
                    f"logical operator {op!r} requires bool operands"
                )
            return TypedExprNode(kind, SemanticType("bool"), op)

        if op in ("==", "!="):
            pointer_null = (
                (left.type.pointer and right.type.name == "null")
                or (right.type.pointer and left.type.name == "null")
            )
            if left.type != right.type and not pointer_null:
                raise Phase1SemanticError(
                    f"comparison operator {op!r} type mismatch: "
                    f"{left.type.name} vs {right.type.name}"
                )
            return TypedExprNode(kind, SemanticType("bool"), op)

        if op in ("<", "<=", ">", ">="):
            if (
                left.type.pointer or right.type.pointer
                or left.type.name not in numeric_names
                or right.type.name not in numeric_names
            ):
                raise Phase1SemanticError(
                    f"relational operator {op!r} requires numeric operands"
                )
            if left.type != right.type:
                raise Phase1SemanticError(
                    f"relational operator {op!r} type mismatch: "
                    f"{left.type.name} vs {right.type.name}"
                )
            return TypedExprNode(kind, SemanticType("bool"), op)

        if op in ("+", "-", "*", "/", "%"):
            if (
                left.type.pointer or right.type.pointer
                or left.type.name not in numeric_names
                or right.type.name not in numeric_names
            ):
                raise Phase1SemanticError(
                    f"arithmetic operator {op!r} requires numeric operands"
                )
            if left.type != right.type:
                raise Phase1SemanticError(
                    f"binary operator {op!r} type mismatch: "
                    f"{left.type.name} vs {right.type.name}"
                )
            if op in ("/", "%") and left.type.name in integer_names:
                divisor = _integer_constant_value(right_expr)
                if divisor == 0:
                    operation = "division" if op == "/" else "modulo"
                    raise Phase1SemanticError(
                        f"integer {operation} by zero is not allowed"
                    )
            if op in ("+", "-", "*") and left.type.name in integer_names:
                left_value = _integer_constant_value(left_expr)
                right_value = _integer_constant_value(right_expr)
                if left_value is not None and right_value is not None:
                    if op == "+":
                        constant_value = left_value + right_value
                    elif op == "-":
                        constant_value = left_value - right_value
                    else:
                        constant_value = left_value * right_value
                    validate_integer_value(constant_value, left.type)
            return TypedExprNode(kind, left.type, op)

        if op in ("&", "|", "^"):
            if (
                left.type.pointer or right.type.pointer
                or left.type.name not in integer_names
                or right.type.name not in integer_names
            ):
                raise Phase1SemanticError(
                    f"bitwise operator {op!r} requires integer operands"
                )
            if left.type != right.type:
                raise Phase1SemanticError(
                    f"binary operator {op!r} type mismatch: "
                    f"{left.type.name} vs {right.type.name}"
                )
            return TypedExprNode(kind, left.type, op)

        if op in ("<<", ">>"):
            if (
                left.type.pointer or right.type.pointer
                or left.type.name not in integer_names
                or right.type.name not in integer_names
            ):
                raise Phase1SemanticError(
                    f"shift operator {op!r} requires integer operands"
                )
            shift = _integer_constant_value(right_expr)
            if shift is not None:
                width, _ = _INTEGER_WIDTHS[left.type.name]
                if shift < 0 or shift >= width:
                    raise Phase1SemanticError(
                        f"shift count {shift} out of range for "
                        f"{left.type.name} width {width}"
                    )
            return TypedExprNode(kind, left.type, op)

        raise Phase1SemanticError(f"unsupported binary operator {op!r}")

    raise Phase1SemanticError(
        f"expression typing not implemented for {kind}"
    )



def _try_result_types(
    expr,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> tuple[SemanticType, ...]:
    """Collect Result wrapper types propagated by nested try expressions."""
    if expr is None:
        return ()

    kind = type(expr).__name__
    nested: list[SemanticType] = []

    if kind == "TryExpr":
        inner_expr = getattr(expr, "expr")
        inner = infer_expression_type(inner_expr, env, typed_module)
        _try_payload_type(inner.type)
        nested.append(inner.type)
        nested.extend(_try_result_types(inner_expr, env, typed_module))
        return tuple(nested)

    if kind == "Binary":
        children = (getattr(expr, "left", None), getattr(expr, "right", None))
    elif kind in ("Unary", "MoveExpr", "UnsafeExpr"):
        children = (getattr(expr, "value", None),)
    elif kind == "Cast":
        children = (getattr(expr, "expr", None),)
    elif kind == "Index":
        children = (getattr(expr, "target", None), getattr(expr, "index", None))
    elif kind == "Member":
        children = (getattr(expr, "target", None),)
    elif kind == "Call":
        children = tuple(getattr(expr, "args", ()))
    elif kind == "MethodCall":
        children = (
            getattr(expr, "target", None),
            *tuple(getattr(expr, "args", ())),
        )
    elif kind == "ArrayLit":
        children = tuple(getattr(expr, "elements", ()))
    elif kind == "StructLit":
        children = tuple(value for _, value in getattr(expr, "fields", ()))
    elif kind == "IfExpr":
        children = (
            getattr(expr, "condition", None),
            getattr(expr, "then_expr", None),
            getattr(expr, "else_expr", None),
        )
    else:
        children = ()

    for child in children:
        nested.extend(_try_result_types(child, env, typed_module))
    return tuple(nested)


def _validate_try_propagation(
    expr,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
    typed_function: TypedFunction,
) -> None:
    """Require every try expression to propagate through a compatible result."""
    for result_type in _try_result_types(expr, env, typed_module):
        if result_type != typed_function.result:
            raise Phase1SemanticError(
                f"try operator in {typed_function.name!r} requires enclosing "
                f"function to return {result_type.name}, got "
                f"{typed_function.result.name}"
            )


def _validate_statement_try_propagation(
    statement,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
    typed_function: TypedFunction,
) -> None:
    """Validate direct expressions owned by one statement before body typing."""
    kind = type(statement).__name__
    expressions = []

    if kind in ("Let", "Return", "Expression"):
        expressions.append(getattr(statement, "value", None))
    elif kind == "Assign":
        expressions.extend(
            (getattr(statement, "target", None), getattr(statement, "value", None))
        )
    elif kind in ("If", "While"):
        expressions.append(getattr(statement, "condition", None))
    elif kind == "For":
        expressions.extend(
            (getattr(statement, "start", None), getattr(statement, "end", None))
        )
    elif kind == "Asm":
        expressions.extend(getattr(statement, "outputs", ()))
        expressions.extend(getattr(statement, "inputs", ()))
    elif kind == "Defer":
        deferred = getattr(statement, "value", None)
        if type(deferred).__name__ == "Assign":
            expressions.extend(
                (getattr(deferred, "target", None), getattr(deferred, "value", None))
            )
        else:
            expressions.append(deferred)

    for expr in expressions:
        _validate_try_propagation(
            expr, env, typed_module, typed_function
        )


def infer_assignment_target_type(
    target,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> TypedExprNode:
    """Resolve a writable target's semantic type without inventing lvalue rules."""
    kind = type(target).__name__
    if kind == "Name":
        name = getattr(target, "value")
        if name not in env:
            raise Phase1SemanticError(
                f"assignment target {name!r} is not a local binding"
            )
        return TypedExprNode(kind, env[name], name)
    if kind in ("Member", "Index"):
        return infer_expression_type(target, env, typed_module)
    raise Phase1SemanticError(
        f"assignment target typing not implemented for {kind}"
    )


def _build_typed_block(
    statements,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
    typed_function: TypedFunction,
) -> tuple[TypedStmtNode, ...]:
    typed_statements: list[TypedStmtNode] = []

    for statement in statements:
        kind = type(statement).__name__
        _validate_statement_try_propagation(
            statement, env, typed_module, typed_function
        )

        if kind == "Let":
            expr = infer_expression_type(
                getattr(statement, "value"), env, typed_module
            )
            explicit = getattr(statement, "type", None)
            declared = semantic_type(explicit) if explicit is not None else expr.type
            if explicit is not None:
                expr = _contextualize_expression(
                    getattr(statement, "value"),
                    expr,
                    declared,
                    env,
                    typed_module,
                )
            if declared != expr.type:
                raise Phase1SemanticError(
                    f"let {statement.name!r} type mismatch: "
                    f"declared {declared.name}, got {expr.type.name}"
                )
            env[statement.name] = declared
            typed_statements.append(
                TypedStmtNode("Let", statement.name, declared, expr)
            )
            continue

        if kind == "Assign":
            target = infer_assignment_target_type(
                getattr(statement, "target"), env, typed_module
            )
            value_expr = getattr(statement, "value")
            value = infer_expression_type(
                value_expr, env, typed_module
            )
            value = _contextualize_expression(
                value_expr, value, target.type, env, typed_module
            )
            if target.type != value.type:
                raise Phase1SemanticError(
                    f"assignment type mismatch for {target.label!r}: "
                    f"expected {target.type.name}, got {value.type.name}"
                )
            typed_statements.append(
                TypedStmtNode("Assign", target.label, target.type, value)
            )
            continue

        if kind == "Return":
            value = getattr(statement, "value", None)
            expr = (
                infer_expression_type(value, env, typed_module)
                if value is not None
                else None
            )
            if expr is not None:
                expr = _contextualize_expression(
                    value,
                    expr,
                    typed_function.result,
                    env,
                    typed_module,
                )
            actual = expr.type if expr is not None else SemanticType("void")
            if actual != typed_function.result:
                raise Phase1SemanticError(
                    f"return type mismatch in {typed_function.name!r}: "
                    f"expected {typed_function.result.name}, got {actual.name}"
                )
            typed_statements.append(
                TypedStmtNode("Return", None, actual, expr)
            )
            continue

        if kind == "Expression":
            expr = infer_expression_type(
                getattr(statement, "value"), env, typed_module
            )
            typed_statements.append(
                TypedStmtNode("Expression", None, expr.type, expr)
            )
            continue

        if kind == "If":
            condition = infer_expression_type(
                getattr(statement, "condition"), env, typed_module
            )
            if condition.type != SemanticType("bool"):
                raise Phase1SemanticError(
                    f"if condition must be bool, got {condition.type.name}"
                )
            then_body = _build_typed_block(
                getattr(statement, "then_body", ()),
                dict(env),
                typed_module,
                typed_function,
            )
            else_body = _build_typed_block(
                getattr(statement, "else_body", ()),
                dict(env),
                typed_module,
                typed_function,
            )
            typed_statements.append(
                TypedStmtNode(
                    "If", None, SemanticType("bool"), condition,
                    then_body, else_body,
                )
            )
            continue

        if kind == "While":
            condition = infer_expression_type(
                getattr(statement, "condition"), env, typed_module
            )
            if condition.type != SemanticType("bool"):
                raise Phase1SemanticError(
                    f"while condition must be bool, got {condition.type.name}"
                )
            body = _build_typed_block(
                getattr(statement, "body", ()),
                dict(env),
                typed_module,
                typed_function,
            )
            typed_statements.append(
                TypedStmtNode(
                    "While", None, SemanticType("bool"), condition, body
                )
            )
            continue

        if kind == "Loop":
            body = _build_typed_block(
                getattr(statement, "body", ()),
                dict(env),
                typed_module,
                typed_function,
            )
            typed_statements.append(
                TypedStmtNode("Loop", None, None, None, body)
            )
            continue

        if kind == "For":
            start = infer_expression_type(
                getattr(statement, "start"), env, typed_module
            )
            end = infer_expression_type(
                getattr(statement, "end"), env, typed_module
            )
            integer_types = {
                "u8", "u16", "u32", "u64", "usize",
                "i8", "i16", "i32", "i64", "isize",
            }
            if start.type.name not in integer_types or end.type.name not in integer_types:
                raise Phase1SemanticError(
                    f"for range bounds must be integers, got "
                    f"{start.type.name} and {end.type.name}"
                )
            if start.type != end.type:
                raise Phase1SemanticError(
                    f"for range bound type mismatch: "
                    f"{start.type.name} vs {end.type.name}"
                )
            loop_env = dict(env)
            loop_env[getattr(statement, "var_name")] = SemanticType("usize")
            body = _build_typed_block(
                getattr(statement, "body", ()),
                loop_env,
                typed_module,
                typed_function,
            )
            typed_statements.append(
                TypedStmtNode(
                    "For",
                    getattr(statement, "var_name"),
                    SemanticType("usize"),
                    start,
                    body,
                    (),
                    end,
                )
            )
            continue

        if kind in ("Break", "Continue"):
            typed_statements.append(
                TypedStmtNode(kind, None, None, None)
            )
            continue

        if kind == "Unsafe":
            body = _build_typed_block(
                getattr(statement, "body", ()),
                dict(env),
                typed_module,
                typed_function,
            )
            typed_statements.append(
                TypedStmtNode("Unsafe", None, None, None, body)
            )
            continue

        if kind == "Asm":
            for output in getattr(statement, "outputs", ()):
                infer_assignment_target_type(output, env, typed_module)
            for input_expr in getattr(statement, "inputs", ()):
                infer_expression_type(input_expr, env, typed_module)
            typed_statements.append(
                TypedStmtNode("Asm", None, None, None)
            )
            continue

        if kind == "Defer":
            deferred_body = getattr(statement, "body", None)
            deferred_value = getattr(statement, "value", None)

            if deferred_body is not None:
                body = _build_typed_block(
                    deferred_body,
                    dict(env),
                    typed_module,
                    typed_function,
                )
                typed_statements.append(
                    TypedStmtNode("Defer", None, None, None, body)
                )
                continue

            if deferred_value is None:
                raise Phase1SemanticError("defer has no action")

            if type(deferred_value).__name__ == "Assign":
                target = infer_assignment_target_type(
                    getattr(deferred_value, "target"), env, typed_module
                )
                value_expr = getattr(deferred_value, "value")
                value = infer_expression_type(
                    value_expr, env, typed_module
                )
                value = _contextualize_expression(
                    value_expr, value, target.type, env, typed_module
                )
                if target.type != value.type:
                    raise Phase1SemanticError(
                        f"defer assignment type mismatch for {target.label!r}: "
                        f"expected {target.type.name}, got {value.type.name}"
                    )
                typed_statements.append(
                    TypedStmtNode(
                        "DeferAssign",
                        target.label,
                        target.type,
                        value,
                    )
                )
                continue

            expr = infer_expression_type(
                deferred_value, env, typed_module
            )
            typed_statements.append(
                TypedStmtNode("Defer", None, expr.type, expr)
            )
            continue

        raise Phase1SemanticError(
            f"body typing not implemented for statement {kind}"
        )

    return tuple(typed_statements)


def build_linear_typed_body(
    parsed_module, typed_module: TypedModule, function_name: str
) -> TypedFunctionBody:
    """Materialize typed facts for canonical structured function bodies."""
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
    statements = _build_typed_block(
        parsed_function.body, env, typed_module, typed_function
    )
    return TypedFunctionBody(function_name, statements)


@dataclass(frozen=True)
class Phase1ModuleSnapshot:
    typed_module: TypedModule
    bodies: tuple[TypedFunctionBody, ...]
    ownership: OwnershipModuleAnalysis
    maturity: str = "ISOLATED_PHASE1"


def build_phase1_semantic_snapshot(parsed_module) -> Phase1ModuleSnapshot:
    """Compose the isolated Phase-1 semantic passes without patching bootstrap.

    This deliberately remains an explicit API: it freezes declarations,
    rejects recursive by-value types, materializes supported structured bodies,
    and runs sole ownership analysis across the module. It neither mutates the
    canonical AST nor installs itself into bootstrap.check.
    """
    typed_module = build_declaration_typed_ast(parsed_module)
    validate_no_recursive_value_types(typed_module)
    bodies = tuple(
        build_linear_typed_body(parsed_module, typed_module, function.name)
        for function in typed_module.functions
    )
    ownership = analyze_module_ownership(parsed_module, typed_module)
    return Phase1ModuleSnapshot(typed_module, bodies, ownership)


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
    elem_type: "SemanticType | None" = None


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
class TypedClass:
    name: str
    fields: tuple[TypedField, ...]
    methods: tuple["TypedFunction", ...]
    public: bool
    attributes: tuple[str, ...]


@dataclass(frozen=True)
class TypedEnumVariant:
    name: str
    value: int | None


@dataclass(frozen=True)
class TypedEnum:
    name: str
    variants: tuple[TypedEnumVariant, ...]
    public: bool


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
    enums: tuple[TypedEnum, ...] = ()
    classes: tuple[TypedClass, ...] = ()
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
        elem_type=(
            semantic_type(type_obj.elem_type)
            if getattr(type_obj, "elem_type", None) is not None
            else None
        ),
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
        enums=tuple(
            TypedEnum(
                name=item.name,
                variants=tuple(
                    TypedEnumVariant(variant.name, variant.value)
                    for variant in item.variants
                ),
                public=bool(item.public),
            )
            for item in getattr(module, "enums", ())
        ),
        classes=tuple(
            TypedClass(
                name=item.name,
                fields=tuple(
                    TypedField(field.name, semantic_type(field.type))
                    for field in item.fields
                ),
                methods=tuple(
                    TypedFunction(
                        name=method.name,
                        params=tuple(
                            TypedParam(name, semantic_type(type_obj))
                            for name, type_obj in method.params
                        ),
                        result=semantic_type(method.result),
                        public=bool(method.public),
                        attributes=tuple(method.attributes),
                    )
                    for method in item.methods
                ),
                public=bool(item.public),
                attributes=tuple(item.attributes),
            )
            for item in getattr(module, "classes", ())
        ),
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
    "TypedFunctionBody", "infer_expression_type",
    "infer_assignment_target_type", "build_linear_typed_body",
    "Phase1ModuleSnapshot", "build_phase1_semantic_snapshot",
    "apply_ownership_moves", "merge_conditional_ownership",
    "validate_loop_ownership", "require_live", "move_state", "merge_branch_states",
    "SourceSpan", "SemanticType",
    "TypedField", "TypedStruct", "TypedClass", "TypedEnumVariant", "TypedEnum",
    "TypedParam", "TypedFunction", "TypedGlobal", "TypedModule",
    "semantic_type", "integer_bounds", "validate_integer_value",
    "validate_no_recursive_value_types",
    "build_declaration_typed_ast",
]