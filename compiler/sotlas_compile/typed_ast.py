"""Phase-1 Typed AST and semantic-core foundation.

This module remains intentionally isolated from the production bootstrap
pipeline. It freezes canonical declarations, materializes structured
function-body types, validates contextual expression contracts, and records
ownership facts without mutating or replacing the production checker.

Maturity: ISOLATED_PHASE1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


MATURITY = "ISOLATED_PHASE1"


class Phase1SemanticError(ValueError):
    """Raised by isolated Phase-1 semantic validators."""


class VarState(str, Enum):
    LIVE = "LIVE"
    MOVED = "MOVED"
    MAYBE_MOVED = "MAYBE_MOVED"
    BORROWED_IMMUT = "BORROWED_IMMUT"
    BORROWED_MUT = "BORROWED_MUT"


class OwnershipDomain(str, Enum):
    EXCLUSIVE = "exclusive"
    SHARED = "shared"
    ISLAND = "island"


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


def ownership_domain(
    type_info: SemanticType, module: TypedModule
) -> OwnershipDomain | None:
    """Resolve the ownership domain frozen in the canonical Typed AST."""
    if type_info.pointer or type_info.is_reference:
        return None
    if type_info.declared_ownership_domain is not None:
        return type_info.declared_ownership_domain
    struct = next(
        (item for item in module.structs if item.name == type_info.name),
        None,
    )
    if struct is None:
        return None
    return struct.ownership_domain


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
    domain: OwnershipDomain


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

    def domain_of(self, name: str) -> OwnershipDomain | None:
        for binding in reversed(self.bindings):
            if binding.name == name:
                return binding.domain
        return None

    def declare(
        self, name: str, type_info: SemanticType, module: TypedModule
    ) -> "OwnershipEnv":
        domain = ownership_domain(type_info, module)
        if domain is None:
            return self
        if self.state_of(name) is not None:
            raise Phase1SemanticError(
                f"ownership binding {name!r} already declared"
            )
        return OwnershipEnv(
            self.bindings + (OwnershipBinding(name, type_info, VarState.LIVE, domain),)
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
        domain = self.domain_of(name)
        if domain is OwnershipDomain.ISLAND:
            raise Phase1SemanticError(
                f"island owner {name!r} cannot move implicitly after quarantine"
            )
        next_state = move_state(name, state)
        updated = []
        replaced = False
        for binding in self.bindings:
            if binding.name == name and not replaced:
                updated.append(
                    OwnershipBinding(binding.name, binding.type, next_state, binding.domain)
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
        return OwnershipEnv(
            tuple(
                merge_ownership_bindings(binding, right[binding.name])
                for binding in self.bindings
            )
        )


def merge_ownership_bindings(
    left: OwnershipBinding, right: OwnershipBinding
) -> OwnershipBinding:
    """Apply the canonical branch-join rule for one ownership binding."""
    if left.name != right.name:
        raise Phase1SemanticError(
            f"cannot merge ownership bindings {left.name!r} and {right.name!r}"
        )
    if left.type != right.type:
        raise Phase1SemanticError(
            f"ownership binding {left.name!r} changed type across branches"
        )
    if left.domain != right.domain:
        raise Phase1SemanticError(
            f"ownership binding {left.name!r} changed domain across branches: "
            f"{left.domain.value} vs {right.domain.value}"
        )
    return OwnershipBinding(
        left.name,
        left.type,
        merge_branch_states(left.state, right.state),
        left.domain,
    )


@dataclass(frozen=True)
class OwnershipDomainTransition:
    binding: str
    type: SemanticType
    source: OwnershipDomain
    target: OwnershipDomain
    source_state: VarState
    operation: str


def plan_ownership_domain_transition(
    binding: OwnershipBinding,
    target: OwnershipDomain,
    operation: str,
) -> OwnershipDomainTransition:
    """Validate a domain transition without pretending backend support exists.

    The first canonical transition is exclusive -> shared through an explicit
    share operation. This function only records semantic intent; it does not
    mutate an OwnershipEnv, add reference counting, or lower runtime behavior.
    """
    if binding.state is not VarState.LIVE:
        raise Phase1SemanticError(
            f"ownership domain transition for {binding.name!r} requires LIVE "
            f"source, got {binding.state.value}"
        )
    if binding.domain is target:
        raise Phase1SemanticError(
            f"ownership binding {binding.name!r} is already in domain "
            f"{target.value!r}"
        )
    if (
        binding.domain is OwnershipDomain.EXCLUSIVE
        and target is OwnershipDomain.SHARED
        and operation == "share"
    ):
        return OwnershipDomainTransition(
            binding=binding.name,
            type=binding.type,
            source=binding.domain,
            target=target,
            source_state=binding.state,
            operation=operation,
        )
    if (
        binding.domain is OwnershipDomain.EXCLUSIVE
        and target is OwnershipDomain.ISLAND
        and operation == "quarantine"
    ):
        return OwnershipDomainTransition(
            binding=binding.name,
            type=binding.type,
            source=binding.domain,
            target=target,
            source_state=binding.state,
            operation=operation,
        )
    raise Phase1SemanticError(
        f"unsupported ownership domain transition for {binding.name!r}: "
        f"{binding.domain.value} -> {target.value} via {operation}"
    )


@dataclass(frozen=True)
class SharedOwnershipAccount:
    binding: str
    type: SemanticType
    strong_refs: int
    accounting: str = "arc"

    @property
    def should_destroy(self) -> bool:
        return self.strong_refs == 0


def open_shared_ownership_account(
    transition: OwnershipDomainTransition,
) -> SharedOwnershipAccount:
    """Materialize semantic ARC accounting for an approved share transition."""
    if (
        transition.source is not OwnershipDomain.EXCLUSIVE
        or transition.target is not OwnershipDomain.SHARED
        or transition.operation != "share"
        or transition.source_state is not VarState.LIVE
    ):
        raise Phase1SemanticError(
            f"cannot open shared ownership account from transition "
            f"{transition.source.value} -> {transition.target.value} "
            f"via {transition.operation}"
        )
    return SharedOwnershipAccount(
        binding=transition.binding,
        type=transition.type,
        strong_refs=1,
    )


def retain_shared_owner(
    account: SharedOwnershipAccount,
) -> SharedOwnershipAccount:
    """Record one explicit strong-owner acquisition."""
    if account.strong_refs <= 0:
        raise Phase1SemanticError(
            f"cannot retain released shared ownership {account.binding!r}"
        )
    return SharedOwnershipAccount(
        binding=account.binding,
        type=account.type,
        strong_refs=account.strong_refs + 1,
        accounting=account.accounting,
    )


def release_shared_owner(
    account: SharedOwnershipAccount,
) -> SharedOwnershipAccount:
    """Record one explicit strong-owner release without backend side effects."""
    if account.strong_refs <= 0:
        raise Phase1SemanticError(
            f"shared ownership {account.binding!r} has no strong owner to release"
        )
    return SharedOwnershipAccount(
        binding=account.binding,
        type=account.type,
        strong_refs=account.strong_refs - 1,
        accounting=account.accounting,
    )


@dataclass(frozen=True)
class SharedOwnershipApplication:
    env: OwnershipEnv
    account: SharedOwnershipAccount
    owners: tuple[str, ...]


@dataclass(frozen=True)
class TypedShareExpression:
    expr: TypedExprNode
    source: str
    alias: str | None
    transition: OwnershipDomainTransition
    application: SharedOwnershipApplication


def apply_shared_transition(
    env: OwnershipEnv,
    transition: OwnershipDomainTransition,
    *,
    alias: str | None = None,
) -> SharedOwnershipApplication:
    """Apply an approved exclusive->shared transition to semantic bindings.

    The original binding remains a live strong owner but changes domain from
    exclusive to shared. Creating an alias is explicit and increments the
    strong-reference account exactly once. No runtime/backend code is emitted.
    """
    source_index = next(
        (
            index for index, binding in enumerate(env.bindings)
            if binding.name == transition.binding
        ),
        None,
    )
    if source_index is None:
        raise Phase1SemanticError(
            f"ownership binding {transition.binding!r} is not tracked"
        )
    source = env.bindings[source_index]
    if (
        source.type != transition.type
        or source.domain is not transition.source
        or source.state is not transition.source_state
    ):
        raise Phase1SemanticError(
            f"ownership binding {source.name!r} no longer matches planned "
            "domain transition"
        )

    account = open_shared_ownership_account(transition)
    updated = list(env.bindings)
    updated[source_index] = OwnershipBinding(
        source.name,
        source.type,
        VarState.LIVE,
        OwnershipDomain.SHARED,
    )
    owners = [source.name]

    if alias is not None:
        if any(binding.name == alias for binding in env.bindings):
            raise Phase1SemanticError(
                f"shared ownership alias {alias!r} already exists"
            )
        if not alias:
            raise Phase1SemanticError("shared ownership alias cannot be empty")
        updated.append(
            OwnershipBinding(
                alias,
                source.type,
                VarState.LIVE,
                OwnershipDomain.SHARED,
            )
        )
        account = retain_shared_owner(account)
        owners.append(alias)

    return SharedOwnershipApplication(
        env=OwnershipEnv(tuple(updated)),
        account=account,
        owners=tuple(owners),
    )


def build_typed_share_expression(
    expr,
    env: OwnershipEnv,
    *,
    alias: str | None = None,
) -> TypedShareExpression:
    """Build canonical Typed AST semantics for an explicit share operation.

    This is deliberately parser-independent. Only a whole tracked binding may
    enter shared ownership at this stage; members, indexes, temporaries and
    arbitrary expressions remain fail-closed until their aliasing contract is
    specified.
    """
    if type(expr).__name__ != "Name":
        raise Phase1SemanticError(
            "share currently requires a direct owned binding"
        )
    source_name = getattr(expr, "value", None)
    source = next(
        (binding for binding in env.bindings if binding.name == source_name),
        None,
    )
    if source is None:
        raise Phase1SemanticError(
            f"share source {source_name!r} is not a tracked ownership binding"
        )
    transition = plan_ownership_domain_transition(
        source,
        OwnershipDomain.SHARED,
        "share",
    )
    application = apply_shared_transition(
        env,
        transition,
        alias=alias,
    )
    label = (
        f"share:{source_name}->{alias}"
        if alias is not None
        else f"share:{source_name}"
    )
    return TypedShareExpression(
        expr=TypedExprNode("Share", source.type, label),
        source=source_name,
        alias=alias,
        transition=transition,
        application=application,
    )


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
    domain: OwnershipDomain | None = None
    left_state: VarState | None = None
    right_state: VarState | None = None
    result_state: VarState | None = None
    point_id: str | None = None
    defer_call: tuple[str, tuple[str, ...]] | None = None
    type: SemanticType | None = None
    destination: str | None = None
    source_domain: OwnershipDomain | None = field(default=None, compare=False)
    target_domain: OwnershipDomain | None = field(default=None, compare=False)
    destination_domain: OwnershipDomain | None = field(default=None, compare=False)


@dataclass(frozen=True)
class SharedCleanupStep:
    owner: str
    account: str
    strong_refs_before: int
    strong_refs_after: int
    destroy_after: bool
    via: str
    point_id: str | None = None


@dataclass(frozen=True)
class SharedCleanupPlan:
    steps: tuple[SharedCleanupStep, ...]


@dataclass(frozen=True)
class SharedExitAction:
    kind: str
    owner: str | None
    via: str
    point_id: str | None = None
    defer_point_id: str | None = None
    defer_call: tuple[str, tuple[str, ...]] | None = None


@dataclass(frozen=True)
class SharedExitPlan:
    actions: tuple[SharedExitAction, ...]


@dataclass(frozen=True)
class OwnershipTrace:
    final_env: OwnershipEnv
    events: tuple[OwnershipEvent, ...]
    shared_cleanup: SharedCleanupPlan = SharedCleanupPlan(())
    shared_path_cleanup: SharedCleanupPlan = SharedCleanupPlan(())
    shared_loop_cleanup: SharedCleanupPlan = SharedCleanupPlan(())
    shared_loop_control_exit: SharedExitPlan = SharedExitPlan(())
    shared_exit: SharedExitPlan = SharedExitPlan(())


def plan_shared_scope_cleanup(
    env: OwnershipEnv,
    events: tuple[OwnershipEvent, ...] | list[OwnershipEvent],
) -> SharedCleanupPlan:
    """Plan deterministic releases for shared strong owners at function scope exit.

    Accounts are reconstructed only from canonical share/retain events. This
    milestone intentionally covers normal function-scope exit; branch-local,
    early-return and defer-aware cleanup remain separate milestones.
    """
    accounts: dict[str, list[str]] = {}
    owner_to_account: dict[str, str] = {}

    for event in events:
        if event.kind == "domain_transition" and event.domain is OwnershipDomain.SHARED:
            if not event.via.startswith("share:"):
                continue
            alias = event.via.split(":", 1)[1]
            account = event.name
            if account in accounts:
                raise Phase1SemanticError(
                    f"duplicate shared ownership account for {account!r}"
                )
            accounts[account] = [account]
            owner_to_account[account] = account
            if alias:
                accounts[account].append(alias)
                owner_to_account[alias] = account
            continue
        if event.kind == "retain" and event.domain is OwnershipDomain.SHARED:
            if not event.via.startswith("share:"):
                continue
            account = event.via.split(":", 1)[1]
            if account not in accounts:
                raise Phase1SemanticError(
                    f"retain for unknown shared ownership account {account!r}"
                )
            if event.name not in accounts[account]:
                accounts[account].append(event.name)
                owner_to_account[event.name] = account

    live_shared = [
        binding.name
        for binding in env.bindings
        if binding.domain is OwnershipDomain.SHARED
        and binding.state is VarState.LIVE
    ]
    missing = [name for name in live_shared if name not in owner_to_account]
    if missing:
        raise Phase1SemanticError(
            "shared cleanup cannot resolve account for owner(s): "
            + ", ".join(sorted(missing))
        )

    steps: list[SharedCleanupStep] = []
    for account, owners in accounts.items():
        live_owners = [name for name in owners if name in live_shared]
        strong_refs = len(live_owners)
        for owner in reversed(live_owners):
            before = strong_refs
            strong_refs -= 1
            steps.append(
                SharedCleanupStep(
                    owner=owner,
                    account=account,
                    strong_refs_before=before,
                    strong_refs_after=strong_refs,
                    destroy_after=strong_refs == 0,
                    via="scope_exit",
                )
            )
    return SharedCleanupPlan(tuple(steps))


def _cleanup_point_id(statement, kind: str) -> str:
    token = getattr(statement, "token", None)
    line = getattr(token, "line", None)
    column = getattr(token, "column", None)
    if line is None or column is None:
        raise Phase1SemanticError(
            f"ownership cleanup point {kind!r} lacks source location"
        )
    return f"{kind}@{line}:{column}"


def _shared_cleanup_for_path(
    env: OwnershipEnv,
    events: tuple[OwnershipEvent, ...] | list[OwnershipEvent],
    via: str,
    *,
    point_id: str | None = None,
) -> tuple[SharedCleanupStep, ...]:
    plan = plan_shared_scope_cleanup(env, events)
    return tuple(
        SharedCleanupStep(
            owner=step.owner,
            account=step.account,
            strong_refs_before=step.strong_refs_before,
            strong_refs_after=step.strong_refs_after,
            destroy_after=step.destroy_after,
            via=via,
            point_id=point_id,
        )
        for step in plan.steps
    )


def plan_shared_exit(
    events: tuple[OwnershipEvent, ...] | list[OwnershipEvent],
    cleanup: SharedCleanupPlan,
) -> SharedExitPlan:
    """Order shared-aware defers before ARC releases at scope exit."""
    actions: list[SharedExitAction] = []
    for event in reversed(tuple(events)):
        if (
            event.kind == "shared_defer_use"
            and event.domain is OwnershipDomain.SHARED
        ):
            actions.append(
                SharedExitAction(
                    "defer",
                    event.name,
                    event.via,
                    defer_point_id=event.point_id,
                    defer_call=event.defer_call,
                )
            )
    for step in cleanup.steps:
        actions.append(
            SharedExitAction("release", step.owner, step.via)
        )
        if step.destroy_after:
            actions.append(
                SharedExitAction("destroy", step.account, step.via)
            )
    return SharedExitPlan(tuple(actions))


def plan_shared_control_exit(
    events: tuple[OwnershipEvent, ...] | list[OwnershipEvent],
    cleanup: SharedCleanupPlan,
    control: str,
    *,
    point_id: str | None = None,
) -> SharedExitPlan:
    """Order loop-scope defers before ARC cleanup for break/continue."""
    base = plan_shared_exit(events, cleanup)
    return SharedExitPlan(
        tuple(
            SharedExitAction(
                action.kind,
                action.owner,
                f"{control}:{action.via}",
                point_id,
                action.defer_point_id,
                action.defer_call,
            )
            for action in base.actions
        )
    )


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
    elif kind in ("Unary", "MoveExpr", "ShareExpr", "UnsafeExpr"):
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
    elif kind in ("Unary", "MoveExpr", "ShareExpr"):
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


def _typed_enum_constructor(
    module: TypedModule, callee: str
):
    """Resolve a canonical enum payload constructor from its lowered call name."""
    for enum in module.enums:
        for variant in enum.variants:
            if f"{enum.name}_{variant.name}" == callee:
                return enum, variant
    return None


def _move_call_arguments(
    env: OwnershipEnv,
    call,
    typed_module: TypedModule,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    callee_name = getattr(call, "callee", "")

    constructor = _typed_enum_constructor(typed_module, callee_name)
    if constructor is not None:
        enum, variant = constructor
        arguments = tuple(getattr(call, "args", ()))
        result = env

        if variant.payload_type is None or len(arguments) != 1:
            return result

        argument = arguments[0]
        if is_sole_type(variant.payload_type, typed_module):
            moved_argument = (
                getattr(argument, "value", None)
                if type(argument).__name__ == "MoveExpr"
                else argument
            )
            if type(moved_argument).__name__ == "Name":
                name = moved_argument.value
                if result.type_of(name) is not None:
                    result = result.move(name)
                    events.append(
                        OwnershipEvent(
                            "move",
                            name,
                            f"enum:{enum.name}::{variant.name}",
                        )
                    )
                    return result

        require_expr_ownership_live(result, argument)
        return result

    callee = _typed_function_map(typed_module).get(callee_name)
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
                if result.domain_of(name) is OwnershipDomain.SHARED:
                    raise Phase1SemanticError(
                        f"shared owner {name!r} cannot be consumed by sole "
                        f"parameter of {callee.name!r} without explicit handover"
                    )
                if result.domain_of(name) is OwnershipDomain.ISLAND:
                    raise Phase1SemanticError(
                        f"island owner {name!r} cannot escape quarantine through "
                        f"sole parameter of {callee.name!r}"
                    )
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
                if result.domain_of(name) is OwnershipDomain.SHARED:
                    raise Phase1SemanticError(
                        f"shared owner {name!r} cannot be consumed by sole "
                        f"parameter of method {callee.name!r} without explicit handover"
                    )
                if result.domain_of(name) is OwnershipDomain.ISLAND:
                    raise Phase1SemanticError(
                        f"island owner {name!r} cannot escape quarantine through "
                        f"sole parameter of method {callee.name!r}"
                    )
                result = result.move(name)
                events.append(
                    OwnershipEvent("move", name, f"method:{callee.name}")
                )
                continue
        require_expr_ownership_live(result, argument)
    return result


def _move_struct_literal_fields(
    env: OwnershipEnv,
    expr,
    typed_module: TypedModule,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    """Transfer sole field ownership into a sole struct literal."""
    if type(expr).__name__ != "StructLit":
        return env

    struct_name = getattr(expr, "struct_name", "")
    struct = next(
        (item for item in typed_module.structs if item.name == struct_name),
        None,
    )
    if struct is None:
        return env

    field_map = {field.name: field for field in struct.fields}
    result = env

    for field_name, field_expr in getattr(expr, "fields", ()):
        field = field_map.get(field_name)
        if field is None:
            continue

        field_is_sole = is_sole_type(field.type, typed_module)
        if field_is_sole and not struct.is_sole:
            raise Phase1SemanticError(
                f"sole field {field_name!r} requires sole container "
                f"{struct.name!r}"
            )

        moved_field = (
            getattr(field_expr, "value", None)
            if type(field_expr).__name__ == "MoveExpr"
            else field_expr
        )

        if field_is_sole and type(moved_field).__name__ == "Name":
            source_name = moved_field.value
            source_type = result.type_of(source_name)
            if source_type is not None:
                result = result.move(source_name)
                events.append(
                    OwnershipEvent(
                        "move",
                        source_name,
                        f"struct:{struct.name}.{field_name}",
                    )
                )
                continue

        if type(field_expr).__name__ == "StructLit":
            result = _move_struct_literal_fields(
                result, field_expr, typed_module, events
            )
        elif type(field_expr).__name__ == "Call":
            result = _move_call_arguments(
                result, field_expr, typed_module, events
            )
        elif type(field_expr).__name__ == "MethodCall":
            result = _move_method_call_arguments(
                result, field_expr, typed_module, events
            )
        elif type(field_expr).__name__ == "TryExpr":
            result = _move_try_wrapped_call_arguments(
                result, field_expr, typed_module, events
            )
        else:
            require_expr_ownership_live(result, field_expr)

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


def _apply_explicit_handover(
    env: OwnershipEnv,
    expr,
    events: list[OwnershipEvent],
    destination=None,
) -> OwnershipEnv:
    """Apply explicit ownership transfer between canonical domains.

    EXCLUSIVE supports the original sink form and binding-to-binding transfer.
    A quarantined ISLAND owner may leave isolation only through an explicit
    destination that is EXCLUSIVE, type-compatible, and already MOVED.
    """
    if type(expr).__name__ != "Name":
        raise Phase1SemanticError(
            "handover currently requires a direct ownership binding"
        )
    name = getattr(expr, "value", None)
    source_domain = env.domain_of(name)
    if source_domain is None:
        raise Phase1SemanticError(
            f"handover target {name!r} is not a tracked exclusive value"
        )
    if source_domain is OwnershipDomain.SHARED:
        raise Phase1SemanticError(
            f"handover target {name!r} must be exclusive, got {source_domain.value}"
        )
    if source_domain is OwnershipDomain.ISLAND and destination is None:
        raise Phase1SemanticError(
            f"island handover for {name!r} requires an explicit exclusive destination"
        )
    env.require_live(name)
    type_info = env.type_of(name)

    destination_name = None
    if destination is not None:
        if type(destination).__name__ != "Name":
            raise Phase1SemanticError(
                "handover destination must be a direct exclusive ownership binding"
            )
        destination_name = getattr(destination, "value", None)
        if destination_name == name:
            raise Phase1SemanticError(
                "handover source and destination must be distinct bindings"
            )
        destination_domain = env.domain_of(destination_name)
        if destination_domain is None:
            raise Phase1SemanticError(
                f"handover destination {destination_name!r} is not tracked"
            )
        if destination_domain is not OwnershipDomain.EXCLUSIVE:
            raise Phase1SemanticError(
                f"handover destination {destination_name!r} must be exclusive, "
                f"got {destination_domain.value}"
            )
        destination_type = env.type_of(destination_name)
        if destination_type != type_info:
            raise Phase1SemanticError(
                f"handover destination {destination_name!r} has incompatible type"
            )
        destination_state = env.state_of(destination_name)
        if destination_state is not VarState.MOVED:
            state_name = (
                destination_state.value
                if destination_state is not None
                else "untracked"
            )
            raise Phase1SemanticError(
                f"handover destination {destination_name!r} must be MOVED "
                f"before reacquisition, got {state_name}"
            )

    next_source_state = move_state(name, env.state_of(name))
    updated: list[OwnershipBinding] = []
    for binding in env.bindings:
        if binding.name == name:
            updated.append(
                OwnershipBinding(
                    binding.name,
                    binding.type,
                    next_source_state,
                    binding.domain,
                )
            )
        elif (
            destination_name is not None
            and binding.name == destination_name
        ):
            updated.append(
                OwnershipBinding(
                    binding.name,
                    binding.type,
                    VarState.LIVE,
                    binding.domain,
                )
            )
        else:
            updated.append(binding)
    result = OwnershipEnv(tuple(updated))

    events.append(
        OwnershipEvent(
            "handover",
            name,
            "handover",
            source_domain,
            type=type_info,
            destination=destination_name,
            source_domain=source_domain,
            target_domain=(
                OwnershipDomain.EXCLUSIVE
                if destination_name is not None
                else None
            ),
            destination_domain=(
                OwnershipDomain.EXCLUSIVE
                if destination_name is not None
                else None
            ),
        )
    )
    return result

def _apply_quarantine(
    env: OwnershipEnv,
    expr,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    """Move one LIVE exclusive binding into the canonical island domain."""
    if type(expr).__name__ != "Name":
        raise Phase1SemanticError(
            "quarantine currently requires a direct exclusive ownership binding"
        )
    name = getattr(expr, "value", None)
    source = next(
        (binding for binding in env.bindings if binding.name == name),
        None,
    )
    if source is None:
        raise Phase1SemanticError(
            f"quarantine target {name!r} is not a tracked ownership binding"
        )
    transition = plan_ownership_domain_transition(
        source,
        OwnershipDomain.ISLAND,
        "quarantine",
    )
    updated: list[OwnershipBinding] = []
    for binding in env.bindings:
        if binding.name == name:
            updated.append(
                OwnershipBinding(
                    binding.name,
                    binding.type,
                    VarState.LIVE,
                    OwnershipDomain.ISLAND,
                )
            )
        else:
            updated.append(binding)
    result = OwnershipEnv(tuple(updated))
    events.append(
        OwnershipEvent(
            "quarantine",
            name,
            "quarantine",
            OwnershipDomain.ISLAND,
            type=transition.type,
            source_domain=transition.source,
            target_domain=transition.target,
        )
    )
    return result


def _apply_return_ownership_transfer(
    env: OwnershipEnv,
    name: str,
    typed_function: TypedFunction,
    events: list[OwnershipEvent],
) -> OwnershipEnv:
    """Transfer one direct owned binding through the function return contract.

    Return-domain changes are never implicit. EXCLUSIVE returns require an
    EXCLUSIVE source; ISLAND returns require an ISLAND source. The source
    binding becomes MOVED while preserving its original domain in the local
    environment, and the event freezes source/target domain facts for the graph.
    """
    source_domain = env.domain_of(name)
    target_domain = typed_function.return_ownership_domain
    if source_domain is None or target_domain is None:
        raise Phase1SemanticError(
            f"return ownership transfer for {name!r} is not tracked"
        )
    if source_domain is not target_domain:
        raise Phase1SemanticError(
            f"return ownership domain mismatch for {name!r}: "
            f"{source_domain.value} -> {target_domain.value}"
        )
    env.require_live(name)
    next_state = move_state(name, env.state_of(name))
    updated = tuple(
        OwnershipBinding(
            binding.name,
            binding.type,
            next_state if binding.name == name else binding.state,
            binding.domain,
        )
        for binding in env.bindings
    )
    events.append(
        OwnershipEvent(
            "move",
            name,
            "return",
            source_domain,
            type=env.type_of(name),
            source_domain=source_domain,
            target_domain=target_domain,
        )
    )
    return OwnershipEnv(updated)


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
            if type(value).__name__ == "ShareExpr":
                shared = build_typed_share_expression(
                    getattr(value, "value", None), env, alias=statement.name
                )
                env = shared.application.env
                events.append(OwnershipEvent(
                    "domain_transition", shared.source,
                    f"share:{statement.name}", OwnershipDomain.SHARED,
                    type=env.type_of(shared.source),
                ))
                events.append(OwnershipEvent(
                    "retain", statement.name,
                    f"share:{shared.source}", OwnershipDomain.SHARED,
                ))
                continue
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
            elif type(value).__name__ == "StructLit":
                env = _move_struct_literal_fields(
                    env, value, typed_module, events
                )
            if type(value).__name__ not in (
                "Name", "MoveExpr", "Call", "MethodCall", "StructLit"
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

        if kind == "Handover":
            env = _apply_explicit_handover(
                env,
                getattr(statement, "value", None),
                events,
                getattr(statement, "destination", None),
            )
            continue

        if kind == "Quarantine":
            env = _apply_quarantine(
                env,
                getattr(statement, "value", None),
                events,
            )
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
                and typed_function.return_ownership_domain is not None
            ):
                moved_value = (
                    getattr(value, "value")
                    if type(value).__name__ == "MoveExpr"
                    else value
                )
                env = _apply_return_ownership_transfer(
                    env,
                    moved_value.value,
                    typed_function,
                    events,
                )
            continue

        if kind in ("If", "While", "Loop", "For"):
            events.append(
                OwnershipEvent("deferred-control-flow", function_name, kind)
            )

    cleanup = plan_shared_scope_cleanup(env, events)
    return OwnershipTrace(env, tuple(events), cleanup)


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


def _block_may_fallthrough(statements) -> bool:
    """Return whether at least one path can reach the end of this block."""
    return not _block_definitely_terminates(statements)


def _statement_definitely_returns(statement) -> bool:
    """Return whether one statement exits the current function on every path."""
    kind = type(statement).__name__
    if kind == "Return":
        return True
    if kind == "Unsafe":
        return _block_definitely_returns(
            getattr(statement, "body", ())
        )
    if kind == "If":
        else_body = getattr(statement, "else_body", ())
        return bool(else_body) and _block_definitely_returns(
            getattr(statement, "then_body", ())
        ) and _block_definitely_returns(else_body)
    return False


def _block_definitely_returns(statements) -> bool:
    """Return whether the canonical AST block definitely returns from its function."""
    for statement in statements:
        if _statement_definitely_returns(statement):
            return True
    return False


def _analyze_block_ownership(
    statements,
    env: OwnershipEnv,
    typed_module: TypedModule,
    typed_function: TypedFunction,
    events: list[OwnershipEvent],
    *,
    history: tuple[OwnershipEvent, ...] = (),
    path_cleanup: list[SharedCleanupStep] | None = None,
    loop_cleanup: list[SharedCleanupStep] | None = None,
    loop_control_exit: list[SharedExitAction] | None = None,
    loop_entry_names: tuple[str, ...] | None = None,
    loop_event_history: tuple[OwnershipEvent, ...] = (),
    loop_control_states: list[tuple[str, OwnershipEnv]] | None = None,
    collect_return_cleanup: bool = True,
) -> OwnershipEnv:
    """Analyze ownership events for a canonical AST block.

    Branch-local bindings are allowed while analyzing a branch but are dropped
    at the merge boundary; only bindings visible on entry participate in the
    ownership join.
    """
    result = env
    if path_cleanup is None:
        path_cleanup = []
    if loop_cleanup is None:
        loop_cleanup = []
    if loop_control_exit is None:
        loop_control_exit = []
    if loop_control_states is None:
        loop_control_states = []
    for statement in statements:
        kind = type(statement).__name__

        if kind == "Let":
            local_type = _declared_local_type(statement)
            value = getattr(statement, "value", None)
            if type(value).__name__ == "ShareExpr":
                shared = build_typed_share_expression(
                    getattr(value, "value", None), result, alias=statement.name
                )
                result = shared.application.env
                events.append(OwnershipEvent(
                    "domain_transition", shared.source,
                    f"share:{statement.name}", OwnershipDomain.SHARED,
                    type=result.type_of(shared.source),
                ))
                events.append(OwnershipEvent(
                    "retain", statement.name,
                    f"share:{shared.source}", OwnershipDomain.SHARED,
                ))
                continue
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
            elif type(value).__name__ == "StructLit":
                result = _move_struct_literal_fields(
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

        if kind == "Handover":
            result = _apply_explicit_handover(
                result,
                getattr(statement, "value", None),
                events,
                getattr(statement, "destination", None),
            )
            continue

        if kind == "Quarantine":
            result = _apply_quarantine(
                result,
                getattr(statement, "value", None),
                events,
            )
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
            elif type(value).__name__ == "StructLit":
                result = _move_struct_literal_fields(
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
                and typed_function.return_ownership_domain is not None
            ):
                moved_value = (
                    getattr(value, "value")
                    if type(value).__name__ == "MoveExpr"
                    else value
                )
                result = _apply_return_ownership_transfer(
                    result,
                    moved_value.value,
                    typed_function,
                    events,
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
            if collect_return_cleanup:
                path_cleanup.extend(
                    _shared_cleanup_for_path(
                        result,
                        history + tuple(events),
                        "early_return",
                        point_id=_cleanup_point_id(statement, "return"),
                    )
                )
            break

        if kind in ("Break", "Continue"):
            control = kind.lower()
            if loop_entry_names is not None:
                local_shared = tuple(
                    binding for binding in result.bindings
                    if binding.name not in loop_entry_names
                    and binding.domain is OwnershipDomain.SHARED
                    and binding.state is VarState.LIVE
                )
                if local_shared:
                    local_plan = plan_shared_scope_cleanup(
                        OwnershipEnv(local_shared),
                        loop_event_history + tuple(events),
                    )
                    control_plan = plan_shared_control_exit(
                        loop_event_history + tuple(events),
                        local_plan,
                        control,
                        point_id=_cleanup_point_id(statement, control),
                    )
                    loop_control_exit.extend(control_plan.actions)
                loop_control_states.append(
                    (
                        control,
                        _project_ownership_env(result, loop_entry_names),
                    )
                )
            events.append(
                OwnershipEvent(
                    "control",
                    typed_function.name,
                    control,
                )
            )
            break

        if kind == "If":
            visible = tuple(binding.name for binding in result.bindings)
            then_body = getattr(statement, "then_body", ())
            else_body = getattr(statement, "else_body", ())
            then_events: list[OwnershipEvent] = []
            else_events: list[OwnershipEvent] = []
            branch_history = history + tuple(events)
            then_env = _analyze_block_ownership(
                then_body,
                result,
                typed_module,
                typed_function,
                then_events,
                history=branch_history,
                path_cleanup=path_cleanup,
                loop_cleanup=loop_cleanup,
                loop_control_exit=loop_control_exit,
                loop_entry_names=loop_entry_names,
                loop_event_history=loop_event_history + tuple(events),
                loop_control_states=loop_control_states,
                collect_return_cleanup=collect_return_cleanup,
            )
            else_env = _analyze_block_ownership(
                else_body,
                result,
                typed_module,
                typed_function,
                else_events,
                history=branch_history,
                path_cleanup=path_cleanup,
                loop_cleanup=loop_cleanup,
                loop_control_exit=loop_control_exit,
                loop_entry_names=loop_entry_names,
                loop_event_history=loop_event_history + tuple(events),
                loop_control_states=loop_control_states,
                collect_return_cleanup=collect_return_cleanup,
            )
            then_env = _project_ownership_env(then_env, visible)
            else_env = _project_ownership_env(else_env, visible)
            then_fallthrough = _block_may_fallthrough(then_body)
            else_fallthrough = _block_may_fallthrough(else_body)

            if then_fallthrough and else_fallthrough:
                merged_env = then_env.merge(else_env)
                for name in visible:
                    left_binding = next(
                        binding for binding in then_env.bindings
                        if binding.name == name
                    )
                    right_binding = next(
                        binding for binding in else_env.bindings
                        if binding.name == name
                    )
                    merged_binding = next(
                        binding for binding in merged_env.bindings
                        if binding.name == name
                    )
                    events.append(
                        OwnershipEvent(
                            "domain_merge",
                            name,
                            "if",
                            merged_binding.domain,
                            left_binding.state,
                            right_binding.state,
                            merged_binding.state,
                        )
                    )
                result = merged_env
            elif then_fallthrough:
                result = then_env
            elif else_fallthrough:
                result = else_env

            events.append(
                OwnershipEvent("branch", typed_function.name, "if")
            )
            events.extend(then_events)
            events.extend(else_events)
            if not then_fallthrough and not else_fallthrough:
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
                history=history + tuple(events),
                path_cleanup=path_cleanup,
                loop_cleanup=loop_cleanup,
                loop_control_exit=loop_control_exit,
                loop_entry_names=loop_entry_names,
                loop_event_history=loop_event_history + tuple(events),
                loop_control_states=loop_control_states,
                collect_return_cleanup=collect_return_cleanup,
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
            defer_point_id = _cleanup_point_id(statement, "defer")
            captured = _statement_referenced_owned_names(result, statement)
            deferred_body = getattr(statement, "body", None)
            deferred_value = getattr(statement, "value", None)
            deferred_events: list[OwnershipEvent] = []
            defer_call = None
            if type(deferred_value).__name__ == "Call":
                args = tuple(getattr(deferred_value, "args", ()))
                if all(type(arg).__name__ == "Name" for arg in args):
                    defer_call = (
                        deferred_value.callee,
                        tuple(arg.value for arg in args),
                    )

            if deferred_body is not None:
                deferred_env = _analyze_block_ownership(
                    deferred_body,
                    result,
                    typed_module,
                    typed_function,
                    deferred_events,
                    history=history + tuple(events),
                    path_cleanup=path_cleanup,
                    loop_cleanup=loop_cleanup,
                    loop_control_exit=loop_control_exit,
                    loop_entry_names=loop_entry_names,
                    loop_event_history=loop_event_history + tuple(events),
                    collect_return_cleanup=False,
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
                    history=history + tuple(events),
                    path_cleanup=path_cleanup,
                    loop_cleanup=loop_cleanup,
                    loop_control_exit=loop_control_exit,
                    loop_entry_names=loop_entry_names,
                    loop_event_history=loop_event_history + tuple(events),
                    collect_return_cleanup=False,
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
                domain = result.domain_of(name)
                if domain is OwnershipDomain.SHARED:
                    result.require_live(name)
                    events.append(
                        OwnershipEvent(
                            "shared_defer_use",
                            name,
                            via,
                            OwnershipDomain.SHARED,
                            point_id=defer_point_id,
                            defer_call=defer_call,
                        )
                    )
                    continue
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
            loop_body = getattr(statement, "body", ())
            body_events: list[OwnershipEvent] = []
            body_control_states: list[tuple[str, OwnershipEnv]] = []
            body_env = _analyze_block_ownership(
                loop_body,
                result,
                typed_module,
                typed_function,
                body_events,
                history=history + tuple(events),
                path_cleanup=path_cleanup,
                loop_cleanup=loop_cleanup,
                loop_control_exit=loop_control_exit,
                loop_entry_names=visible,
                loop_event_history=(),
                loop_control_states=body_control_states,
                collect_return_cleanup=collect_return_cleanup,
            )

            control_state_envs = [env for _, env in body_control_states]
            invariant_envs = [body_env, *control_state_envs]
            for candidate_env in invariant_envs:
                for name in visible:
                    before_binding = next(
                        binding for binding in result.bindings
                        if binding.name == name
                    )
                    after_binding = next(
                        binding for binding in candidate_env.bindings
                        if binding.name == name
                    )
                    if before_binding.type != after_binding.type:
                        raise Phase1SemanticError(
                            f"ownership binding {name!r} changed type across loop backedge"
                        )
                    if before_binding.domain is not after_binding.domain:
                        raise Phase1SemanticError(
                            f"ownership binding {name!r} changed domain across loop "
                            f"backedge: {before_binding.domain.value} vs "
                            f"{after_binding.domain.value}"
                        )
                    if before_binding.state is not after_binding.state:
                        raise Phase1SemanticError(
                            f"sole value {name!r} moved inside loop without reinitialization"
                        )

            local_shared = tuple(
                binding for binding in body_env.bindings
                if binding.name not in visible
                and binding.domain is OwnershipDomain.SHARED
                and binding.state is VarState.LIVE
            )
            body_may_fallthrough = _block_may_fallthrough(loop_body)
            if local_shared and body_may_fallthrough:
                local_env = OwnershipEnv(local_shared)
                local_plan = plan_shared_scope_cleanup(
                    local_env,
                    history + tuple(events) + tuple(body_events),
                )
                for step in local_plan.steps:
                    loop_cleanup.append(
                        SharedCleanupStep(
                            owner=step.owner,
                            account=step.account,
                            strong_refs_before=step.strong_refs_before,
                            strong_refs_after=step.strong_refs_after,
                            destroy_after=step.destroy_after,
                            via=f"loop_backedge:{kind.lower()}",
                            point_id=_cleanup_point_id(
                                statement, f"{kind.lower()}_backedge"
                            ),
                        )
                    )

            body_env = _project_ownership_env(body_env, visible)
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

    path_cleanup: list[SharedCleanupStep] = []
    loop_cleanup: list[SharedCleanupStep] = []
    loop_control_exit: list[SharedExitAction] = []
    env = _analyze_block_ownership(
        parsed_function.body,
        env,
        typed_module,
        typed_function,
        events,
        path_cleanup=path_cleanup,
        loop_cleanup=loop_cleanup,
        loop_control_exit=loop_control_exit,
    )
    cleanup = plan_shared_scope_cleanup(env, events)
    exit_plan = plan_shared_exit(events, cleanup)
    return OwnershipTrace(
        env,
        tuple(events),
        cleanup,
        SharedCleanupPlan(tuple(path_cleanup)),
        SharedCleanupPlan(tuple(loop_cleanup)),
        SharedExitPlan(tuple(loop_control_exit)),
        exit_plan,
    )


@dataclass(frozen=True)
class OwnershipParamContract:
    name: str
    takes_ownership: bool
    domain: OwnershipDomain | None = None


@dataclass(frozen=True)
class OwnershipFunctionSummary:
    name: str
    params: tuple[OwnershipParamContract, ...]
    returns_sole: bool
    calls: tuple[str, ...]
    return_domain: OwnershipDomain | None = None


@dataclass(frozen=True)
class OwnershipModuleAnalysis:
    summaries: tuple[OwnershipFunctionSummary, ...]
    traces: tuple[tuple[str, OwnershipTrace], ...]


@dataclass(frozen=True)
class OwnershipDomainNode:
    function: str
    binding: str
    type: SemanticType
    domain: OwnershipDomain
    final_state: VarState

    @property
    def key(self) -> str:
        return f"{self.function}::{self.binding}"


@dataclass(frozen=True)
class OwnershipDomainTransfer:
    function: str
    binding: str
    domain: OwnershipDomain
    via: str
    destination: str | None = None
    source_domain: OwnershipDomain | None = field(default=None, compare=False)
    target_domain: OwnershipDomain | None = field(default=None, compare=False)
    destination_domain: OwnershipDomain | None = field(default=None, compare=False)

    @property
    def source_key(self) -> str:
        return f"{self.function}::{self.binding}"


@dataclass(frozen=True)
class OwnershipDomainMerge:
    function: str
    binding: str
    domain: OwnershipDomain
    left_state: VarState
    right_state: VarState
    result_state: VarState
    via: str


@dataclass(frozen=True)
class OwnershipDomainGraph:
    nodes: tuple[OwnershipDomainNode, ...]
    transfers: tuple[OwnershipDomainTransfer, ...]
    merges: tuple[OwnershipDomainMerge, ...] = ()
    planned_transitions: tuple[OwnershipDomainTransition, ...] = ()
    shared_accounts: tuple[SharedOwnershipAccount, ...] = ()


def build_ownership_domain_graph(
    analysis: OwnershipModuleAnalysis,
) -> OwnershipDomainGraph:
    """Project ownership traces into a backend-neutral domain graph.

    Nodes identify tracked owners by function scope. Transfer edges preserve
    the semantic sink recorded by the ownership pass (call, return, struct
    field, enum payload, and future domain transitions) without interpreting
    it as backend behavior.
    """
    nodes: list[OwnershipDomainNode] = []
    transfers: list[OwnershipDomainTransfer] = []
    merges: list[OwnershipDomainMerge] = []
    node_keys: set[str] = set()

    for function_name, trace in analysis.traces:
        bindings = {binding.name: binding for binding in trace.final_env.bindings}
        for binding in trace.final_env.bindings:
            node = OwnershipDomainNode(
                function=function_name,
                binding=binding.name,
                type=binding.type,
                domain=binding.domain,
                final_state=binding.state,
            )
            if node.key in node_keys:
                raise Phase1SemanticError(
                    f"duplicate ownership-domain node {node.key!r}"
                )
            node_keys.add(node.key)
            nodes.append(node)

        for event in trace.events:
            if event.kind in ("move", "handover", "quarantine"):
                binding = bindings.get(event.name)
                if binding is None:
                    raise Phase1SemanticError(
                        f"ownership transfer for untracked binding "
                        f"{function_name}::{event.name}"
                    )
                source_domain = event.source_domain
                target_domain = event.target_domain
                destination_domain = event.destination_domain

                if event.kind == "quarantine":
                    if (
                        source_domain is not OwnershipDomain.EXCLUSIVE
                        or target_domain is not OwnershipDomain.ISLAND
                    ):
                        raise Phase1SemanticError(
                            f"incomplete quarantine domain transition for "
                            f"{function_name}::{event.name}"
                        )
                elif event.kind == "handover" and event.destination is not None:
                    if source_domain is None or target_domain is None:
                        raise Phase1SemanticError(
                            f"incomplete handover domain transition for "
                            f"{function_name}::{event.name}"
                        )
                    if destination_domain is not target_domain:
                        raise Phase1SemanticError(
                            f"handover destination domain mismatch for "
                            f"{function_name}::{event.name}"
                        )
                elif event.kind == "move" and event.via == "return":
                    if source_domain is None:
                        source_domain = binding.domain
                    if target_domain is None:
                        target_domain = source_domain
                    if source_domain is not target_domain:
                        raise Phase1SemanticError(
                            f"return transfer changes ownership domain for "
                            f"{function_name}::{event.name}"
                        )
                elif source_domain is None:
                    source_domain = binding.domain

                transfers.append(
                    OwnershipDomainTransfer(
                        function=function_name,
                        binding=event.name,
                        domain=binding.domain,
                        via=event.via,
                        destination=event.destination,
                        source_domain=source_domain,
                        target_domain=target_domain,
                        destination_domain=destination_domain,
                    )
                )
                continue
            if event.kind == "domain_merge":
                if (
                    event.domain is None
                    or event.left_state is None
                    or event.right_state is None
                    or event.result_state is None
                ):
                    raise Phase1SemanticError(
                        f"incomplete ownership-domain merge fact for "
                        f"{function_name}::{event.name}"
                    )
                merges.append(
                    OwnershipDomainMerge(
                        function=function_name,
                        binding=event.name,
                        domain=event.domain,
                        left_state=event.left_state,
                        right_state=event.right_state,
                        result_state=event.result_state,
                        via=event.via,
                    )
                )

    return OwnershipDomainGraph(
        tuple(nodes), tuple(transfers), tuple(merges)
    )


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
                        param.ownership_domain is not None,
                        param.ownership_domain,
                    )
                    for param in function.params
                ),
                returns_sole=(
                    function.return_ownership_domain
                    is OwnershipDomain.EXCLUSIVE
                ),
                calls=tuple(calls),
                return_domain=function.return_ownership_domain,
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
    is_mut: bool = False


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
    if kind == "Binary":
        op = getattr(expr, "op", None)
        if op not in ("+", "-", "*"):
            return None
        left = _integer_constant_value(getattr(expr, "left", None))
        right = _integer_constant_value(getattr(expr, "right", None))
        if left is None or right is None:
            return None
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        return left * right
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


def _is_unsuffixed_integer_constant_expr(expr) -> bool:
    """Return whether a simple integer constant expression has no type suffixes."""
    if _is_unsuffixed_integer_literal_expr(expr):
        return True
    if type(expr).__name__ != "Binary":
        return False
    if getattr(expr, "op", None) not in ("+", "-", "*"):
        return False
    return (
        _is_unsuffixed_integer_constant_expr(getattr(expr, "left", None))
        and _is_unsuffixed_integer_constant_expr(getattr(expr, "right", None))
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
    if not _is_unsuffixed_integer_constant_expr(expr):
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

    if (
        inferred.type.pointer
        and expected.pointer
        and inferred.type.is_reference
        and expected.is_reference
        and inferred.type.name == expected.name
        and not inferred.type.is_array
        and not expected.is_array
        and inferred.type.mutable
        and not expected.mutable
    ):
        return TypedExprNode(inferred.kind, expected, inferred.label)

    if (
        inferred.type.pointer
        and expected.pointer
        and not inferred.type.is_reference
        and not expected.is_reference
        and not inferred.type.is_array
        and not expected.is_array
        and (
            inferred.type.name == expected.name
            or inferred.type.name == "void"
            or expected.name == "void"
        )
        and not (expected.mutable and not inferred.type.mutable)
    ):
        return TypedExprNode(inferred.kind, expected, inferred.label)

    if (
        type(expr).__name__ == "NullLit"
        and expected.pointer
        and not expected.is_reference
        and not expected.is_array
    ):
        return TypedExprNode(inferred.kind, expected, inferred.label)

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
        for item in typed_module.functions:
            if item.name == name:
                return TypedExprNode(
                    kind,
                    SemanticType(
                        "__fn_ptr",
                        is_fn_ptr=True,
                        fn_params=tuple(param.type for param in item.params),
                        fn_ret=item.result,
                    ),
                    name,
                )
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
        return TypedExprNode(kind, SemanticType("u8", pointer=True), None)

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
        variant = next(
            (item for item in enum.variants if item.name == variant_name),
            None,
        )
        if variant is None:
            raise Phase1SemanticError(
                f"enum {enum_name!r} has no variant {variant_name!r}"
            )
        if variant.payload_type is not None:
            raise Phase1SemanticError(
                f"enum variant {enum_name}::{variant_name} requires payload"
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
                    mutable=bool(getattr(expr, "mutable", False)),
                    is_array=inner.type.is_array,
                    array_size=inner.type.array_size,
                    is_reference=True,
                    elem_type=inner.type.elem_type,
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
            if not _is_scalar_integer_type(inner.type):
                raise Phase1SemanticError(
                    f"bitwise not requires integer, got {inner.type.name}"
                )
            return TypedExprNode(kind, inner.type, op)
        if op == "-":
            signed_numeric_types = {
                "i8", "i16", "i32", "i64", "isize", "f32", "f64"
            }
            if (
                not _is_scalar_numeric_type(inner.type)
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
        if not _is_scalar_integer_type(index.type):
            raise Phase1SemanticError(
                f"array index must be scalar integer, got {index.type.name}"
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
                    pointer=False,
                    mutable=False,
                    is_reference=False,
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
        owner_struct = next(
            (
                item for item in typed_module.structs
                if item.name == owner_name
            ),
            None,
        )
        function_field = None
        if owner_struct is not None:
            function_field = next(
                (
                    item for item in owner_struct.fields
                    if item.name == method_name and item.type.is_fn_ptr
                ),
                None,
            )
        if function_field is not None:
            arguments = tuple(getattr(expr, "args", ()))
            expected_params = function_field.type.fn_params
            if len(arguments) != len(expected_params):
                raise Phase1SemanticError(
                    f"function field {owner_name}.{method_name} "
                    "has wrong argument count"
                )
            for argument, expected in zip(arguments, expected_params):
                inferred = infer_expression_type(
                    argument, env, typed_module
                )
                contextual = _contextualize_expression(
                    argument, inferred, expected, env, typed_module
                )
                if contextual.type != expected:
                    raise Phase1SemanticError(
                        f"function field {owner_name}.{method_name} "
                        "argument type mismatch: "
                        f"expected {expected.name}, got "
                        f"{contextual.type.name}"
                    )
            result_type = (
                function_field.type.fn_ret
                or SemanticType("void")
            )
            return TypedExprNode(
                kind,
                result_type,
                f"{owner_name}.{method_name}",
            )

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

    if kind == "ShareExpr":
        source = getattr(expr, "value", None)
        if type(source).__name__ != "Name":
            raise Phase1SemanticError(
                "share currently requires a direct owned binding"
            )
        source_name = getattr(source, "value", None)
        source_type = env.get(source_name)
        if source_type is None:
            raise Phase1SemanticError(
                f"share source {source_name!r} is not declared"
            )
        if not is_sole_type(source_type, typed_module):
            raise Phase1SemanticError(
                f"share source {source_name!r} is not an exclusive sole value"
            )
        return TypedExprNode("Share", source_type, f"share:{source_name}")

    if kind == "Call":
        callee = getattr(expr, "callee")

        constructor = None
        for enum in typed_module.enums:
            for variant in enum.variants:
                if f"{enum.name}_{variant.name}" == callee:
                    constructor = (enum, variant)
                    break
            if constructor is not None:
                break

        if constructor is not None:
            enum, variant = constructor
            if variant.payload_type is None:
                raise Phase1SemanticError(
                    f"enum variant {enum.name}::{variant.name} has no payload"
                )
            arguments = tuple(getattr(expr, "args", ()))
            if len(arguments) != 1:
                raise Phase1SemanticError(
                    f"enum constructor {enum.name}::{variant.name} "
                    "requires exactly one payload"
                )
            inferred = infer_expression_type(
                arguments[0], env, typed_module
            )
            contextual = _contextualize_expression(
                arguments[0],
                inferred,
                variant.payload_type,
                env,
                typed_module,
            )
            if contextual.type != variant.payload_type:
                raise Phase1SemanticError(
                    f"enum constructor {enum.name}::{variant.name} "
                    f"payload type mismatch: expected "
                    f"{variant.payload_type.name}, got {contextual.type.name}"
                )
            return TypedExprNode(
                kind,
                SemanticType(enum.name),
                f"{enum.name}::{variant.name}",
            )

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
                (
                    left.type.pointer
                    and not left.type.is_reference
                    and right.type.name == "null"
                )
                or (
                    right.type.pointer
                    and not right.type.is_reference
                    and left.type.name == "null"
                )
            )
            if left.type != right.type and not pointer_null:
                raise Phase1SemanticError(
                    f"comparison operator {op!r} type mismatch: "
                    f"{left.type.name} vs {right.type.name}"
                )
            return TypedExprNode(kind, SemanticType("bool"), op)

        if op in ("<", "<=", ">", ">="):
            if (
                not _is_scalar_numeric_type(left.type)
                or not _is_scalar_numeric_type(right.type)
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

        if (
            op in ("+", "-")
            and left.type.pointer
            and not left.type.is_reference
            and _is_scalar_integer_type(right.type)
        ):
            return TypedExprNode(kind, left.type, op)

        if op in ("+", "-", "*", "/", "%"):
            if (
                not _is_scalar_numeric_type(left.type)
                or not _is_scalar_numeric_type(right.type)
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
                left_value = _integer_constant_value(left_expr)
                _, signed = _INTEGER_WIDTHS[left.type.name]
                if signed and divisor == -1 and left_value is not None:
                    minimum, _ = integer_bounds(left.type)
                    if left_value == minimum:
                        operation = "division" if op == "/" else "modulo"
                        raise Phase1SemanticError(
                            f"integer {operation} overflow for "
                            f"{left.type.name} minimum divided by -1"
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
                not _is_scalar_integer_type(left.type)
                or not _is_scalar_integer_type(right.type)
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
                not _is_scalar_integer_type(left.type)
                or not _is_scalar_integer_type(right.type)
            ):
                raise Phase1SemanticError(
                    f"shift operator {op!r} requires integer operands"
                )
            shift = _integer_constant_value(right_expr)
            if shift is not None:
                width, signed = _INTEGER_WIDTHS[left.type.name]
                if shift < 0 or shift >= width:
                    raise Phase1SemanticError(
                        f"shift count {shift} out of range for "
                        f"{left.type.name} width {width}"
                    )
                left_value = _integer_constant_value(left_expr)
                if signed and left_value is not None and left_value < 0:
                    direction = "left" if op == "<<" else "right"
                    raise Phase1SemanticError(
                        f"{direction} shift of negative signed integer "
                        "is not allowed"
                    )
                if op == "<<" and left_value is not None:
                    validate_integer_value(
                        left_value << shift, left.type
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
    in_unsafe: bool = False,
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
    if kind == "Index":
        container = infer_expression_type(
            getattr(target, "target"), env, typed_module
        )
        if container.type.is_reference:
            if not container.type.mutable:
                raise Phase1SemanticError(
                    "assignment through immutable reference is not allowed"
                )
        elif container.type.pointer and not in_unsafe:
            raise Phase1SemanticError(
                "raw pointer index assignment requires unsafe"
            )
        return infer_expression_type(target, env, typed_module)
    if kind == "Member":
        container = infer_expression_type(
            getattr(target, "target"), env, typed_module
        )
        if container.type.is_reference:
            if not container.type.mutable:
                raise Phase1SemanticError(
                    "assignment through immutable reference is not allowed"
                )
        elif container.type.pointer and not in_unsafe:
            raise Phase1SemanticError(
                "raw pointer member assignment requires unsafe"
            )
        return infer_expression_type(target, env, typed_module)
    if kind == "Unary" and getattr(target, "op", None) == "*":
        pointee = infer_expression_type(
            getattr(target, "value"), env, typed_module
        )
        if pointee.type.is_reference:
            if not pointee.type.mutable:
                raise Phase1SemanticError(
                    "assignment through immutable reference is not allowed"
                )
        else:
            if not pointee.type.pointer:
                raise Phase1SemanticError(
                    "dereference assignment target must be a pointer or reference"
                )
            if not in_unsafe:
                raise Phase1SemanticError(
                    "raw pointer dereference assignment requires unsafe"
                )
        return TypedExprNode(
            kind,
            SemanticType(
                pointee.type.name,
                pointer=False,
                mutable=False,
                is_reference=False,
            ),
            "*",
        )
    raise Phase1SemanticError(
        f"assignment target typing not implemented for {kind}"
    )


def _mutable_place(
    expr,
    mutable_bindings: set[str],
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> bool:
    kind = type(expr).__name__
    if kind == "Name":
        name = getattr(expr, "value")
        if name in env:
            return name in mutable_bindings
        global_item = next(
            (item for item in typed_module.globals if item.name == name),
            None,
        )
        return bool(global_item and global_item.is_mut)
    if kind in ("Index", "Member"):
        return _mutable_place(
            getattr(expr, "target"),
            mutable_bindings,
            env,
            typed_module,
        )
    if kind == "Unary" and getattr(expr, "op", None) == "*":
        pointee = infer_expression_type(
            getattr(expr, "value"), env, typed_module
        )
        return bool(pointee.type.pointer and pointee.type.mutable)
    return False


def _validate_mutable_borrows(
    expr,
    mutable_bindings: set[str],
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> None:
    if expr is None:
        return

    kind = type(expr).__name__
    if (
        kind == "Unary"
        and getattr(expr, "op", None) == "&"
        and bool(getattr(expr, "mutable", False))
        and not _mutable_place(
            getattr(expr, "value"),
            mutable_bindings,
            env,
            typed_module,
        )
    ):
        raise Phase1SemanticError(
            "mutable reference requires mutable binding"
        )

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
        _validate_mutable_borrows(
            child, mutable_bindings, env, typed_module
        )


def _validate_statement_mutable_borrows(
    statement,
    mutable_bindings: set[str],
    env: dict[str, SemanticType],
    typed_module: TypedModule,
) -> None:
    kind = type(statement).__name__
    if kind in ("Let", "Return", "Expression"):
        expressions = (getattr(statement, "value", None),)
    elif kind == "Assign":
        expressions = (
            getattr(statement, "target", None),
            getattr(statement, "value", None),
        )
    elif kind in ("If", "While"):
        expressions = (getattr(statement, "condition", None),)
    elif kind == "For":
        expressions = (
            getattr(statement, "start", None),
            getattr(statement, "end", None),
        )
    elif kind == "Asm":
        expressions = (
            *tuple(getattr(statement, "outputs", ())),
            *tuple(getattr(statement, "inputs", ())),
        )
    elif kind == "Defer":
        deferred = getattr(statement, "value", None)
        if type(deferred).__name__ == "Assign":
            expressions = (
                getattr(deferred, "target", None),
                getattr(deferred, "value", None),
            )
        else:
            expressions = (deferred,)
    else:
        expressions = ()

    for expr in expressions:
        _validate_mutable_borrows(
            expr, mutable_bindings, env, typed_module
        )


def _build_typed_block(
    statements,
    env: dict[str, SemanticType],
    typed_module: TypedModule,
    typed_function: TypedFunction,
    in_unsafe: bool = False,
    mutable_bindings: set[str] | None = None,
) -> tuple[TypedStmtNode, ...]:
    typed_statements: list[TypedStmtNode] = []
    if mutable_bindings is None:
        mutable_bindings = set()

    for statement in statements:
        kind = type(statement).__name__
        _validate_statement_mutable_borrows(
            statement, mutable_bindings, env, typed_module
        )
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
            if bool(getattr(statement, "is_mut", False)):
                mutable_bindings.add(statement.name)
            else:
                mutable_bindings.discard(statement.name)
            typed_statements.append(
                TypedStmtNode(
                    "Let",
                    statement.name,
                    declared,
                    expr,
                    is_mut=bool(getattr(statement, "is_mut", False)),
                )
            )
            continue

        if kind == "Assign":
            target = infer_assignment_target_type(
                getattr(statement, "target"), env, typed_module, in_unsafe
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
                in_unsafe,
                set(mutable_bindings),
            )
            else_body = _build_typed_block(
                getattr(statement, "else_body", ()),
                dict(env),
                typed_module,
                typed_function,
                in_unsafe,
                set(mutable_bindings),
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
                in_unsafe,
                set(mutable_bindings),
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
                in_unsafe,
                set(mutable_bindings),
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
            start_is_integer = _is_scalar_integer_type(start.type)
            end_is_integer = _is_scalar_integer_type(end.type)
            if not start_is_integer or not end_is_integer:
                raise Phase1SemanticError(
                    f"for range bounds must be scalar integers, got "
                    f"{start.type.name} and {end.type.name}"
                )
            if start.type != end.type:
                raise Phase1SemanticError(
                    f"for range bound type mismatch: "
                    f"{start.type.name} vs {end.type.name}"
                )
            loop_env = dict(env)
            loop_name = getattr(statement, "var_name")
            loop_env[loop_name] = start.type
            loop_mutable_bindings = set(mutable_bindings)
            if bool(getattr(statement, "is_mut", False)):
                loop_mutable_bindings.add(loop_name)
            else:
                loop_mutable_bindings.discard(loop_name)
            body = _build_typed_block(
                getattr(statement, "body", ()),
                loop_env,
                typed_module,
                typed_function,
                in_unsafe,
                loop_mutable_bindings,
            )
            typed_statements.append(
                TypedStmtNode(
                    "For",
                    getattr(statement, "var_name"),
                    start.type,
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
                True,
                set(mutable_bindings),
            )
            typed_statements.append(
                TypedStmtNode("Unsafe", None, None, None, body)
            )
            continue

        if kind == "Asm":
            for output in getattr(statement, "outputs", ()):
                infer_assignment_target_type(
                    output, env, typed_module, in_unsafe
                )
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
                    in_unsafe,
                    set(mutable_bindings),
                )
                typed_statements.append(
                    TypedStmtNode("Defer", None, None, None, body)
                )
                continue

            if deferred_value is None:
                raise Phase1SemanticError("defer has no action")

            if type(deferred_value).__name__ == "Assign":
                target = infer_assignment_target_type(
                    getattr(deferred_value, "target"),
                    env,
                    typed_module,
                    in_unsafe,
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
    ownership_domains: OwnershipDomainGraph
    enum_layouts: tuple[TypedEnumLayout, ...] = ()
    enum_storage_layouts: tuple[TypedEnumStorageLayout, ...] = ()
    maturity: str = MATURITY


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
    ownership_domains = build_ownership_domain_graph(ownership)
    enum_layouts = lower_module_enum_layouts(typed_module)
    enum_storage_layouts = lower_module_enum_storage_layouts(enum_layouts)
    return Phase1ModuleSnapshot(
        typed_module=typed_module,
        bodies=bodies,
        ownership=ownership,
        ownership_domains=ownership_domains,
        enum_layouts=enum_layouts,
        enum_storage_layouts=enum_storage_layouts,
    )


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
    is_fn_ptr: bool = False
    fn_params: tuple["SemanticType", ...] = ()
    fn_ret: "SemanticType | None" = None
    declared_ownership_domain: OwnershipDomain | None = field(default=None, compare=False)


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
    ownership_domain: OwnershipDomain | None = None


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
    payload_type: SemanticType | None = None


@dataclass(frozen=True)
class TypedEnum:
    name: str
    variants: tuple[TypedEnumVariant, ...]
    public: bool


@dataclass(frozen=True)
class TypedEnumVariantLayout:
    name: str
    tag: int
    payload_type: SemanticType | None


@dataclass(frozen=True)
class TypedEnumLayout:
    enum_name: str
    storage: str
    variants: tuple[TypedEnumVariantLayout, ...]


@dataclass(frozen=True)
class TypedEnumPayloadSlot:
    variant_name: str
    active_tag: int
    payload_type: SemanticType


@dataclass(frozen=True)
class TypedEnumStorageLayout:
    enum_name: str
    tag_storage: str
    payload_storage: str
    payload_slots: tuple[TypedEnumPayloadSlot, ...]


def lower_enum_storage_layout(
    layout: TypedEnumLayout,
) -> TypedEnumStorageLayout:
    """Describe backend-neutral storage for one normalized enum layout.

    Every enum stores its discriminant separately. Payload-bearing variants
    share one logical union storage, and a payload slot is valid only while
    the enum tag equals that slot's active_tag. Width, alignment, padding, and
    concrete backend syntax remain intentionally unspecified here.
    """
    payload_slots = tuple(
        TypedEnumPayloadSlot(
            variant_name=variant.name,
            active_tag=variant.tag,
            payload_type=variant.payload_type,
        )
        for variant in layout.variants
        if variant.payload_type is not None
    )

    if layout.storage == "tag_only":
        if payload_slots:
            raise Phase1SemanticError(
                f"enum {layout.enum_name!r} tag-only layout contains payload slots"
            )
        payload_storage = "none"
    elif layout.storage == "tagged_union":
        if not payload_slots:
            raise Phase1SemanticError(
                f"enum {layout.enum_name!r} tagged-union layout has no payload slots"
            )
        payload_storage = "union"
    else:
        raise Phase1SemanticError(
            f"enum {layout.enum_name!r} has unknown storage {layout.storage!r}"
        )

    return TypedEnumStorageLayout(
        enum_name=layout.enum_name,
        tag_storage="discriminant",
        payload_storage=payload_storage,
        payload_slots=payload_slots,
    )


def lower_enum_layout(enum: TypedEnum) -> TypedEnumLayout:
    """Normalize enum discriminants before any backend-specific ABI lowering.

    Payload-bearing enums are represented semantically as tagged unions, while
    payload-free enums remain tag-only.  This pass fixes variant tags and
    rejects ambiguous duplicate discriminants without choosing a C/native
    storage ABI yet.
    """
    next_tag = 0
    seen_tags: dict[int, str] = {}
    variants: list[TypedEnumVariantLayout] = []

    for variant in enum.variants:
        tag = variant.value if variant.value is not None else next_tag
        previous = seen_tags.get(tag)
        if previous is not None:
            raise Phase1SemanticError(
                f"enum {enum.name!r} has duplicate discriminant {tag}: "
                f"{previous!r} and {variant.name!r}"
            )
        seen_tags[tag] = variant.name
        variants.append(
            TypedEnumVariantLayout(
                name=variant.name,
                tag=tag,
                payload_type=variant.payload_type,
            )
        )
        next_tag = tag + 1

    storage = (
        "tagged_union"
        if any(item.payload_type is not None for item in variants)
        else "tag_only"
    )
    return TypedEnumLayout(enum.name, storage, tuple(variants))


def lower_module_enum_layouts(
    module: TypedModule,
) -> tuple[TypedEnumLayout, ...]:
    """Lower every typed enum to a backend-neutral canonical layout."""
    return tuple(lower_enum_layout(enum) for enum in module.enums)


def lower_module_enum_storage_layouts(
    layouts: tuple[TypedEnumLayout, ...],
) -> tuple[TypedEnumStorageLayout, ...]:
    """Plan logical tag/payload storage for normalized enum layouts."""
    return tuple(lower_enum_storage_layout(layout) for layout in layouts)


@dataclass(frozen=True)
class TypedParam:
    name: str
    type: SemanticType
    ownership_domain: OwnershipDomain | None = None


@dataclass(frozen=True)
class TypedFunction:
    name: str
    params: tuple[TypedParam, ...]
    result: SemanticType
    public: bool
    attributes: tuple[str, ...]
    return_ownership_domain: OwnershipDomain | None = None


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
        is_fn_ptr=bool(getattr(type_obj, "is_fn_ptr", False)),
        fn_params=tuple(
            semantic_type(item)
            for item in getattr(type_obj, "fn_params", ())
        ),
        fn_ret=(
            semantic_type(type_obj.fn_ret)
            if getattr(type_obj, "fn_ret", None) is not None
            else None
        ),
        declared_ownership_domain=(
            OwnershipDomain.ISLAND
            if getattr(type_obj, "ownership_domain", None) == "island"
            else None
        ),
    )


_INTEGER_WIDTHS = {
    "u8": (8, False), "u16": (16, False), "u32": (32, False),
    "u64": (64, False), "usize": (64, False),
    "i8": (8, True), "i16": (16, True), "i32": (32, True),
    "i64": (64, True), "isize": (64, True),
}


def _is_scalar_integer_type(type_info: SemanticType) -> bool:
    return (
        not type_info.pointer
        and not type_info.is_array
        and not type_info.is_reference
        and type_info.name in _INTEGER_WIDTHS
    )


def _is_scalar_numeric_type(type_info: SemanticType) -> bool:
    return (
        _is_scalar_integer_type(type_info)
        or (
            not type_info.pointer
            and not type_info.is_array
            and not type_info.is_reference
            and type_info.name in {"f32", "f64"}
        )
    )


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
    exclusive_type_names = frozenset(
        item.name
        for item in module.structs
        if bool(getattr(item, "is_sole", False))
    )

    def explicit_domain(type_obj) -> OwnershipDomain | None:
        frozen = semantic_type(type_obj)
        declared = frozen.declared_ownership_domain
        if declared is OwnershipDomain.ISLAND:
            if frozen.pointer or frozen.is_reference or frozen.is_array:
                raise Phase1SemanticError(
                    "island ownership requires a direct by-value sole type"
                )
            if frozen.name not in exclusive_type_names:
                raise Phase1SemanticError(
                    f"island ownership requires sole type, got {frozen.name!r}"
                )
            return OwnershipDomain.ISLAND
        if frozen.pointer or frozen.is_reference:
            return None
        if frozen.name in exclusive_type_names:
            return OwnershipDomain.EXCLUSIVE
        return None

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
                ownership_domain=(
                    OwnershipDomain.EXCLUSIVE
                    if bool(getattr(item, "is_sole", False))
                    else None
                ),
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
                    TypedParam(
                        name,
                        semantic_type(type_obj),
                        explicit_domain(type_obj),
                    )
                    for name, type_obj in item.params
                ),
                result=semantic_type(item.result),
                public=bool(item.public),
                attributes=tuple(item.attributes),
                return_ownership_domain=explicit_domain(item.result),
            )
            for item in module.functions
        ),
        filename=module.filename,
        enums=tuple(
            TypedEnum(
                name=item.name,
                variants=tuple(
                    TypedEnumVariant(
                        variant.name,
                        variant.value,
                        (
                            semantic_type(variant.payload_type)
                            if getattr(variant, "payload_type", None) is not None
                            else None
                        ),
                    )
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
                            TypedParam(
                                name,
                                semantic_type(type_obj),
                                explicit_domain(type_obj),
                            )
                            for name, type_obj in method.params
                        ),
                        result=semantic_type(method.result),
                        public=bool(method.public),
                        attributes=tuple(method.attributes),
                        return_ownership_domain=explicit_domain(method.result),
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
    "MATURITY", "Phase1SemanticError", "VarState", "OwnershipDomain",
    "ownership_domain", "sole_type_names", "is_sole_type",
    "initial_ownership_state", "require_sole_transfer", "OwnershipBinding", "OwnershipEnv",
    "seed_function_ownership", "OwnershipEvent", "SharedCleanupStep",
    "SharedCleanupPlan", "SharedExitAction", "SharedExitPlan", "OwnershipTrace",
    "plan_shared_scope_cleanup", "plan_shared_exit",
    "plan_shared_control_exit",
    "require_expr_ownership_live",
    "analyze_linear_function_ownership", "analyze_function_ownership",
    "OwnershipParamContract", "OwnershipFunctionSummary",
    "OwnershipModuleAnalysis", "OwnershipDomainNode", "OwnershipDomainTransfer",
    "OwnershipDomainMerge", "OwnershipDomainTransition",
    "SharedOwnershipAccount", "OwnershipDomainGraph", "build_ownership_domain_graph",
    "merge_ownership_bindings", "plan_ownership_domain_transition",
    "open_shared_ownership_account", "retain_shared_owner", "release_shared_owner",
    "SharedOwnershipApplication", "TypedShareExpression",
    "apply_shared_transition", "build_typed_share_expression",
    "summarize_module_ownership", "analyze_module_ownership", "TypedExprNode", "TypedStmtNode",
    "TypedFunctionBody", "infer_expression_type",
    "infer_assignment_target_type", "build_linear_typed_body",
    "Phase1ModuleSnapshot", "build_phase1_semantic_snapshot",
    "apply_ownership_moves", "merge_conditional_ownership",
    "validate_loop_ownership", "require_live", "move_state", "merge_branch_states",
    "SourceSpan", "SemanticType",
    "TypedField", "TypedStruct", "TypedClass", "TypedEnumVariant", "TypedEnum",
    "TypedEnumVariantLayout", "TypedEnumLayout", "lower_enum_layout",
    "TypedEnumPayloadSlot", "TypedEnumStorageLayout",
    "lower_enum_storage_layout", "lower_module_enum_layouts",
    "lower_module_enum_storage_layouts",
    "TypedParam", "TypedFunction", "TypedGlobal", "TypedModule",
    "semantic_type", "integer_bounds", "validate_integer_value",
    "validate_no_recursive_value_types",
    "build_declaration_typed_ast",
]
