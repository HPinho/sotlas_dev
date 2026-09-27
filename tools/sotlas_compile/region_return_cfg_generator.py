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
        def _try_lower_region_handover_branch(
            self,
            fn: Any,
            function: Any,
        ) -> bool:
            """Lower a consuming call, two exclusive handover arms, then a call.

            This represents branch-local lifetime points in the canonical CFG;
            it does not claim native runtime lowering for REGION values.
            """
            body = tuple(getattr(fn, "body", ()) or ())
            if (
                len(body) != 4
                or type(body[0]).__name__ != "Expression"
                or type(body[2]).__name__ != "Expression"
                or type(body[1]).__name__ != "If"
                or type(body[-1]).__name__ != "Return"
                or getattr(body[-1], "value", None) is not None
            ):
                return False
            pre_call = getattr(body[0], "value", None)
            post_call = getattr(body[2], "value", None)
            branch = body[1]
            if any(type(item).__name__ != "Call" for item in (pre_call, post_call)):
                return False
            then_body = tuple(getattr(branch, "then_body", ()) or ())
            else_body = tuple(getattr(branch, "else_body", ()) or ())
            if (
                len(then_body) != 1
                or len(else_body) != 1
                or any(type(item).__name__ != "Handover" for item in then_body + else_body)
            ):
                return False

            parameters = self._parameter_map(fn)

            def name_of(value: Any) -> str | None:
                return self._source_name(value)

            def handover_names(statement: Any) -> tuple[str, str] | None:
                source = name_of(getattr(statement, "value", None))
                destination = name_of(getattr(statement, "destination", None))
                if source is None or destination is None or source == destination:
                    return None
                source_type = parameters.get(source)
                destination_type = parameters.get(destination)
                if (
                    source_type is None
                    or destination_type is None
                    or getattr(source_type, "ownership_domain", None) != "region"
                    or getattr(destination_type, "ownership_domain", None) != "region"
                    or getattr(source_type, "name", None) != getattr(destination_type, "name", None)
                ):
                    return None
                return source, destination

            then_transfer, else_transfer = then_body[0], else_body[0]
            transfer_names = handover_names(then_transfer)
            if transfer_names is None or handover_names(else_transfer) != transfer_names:
                return False
            source_name, destination_name = transfer_names

            condition_name = name_of(getattr(branch, "condition", None))
            condition_type = parameters.get(condition_name or "")
            if condition_name is None or self._type_name(condition_type, "any") != "bool":
                return False

            def consuming_call(call: Any):
                callee = getattr(self, "_parsed_functions", {}).get(
                    getattr(call, "callee", "")
                )
                arguments = tuple(getattr(call, "args", ()) or ())
                target_parameters = tuple(getattr(callee, "params", ()) or ())
                if (
                    callee is None
                    or self._type_name(getattr(callee, "result", None), "void") != "void"
                    or len(arguments) != 1
                    or len(target_parameters) != 1
                    or type(arguments[0]).__name__ != "MoveExpr"
                    or name_of(getattr(arguments[0], "value", None)) != destination_name
                ):
                    return None
                target_type = self._parameter_name_type(target_parameters[0])[1]
                if (
                    target_type is None
                    or getattr(target_type, "ownership_domain", None) != "region"
                    or getattr(target_type, "name", None)
                    != getattr(parameters[destination_name], "name", None)
                ):
                    return None
                return callee

            pre_callee = consuming_call(pre_call)
            post_callee = consuming_call(post_call)
            if pre_callee is None or post_callee is None:
                return False
            condition = next(
                (item for item in function.parameters if item.name == condition_name),
                None,
            )
            if condition is None:
                return False
            entry = function.blocks[0] if function.blocks else None
            if entry is None:
                return False

            # Build on a temporary instruction list so unsupported forms never
            # leave a partially modified function behind.
            base_instructions = [
                item for item in entry.instructions
                if not isinstance(item, sir.ReturnInst)
            ]
            pre_inst = sir.CallInst(
                callee=pre_call.callee,
                arguments=[sir.SIRValue(destination_name, parameters[destination_name].name)],
                source_point_id=self._statement_point_id(body[0], "call"),
            )
            then_label, else_label, join_label = (
                "region_handover_then", "region_handover_else", "region_handover_join"
            )
            then_block = sir.SIRBasicBlock(then_label)
            else_block = sir.SIRBasicBlock(else_label)
            join_block = sir.SIRBasicBlock(join_label)
            branches = []
            for block, transfer in ((then_block, then_transfer), (else_block, else_transfer)):
                block.add(sir.OwnershipDomainPointInst(
                    operation="handover",
                    source_name=source_name,
                    destination_name=destination_name,
                    point_id=self._statement_point_id(transfer, "handover"),
                ))
                block.add(sir.CallInst(
                    callee=post_call.callee,
                    arguments=[sir.SIRValue(destination_name, parameters[destination_name].name)],
                    source_point_id=self._statement_point_id(body[2], "call"),
                ))
                block.add(sir.BranchInst(target_block=join_label))
                branches.append(block)
            # The post-join consumer is one source call after the merge. Keep
            # one SIR call at the join so call-site identity remains one-to-one.
            then_block.instructions.pop(-2)
            else_block.instructions.pop(-2)
            join_block.add(sir.CallInst(
                callee=post_call.callee,
                arguments=[sir.SIRValue(destination_name, parameters[destination_name].name)],
                source_point_id=self._statement_point_id(body[2], "call"),
            ))
            join_block.add(sir.ReturnInst(
                point_id=self._statement_point_id(body[-1], "return")
            ))
            entry.instructions = [
                *base_instructions,
                pre_inst,
                sir.CondBranchInst(condition, then_label, else_label),
            ]
            function.blocks.extend([*branches, join_block])
            return True

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

        def _lower_function(self, fn: Any):
            function = super()._lower_function(fn)
            self._try_lower_region_handover_branch(fn, function)
            body = tuple(getattr(fn, "body", ()) or ())
            while len(body) == 1 and type(body[0]).__name__ == "Unsafe":
                body = tuple(getattr(body[0], "body", ()) or ())
            if (
                len(body) == 1
                and type(body[0]).__name__ == "Return"
                and type(getattr(body[0], "value", None)).__name__ == "Call"
                and getattr(body[0].value, "callee", None) == "transition"
                and not any(
                    isinstance(instruction, sir.StateTransitionInst)
                    for block in function.blocks
                    for instruction in block.instructions
                )
            ):
                self._try_lower_state_transition(
                    fn,
                    function.blocks[0],
                    getattr(fn, "ret", None)
                    or getattr(fn, "result", None)
                    or getattr(fn, "return_type", None),
                )
            return function

    RegionReturnCFGSIRGenerator.__name__ = "RegionReturnCFGSIRGenerator"
    return RegionReturnCFGSIRGenerator


__all__ = ["make_region_return_cfg_generator"]
