"""Narrow canonical SIR lowering for scalar returns and direct scalar calls.

The prototype SIR generator already owns honest condition lowering for boolean
parameters and integer comparisons, and it separately owns direct same-typed
scalar parameter returns. This extension composes those existing contracts for
two deliberately small, fully checked source shapes without inventing values:

    if condition { return parameter_a; }
    return parameter_b;

or the equivalent fully terminating if/else form, plus:

    return callee(parameter_a, parameter_b, ...);

The direct-call return path is intentionally narrow: the callee must be a parsed
module function (including the current function for M16.3e self recursion), every
argument must be a direct caller parameter with an exactly matching scalar type,
and the callee return type must exactly match the caller return type. More general
call expressions, locals, literals, nested calls, conversions and aggregate values
remain fail-closed for later milestones.
"""
from __future__ import annotations

from typing import Any

from .region_return_cfg_generator import make_region_return_cfg_generator


_SCALAR_TYPES = {
    "bool",
    "u8", "i8",
    "u16", "i16",
    "u32", "i32",
    "u64", "i64",
    "usize", "isize",
    "f32", "f64",
}


def make_scalar_if_return_cfg_generator(sir):
    base = make_region_return_cfg_generator(sir)

    class ScalarIfReturnCFGSIRGenerator(base):
        @staticmethod
        def _direct_return_parameter(
            statement: Any,
            params: list[Any],
            return_type: str,
        ):
            if type(statement).__name__ not in ("Return", "ReturnNode"):
                return None
            expression = getattr(statement, "value", None)
            kind = type(expression).__name__
            if kind == "Name":
                name = getattr(expression, "value", None)
            elif kind == "IdentNode":
                name = getattr(expression, "name", None)
            else:
                return None
            value = next(
                (item for item in params if item.name == name),
                None,
            )
            if value is None or value.type_name != return_type:
                return None
            return value

        @staticmethod
        def _call_argument_name(argument: Any) -> str | None:
            kind = type(argument).__name__
            if kind == "Name":
                name = getattr(argument, "value", None)
            elif kind == "IdentNode":
                name = getattr(argument, "name", None)
            else:
                return None
            return name if isinstance(name, str) and name else None

        def _parsed_parameter_type(self, parameter: Any) -> str | None:
            if isinstance(parameter, tuple) and len(parameter) == 2:
                type_info = parameter[1]
            else:
                type_info = (
                    getattr(parameter, "type_ann", None)
                    or getattr(parameter, "type", None)
                )
            try:
                return self._type_name(type_info, "void")
            except ValueError:
                return None

        @staticmethod
        def _parsed_function_is_system(function: Any) -> bool:
            if bool(getattr(function, "is_system", False)):
                return True
            attributes = tuple(getattr(function, "attributes", ()) or ())
            if "@system" in attributes:
                return True
            directives = tuple(getattr(function, "directives", ()) or ())
            return any(getattr(item, "name", "") == "system" for item in directives)

        def _try_lower_direct_call_subset(
            self,
            fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            """Lower `return callee(params...)` as one typed SSA direct call.

            Existing direct/whisper ownership-call lowering remains owned by the
            base generator and is used whenever this scalar-return shape does not
            match exactly. M16.3e permits the same checked shape when ``callee``
            resolves to ``fn`` itself; no broader source-call form is introduced.
            """
            body = list(getattr(fn, "body", None) or ())
            if (
                return_type not in _SCALAR_TYPES
                or len(body) != 1
                or type(body[0]).__name__ not in ("Return", "ReturnNode")
            ):
                return super()._try_lower_direct_call_subset(
                    fn, entry_block, sir_params, return_type
                )

            return_statement = body[0]
            call = getattr(return_statement, "value", None)
            if type(call).__name__ != "Call":
                return super()._try_lower_direct_call_subset(
                    fn, entry_block, sir_params, return_type
                )

            callee_name = getattr(call, "callee", None)
            parsed_functions = getattr(self, "_parsed_functions", {})
            callee = parsed_functions.get(callee_name)
            if callee is None:
                return False

            callee_return = (
                getattr(callee, "ret", None)
                or getattr(callee, "result", None)
                or getattr(callee, "return_type", None)
            )
            try:
                callee_return_type = self._type_name(callee_return, "void")
            except ValueError:
                return False
            if callee_return_type != return_type:
                return False

            parsed_parameters = tuple(getattr(callee, "params", ()) or ())
            arguments = tuple(getattr(call, "args", ()) or ())
            if len(parsed_parameters) != len(arguments):
                return False

            caller_values = {value.name: value for value in sir_params}
            sir_arguments: list[Any] = []
            for argument, target_parameter in zip(
                arguments, parsed_parameters, strict=True
            ):
                source_name = self._call_argument_name(argument)
                if source_name is None:
                    return False
                source_value = caller_values.get(source_name)
                target_type = self._parsed_parameter_type(target_parameter)
                if (
                    source_value is None
                    or target_type not in _SCALAR_TYPES
                    or source_value.type_name != target_type
                ):
                    return False
                sir_arguments.append(source_value)

            result = self._next_val("call", return_type)
            entry_block.add(sir.CallInst(
                callee=callee_name,
                arguments=sir_arguments,
                result=result,
                is_system=self._parsed_function_is_system(callee),
                source_point_id=self._statement_point_id(call, "call"),
            ))
            entry_block.add(sir.ReturnInst(
                value=result,
                point_id=self._statement_point_id(return_statement, "return"),
            ))
            return True

        def _try_lower_simple_if_returns(
            self,
            fn: Any,
            sir_fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            # Preserve every existing void/ownership behavior in the base
            # generator.  This extension only owns non-void scalar returns.
            if return_type == "void":
                return super()._try_lower_simple_if_returns(
                    fn,
                    sir_fn,
                    entry_block,
                    sir_params,
                    return_type,
                )
            if return_type not in _SCALAR_TYPES:
                return False

            body = list(getattr(fn, "body", None) or ())
            if not body or type(body[0]).__name__ not in ("If", "IfNode"):
                return False
            if len(sir_fn.blocks) != 1 or sir_fn.blocks[0] is not entry_block:
                return False

            if_node = body[0]
            then_body = list(getattr(if_node, "then_body", None) or ())
            else_body_raw = getattr(if_node, "else_body", None)
            else_body = list(else_body_raw or ())

            if len(then_body) != 1:
                return False
            then_value = self._direct_return_parameter(
                then_body[0], sir_params, return_type
            )
            if then_value is None:
                return False

            if_point = self._statement_point_id(if_node, "if")
            line_column = if_point.removeprefix("if@").replace(":", "_")
            then_label = f"if_{line_column}_then"
            else_label = f"if_{line_column}_else"
            cont_label = f"if_{line_column}_cont"

            condition = getattr(if_node, "condition", None)

            if else_body:
                if len(body) != 1 or len(else_body) != 1:
                    return False
                else_value = self._direct_return_parameter(
                    else_body[0], sir_params, return_type
                )
                if else_value is None:
                    return False
                condition_plan = self._condition_branch_plan(
                    condition,
                    sir_params,
                    entry_block.label,
                    then_label,
                    else_label,
                    f"if_{line_column}",
                )
                if condition_plan is None:
                    return False
                reserved = {then_label, else_label}
                if any(
                    label in reserved
                    for label, _ in condition_plan
                    if label != entry_block.label
                ):
                    return False
                existing = {block.label for block in sir_fn.blocks}
                internal = {
                    label
                    for label, _ in condition_plan
                    if label != entry_block.label
                }
                if (reserved | internal) & existing:
                    return False

                self._install_condition_branch_plan(
                    sir_fn, entry_block, condition_plan
                )
                then_block = sir_fn.add_block(then_label)
                else_block = sir_fn.add_block(else_label)
                then_block.add(sir.ReturnInst(
                    value=then_value,
                    point_id=self._statement_point_id(
                        then_body[0], "return"
                    ),
                ))
                else_block.add(sir.ReturnInst(
                    value=else_value,
                    point_id=self._statement_point_id(
                        else_body[0], "return"
                    ),
                ))
                return True

            if len(body) != 2:
                return False
            final_return = body[1]
            final_value = self._direct_return_parameter(
                final_return, sir_params, return_type
            )
            if final_value is None:
                return False

            condition_plan = self._condition_branch_plan(
                condition,
                sir_params,
                entry_block.label,
                then_label,
                cont_label,
                f"if_{line_column}",
            )
            if condition_plan is None:
                return False
            reserved = {then_label, cont_label}
            if any(
                label in reserved
                for label, _ in condition_plan
                if label != entry_block.label
            ):
                return False
            existing = {block.label for block in sir_fn.blocks}
            internal = {
                label
                for label, _ in condition_plan
                if label != entry_block.label
            }
            if (reserved | internal) & existing:
                return False

            self._install_condition_branch_plan(
                sir_fn, entry_block, condition_plan
            )
            then_block = sir_fn.add_block(then_label)
            cont_block = sir_fn.add_block(cont_label)
            then_block.add(sir.ReturnInst(
                value=then_value,
                point_id=self._statement_point_id(
                    then_body[0], "return"
                ),
            ))
            cont_block.add(sir.ReturnInst(
                value=final_value,
                point_id=self._statement_point_id(
                    final_return, "return"
                ),
            ))
            return True

    ScalarIfReturnCFGSIRGenerator.__name__ = (
        "ScalarIfReturnCFGSIRGenerator"
    )
    return ScalarIfReturnCFGSIRGenerator


__all__ = ["make_scalar_if_return_cfg_generator"]
