"""Canonical backend-neutral State Space semantics for Sotlas Phase 4.

A State Space is a finite set of named states plus an explicit directed graph of
allowed transitions. State payloads are part of each state's semantic contract.
This first Phase-4 slice deliberately does not invent an initial state, runtime
storage, UI behavior, or typestate lowering; those are composed in later slices.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .typed_ast import Phase1SemanticError


class StateSpaceError(Phase1SemanticError):
    """Raised when a canonical State Space contract is malformed or violated."""


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class StateSpacePayload:
    """One ordered payload item carried by a state.

    ``name=None`` models positional payload syntax such as ``completed(File)``;
    named payloads model syntax such as ``downloading(progress: Percent)``.
    """

    type_name: str
    name: str | None = None


@dataclass(frozen=True)
class StateSpaceState:
    name: str
    payload: tuple[StateSpacePayload, ...] = ()


@dataclass(frozen=True)
class StateSpaceTransition:
    source: str
    target: str


@dataclass(frozen=True)
class StateSpacePlan:
    """Certified finite-state graph with deterministic source-order facts."""

    name: str
    states: tuple[StateSpaceState, ...]
    transitions: tuple[StateSpaceTransition, ...]

    def state(self, name: str) -> StateSpaceState:
        matches = tuple(item for item in self.states if item.name == name)
        if len(matches) != 1:
            raise StateSpaceError(
                f"state space {self.name!r} requires exactly one state {name!r}"
            )
        return matches[0]

    def allows(self, source: str, target: str) -> bool:
        self.state(source)
        self.state(target)
        return any(
            item.source == source and item.target == target
            for item in self.transitions
        )

    def require_transition(self, source: str, target: str) -> StateSpaceTransition:
        self.state(source)
        self.state(target)
        matches = tuple(
            item
            for item in self.transitions
            if item.source == source and item.target == target
        )
        if len(matches) != 1:
            raise StateSpaceError(
                f"state space {self.name!r} forbids transition {source} -> {target}"
            )
        return matches[0]

    def successors(self, state: str) -> tuple[StateSpaceState, ...]:
        self.state(state)
        names = tuple(
            item.target for item in self.transitions if item.source == state
        )
        return tuple(self.state(name) for name in names)

    def predecessors(self, state: str) -> tuple[StateSpaceState, ...]:
        self.state(state)
        names = tuple(
            item.source for item in self.transitions if item.target == state
        )
        return tuple(self.state(name) for name in names)


def _require_identifier(value: str, *, role: str) -> None:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise StateSpaceError(f"{role} requires a valid Sotlas identifier")


def _validate_payload(space: str, state: StateSpaceState) -> None:
    named: set[str] = set()
    for item in state.payload:
        if not isinstance(item, StateSpacePayload):
            raise StateSpaceError(
                f"state space {space!r} state {state.name!r} has invalid payload"
            )
        if not isinstance(item.type_name, str) or not item.type_name.strip():
            raise StateSpaceError(
                f"state space {space!r} state {state.name!r} has payload without type"
            )
        if item.name is None:
            continue
        _require_identifier(item.name, role="state payload name")
        if item.name in named:
            raise StateSpaceError(
                f"state space {space!r} state {state.name!r} repeats payload {item.name!r}"
            )
        named.add(item.name)


def certify_state_space(
    name: str,
    states: tuple[StateSpaceState, ...],
    transitions: tuple[StateSpaceTransition, ...],
) -> StateSpacePlan:
    """Validate and freeze one canonical State Space graph.

    Source order is preserved for both states and transitions; no implicit edge,
    reverse edge, transitive edge, or initial state is synthesized.
    """
    _require_identifier(name, role="state space name")
    if not states:
        raise StateSpaceError(f"state space {name!r} requires at least one state")

    by_name: dict[str, StateSpaceState] = {}
    for state in states:
        if not isinstance(state, StateSpaceState):
            raise StateSpaceError(f"state space {name!r} contains invalid state")
        _require_identifier(state.name, role="state name")
        if state.name in by_name:
            raise StateSpaceError(
                f"state space {name!r} repeats state {state.name!r}"
            )
        _validate_payload(name, state)
        by_name[state.name] = state

    seen_edges: set[tuple[str, str]] = set()
    checked_transitions: list[StateSpaceTransition] = []
    for transition in transitions:
        if not isinstance(transition, StateSpaceTransition):
            raise StateSpaceError(f"state space {name!r} contains invalid transition")
        if transition.source not in by_name:
            raise StateSpaceError(
                f"state space {name!r} transition references unknown source "
                f"{transition.source!r}"
            )
        if transition.target not in by_name:
            raise StateSpaceError(
                f"state space {name!r} transition references unknown target "
                f"{transition.target!r}"
            )
        edge = (transition.source, transition.target)
        if edge in seen_edges:
            raise StateSpaceError(
                f"state space {name!r} repeats transition "
                f"{transition.source} -> {transition.target}"
            )
        seen_edges.add(edge)
        checked_transitions.append(transition)

    return StateSpacePlan(
        name=name,
        states=tuple(states),
        transitions=tuple(checked_transitions),
    )


__all__ = [
    "StateSpaceError",
    "StateSpacePayload",
    "StateSpaceState",
    "StateSpaceTransition",
    "StateSpacePlan",
    "certify_state_space",
]
