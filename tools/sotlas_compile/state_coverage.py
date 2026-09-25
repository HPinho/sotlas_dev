"""Backend-neutral state-coverage semantics for Sotlas Phase 4.

This layer checks consumers that enumerate State Space states (for example
future ``when``/view constructs) without depending on parser or backend details.
It validates state names, rejects duplicate arms, preserves source order, and
computes missing states in declaration order.  Exhaustiveness is an explicit
semantic gate rather than an inferred backend behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from .state_space import StateSpacePlan
from .typed_ast import Phase1SemanticError


class StateCoverageError(Phase1SemanticError):
    """Raised when a State Space consumer has invalid or incomplete coverage."""


@dataclass(frozen=True)
class StateCoveragePlan:
    """Certified coverage facts for one consumer of a State Space."""

    space_name: str
    declared_states: tuple[str, ...]
    arms: tuple[str, ...]
    missing_states: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_states

    @property
    def covered_count(self) -> int:
        return len(self.arms)

    @property
    def total_count(self) -> int:
        return len(self.declared_states)

    def coverage_text(self) -> str:
        return f"{self.covered_count}/{self.total_count}"

    def require_complete(self) -> "StateCoveragePlan":
        if self.missing_states:
            missing = ", ".join(self.missing_states)
            raise StateCoverageError(
                f"state coverage for {self.space_name!r} is incomplete: "
                f"{self.coverage_text()}; missing: {missing}"
            )
        return self


def analyze_state_coverage(
    space: StateSpacePlan,
    arms: tuple[str, ...],
) -> StateCoveragePlan:
    """Validate named state arms and compute deterministic missing-state facts."""
    if not isinstance(space, StateSpacePlan):
        raise StateCoverageError("state coverage requires a certified StateSpacePlan")
    if not isinstance(arms, tuple):
        raise StateCoverageError("state coverage arms must be a source-ordered tuple")

    seen: set[str] = set()
    checked_arms: list[str] = []
    for state_name in arms:
        if not isinstance(state_name, str) or not state_name:
            raise StateCoverageError("state coverage arm requires a state name")
        if state_name in seen:
            raise StateCoverageError(
                f"state coverage for {space.name!r} repeats state {state_name!r}"
            )
        try:
            space.state(state_name)
        except Phase1SemanticError as exc:
            raise StateCoverageError(
                f"state coverage for {space.name!r} references unknown state "
                f"{state_name!r}"
            ) from exc
        seen.add(state_name)
        checked_arms.append(state_name)

    declared_states = tuple(state.name for state in space.states)
    missing_states = tuple(
        state_name for state_name in declared_states if state_name not in seen
    )
    return StateCoveragePlan(
        space_name=space.name,
        declared_states=declared_states,
        arms=tuple(checked_arms),
        missing_states=missing_states,
    )


def require_exhaustive_state_coverage(
    space: StateSpacePlan,
    arms: tuple[str, ...],
) -> StateCoveragePlan:
    """Certify that one consumer covers every state exactly once."""
    return analyze_state_coverage(space, arms).require_complete()


__all__ = [
    "StateCoverageError",
    "StateCoveragePlan",
    "analyze_state_coverage",
    "require_exhaustive_state_coverage",
]
