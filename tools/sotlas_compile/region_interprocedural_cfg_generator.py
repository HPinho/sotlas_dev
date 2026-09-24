"""REGION SIR-generator extension for interprocedural ownership-taking calls.

The REGION-aware CFG generator lowers the actual CallInst. This wrapper also
preserves every validated REGION->REGION move argument as a source-stable
RegionCallTransferInst immediately before that call. The fact is backend-neutral
and carries no runtime behavior.
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
            if not allow_move:
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

            markers: list[Any] = []
            for argument_index, (argument, parameter) in enumerate(
                zip(arguments, parameters, strict=True)
            ):
                if type(argument).__name__ != "MoveExpr":
                    continue
                source_name = self._source_name(getattr(argument, "value", None))
                if source_name is None:
                    continue
                source_type = caller_params.get(source_name)
                parameter_name, target_type = self._parameter_name_type(parameter)
                if source_type is None or target_type is None or not parameter_name:
                    continue
                if (
                    getattr(source_type, "ownership_domain", None) != "region"
                    or getattr(target_type, "ownership_domain", None) != "region"
                    or getattr(source_type, "name", None)
                    != getattr(target_type, "name", None)
                ):
                    continue
                markers.append(
                    sir.RegionCallTransferInst(
                        operation="call_transfer",
                        source_name=source_name,
                        destination_name=f"{call.callee}.{parameter_name}",
                        point_id=self._statement_point_id(call, "call"),
                        source=sir.SIRValue(source_name, source_type.name),
                        callee=call.callee,
                        parameter=parameter_name,
                        argument_index=argument_index,
                        source_domain="region",
                        target_domain="region",
                    )
                )

            if not markers:
                return instructions, saw_region_fact
            if not instructions or not isinstance(instructions[-1], sir.CallInst):
                raise ValueError(
                    "REGION interprocedural lowering lost the canonical CallInst"
                )
            if any(isinstance(item, sir.RegionCallTransferInst) for item in instructions):
                raise ValueError("duplicate REGION call-transfer SIR fact")
            return [*instructions[:-1], *markers, instructions[-1]], True

    RegionInterproceduralCFGSIRGenerator.__name__ = (
        "RegionInterproceduralCFGSIRGenerator"
    )
    return RegionInterproceduralCFGSIRGenerator


__all__ = ["make_region_interprocedural_cfg_generator"]
