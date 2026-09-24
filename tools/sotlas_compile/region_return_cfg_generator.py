"""Narrow SIR support for REGION-returning calls bound by a local let.

This extension preserves the already type-checked source shape
``let out: region T = callee(move owner);`` in canonical SIR.  It does not add
runtime behavior or backend lowering; it only prevents the REGION return value
from disappearing before interprocedural lifetime certification.
"""
from __future__ import annotations

from typing import Any

from .region_interprocedural_cfg_generator import (
    make_region_interprocedural_cfg_generator,
)


def make_region_return_cfg_generator(sir):
    base = make_region_interprocedural_cfg_generator(sir)

    class RegionReturnCFGSIRGenerator(base):
        def _try_lower_region_return_binding(
            self,
            fn: Any,
            entry_block: Any,
            return_type: str,
        ) -> bool:
            if return_type != "void":
                return False
            body = tuple(getattr(fn, "body", None) or ())
            if len(body) != 2:
                return False
            statement, terminal = body
            if type(statement).__name__ != "Let":
                return False
            if type(terminal).__name__ not in ("Return", "ReturnNode"):
                return False
            if getattr(terminal, "value", None) is not None:
                return False

            call = getattr(statement, "value", None)
            if type(call).__name__ != "Call":
                return False
            callee = getattr(self, "_parsed_functions", {}).get(
                getattr(call, "callee", "")
            )
            if callee is None:
                return False

            result_type = getattr(callee, "result", None)
            declared_type = getattr(statement, "type", None)
            if (
                result_type is None
                or declared_type is None
                or getattr(result_type, "ownership_domain", None) != "region"
                or getattr(declared_type, "ownership_domain", None) != "region"
                or getattr(result_type, "name", None)
                != getattr(declared_type, "name", None)
            ):
                return False

            parameters = tuple(getattr(callee, "params", ()) or ())
            arguments = tuple(getattr(call, "args", ()) or ())
            if not parameters or len(parameters) != len(arguments):
                return False

            caller_params = self._parameter_map(fn)
            call_arguments: list[Any] = []
            saw_region_move = False
            for argument, parameter in zip(arguments, parameters, strict=True):
                _, target_type = self._parameter_name_type(parameter)
                if target_type is None:
                    return False
                if getattr(target_type, "ownership_domain", None) != "region":
                    return False
                if type(argument).__name__ != "MoveExpr":
                    return False
                moved = getattr(argument, "value", None)
                source_name = self._source_name(moved)
                source_type = caller_params.get(source_name or "")
                if (
                    source_name is None
                    or source_type is None
                    or getattr(source_type, "ownership_domain", None) != "region"
                    or getattr(source_type, "name", None)
                    != getattr(target_type, "name", None)
                ):
                    return False
                call_arguments.append(
                    sir.SIRValue(source_name, source_type.name)
                )
                saw_region_move = True

            if not saw_region_move:
                return False

            destination = getattr(statement, "name", None)
            if not isinstance(destination, str) or not destination:
                return False
            result = sir.SIRValue(destination, result_type.name)
            entry_block.add(
                sir.CallInst(
                    callee=call.callee,
                    arguments=call_arguments,
                    result=result,
                )
            )
            entry_block.add(
                sir.ReturnInst(
                    point_id=self._statement_point_id(terminal, "return")
                )
            )
            return True

        def _try_lower_linear_ownership_points(
            self,
            fn: Any,
            entry_block: Any,
            return_type: str,
        ) -> bool:
            if self._try_lower_region_return_binding(
                fn, entry_block, return_type
            ):
                return True
            return super()._try_lower_linear_ownership_points(
                fn, entry_block, return_type
            )

    RegionReturnCFGSIRGenerator.__name__ = "RegionReturnCFGSIRGenerator"
    return RegionReturnCFGSIRGenerator


__all__ = ["make_region_return_cfg_generator"]
