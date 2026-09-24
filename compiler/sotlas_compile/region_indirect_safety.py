"""Fail-closed REGION lifetime checks for indirect function-pointer calls.

Indirect calls do not currently carry a canonical no-escape summary.  Reuse the
same REGION owner/alias tracking as method-boundary validation and reject any
REGION-derived reference that reaches a call marked by the production checker
as ``is_vtable_call``.  This does not invent a new borrow form: a future
indirect-call certificate can relax this gate only after the callee contract is
represented canonically.
"""
from __future__ import annotations

from .region_method_safety import _RegionMethodEscapeChecker


class _RegionIndirectEscapeChecker(_RegionMethodEscapeChecker):
    def _check_expr(self, expr, scope, aliases, region_owners) -> None:
        for call in self._method_calls(expr):
            if not bool(getattr(call, "is_vtable_call", False)):
                continue
            owners: set[str] = set()
            for argument in call.args:
                owners.update(
                    self._reference_sources(argument, aliases, region_owners)
                )
            if not owners:
                continue
            owner = sorted(owners)[0]
            self.error(
                f"reference to region owner {owner!r} cannot cross indirect "
                "function-pointer call without a verified no-escape summary",
                call.token,
            )


def install(bootstrap) -> None:
    if getattr(bootstrap, "_REGION_INDIRECT_SAFETY_INSTALLED", False):
        return

    original_check = bootstrap.check

    def region_indirect_safe_check(
        module,
        imported_fns=None,
        imported_types=None,
        imported_enums=None,
        imported_globals=None,
    ):
        result = original_check(
            module,
            imported_fns,
            imported_types,
            imported_enums,
            imported_globals,
        )
        _RegionIndirectEscapeChecker(
            bootstrap,
            module,
            imported_fns=imported_fns,
            imported_types=imported_types,
        ).check()
        return result

    bootstrap.check = region_indirect_safe_check
    bootstrap._REGION_INDIRECT_SAFETY_INSTALLED = True


__all__ = ["install"]
