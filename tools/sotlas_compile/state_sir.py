"""SIR representation for certified State Space transitions."""
from __future__ import annotations

import re

from .canonical_sir import load_canonical_sir
from .state_typestate import TypestateTransitionFact


class StateTransitionSIRError(ValueError):
    """Raised when a typestate proof cannot be represented faithfully in SIR."""


_POINT_ID = re.compile(r"^state_transition@[1-9][0-9]*:[1-9][0-9]*$")


def lower_typestate_transition(fact: TypestateTransitionFact, source, result_name: str):
    """Lower one graph-certified transition to a source-stable SIR instruction.

    This is a backend-neutral representation only. Backends must reject this
    instruction until they implement the same transition contract.
    """
    if not isinstance(fact, TypestateTransitionFact):
        raise StateTransitionSIRError(
            "State Transition SIR requires a certified typestate transition"
        )
    if not isinstance(result_name, str) or not result_name:
        raise StateTransitionSIRError("State Transition SIR requires a result name")
    if not isinstance(fact.point_id, str) or _POINT_ID.fullmatch(fact.point_id) is None:
        raise StateTransitionSIRError(
            "State Transition SIR requires source-stable identity "
            "state_transition@line:column"
        )

    sir = load_canonical_sir()
    value_type = f"{fact.source.type_name}<{fact.source.state_name}>"
    result_type = f"{fact.target.type_name}<{fact.target.state_name}>"
    if not isinstance(source, sir.SIRValue) or source.type_name != value_type:
        raise StateTransitionSIRError(
            f"State Transition SIR source must have type {value_type}"
        )
    if fact.source.space_name != fact.target.space_name:
        raise StateTransitionSIRError("State Transition SIR cannot change State Spaces")
    if fact.source.type_name != fact.target.type_name:
        raise StateTransitionSIRError("State Transition SIR cannot change nominal types")

    result = sir.SIRValue(result_name, result_type)
    return sir.StateTransitionInst(
        source=source,
        result=result,
        space_name=fact.source.space_name,
        source_state=fact.source.state_name,
        target_state=fact.target.state_name,
        point_id=fact.point_id,
    )


__all__ = ["StateTransitionSIRError", "lower_typestate_transition"]
