"""Checked-frontend bridge for canonical REGION lifetime topology."""
from __future__ import annotations

from .region_lifetime import RegionLifetimePlan, build_region_lifetime_plan
from .typed_ast import OwnershipDomainGraph, Phase1SemanticError


class RegionFrontendPlanError(Phase1SemanticError):
    """Raised when a checked frontend snapshot cannot supply REGION facts."""


def plan_checked_region_lifetime(
    checked_module: object,
    *,
    function: str,
) -> RegionLifetimePlan:
    """Derive REGION lifetime topology directly from a Phase-1 checked module.

    The bridge consumes the semantic snapshot already produced by Phase 1.  It
    does not reparse source, rebuild ownership events, or invent region facts.
    """
    semantic = getattr(checked_module, "semantic", None)
    if semantic is None:
        raise RegionFrontendPlanError(
            "REGION frontend planning requires a Phase1CheckedModule semantic snapshot"
        )
    graph = getattr(semantic, "ownership_domains", None)
    if not isinstance(graph, OwnershipDomainGraph):
        raise RegionFrontendPlanError(
            "REGION frontend planning requires the canonical ownership domain graph"
        )
    return build_region_lifetime_plan(graph, function=function)


__all__ = [
    "RegionFrontendPlanError",
    "plan_checked_region_lifetime",
]
