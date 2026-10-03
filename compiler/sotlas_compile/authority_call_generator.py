"""Narrow canonical SIR lowering for source-certified Authority Domain calls.

The generic prototype SIR generator intentionally does not lower arbitrary
straight-line calls yet. Phase 3 needs source ``@system(capability)`` calls to
survive into SIR so their sidecar authority certificate can be verified.

This extension lowers source-certified authority calls that already exist in
``AuthorityDomainPlan``. Named ABI edges become source-stable
``AuthorityABIInst`` operations; source abstraction edges remain ordinary
calls. Unsupported source call shapes stay fail-closed.
"""
from __future__ import annotations

from typing import Any

from .authority import AuthorityDomainPlan, AuthorityDomainError
from .region_return_cfg_generator import make_region_return_cfg_generator


def make_authority_call_generator(sir, authority: AuthorityDomainPlan):
    if not isinstance(authority, AuthorityDomainPlan):
        raise AuthorityDomainError(
            "authority SIR lowering requires canonical AuthorityDomainPlan"
        )

    contracts = {item.function: item for item in authority.contracts}
    if len(contracts) != len(authority.contracts):
        raise AuthorityDomainError(
            "authority SIR lowering received duplicate function contracts"
        )
    edges = {}
    for edge in authority.calls:
        key = (edge.caller, edge.point_id)
        if key in edges:
            raise AuthorityDomainError(
                f"authority SIR lowering received duplicate source point "
                f"{edge.caller}::{edge.point_id}"
            )
        edges[key] = edge

    base = make_region_return_cfg_generator(sir)

    class AuthorityCallSIRGenerator(base):
        @staticmethod
        def _authority_call_point(call: object) -> str | None:
            token = getattr(call, "token", None)
            line = getattr(token, "line", None)
            column = getattr(token, "column", None)
            if not isinstance(line, int) or not isinstance(column, int):
                return None
            return f"call@{line}:{column}"

        def _try_lower_authority_calls(
            self,
            fn: Any,
            entry_block: Any,
            return_type: str,
        ) -> bool:
            body = tuple(getattr(fn, "body", None) or ())
            if len(body) < 1:
                return False
            terminal = body[-1]
            if type(terminal).__name__ not in ("Return", "ReturnNode"):
                return False

            caller = getattr(fn, "name", None)
            if not isinstance(caller, str) or caller not in contracts:
                return False

            parameter_types = self._parameter_map(fn)
            emitted: list[Any] = []

            def lower_call(call: Any, *, returned: bool = False) -> Any | None:
                point_id = self._authority_call_point(call)
                if point_id is None:
                    return None
                edge = edges.get((caller, point_id))
                if edge is None:
                    return None
                callee = getattr(call, "callee", None)
                if edge.callee != callee:
                    raise AuthorityDomainError(
                        f"authority SIR lowering point {caller}::{point_id} "
                        "does not match its certified callee"
                    )
                if edge.target_kind == "source":
                    if tuple(getattr(call, "args", ()) or ()) or returned:
                        return None
                    target = contracts.get(edge.callee)
                    if target is None or not target.is_system:
                        raise AuthorityDomainError(
                            f"authority SIR lowering target {edge.callee!r} "
                            "lacks a system authority contract"
                        )
                    return sir.CallInst(
                        callee=edge.callee,
                        arguments=[],
                        is_system=target.legacy_unrestricted,
                    )
                if edge.target_kind != "abi_intrinsic":
                    return None
                signatures = {
                    "__cli": ((), "void"), "__sti": ((), "void"),
                    "__outb": (("u16", "u8"), "void"),
                    "__inb": (("u16",), "u8"),
                }
                signature = signatures.get(edge.callee)
                if signature is None:
                    return None
                argument_types, result_type = signature
                arguments = tuple(getattr(call, "args", ()) or ())
                if len(arguments) != len(argument_types):
                    return None
                values = []
                for argument, expected_type in zip(arguments, argument_types, strict=True):
                    if type(argument).__name__ not in ("Name", "IdentNode", "Identifier"):
                        return None
                    source_name = getattr(argument, "name", None)
                    if not isinstance(source_name, str):
                        source_name = getattr(argument, "value", None)
                    source_type = parameter_types.get(source_name or "")
                    if (
                        source_type is None
                        or getattr(source_type, "name", None) != expected_type
                    ):
                        return None
                    values.append(sir.SIRValue(source_name, expected_type))
                result = None
                if returned:
                    if result_type == "void" or return_type != result_type:
                        return None
                    result = sir.SIRValue(
                        name=f"authority_{point_id.replace('@', '').replace(':', '_')}",
                        type_name=result_type,
                    )
                elif result_type != "void":
                    return None
                return sir.AuthorityABIInst(
                    symbol=edge.callee,
                    point_id=point_id,
                    required_capabilities=edge.required_capabilities,
                    arguments=values,
                    result=result,
                )

            for statement in body[:-1]:
                if type(statement).__name__ != "Expression":
                    return False
                call = getattr(statement, "value", None)
                if type(call).__name__ != "Call":
                    return False
                lowered = lower_call(call)
                if lowered is None:
                    return False
                emitted.append(lowered)

            return_value = getattr(terminal, "value", None)
            if return_value is not None:
                if type(return_value).__name__ != "Call":
                    return False
                lowered = lower_call(return_value, returned=True)
                if lowered is None:
                    return False
                for instruction in emitted:
                    entry_block.add(instruction)
                entry_block.add(lowered)
                entry_block.add(
                    sir.ReturnInst(
                        lowered.result,
                        point_id=self._statement_point_id(terminal, "return"),
                    )
                )
                return True

            if return_type != "void":
                return False

            if not emitted:
                return False
            for instruction in emitted:
                entry_block.add(instruction)
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
            if self._try_lower_authority_calls(fn, entry_block, return_type):
                return True
            return super()._try_lower_linear_ownership_points(
                fn, entry_block, return_type
            )

    AuthorityCallSIRGenerator.__name__ = "AuthorityCallSIRGenerator"
    return AuthorityCallSIRGenerator


__all__ = ["make_authority_call_generator"]
