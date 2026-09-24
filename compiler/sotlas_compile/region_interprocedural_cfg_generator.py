"""REGION SIR-generator extension for pure interprocedural move calls.

The REGION-aware CFG generator already lowers mixed borrow/transfer shapes. A
function containing only ``callee(move region_owner); ...; return;`` previously
fell back because the gating boolean counted REGION borrows/handovers but not a
REGION->REGION move through a call. This wrapper recognizes exactly that already
validated ownership-taking call shape; all instruction construction still comes
from the existing REGION generator.
"""
from __future__ import annotations

from typing import Any

from .region_cfg_generator import make_region_cfg_generator


def make_region_interprocedural_cfg_generator(sir):
    base = make_region_cfg_generator(sir)

    class RegionInterproceduralCFGSIRGenerator(base):
        def _region_call_instructions(
            self,
            call: Any,
            caller_params: dict[str, Any],
            slots: dict[str, Any],
            *,
            allow_move: bool,
        ):
            result = super()._region_call_instructions(
                call,
                caller_params,
                slots,
                allow_move=allow_move,
            )
            if result is None:
                return None
            instructions, saw_region_fact = result
            if saw_region_fact or not allow_move:
                return result

            callee = getattr(self, "_parsed_functions", {}).get(
                getattr(call, "callee", "")
            )
            if callee is None:
                return result
            parameters = tuple(getattr(callee, "params", ()) or ())
            arguments = tuple(getattr(call, "args", ()) or ())
            if len(parameters) != len(arguments):
                return result

            for argument, parameter in zip(arguments, parameters, strict=True):
                if type(argument).__name__ != "MoveExpr":
                    continue
                moved = getattr(argument, "value", None)
                source_name = self._source_name(moved)
                if source_name is None:
                    continue
                source_type = caller_params.get(source_name)
                _, target_type = self._parameter_name_type(parameter)
                if source_type is None or target_type is None:
                    continue
                if (
                    getattr(source_type, "ownership_domain", None) == "region"
                    and getattr(target_type, "ownership_domain", None) == "region"
                    and getattr(source_type, "name", None)
                    == getattr(target_type, "name", None)
                ):
                    saw_region_fact = True
                    break

            return instructions, saw_region_fact

    RegionInterproceduralCFGSIRGenerator.__name__ = (
        "RegionInterproceduralCFGSIRGenerator"
    )
    return RegionInterproceduralCFGSIRGenerator


__all__ = ["make_region_interprocedural_cfg_generator"]
