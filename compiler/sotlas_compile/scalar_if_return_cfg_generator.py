"""Narrow canonical SIR lowering for scalar structured-if returns.

The prototype SIR generator already owns honest condition lowering for boolean
parameters and integer comparisons, and it separately owns direct same-typed
scalar parameter returns.  This extension composes those existing contracts for
one deliberately small structured CFG shape without inventing values:

    if condition { return parameter_a; }
    return parameter_b;

or the equivalent fully terminating if/else form.

Only direct parameter names with the function's declared scalar return type are
accepted.  Calls, locals, arithmetic return expressions, mutations, and other
shapes remain on the base generator's fail-closed ``unlowered_functions`` path.
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
