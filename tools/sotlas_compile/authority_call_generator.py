"""Narrow canonical SIR lowering for source-certified Authority Domain calls.

The generic prototype SIR generator intentionally does not lower arbitrary
straight-line calls yet. Phase 3 needs source ``@system(capability)`` calls to
survive into SIR so their sidecar authority certificate can be verified.

This extension lowers only direct, zero-argument, ``void`` authority calls that
already exist in ``AuthorityDomainPlan``. It does not infer capabilities, does
not lower external/intrinsic calls, and does not broaden general call lowering.
Unsupported authority-call shapes remain absent and are therefore rejected by
``certify_authority_sir`` in the strict checked-Authority path.
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
            if return_type != "void":
                return False
            body = tuple(getattr(fn, "body", None) or ())
            if len(body) < 2:
                return False
            terminal = body[-1]
            if type(terminal).__name__ not in ("Return", "ReturnNode"):
                return False
            if getattr(terminal, "value", None) is not None:
                return False

            caller = getattr(fn, "name", None)
            if not isinstance(caller, str) or caller not in contracts:
                return False

            emitted: list[Any] = []
            for statement in body[:-1]:
                if type(statement).__name__ != "Expression":
                    return False
                call = getattr(statement, "value", None)
                if type(call).__name__ != "Call":
                    return False
                if tuple(getattr(call, "args", ()) or ()):
                    return False
                point_id = self._authority_call_point(call)
                if point_id is None:
                    return False
                edge = edges.get((caller, point_id))
                if edge is None:
                    return False
                callee = getattr(call, "callee", None)
                if edge.callee != callee:
                    raise AuthorityDomainError(
                        f"authority SIR lowering point {caller}::{point_id} "
                        "does not match its certified callee"
                    )
                target = contracts.get(edge.callee)
                if target is None or not target.is_system:
                    raise AuthorityDomainError(
                        f"authority SIR lowering target {edge.callee!r} "
                        "lacks a system authority contract"
                    )
                emitted.append(
                    sir.CallInst(
                        callee=edge.callee,
                        arguments=[],
                        is_system=target.legacy_unrestricted,
                    )
                )

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
