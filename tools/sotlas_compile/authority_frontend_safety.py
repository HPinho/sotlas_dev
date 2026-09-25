"""Production frontend gate for named Authority ABI contracts.

The canonical memory/FFI safety pass still owns unsafe and legacy ``@system``
rules. This extension delegates the narrowly contracted privileged intrinsics
from that generic gate to ``AuthorityDomainPlan`` so the same least-authority
semantics used by Phase 3 also protect ``bootstrap.check`` / ``compile_source``.

No capability rule is duplicated here: ``authority_abi`` names the boundary and
``authority.plan_authority_domains`` decides whether the caller may cross it.
"""
from __future__ import annotations

import importlib
import re

from .authority_abi import AUTHORITY_ABI_CONTRACTS
from .language_safety import register_safe_system_builtins


_CALL_POINT_RE = re.compile(r"\bcall@([0-9]+):([0-9]+)\b")


def _error_location(message: str) -> tuple[int, int]:
    match = _CALL_POINT_RE.search(message)
    if match is None:
        return 1, 1
    return int(match.group(1)), int(match.group(2))


def install(bootstrap) -> None:
    """Compose canonical named Authority checking into the production frontend."""
    if getattr(bootstrap, "_AUTHORITY_FRONTEND_SAFETY_INSTALLED", False):
        return

    # These symbols stop using the old all-or-nothing builtin gate only because
    # the canonical Authority planner below immediately validates their named
    # contracts before bootstrap.check can return successfully.
    register_safe_system_builtins(
        contract.symbol for contract in AUTHORITY_ABI_CONTRACTS
    )

    previous_check = bootstrap.check

    def authority_checked_check(
        module,
        imported_fns=None,
        imported_types=None,
        imported_enums=None,
        imported_globals=None,
    ):
        result = previous_check(
            module,
            imported_fns,
            imported_types,
            imported_enums,
            imported_globals,
        )

        package = bootstrap.__package__ or "sotlas_compile"
        authority = importlib.import_module(f"{package}.authority")
        try:
            authority.plan_authority_domains(module)
        except authority.AuthorityDomainError as error:
            line, column = _error_location(str(error))
            raise bootstrap.SotlasBootstrapError(
                str(error),
                line,
                column,
                getattr(module, "filename", None),
                getattr(module, "source", None),
            ) from error
        return result

    bootstrap.check = authority_checked_check
    bootstrap._AUTHORITY_FRONTEND_SAFETY_INSTALLED = True


__all__ = ["install"]
