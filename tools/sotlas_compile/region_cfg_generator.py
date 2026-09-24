"""Narrow REGION-aware extension of the prototype SIR generator.

The canonical SIR generator intentionally supports only verified subsets of the
language. REGION CFG certification needs two additional shapes that are already
accepted by the semantic frontend: straight-line call-scoped borrows followed by
an ownership transfer, and call-scoped borrows inside a simple while loop.

This module extends only those shapes. Every emitted lifetime marker is derived
from the original AST source point and is still validated by the existing
ownership placement pass against the canonical Typed-AST ownership facts. Any
shape outside this exact subset falls back to the base generator or fails closed.
"""
from __future__ import annotations

from typing import Any


def make_region_cfg_generator(sir):
    """Return a SIRGenerator subclass with the narrow REGION CFG extensions."""

    base = sir.SIRGenerator

    class RegionCFGSIRGenerator(base):
        @staticmethod
        def _parameter_map(function: Any) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for parameter in getattr(function, "params", ()) or ():
                if isinstance(parameter, tuple) and len(parameter) == 2:
                    result[parameter[0]] = parameter[1]
                else:
                    name = getattr(parameter, "name", "")
                    typ = (
                        getattr(parameter, "type_ann", None)
                        or getattr(parameter, "type", None)
                    )
                    if isinstance(name, str) and name:
                        result[name] = typ
            return result

        @staticmethod
        def _slot_map(entry_block) -> dict[str, Any]:
            return {
                instruction.var_name: instruction.result
                for instruction in entry_block.instructions
                if isinstance(instruction, sir.AllocStackInst)
            }

        @staticmethod
        def _parameter_name_type(parameter: Any) -> tuple[str, Any]:
            if isinstance(parameter, tuple) and len(parameter) == 2:
                return parameter[0], parameter[1]
            return (
                getattr(parameter, "name", ""),
                getattr(parameter, "type_ann", None)
                or getattr(parameter, "type", None),
            )

        @staticmethod
        def _source_name(expr: Any) -> str | None:
            if type(expr).__name__ == "Name":
                value = getattr(expr, "value", None)
                return value if isinstance(value, str) and value else None
            return None

        def _region_call_instructions(
            self,
            call: Any,
            caller_params: dict[str, Any],
            slots: dict[str, Any],
            *,
            allow_move: bool,
        ) -> tuple[list[Any], bool] | None:
            if type(call).__name__ != "Call":
                return None
            callee = getattr(self, "_parsed_functions", {}).get(
                getattr(call, "callee", "")
            )
            if callee is None:
                return None
            result_type = getattr(callee, "result", None)
            if getattr(result_type, "name", result_type) != "void":
                return None
            parameters = tuple(getattr(callee, "params", ()) or ())
            arguments = tuple(getattr(call, "args", ()) or ())
            if not parameters or len(parameters) != len(arguments):
                return None

            emitted: list[Any] = []
            call_arguments: list[Any] = []
            saw_region_borrow = False

            for argument, parameter in zip(arguments, parameters, strict=True):
                parameter_name, target_type = self._parameter_name_type(parameter)
                if not parameter_name or target_type is None:
                    return None
                target_domain = getattr(target_type, "ownership_domain", None)

                if target_domain in ("direct", "whisper"):
                    source_name: str | None = None
                    source_type = None
                    source_domain = None
                    argument_value = None

                    if (
                        type(argument).__name__ == "Unary"
                        and getattr(argument, "op", None) == "&"
                    ):
                        source_name = self._source_name(
                            getattr(argument, "value", None)
                        )
                        if source_name is None:
                            return None
                        source_type = caller_params.get(source_name)
                        source_domain = (
                            getattr(source_type, "ownership_domain", None)
                            if source_type is not None else None
                        ) or "exclusive"
                        slot = slots.get(source_name)
                        if (
                            source_type is None
                            or slot is None
                            or getattr(source_type, "name", None)
                            != getattr(target_type, "name", None)
                        ):
                            return None
                        allowed = (
                            ("exclusive", "shared", "island", "region", "direct")
                            if target_domain == "direct"
                            else (
                                "exclusive", "shared", "island", "region",
                                "direct", "whisper",
                            )
                        )
                        if source_domain not in allowed:
                            return None
                        argument_value = sir.SIRValue(
                            slot.name,
                            f"{source_type.name}*",
                        )
                    elif type(argument).__name__ == "Name":
                        source_name = self._source_name(argument)
                        if source_name is None:
                            return None
                        source_type = caller_params.get(source_name)
                        source_domain = (
                            getattr(source_type, "ownership_domain", None)
                            if source_type is not None else None
                        )
                        compatible = (
                            source_domain == target_domain
                            or (
                                source_domain == "direct"
                                and target_domain == "whisper"
                            )
                        )
                        slot = slots.get(source_name)
                        if (
                            source_type is None
                            or slot is None
                            or not compatible
                            or getattr(source_type, "name", None)
                            != getattr(target_type, "name", None)
                        ):
                            return None
                        loaded = self._next_val(
                            f"region_borrow_{source_name}",
                            self._type_name(source_type),
                        )
                        emitted.append(sir.LoadInst(source=slot, result=loaded))
                        argument_value = loaded
                    else:
                        return None

                    point_id = self._statement_point_id(call, target_domain)
                    marker_type = (
                        sir.DirectAccessInst
                        if target_domain == "direct"
                        else sir.WhisperBorrowInst
                    )
                    emitted.append(marker_type(
                        source=sir.SIRValue(source_name, source_type.name),
                        callee=call.callee,
                        parameter=parameter_name,
                        source_domain=source_domain,
                        point_id=point_id,
                    ))
                    call_arguments.append(argument_value)
                    saw_region_borrow = (
                        saw_region_borrow or source_domain == "region"
                    )
                    continue

                if not allow_move or type(argument).__name__ != "MoveExpr":
                    return None
                moved = getattr(argument, "value", None)
                source_name = self._source_name(moved)
                if source_name is None:
                    return None
                source_type = caller_params.get(source_name)
                source_domain = (
                    getattr(source_type, "ownership_domain", None)
                    if source_type is not None else None
                )
                if (
                    source_type is None
                    or source_domain is None
                    or target_domain is None
                    or getattr(source_type, "name", None)
                    != getattr(target_type, "name", None)
                ):
                    return None
                call_arguments.append(
                    sir.SIRValue(source_name, source_type.name)
                )

            emitted.append(
                sir.CallInst(callee=call.callee, arguments=call_arguments)
            )
            return emitted, saw_region_borrow

        def _try_lower_region_linear_points(
            self,
            fn: Any,
            entry_block: Any,
            return_type: str,
        ) -> bool:
            if return_type != "void":
                return False
            body = getattr(fn, "body", None) or []
            if (
                len(body) < 2
                or type(body[-1]).__name__ not in ("Return", "ReturnNode")
            ):
                return False

            caller_params = self._parameter_map(fn)
            slots = self._slot_map(entry_block)
            lowered: list[Any] = []
            saw_region_point = False

            for statement in body[:-1]:
                kind = type(statement).__name__
                if kind == "Expression":
                    call_result = self._region_call_instructions(
                        getattr(statement, "value", None),
                        caller_params,
                        slots,
                        allow_move=True,
                    )
                    if call_result is None:
                        return False
                    instructions, saw_region_borrow = call_result
                    lowered.extend(instructions)
                    saw_region_point = saw_region_point or saw_region_borrow
                    continue

                if kind not in ("Handover", "Quarantine"):
                    return False
                source = getattr(statement, "value", None)
                source_name = self._source_name(source)
                if source_name is None:
                    return False
                destination = getattr(statement, "destination", None)
                destination_name = (
                    self._source_name(destination)
                    if destination is not None else None
                )
                if kind == "Handover" and destination_name is None:
                    return False
                source_type = caller_params.get(source_name)
                source_domain = (
                    getattr(source_type, "ownership_domain", None)
                    if source_type is not None else None
                )
                saw_region_point = saw_region_point or source_domain == "region"
                operation = kind.lower()
                lowered.append(sir.OwnershipDomainPointInst(
                    operation=operation,
                    source_name=source_name,
                    destination_name=destination_name,
                    point_id=self._statement_point_id(statement, operation),
                ))

            if not saw_region_point:
                return False
            lowered.append(sir.ReturnInst(
                point_id=self._statement_point_id(body[-1], "return")
            ))
            for instruction in lowered:
                entry_block.add(instruction)
            return True

        def _try_lower_region_loop_borrow(
            self,
            fn: Any,
            sir_fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            if return_type != "void":
                return False
            body = getattr(fn, "body", None) or []
            if not body or type(body[0]).__name__ not in ("While", "WhileNode"):
                return False
            if len(body) > 2:
                return False
            terminal_return = None
            if len(body) == 2:
                if type(body[1]).__name__ not in ("Return", "ReturnNode"):
                    return False
                terminal_return = body[1]

            loop = body[0]
            loop_body = tuple(getattr(loop, "body", None) or ())
            if not loop_body:
                return False
            caller_params = self._parameter_map(fn)
            slots = self._slot_map(entry_block)
            body_instructions: list[Any] = []
            saw_region_borrow = False
            for statement in loop_body:
                if type(statement).__name__ != "Expression":
                    return False
                call_result = self._region_call_instructions(
                    getattr(statement, "value", None),
                    caller_params,
                    slots,
                    allow_move=False,
                )
                if call_result is None:
                    return False
                instructions, call_has_region_borrow = call_result
                if not call_has_region_borrow:
                    return False
                saw_region_borrow = True
                body_instructions.extend(instructions)
            if not saw_region_borrow:
                return False

            point = self._statement_point_id(loop, "while").removeprefix(
                "while@"
            )
            line, column = point.split(":", 1)
            cond_label = f"while_{line}_{column}_cond"
            body_label = f"while_{line}_{column}_body"
            exit_label = f"while_{line}_{column}_exit"
            condition_plan = self._condition_branch_plan(
                getattr(loop, "condition", None),
                sir_params,
                cond_label,
                body_label,
                exit_label,
                f"while_{line}_{column}",
            )
            if condition_plan is None or any(
                label in (body_label, exit_label)
                for label, _ in condition_plan if label != cond_label
            ):
                return False

            entry_block.add(sir.BranchInst(cond_label))
            cond_block = sir_fn.add_block(cond_label)
            self._install_condition_branch_plan(
                sir_fn, cond_block, condition_plan
            )
            loop_block = sir_fn.add_block(body_label)
            for instruction in body_instructions:
                loop_block.add(instruction)
            loop_block.add(sir.BranchInst(
                cond_label,
                point_id=self._statement_point_id(loop, "while_backedge"),
                control_kind="backedge",
            ))
            exit_block = sir_fn.add_block(exit_label)
            exit_block.add(sir.ReturnInst(
                point_id=(
                    self._statement_point_id(terminal_return, "return")
                    if terminal_return is not None else None
                )
            ))
            return True

        def _try_lower_simple_loop_control(
            self,
            fn: Any,
            sir_fn: Any,
            entry_block: Any,
            sir_params: list[Any],
            return_type: str,
        ) -> bool:
            if self._try_lower_region_loop_borrow(
                fn, sir_fn, entry_block, sir_params, return_type
            ):
                return True
            return super()._try_lower_simple_loop_control(
                fn, sir_fn, entry_block, sir_params, return_type
            )

        def _try_lower_linear_ownership_points(
            self,
            fn: Any,
            entry_block: Any,
            return_type: str,
        ) -> bool:
            if self._try_lower_region_linear_points(
                fn, entry_block, return_type
            ):
                return True
            return super()._try_lower_linear_ownership_points(
                fn, entry_block, return_type
            )

    RegionCFGSIRGenerator.__name__ = "RegionCFGSIRGenerator"
    return RegionCFGSIRGenerator


__all__ = ["make_region_cfg_generator"]
