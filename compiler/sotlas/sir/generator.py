"""Gerador de SIR a partir da AST do compilador Sotlas.

Mapeia declarações e corpos de função para blocos básicos SSA do SIR.
"""
from __future__ import annotations
from typing import Any, Optional
from .instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst,
    OwnershipDomainPointInst, SharedOwnershipPointInst, DirectAccessInst,
    WhisperBorrowInst,
    ReturnInst, BranchInst, CondBranchInst, CompareInst, SystemOpInst
)


class SIRGenerator:
    def __init__(self, module_name: str = "main"):
        self.module_name = module_name
        self.sir_mod = SIRModule(name=module_name)
        self._val_counter = 0

    def _next_val(self, prefix: str = "v", type_name: str = "i32") -> SIRValue:
        v = SIRValue(name=f"{prefix}{self._val_counter}", type_name=type_name)
        self._val_counter += 1
        return v

    @staticmethod
    def _type_name(type_info: Any, default: str = "void") -> str:
        """Normalize frontend/bootstrap type objects into canonical SIR names."""
        if type_info is None:
            return default
        if isinstance(type_info, str):
            return type_info

        display_name = getattr(type_info, "display_name", None)
        if callable(display_name):
            rendered = display_name()
            if rendered:
                return rendered

        name = getattr(type_info, "name", None)
        if isinstance(name, str) and name:
            if (
                getattr(type_info, "pointer", False)
                or getattr(type_info, "is_reference", False)
            ):
                return f"{name}*"
            return name

        primitive = getattr(type_info, "primitive", None)
        primitive_name = getattr(primitive, "name", None)
        if isinstance(primitive_name, str) and primitive_name:
            return primitive_name.lower().removeprefix("kw_")

        raise ValueError(
            f"SIR generator cannot normalize type {type(type_info).__name__}"
        )

    @staticmethod
    def _terminal_return_point_id(fn: Any) -> str | None:
        """Return source-stable identity for a directly represented terminal return.

        The prototype generator still owns only one linear entry block. Therefore
        it may attach a point ID only when the function body itself ends in a
        direct Return/ReturnNode. Nested returns remain for structured CFG lowering.
        """
        body = getattr(fn, "body", None)
        if not body:
            return None
        terminal = body[-1]
        if type(terminal).__name__ not in ("Return", "ReturnNode"):
            return None

        span = getattr(terminal, "span", None)
        line = getattr(span, "line", None)
        column = getattr(span, "col", None)
        if line is None or column is None:
            token = getattr(terminal, "token", None)
            line = getattr(token, "line", None)
            column = getattr(token, "column", None)
        if line is None or column is None:
            raise ValueError("terminal SIR return lacks source location")
        return f"return@{line}:{column}"

    @staticmethod
    def _statement_point_id(statement: Any, kind: str) -> str:
        span = getattr(statement, "span", None)
        line = getattr(span, "line", None)
        column = getattr(span, "col", None)
        if line is None or column is None:
            token = getattr(statement, "token", None)
            line = getattr(token, "line", None)
            column = getattr(token, "column", None)
        if line is None or column is None:
            raise ValueError(f"{kind} SIR statement lacks source location")
        return f"{kind}@{line}:{column}"

    @staticmethod
    def _simple_condition_value(condition: Any, params: list[SIRValue]) -> SIRValue | None:
        """Return an existing boolean SSA value for conditions already representable."""
        if type(condition).__name__ not in ("IdentNode", "Name"):
            return None
        name = getattr(condition, "name", None) or getattr(condition, "value", None)
        for param in params:
            if param.name == name and param.type_name == "bool":
                return param
        return None

    def _condition_branch_plan(
        self,
        condition: Any,
        params: list[SIRValue],
        start_label: str,
        true_target: str,
        false_target: str,
        label_prefix: str,
    ) -> list[tuple[str, Any]] | None:
        """Build CFG edges for boolean literals, params, !, &&, and ||."""
        branches: list[tuple[str, Any]] = []
        labels: set[str] = set()
        serial = 0
        operator_names = {
            "==": "EQ", "!=": "NEQ", "<": "LT", "<=": "LTE",
            ">": "GT", ">=": "GTE", "&&": "AND", "||": "OR",
        }

        def condition_operator(node: Any) -> str | None:
            operator = getattr(node, "op", None)
            return getattr(operator, "name", None) or operator_names.get(
                operator
            )

        def simple_integer_comparison(node: Any) -> CompareInst | None:
            if type(node).__name__ not in ("BinaryExprNode", "Binary"):
                return None
            operation = condition_operator(node)
            if operation not in ("EQ", "NEQ", "LT", "LTE", "GT", "GTE"):
                return None
            left_node = getattr(node, "left", None)
            right_node = getattr(node, "right", None)
            if type(left_node).__name__ not in ("IdentNode", "Name") or type(
                right_node
            ).__name__ not in ("IdentNode", "Name"):
                return None
            left_name = getattr(left_node, "name", None) or getattr(
                left_node, "value", None
            )
            right_name = getattr(right_node, "name", None) or getattr(
                right_node, "value", None
            )
            left_value = next(
                (param for param in params if param.name == left_name), None
            )
            right_value = next(
                (param for param in params if param.name == right_name), None
            )
            integer_types = {
                "u8", "i8", "u16", "i16", "u32", "i32", "u64", "i64",
                "usize", "isize",
            }
            if (
                left_value is None or right_value is None
                or left_value.type_name not in integer_types
                or right_value.type_name != left_value.type_name
            ):
                return None
            result = self._next_val("cmp", "bool")
            return CompareInst(operation, left_value, right_value, result)

        def emit(node: Any, label: str, yes: str, no: str, depth: int = 0) -> bool:
            nonlocal serial
            if depth > 32:
                return False
            kind = type(node).__name__
            if kind == "LiteralNode":
                token_kind = getattr(node, "kind", None)
                token_name = getattr(token_kind, "name", None)
                if token_name not in ("KW_TRUE", "KW_FALSE"):
                    return False
                target = yes if token_name == "KW_TRUE" else no
                branches.append((label, BranchInst(target)))
                return True
            if kind in ("UnaryExprNode", "Unary"):
                operator = getattr(node, "op", None)
                if getattr(operator, "name", None) not in ("NOT", "BANG"):
                    return False
                operand = getattr(node, "operand", None)
                if operand is None:
                    operand = getattr(node, "value", None)
                return emit(operand, label, no, yes, depth + 1)
            if kind in ("BinaryExprNode", "Binary"):
                operator = condition_operator(node)
                if operator in ("AND", "OR"):
                    intermediate = f"{label_prefix}_logic_{serial}"
                    serial += 1
                    if intermediate in labels or intermediate in (yes, no, start_label):
                        return False
                    labels.add(intermediate)
                    left = getattr(node, "left", None)
                    right = getattr(node, "right", None)
                    if operator == "AND":
                        return emit(left, label, intermediate, no, depth + 1) and emit(
                            right, intermediate, yes, no, depth + 1
                        )
                    return emit(left, label, yes, intermediate, depth + 1) and emit(
                        right, intermediate, yes, no, depth + 1
                    )

            comparison = simple_integer_comparison(node)
            if comparison is not None:
                branches.append((label, comparison))
                branches.append((label, CondBranchInst(
                    condition=comparison.result,
                    true_block=yes,
                    false_block=no,
                )))
                return True

            value = self._simple_condition_value(node, params)
            if value is None:
                return False
            branches.append((label, CondBranchInst(
                condition=value, true_block=yes, false_block=no
            )))
            return True

        if not emit(condition, start_label, true_target, false_target):
            return None
        if len(branches) < 2 and labels:
            return None
        return branches

    @staticmethod
    def _install_condition_branch_plan(
        sir_fn: SIRFunction,
        start_block: SIRBasicBlock,
        plan: list[tuple[str, Any]],
    ) -> None:
        for label, branch in plan:
            block = start_block if label == start_block.label else sir_fn.add_block(label)
            block.add(branch)

    def _try_lower_simple_if_returns(
        self,
        fn: Any,
        sir_fn: SIRFunction,
        entry_block: SIRBasicBlock,
        sir_params: list[SIRValue],
        return_type: str,
    ) -> bool:
        """Lower the first honest void structured-if subset used by ownership cleanup.

        Supported shapes:
          if flag { return; }
          return;

        and:
          if flag { return; } else { return; }

        Each branch must contain exactly one direct return. The condition must
        already exist as a parameter SSA value; no placeholder condition is invented.
        """
        if return_type != "void":
            # Return-value expression lowering is not implemented in this
            # prototype subset. Never emit valueless ReturnInst for non-void.
            return False

        body = getattr(fn, "body", None) or []
        if not body:
            return False

        if_indexes = [
            index for index, statement in enumerate(body)
            if type(statement).__name__ in ("If", "IfNode")
        ]
        if len(if_indexes) != 1:
            return False
        if_index = if_indexes[0]
        prefix = body[:if_index]
        tail = body[if_index:]
        shared_aliases: set[str] = set()
        shared_alias_types: dict[str, Any] = {}
        shared_markers: list[SharedOwnershipPointInst] = []
        direct_markers: list[DirectAccessInst] = []
        caller_params = dict(
            item for item in getattr(fn, "params", ())
            if isinstance(item, tuple) and len(item) == 2
        )

        def direct_defer_names(value: Any) -> tuple[str, ...] | None:
            kind = type(value).__name__
            if kind == "Name":
                names = (getattr(value, "value", None),)
            elif kind == "Call":
                args = tuple(getattr(value, "args", ()))
                names_list = []
                for argument in args:
                    if type(argument).__name__ == "Name":
                        names_list.append(argument.value)
                    elif (
                        type(argument).__name__ == "Unary"
                        and getattr(argument, "op", None) == "&"
                        and type(getattr(argument, "value", None)).__name__
                        == "Name"
                    ):
                        names_list.append(argument.value.value)
                    else:
                        return None
                names = tuple(names_list)
            elif kind == "MethodCall":
                receiver = getattr(value, "target", None)
                args = tuple(getattr(value, "args", ()))
                if type(receiver).__name__ != "Name" or any(
                    type(arg).__name__ != "Name" for arg in args
                ):
                    return None
                names = (
                    getattr(receiver, "value", None),
                    *(getattr(arg, "value", None) for arg in args),
                )
            else:
                return None
            if not all(isinstance(name, str) and name for name in names):
                return None
            return names

        for statement in prefix:
            kind = type(statement).__name__
            if kind == "Let":
                value = getattr(statement, "value", None)
                if type(value).__name__ != "ShareExpr":
                    return False
                source = getattr(value, "value", None)
                source_name = (
                    getattr(source, "value", None)
                    or getattr(source, "name", None)
                )
                alias_name = getattr(statement, "name", None)
                if (
                    not isinstance(source_name, str) or not source_name
                    or not isinstance(alias_name, str) or not alias_name
                ):
                    return False
                shared_aliases.add(alias_name)
                shared_alias_types[alias_name] = caller_params.get(source_name)
                shared_markers.append(
                    SharedOwnershipPointInst(
                        source_name=source_name,
                        alias_name=alias_name,
                        point_id=self._statement_point_id(statement, "share"),
                    )
                )
                continue
            if kind == "Defer":
                deferred = getattr(statement, "value", None)
                names = direct_defer_names(deferred)
                if names is None or not shared_aliases.intersection(names):
                    return False
                if type(deferred).__name__ == "Call":
                    callee = getattr(self, "_parsed_functions", {}).get(
                        deferred.callee
                    )
                    callee_params = tuple(
                        getattr(callee, "params", ()) if callee is not None else ()
                    )
                    if len(callee_params) != len(deferred.args):
                        return False
                    for argument, (parameter_name, parameter_type) in zip(
                        deferred.args, callee_params
                    ):
                        if (
                            getattr(parameter_type, "ownership_domain", None)
                            != "direct"
                            or type(argument).__name__ != "Unary"
                            or getattr(argument, "op", None) != "&"
                            or type(getattr(argument, "value", None)).__name__
                            != "Name"
                        ):
                            continue
                        source_name = argument.value.value
                        source_type = shared_alias_types.get(source_name)
                        if source_type is None or getattr(
                            source_type, "name", None
                        ) != getattr(parameter_type, "name", None):
                            return False
                        direct_markers.append(DirectAccessInst(
                            source=SIRValue(source_name, source_type.name),
                            callee=deferred.callee,
                            parameter=parameter_name,
                            source_domain="shared",
                            point_id=self._statement_point_id(
                                deferred, "direct"
                            ),
                        ))
                continue
            return False

        if_node = tail[0]
        if type(if_node).__name__ not in ("If", "IfNode"):
            return False
        condition = getattr(if_node, "condition", None)

        then_body = getattr(if_node, "then_body", None) or []
        else_body = getattr(if_node, "else_body", None)
        if len(then_body) != 1 or type(then_body[0]).__name__ not in ("Return", "ReturnNode"):
            return False

        if_span = getattr(if_node, "span", None)
        if_line = getattr(if_span, "line", 0)
        if_col = getattr(if_span, "col", 0)
        then_label = f"if_{if_line}_{if_col}_then"
        else_label = f"if_{if_line}_{if_col}_else"
        cont_label = f"if_{if_line}_{if_col}_cont"

        if else_body:
            if not isinstance(else_body, list):
                return False
            if len(else_body) != 1 or type(else_body[0]).__name__ not in ("Return", "ReturnNode"):
                return False
            if len(tail) != 1:
                return False
            true_target, false_target = then_label, else_label
            condition_plan = self._condition_branch_plan(
                condition, sir_params, entry_block.label,
                true_target, false_target,
                f"if_{if_line}_{if_col}",
            )
            if condition_plan is None or any(
                label in (then_label, else_label, cont_label)
                for label, _ in condition_plan if label != entry_block.label
            ):
                return False

            for marker in shared_markers:
                entry_block.add(marker)
            for marker in direct_markers:
                entry_block.add(marker)
            self._install_condition_branch_plan(
                sir_fn, entry_block, condition_plan
            )
            then_block = sir_fn.add_block(then_label)
            else_block = sir_fn.add_block(else_label)
            then_block.add(
                ReturnInst(
                    point_id=self._statement_point_id(then_body[0], "return")
                )
            )
            else_block.add(
                ReturnInst(
                    point_id=self._statement_point_id(else_body[0], "return")
                )
            )
            return True

        if len(tail) != 2 or type(tail[1]).__name__ not in ("Return", "ReturnNode"):
            return False
        condition_plan = self._condition_branch_plan(
            condition, sir_params, entry_block.label,
            then_label, cont_label,
            f"if_{if_line}_{if_col}",
        )
        if condition_plan is None or any(
            label in (then_label, else_label, cont_label)
            for label, _ in condition_plan if label != entry_block.label
        ):
            return False

        for marker in shared_markers:
            entry_block.add(marker)
        for marker in direct_markers:
            entry_block.add(marker)
        self._install_condition_branch_plan(sir_fn, entry_block, condition_plan)
        then_block = sir_fn.add_block(then_label)
        cont_block = sir_fn.add_block(cont_label)
        then_block.add(
            ReturnInst(
                point_id=self._statement_point_id(then_body[0], "return")
            )
        )
        cont_block.add(
            ReturnInst(
                point_id=self._statement_point_id(tail[1], "return")
            )
        )
        return True

    def _try_lower_simple_loop_control(
        self,
        fn: Any,
        sir_fn: SIRFunction,
        entry_block: SIRBasicBlock,
        sir_params: list[SIRValue],
        return_type: str,
    ) -> bool:
        """Lower a minimal honest while CFG with break, continue, or empty backedge."""
        if return_type != "void":
            return False

        body = getattr(fn, "body", None) or []
        if not body or type(body[0]).__name__ not in ("While", "WhileNode"):
            return False

        loop = body[0]
        condition = getattr(loop, "condition", None)

        loop_body = getattr(loop, "body", None) or []
        control_stmt = None
        control_kind = "backedge"
        if len(loop_body) == 1:
            control_stmt = loop_body[0]
            control_name = type(control_stmt).__name__
            if control_name in ("Break", "BreakNode"):
                control_kind = "break"
            elif control_name in ("Continue", "ContinueNode"):
                control_kind = "continue"
            else:
                return False
        elif len(loop_body) != 0:
            return False

        if len(body) > 2:
            return False
        terminal_return = None
        if len(body) == 2:
            if type(body[1]).__name__ not in ("Return", "ReturnNode"):
                return False
            terminal_return = body[1]

        span = getattr(loop, "span", None)
        line = getattr(span, "line", 0)
        column = getattr(span, "col", 0)
        cond_label = f"while_{line}_{column}_cond"
        body_label = f"while_{line}_{column}_body"
        exit_label = f"while_{line}_{column}_exit"
        condition_plan = self._condition_branch_plan(
            condition, sir_params, cond_label, body_label, exit_label,
            f"while_{line}_{column}",
        )
        if condition_plan is None or any(
            label in (body_label, exit_label)
            for label, _ in condition_plan if label != cond_label
        ):
            return False

        entry_block.add(BranchInst(cond_label))
        cond_block = sir_fn.add_block(cond_label)
        self._install_condition_branch_plan(sir_fn, cond_block, condition_plan)

        loop_body_block = sir_fn.add_block(body_label)
        if control_kind == "break":
            target = exit_label
            point_id = self._statement_point_id(control_stmt, "break")
        elif control_kind == "continue":
            target = cond_label
            point_id = self._statement_point_id(control_stmt, "continue")
        else:
            target = cond_label
            point_id = self._statement_point_id(loop, "while_backedge")
        loop_body_block.add(
            BranchInst(
                target,
                point_id=point_id,
                control_kind=control_kind,
            )
        )

        exit_block = sir_fn.add_block(exit_label)
        exit_block.add(
            ReturnInst(
                point_id=(
                    self._statement_point_id(terminal_return, "return")
                    if terminal_return is not None
                    else None
                )
            )
        )
        return True

    def _try_lower_linear_ownership_points(
        self,
        fn: Any,
        entry_block: SIRBasicBlock,
        return_type: str,
    ) -> bool:
        """Lower the honest linear ownership-transfer subset to source markers."""
        if return_type != "void":
            return False
        body = getattr(fn, "body", None) or []
        if not body or type(body[-1]).__name__ not in ("Return", "ReturnNode"):
            return False

        transfers = body[:-1]
        if not transfers:
            return False
        supported = {"Quarantine", "Handover", "Let"}
        for statement in transfers:
            kind = type(statement).__name__
            if kind not in supported:
                return False
            if kind == "Let":
                value = getattr(statement, "value", None)
                if type(value).__name__ != "ShareExpr":
                    return False

        for statement in transfers:
            kind = type(statement).__name__
            value = getattr(statement, "value", None)
            if kind == "Let":
                shared_source = getattr(value, "value", None)
                source_name = (
                    getattr(shared_source, "value", None)
                    or getattr(shared_source, "name", None)
                )
                alias_name = getattr(statement, "name", None)
                if (
                    not isinstance(source_name, str) or not source_name
                    or not isinstance(alias_name, str) or not alias_name
                ):
                    raise ValueError(
                        "share SIR point requires direct source and alias bindings"
                    )
                entry_block.add(
                    SharedOwnershipPointInst(
                        source_name=source_name,
                        alias_name=alias_name,
                        point_id=self._statement_point_id(statement, "share"),
                    )
                )
                continue

            source_name = (
                getattr(value, "value", None)
                or getattr(value, "name", None)
            )
            if not isinstance(source_name, str) or not source_name:
                raise ValueError(
                    f"{kind.lower()} SIR point requires direct source binding"
                )
            destination = getattr(statement, "destination", None)
            destination_name = (
                getattr(destination, "value", None)
                or getattr(destination, "name", None)
                if destination is not None else None
            )
            if destination is not None and (
                not isinstance(destination_name, str) or not destination_name
            ):
                raise ValueError(
                    "handover SIR point requires direct destination binding"
                )
            operation = kind.lower()
            entry_block.add(
                OwnershipDomainPointInst(
                    operation=operation,
                    source_name=source_name,
                    destination_name=destination_name,
                    point_id=self._statement_point_id(statement, operation),
                )
            )

        entry_block.add(
            ReturnInst(
                point_id=self._statement_point_id(body[-1], "return")
            )
        )
        return True

    def _try_lower_sequential_if_returns(
        self,
        fn: Any,
        sir_fn: SIRFunction,
        entry_block: SIRBasicBlock,
        sir_params: list[SIRValue],
        return_type: str,
    ) -> bool:
        """Lower multiple parameter-boolean early returns followed by return.

        This adds real, source-identified exits to the current CFG subset while
        keeping conditions and branch bodies deliberately restricted.
        """
        if return_type != "void":
            return False
        body = getattr(fn, "body", None) or []
        if len(body) < 3 or type(body[-1]).__name__ not in ("Return", "ReturnNode"):
            return False
        if_nodes = body[:-1]
        if len(if_nodes) < 2:
            return False
        if any(type(node).__name__ not in ("If", "IfNode") for node in if_nodes):
            return False
        branch_specs = []
        labels = set()
        for node in if_nodes:
            condition = getattr(node, "condition", None)
            then_body = getattr(node, "then_body", None) or []
            if (
                getattr(node, "else_body", None)
                or len(then_body) != 1
                or type(then_body[0]).__name__ not in ("Return", "ReturnNode")
            ):
                return False
            source_point = self._statement_point_id(node, "if")
            return_point = self._statement_point_id(then_body[0], "return")
            line_column = source_point.removeprefix("if@")
            exit_label = f"if_{line_column.replace(':', '_')}_then"
            next_label = f"if_{line_column.replace(':', '_')}_next"
            if exit_label in labels or next_label in labels:
                return False
            labels.update((exit_label, next_label))
            branch_specs.append((condition, return_point, exit_label, next_label, line_column))
        final_return_point = self._statement_point_id(body[-1], "return")

        branches = []
        internal_labels = set()
        for index, (condition, return_point, exit_label, next_label, line_column) in enumerate(branch_specs):
            start_label = entry_block.label if index == 0 else branch_specs[index - 1][3]
            plan = self._condition_branch_plan(
                condition, sir_params, start_label, exit_label, next_label,
                f"if_{line_column.replace(':', '_')}",
            )
            if plan is None:
                return False
            new_internal = {label for label, _ in plan if label != start_label}
            if new_internal & labels or new_internal & internal_labels:
                return False
            internal_labels.update(new_internal)
            branches.append((start_label, plan, return_point, exit_label, next_label))

        next_label = None
        for index, (start_label, plan, return_point, exit_label, next_label) in enumerate(branches):
            test_block = entry_block if index == 0 else sir_fn.add_block(start_label)
            self._install_condition_branch_plan(sir_fn, test_block, plan)
            sir_fn.add_block(exit_label).add(ReturnInst(
                point_id=return_point
            ))

        final_block = sir_fn.add_block(next_label)
        final_block.add(ReturnInst(
            point_id=final_return_point
        ))
        return True

    def _try_lower_direct_call_subset(
        self,
        fn: Any,
        entry_block: SIRBasicBlock,
        sir_params: list[SIRValue],
        return_type: str,
    ) -> bool:
        """Lower straight-line direct/whisper borrows of whole bindings."""
        body = getattr(fn, "body", None) or []
        if not body or type(body[-1]).__name__ not in ("Return", "ReturnNode"):
            return False
        if return_type != "void" or any(
            type(item).__name__ not in ("Expression", "Defer")
            or type(getattr(item, "value", None)).__name__ != "Call"
            for item in body[:-1]
        ):
            return False

        parsed_functions = getattr(self, "_parsed_functions", {})
        sole_names = getattr(self, "_sole_names", frozenset())
        caller_params = {}
        for param in getattr(fn, "params", ()):
            if isinstance(param, tuple) and len(param) == 2:
                caller_params[param[0]] = param[1]
            else:
                caller_params[getattr(param, "name", "")] = (
                    getattr(param, "type_ann", None)
                    or getattr(param, "type", None)
                )
        slots = {
            instruction.var_name: instruction.result
            for instruction in entry_block.instructions
            if isinstance(instruction, AllocStackInst)
        }

        direct_params = []
        direct_calls = []
        direct_loads_by_call = []
        for statement in body[:-1]:
            call = statement.value
            callee = parsed_functions.get(call.callee)
            if callee is None:
                return False
            target_params = []
            for parameter in getattr(callee, "params", ()):
                if isinstance(parameter, tuple) and len(parameter) == 2:
                    target_params.append((parameter[0], parameter[1]))
                else:
                    target_params.append((
                        getattr(parameter, "name", ""),
                        getattr(parameter, "type_ann", None)
                        or getattr(parameter, "type", None),
                    ))
            if (
                len(target_params) != len(call.args)
                or not target_params
                or any(
                    getattr(param_type, "ownership_domain", None)
                    not in ("direct", "whisper")
                    for _, param_type in target_params
                )
            ):
                return False
            call_loads = []
            call_values = []
            for argument, (target_name, target_type) in zip(
                call.args, target_params
            ):
                source_domain = "exclusive"
                if type(argument).__name__ == "Unary":
                    if (
                        getattr(argument, "op", None) != "&"
                        or type(getattr(argument, "value", None)).__name__
                        != "Name"
                    ):
                        return False
                    source_name = argument.value.value
                    source_type = caller_params.get(source_name)
                    source_domain = (
                        getattr(source_type, "ownership_domain", None)
                        or "exclusive"
                    )
                    if (
                        source_type is None
                        or getattr(source_type, "name", None) not in sole_names
                        or getattr(source_type, "name", None)
                        != getattr(target_type, "name", None)
                        or source_name not in slots
                    ):
                        return False
                    call_values.append(SIRValue(
                        slots[source_name].name,
                        f"{source_type.name}*",
                    ))
                elif type(argument).__name__ == "Name":
                    source_name = argument.value
                    source_type = caller_params.get(source_name)
                    source_domain = getattr(
                        source_type, "ownership_domain", None
                    )
                    target_domain = getattr(
                        target_type, "ownership_domain", None
                    )
                    compatible_forward = (
                        source_domain == target_domain
                        or (source_domain == "direct" and target_domain == "whisper")
                    )
                    if (
                        source_type is None
                        or not compatible_forward
                        or getattr(source_type, "name", None)
                        != getattr(target_type, "name", None)
                        or source_name not in slots
                    ):
                        return False
                    source_domain = getattr(source_type, "ownership_domain", None)
                    loaded = self._next_val(
                        f"direct_{source_name}",
                        self._type_name(source_type),
                    )
                    call_loads.append(LoadInst(
                        source=slots[source_name], result=loaded
                    ))
                    call_values.append(loaded)
                else:
                    return False
                access_domain = getattr(target_type, "ownership_domain", None)
                point_id = self._statement_point_id(call, access_domain)
                direct_params.append((
                    source_name, call.callee, target_name, point_id,
                    source_type, source_domain, access_domain,
                ))
            direct_loads_by_call.append(call_loads)
            direct_calls.append(CallInst(
                callee=call.callee,
                arguments=call_values,
            ))

        # Markers are inserted before calls at their source point so the
        # ownership graph can verify that every borrow reached SIR.
        rebuilt = list(entry_block.instructions)
        rebuilt = rebuilt[:len(slots) * 2]
        call_index = 0
        for statement in body[:-1]:
            call = statement.value
            # Parameter-specific source identities distinguish mixed direct
            # and whisper arguments at the same call site.
            call_index_for_markers = call_index
            rebuilt.extend(direct_loads_by_call[call_index_for_markers])
            for (
                source_name, callee_name, parameter_name, marker_point,
                source_type, source_domain, access_domain,
            ) in direct_params:
                if callee_name == call.callee and marker_point.startswith(
                    f"{access_domain}@{call.token.line}:{call.token.column}"
                ):
                    access_instruction = (
                        DirectAccessInst(
                            source=SIRValue(source_name, source_type.name),
                            callee=callee_name,
                            parameter=parameter_name,
                            source_domain=source_domain,
                            point_id=marker_point,
                        )
                        if access_domain == "direct"
                        else WhisperBorrowInst(
                            source=SIRValue(source_name, source_type.name),
                            callee=callee_name,
                            parameter=parameter_name,
                            source_domain=source_domain,
                            point_id=marker_point,
                        )
                    )
                    rebuilt.append(access_instruction)
            rebuilt.append(direct_calls[call_index])
            call_index += 1
        rebuilt.append(ReturnInst(
            point_id=self._terminal_return_point_id(fn)
        ))
        entry_block.instructions = rebuilt
        return True

    def generate_from_ast(self, ast: Any) -> SIRModule:
        """Gera o SIR a partir de um módulo AST parsed pelo frontend."""
        module_name = getattr(ast, "name", self.module_name)
        self.sir_mod = SIRModule(name=module_name)
        self._parsed_functions = {
            function.name: function
            for function in getattr(ast, "functions", ())
        }
        self._sole_names = frozenset(
            item.name for item in getattr(ast, "structs", ())
            if getattr(item, "is_sole", False)
        )

        # Suporta nós de função tanto do frontend rico quanto do bootstrap
        functions = getattr(ast, "functions", None)
        if functions is None and hasattr(ast, "decls"):
            functions = [d for d in ast.decls if getattr(d, "__class__", None).__name__ == "FnDeclNode"]

        if functions:
            for fn in functions:
                self._lower_function(fn)

        return self.sir_mod

    def _lower_function(self, fn: Any) -> SIRFunction:
        fn_name = getattr(fn, "name", "anonymous")
        params = getattr(fn, "params", [])
        ret_type = (
            getattr(fn, "ret", None)
            or getattr(fn, "result", None)
            or getattr(fn, "return_type", None)
        )
        ret_str = self._type_name(ret_type, "void")
        directives = getattr(fn, "directives", []) or []
        dir_names = [getattr(d, "name", "") for d in directives]
        attrs = getattr(fn, "attributes", []) or []
        is_system = "@system" in attrs or "system" in dir_names or getattr(fn, "is_system", False)

        sir_params = []
        for p in params:
            if isinstance(p, tuple) and len(p) == 2:
                p_name, p_type = p
            else:
                p_name = getattr(p, "name", "arg")
                p_type = getattr(p, "type_ann", None) or getattr(p, "type", None)
            p_type_str = self._type_name(p_type, "any")
            sir_params.append(SIRValue(name=p_name, type_name=p_type_str))

        sir_fn = SIRFunction(
            name=fn_name,
            parameters=sir_params,
            return_type=ret_str,
            is_system=is_system
        )
        self.sir_mod.add_function(sir_fn)

        entry_block = sir_fn.add_block("0")

        # Emite alocações para parâmetros locais
        for p in sir_params:
            stack_slot = self._next_val(f"slot_{p.name}", p.type_name)
            entry_block.add(AllocStackInst(var_name=p.name, type_name=p.type_name, result=stack_slot))
            entry_block.add(StoreInst(destination=stack_slot, source=p))

        if self._try_lower_direct_call_subset(
            fn, entry_block, sir_params, ret_str
        ):
            return sir_fn

        # Primeiro subconjunto estruturado de CFG: if booleano por parâmetro
        # com retornos diretos. Só é ativado quando todos os caminhos podem ser
        # representados honestamente pelo protótipo atual.
        if self._try_lower_simple_if_returns(
            fn, sir_fn, entry_block, sir_params, ret_str
        ):
            return sir_fn

        if self._try_lower_sequential_if_returns(
            fn, sir_fn, entry_block, sir_params, ret_str
        ):
            return sir_fn

        if self._try_lower_simple_loop_control(
            fn, sir_fn, entry_block, sir_params, ret_str
        ):
            return sir_fn

        if self._try_lower_linear_ownership_points(
            fn, entry_block, ret_str
        ):
            return sir_fn

        # Emite retorno padrão no fallback protótipo. Este comentário é também
        # uma sentinela do reality gate: o SIRGenerator ainda não faz lowering
        # completo de corpos de função.
        # Quando o bloco corresponde a um return terminal direto da AST,
        # preserva sua identidade source-stable.
        return_point = self._terminal_return_point_id(fn)
        entry_block.add(
            ReturnInst(
                value=None if ret_str == "void"
                else self._next_val("ret_val", ret_str),
                point_id=return_point,
            )
        )
        return sir_fn
