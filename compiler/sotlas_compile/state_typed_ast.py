"""Canonical Phase-4 Typed AST extension for State Spaces.

This module does not define another parser or checker. It freezes the already
certified :mod:`state_frontend` facts into a typed, declaration-aware snapshot
that can be attached to ``Phase1CheckedModule`` while the production release
gate remains fail-closed until SIR/backend support exists.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from .state_frontend import StateSpaceFrontendPlan, plan_state_space_frontend
from .state_typestate import StateQualifiedType, certify_typestate
from .typed_ast import Phase1SemanticError


class StateSpaceTypedASTError(Phase1SemanticError):
    """Raised when frontend State Space facts cannot be frozen consistently."""


@dataclass(frozen=True)
class TypedStatePayload:
    type_name: str
    name: str | None = None


@dataclass(frozen=True)
class TypedState:
    name: str
    payload: tuple[TypedStatePayload, ...] = ()


@dataclass(frozen=True)
class TypedStateTransition:
    source: str
    target: str


@dataclass(frozen=True)
class TypedStateSpace:
    name: str
    states: tuple[TypedState, ...]
    transitions: tuple[TypedStateTransition, ...]
    initial_state: str | None
    public: bool
    line: int
    column: int


@dataclass(frozen=True)
class TypedStateTypeSite:
    """One state-qualified type attached to a deterministic declaration site."""

    site_id: str
    qualified: StateQualifiedType


@dataclass(frozen=True)
class StateSpaceTypedSnapshot:
    """Typed-AST facts for all State Spaces and typestate sites in one module."""

    spaces: tuple[TypedStateSpace, ...]
    type_sites: tuple[TypedStateTypeSite, ...]

    def space(self, name: str) -> TypedStateSpace:
        matches = tuple(item for item in self.spaces if item.name == name)
        if len(matches) != 1:
            raise StateSpaceTypedASTError(
                f"typed State Space {name!r} is not uniquely defined"
            )
        return matches[0]

    def site(self, site_id: str) -> TypedStateTypeSite:
        matches = tuple(item for item in self.type_sites if item.site_id == site_id)
        if len(matches) != 1:
            raise StateSpaceTypedASTError(
                f"typestate site {site_id!r} is not uniquely defined"
            )
        return matches[0]


_TYPESTATE_NAME_RE = re.compile(
    r"^(?P<space>[A-Za-z_][A-Za-z0-9_]*)<"
    r"(?P<state>[A-Za-z_][A-Za-z0-9_]*)>$"
)


def _qualified_from_type(type_obj, frontend: StateSpaceFrontendPlan):
    name = getattr(type_obj, "name", "")
    space_name = getattr(type_obj, "state_space", None)
    state_name = getattr(type_obj, "state_name", None)
    if space_name is None and state_name is None:
        match = _TYPESTATE_NAME_RE.fullmatch(name or "")
        if match is None:
            return None
        space_name = match.group("space")
        state_name = match.group("state")
    elif not isinstance(space_name, str) or not isinstance(state_name, str):
        raise StateSpaceTypedASTError(
            "typed State Space name must include both space and state"
        )
    try:
        space = frontend.space(space_name)
    except Phase1SemanticError:
        # Ordinary generics remain ordinary when no same-named State Space
        # exists. The frontend already uses this same disambiguation rule.
        return None
    try:
        return certify_typestate(
            space,
            name,
            state_name,
        )
    except Phase1SemanticError as error:
        raise StateSpaceTypedASTError(str(error)) from error


def _point(statement) -> str:
    token = getattr(statement, "token", None)
    line = getattr(token, "line", None)
    column = getattr(token, "column", None)
    if line is None or column is None:
        return "unknown"
    return f"{line}:{column}"


def _iter_local_type_sites(function_name: str, statements, path: str = "body"):
    for statement in statements:
        kind = type(statement).__name__
        if kind == "Let" and getattr(statement, "type", None) is not None:
            yield (
                f"fn:{function_name}:{path}:let:{statement.name}@{_point(statement)}",
                statement.type,
            )
        if kind == "If":
            yield from _iter_local_type_sites(
                function_name,
                getattr(statement, "then_body", ()),
                f"{path}:if@{_point(statement)}:then",
            )
            yield from _iter_local_type_sites(
                function_name,
                getattr(statement, "else_body", ()),
                f"{path}:if@{_point(statement)}:else",
            )
        elif kind == "Discern":
            for case in getattr(statement, "cases", ()):
                yield from _iter_local_type_sites(
                    function_name,
                    getattr(case, "body", ()),
                    f"{path}:discern:{case.state_name}@{_point(statement)}",
                )
        elif kind in ("While", "Loop", "For", "Unsafe"):
            yield from _iter_local_type_sites(
                function_name,
                getattr(statement, "body", ()),
                f"{path}:{kind.lower()}@{_point(statement)}",
            )
        elif kind == "Defer" and getattr(statement, "body", None) is not None:
            yield from _iter_local_type_sites(
                function_name,
                statement.body,
                f"{path}:defer@{_point(statement)}",
            )


def _iter_declared_type_sites(module):
    for struct in getattr(module, "structs", ()):
        for field in getattr(struct, "fields", ()):
            yield f"struct:{struct.name}:field:{field.name}", field.type
    for class_decl in getattr(module, "classes", ()):
        for field in getattr(class_decl, "fields", ()):
            yield f"class:{class_decl.name}:field:{field.name}", field.type
    for enum in getattr(module, "enums", ()):
        for variant in getattr(enum, "variants", ()):
            payload = getattr(variant, "payload_type", None)
            if payload is not None:
                yield f"enum:{enum.name}:variant:{variant.name}:payload", payload
    for glob in getattr(module, "globals", ()):
        yield f"global:{glob.name}", glob.type
    for function in getattr(module, "functions", ()):
        for index, (name, type_obj) in enumerate(getattr(function, "params", ())):
            yield f"fn:{function.name}:param:{index}:{name}", type_obj
        result = getattr(function, "result", None)
        if result is not None:
            yield f"fn:{function.name}:return", result
        yield from _iter_local_type_sites(
            function.name,
            getattr(function, "body", ()),
        )


def _fact_key(value: StateQualifiedType) -> tuple[str, str, str]:
    return value.type_name, value.space_name, value.state_name


def build_state_space_typed_snapshot(
    module,
    frontend: StateSpaceFrontendPlan,
) -> StateSpaceTypedSnapshot:
    """Freeze frontend State Space facts into the canonical Phase-4 Typed AST.

    The function cross-checks every direct declared ``Type<State>`` fact against
    the frontend certificate instead of reinterpreting source independently.
    """
    if not isinstance(frontend, StateSpaceFrontendPlan):
        raise StateSpaceTypedASTError(
            "State Space Typed AST requires a StateSpaceFrontendPlan"
        )

    typed_spaces: list[TypedStateSpace] = []
    for decl in frontend.declarations:
        canonical = frontend.space(decl.name)
        typed_spaces.append(
            TypedStateSpace(
                name=decl.name,
                states=tuple(
                    TypedState(
                        state.name,
                        tuple(
                            TypedStatePayload(item.type_name, item.name)
                            for item in state.payload
                        ),
                    )
                    for state in canonical.states
                ),
                transitions=tuple(
                    TypedStateTransition(edge.source, edge.target)
                    for edge in canonical.transitions
                ),
                initial_state=canonical.initial_state,
                public=bool(decl.public),
                line=decl.line,
                column=decl.column,
            )
        )

    sites: list[TypedStateTypeSite] = []
    seen_sites: set[str] = set()
    for site_id, type_obj in _iter_declared_type_sites(module):
        qualified = _qualified_from_type(type_obj, frontend)
        if qualified is None:
            continue
        if site_id in seen_sites:
            raise StateSpaceTypedASTError(
                f"duplicate typestate declaration site {site_id!r}"
            )
        seen_sites.add(site_id)
        sites.append(TypedStateTypeSite(site_id, qualified))

    frontend_facts = Counter(_fact_key(item) for item in frontend.qualified_types)
    typed_facts = Counter(_fact_key(item.qualified) for item in sites)
    if frontend_facts != typed_facts:
        raise StateSpaceTypedASTError(
            "State Space Typed AST diverges from certified frontend typestate facts"
        )

    return StateSpaceTypedSnapshot(tuple(typed_spaces), tuple(sites))


def check_state_space_preview_semantics(module, bootstrap) -> StateSpaceFrontendPlan:
    """Certify declared State Spaces for the opt-in semantic pipeline."""
    frontend = plan_state_space_frontend(module, bootstrap=bootstrap)
    if not frontend.declarations:
        bootstrap.check(module)
        return frontend
    from copy import deepcopy

    shadow = deepcopy(module)
    shadow._state_phase1_internal = True
    bootstrap.check(shadow)
    module.state_transition_facts = shadow.state_transition_facts
    module.state_space_frontend_plan = shadow.state_space_frontend_plan
    return frontend


__all__ = [
    "StateSpaceTypedASTError",
    "TypedStatePayload",
    "TypedState",
    "TypedStateTransition",
    "TypedStateSpace",
    "TypedStateTypeSite",
    "StateSpaceTypedSnapshot",
    "build_state_space_typed_snapshot",
    "check_state_space_preview_semantics",
]
