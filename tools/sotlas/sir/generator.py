"""Gerador de SIR a partir da AST do compilador Sotlas.

Mapeia declarações e corpos de função para blocos básicos SSA do SIR.
"""
from __future__ import annotations
from typing import Any, Optional
from .instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst,
    ReturnInst, BranchInst, CondBranchInst, SystemOpInst
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
            if param.name == name:
                return param
        return None

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
        if not body or type(body[0]).__name__ not in ("If", "IfNode"):
            return False

        if_node = body[0]
        condition = self._simple_condition_value(
            getattr(if_node, "condition", None),
            sir_params,
        )
        if condition is None:
            return False

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

        if else_body is not None:
            if not isinstance(else_body, list):
                return False
            if len(else_body) != 1 or type(else_body[0]).__name__ not in ("Return", "ReturnNode"):
                return False
            if len(body) != 1:
                return False

            entry_block.add(
                CondBranchInst(
                    condition=condition,
                    true_block=then_label,
                    false_block=else_label,
                )
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

        if len(body) != 2 or type(body[1]).__name__ not in ("Return", "ReturnNode"):
            return False

        entry_block.add(
            CondBranchInst(
                condition=condition,
                true_block=then_label,
                false_block=cont_label,
            )
        )
        then_block = sir_fn.add_block(then_label)
        cont_block = sir_fn.add_block(cont_label)
        then_block.add(
            ReturnInst(
                point_id=self._statement_point_id(then_body[0], "return")
            )
        )
        cont_block.add(
            ReturnInst(
                point_id=self._statement_point_id(body[1], "return")
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
        condition = self._simple_condition_value(
            getattr(loop, "condition", None),
            sir_params,
        )
        if condition is None:
            return False

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

        entry_block.add(BranchInst(cond_label))
        cond_block = sir_fn.add_block(cond_label)
        cond_block.add(
            CondBranchInst(
                condition=condition,
                true_block=body_label,
                false_block=exit_label,
            )
        )

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

    def generate_from_ast(self, ast: Any) -> SIRModule:
        """Gera o SIR a partir de um módulo AST parsed pelo frontend."""
        module_name = getattr(ast, "name", self.module_name)
        self.sir_mod = SIRModule(name=module_name)

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

        # Primeiro subconjunto estruturado de CFG: if booleano por parâmetro
        # com retornos diretos. Só é ativado quando todos os caminhos podem ser
        # representados honestamente pelo protótipo atual.
        if self._try_lower_simple_if_returns(
            fn, sir_fn, entry_block, sir_params, ret_str
        ):
            return sir_fn

        if self._try_lower_simple_loop_control(
            fn, sir_fn, entry_block, sir_params, ret_str
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
