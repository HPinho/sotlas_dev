"""Backend-neutral typestate semantics for Sotlas Phase 4.

This layer composes a certified :mod:`state_space` graph with state-qualified
value types such as ``Device<Discovered>``.  It deliberately models only the
semantic contract: exact state requirements and explicit graph transitions.
Parser syntax, runtime storage, payload values, and backend lowering remain
separate concerns.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .state_space import StateSpacePlan, StateSpaceTransition
from .typed_ast import Phase1SemanticError


class TypestateError(Phase1SemanticError):
    """Raised when a state-qualified type violates its State Space contract."""


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class StateQualifiedType:
    """One backend-neutral ``Type<State>`` semantic fact."""

    type_name: str
    space_name: str
    state_name: str

    def display(self) -> str:
        return f"{self.type_name}<{self.state_name}>"


@dataclass(frozen=True)
class TypestateTransitionFact:
    """Certified change between two state-qualified views of one base type."""

    source: StateQualifiedType
    target: StateQualifiedType
    transition: StateSpaceTransition
    point_id: str | None = None



def _require_identifier(value: str, *, role: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise TypestateError(f"{role} requires a valid Sotlas identifier")



def certify_typestate(
    space: StateSpacePlan,
    type_name: str,
    state_name: str,
) -> StateQualifiedType:
    """Bind one nominal type to an existing state in ``space``.

    No initial state is inferred.  The caller must state the current state
    explicitly, keeping construction and transition semantics fail-closed.
    """
    if not isinstance(space, StateSpacePlan):
        raise TypestateError("typestate requires a certified StateSpacePlan")
    _require_identifier(type_name, role="typestate base type")
    _require_identifier(state_name, role="typestate state")
    try:
        space.state(state_name)
    except Phase1SemanticError as exc:
        raise TypestateError(
            f"typestate {type_name}<{state_name}> references unknown state "
            f"in space {space.name!r}"
        ) from exc
    return StateQualifiedType(
        type_name=type_name,
        space_name=space.name,
        state_name=state_name,
    )



def require_typestate(
    expected: StateQualifiedType,
    actual: StateQualifiedType,
) -> StateQualifiedType:
    """Require an exact state-qualified type at a semantic boundary."""
    if not isinstance(expected, StateQualifiedType) or not isinstance(
        actual, StateQualifiedType
    ):
        raise TypestateError("typestate boundary requires state-qualified types")
    if expected.type_name != actual.type_name:
        raise TypestateError(
            f"typestate requires {expected.display()}, received {actual.display()}"
        )
    if expected.space_name != actual.space_name:
        raise TypestateError(
            f"typestate {actual.display()} belongs to state space "
            f"{actual.space_name!r}, expected {expected.space_name!r}"
        )
    if expected.state_name != actual.state_name:
        raise TypestateError(
            f"typestate requires {expected.display()}, received {actual.display()}"
        )
    return actual



def transition_typestate(
    space: StateSpacePlan,
    value: StateQualifiedType,
    target_state: str,
    *,
    point_id: str | None = None,
) -> TypestateTransitionFact:
    """Certify one explicit typestate transition through the State Space graph."""
    if not isinstance(space, StateSpacePlan):
        raise TypestateError("typestate transition requires a certified StateSpacePlan")
    if not isinstance(value, StateQualifiedType):
        raise TypestateError("typestate transition requires a state-qualified value")
    if point_id is not None and (
        not isinstance(point_id, str)
        or re.fullmatch(r"state_transition@[1-9][0-9]*:[1-9][0-9]*", point_id)
        is None
    ):
        raise TypestateError(
            "typestate transition requires a source-stable point id "
            "state_transition@line:column"
        )
    _require_identifier(target_state, role="typestate transition target")
    if value.space_name != space.name:
        raise TypestateError(
            f"typestate {value.display()} belongs to state space {value.space_name!r}, "
            f"not {space.name!r}"
        )
    try:
        edge = space.require_transition(value.state_name, target_state)
    except Phase1SemanticError as exc:
        raise TypestateError(
            f"invalid typestate transition for {value.type_name}: "
            f"{value.state_name} -> {target_state}"
        ) from exc
    target = StateQualifiedType(
        type_name=value.type_name,
        space_name=value.space_name,
        state_name=target_state,
    )
    return TypestateTransitionFact(
        source=value,
        target=target,
        transition=edge,
        point_id=point_id,
    )


__all__ = [
    "TypestateError",
    "StateQualifiedType",
    "TypestateTransitionFact",
    "certify_typestate",
    "require_typestate",
    "transition_typestate",
]
