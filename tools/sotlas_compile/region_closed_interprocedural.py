"""Closed backend-neutral REGION interprocedural ownership graph.

This layer composes already-certified local/interprocedural lifetime facts,
caller-to-callee boundary links, callee-return-to-caller-owner links, the
symbolic arena/lifetime epoch graph and its path-sensitive local reaching-epoch
certificate. It adds no runtime ABI or backend lowering; it only revalidates
that the certificates describe one coherent ownership topology.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .canonical_sir import build_canonical_checked_ownership_sir
from .region_arena import (
    RegionArenaLifetimeGraph,
    build_region_arena_lifetime_graph,
)
from .region_arena_flow import (
    RegionArenaFlowCertificate,
    certify_region_arena_flow,
)
from .region_boundary_link import (
    RegionBoundaryLinkPlan,
    plan_checked_region_boundary_links,
)
from .region_interprocedural import (
    RegionInterproceduralFunctionPlan,
    RegionInterproceduralLifetimePlan,
    plan_checked_region_interprocedural,
)
from .region_return_link import (
    RegionReturnCallLink,
    RegionReturnLinkPlan,
    plan_checked_region_return_links,
)
from .typed_ast import Phase1SemanticError


class RegionClosedInterproceduralError(Phase1SemanticError):
    """Raised when certified REGION interprocedural layers disagree."""


@dataclass(frozen=True)
class RegionClosedInterproceduralPlan:
    lifetime: RegionInterproceduralLifetimePlan
    boundaries: RegionBoundaryLinkPlan
    return_links: RegionReturnLinkPlan
    arena_lifetime: RegionArenaLifetimeGraph
    arena_flow: RegionArenaFlowCertificate | None = None

    def function(self, name: str) -> RegionInterproceduralFunctionPlan:
        return self.lifetime.function(name)

    def returns_from(self, caller: str) -> tuple[RegionReturnCallLink, ...]:
        self.function(caller)
        return tuple(item for item in self.return_links.links if item.caller == caller)

    def return_at_call(self, caller: str, point_id: str) -> RegionReturnCallLink:
        self.function(caller)
        matches = tuple(
            item
            for item in self.return_links.links
            if item.caller == caller and item.point_id == point_id
        )
        if len(matches) != 1:
            raise RegionClosedInterproceduralError(
                f"closed REGION graph requires exactly one return link {caller}::{point_id}"
            )
        return matches[0]

    def require_complete_arena_flow(self) -> RegionArenaFlowCertificate:
        """Return the checked arena-flow certificate or fail closed if incomplete."""
        if self.arena_flow is None:
            raise RegionClosedInterproceduralError(
                "closed REGION graph lacks checked arena-flow certification"
            )
        if not self.arena_flow.complete:
            reasons = tuple(dict.fromkeys(item.reason for item in self.arena_flow.unresolved))
            raise RegionClosedInterproceduralError(
                "closed REGION arena flow is incomplete: " + ", ".join(reasons)
            )
        return self.arena_flow


def build_region_closed_interprocedural_plan(
    lifetime: RegionInterproceduralLifetimePlan,
    boundaries: RegionBoundaryLinkPlan,
    return_links: RegionReturnLinkPlan,
) -> RegionClosedInterproceduralPlan:
    if not isinstance(lifetime, RegionInterproceduralLifetimePlan):
        raise RegionClosedInterproceduralError(
            "closed REGION graph requires certified interprocedural lifetime facts"
        )
    if not isinstance(boundaries, RegionBoundaryLinkPlan):
        raise RegionClosedInterproceduralError(
            "closed REGION graph requires certified caller/callee boundaries"
        )
    if not isinstance(return_links, RegionReturnLinkPlan):
        raise RegionClosedInterproceduralError(
            "closed REGION graph requires certified return links"
        )

    lifetime_functions = {item.function for item in lifetime.functions}
    boundary_functions = {
        item.function for item in boundaries.boundaries.boundaries
    }
    if len(lifetime_functions) != len(lifetime.functions):
        raise RegionClosedInterproceduralError(
            "closed REGION graph contains duplicate lifetime functions"
        )
    if len(boundary_functions) != len(boundaries.boundaries.boundaries):
        raise RegionClosedInterproceduralError(
            "closed REGION graph contains duplicate function boundaries"
        )
    if lifetime_functions != boundary_functions:
        raise RegionClosedInterproceduralError(
            "closed REGION graph function boundaries diverged from lifetime functions"
        )

    seen_return_identities: set[tuple[str, str, str]] = set()
    for link in return_links.links:
        if link.caller not in lifetime_functions or link.callee not in lifetime_functions:
            raise RegionClosedInterproceduralError(
                f"closed REGION return link references unknown function {link.caller}->{link.callee}"
            )
        if link.identity in seen_return_identities:
            raise RegionClosedInterproceduralError(
                f"duplicate closed REGION return-link identity {link.identity!r}"
            )
        seen_return_identities.add(link.identity)

        point = lifetime.call_point(link.caller, link.point_id)
        if point.callee != link.callee:
            raise RegionClosedInterproceduralError(
                f"closed REGION return link {link.caller}::{link.point_id} callee diverged from call CFG"
            )

        outgoing = boundaries.outgoing(link.caller, link.point_id)
        if not outgoing or any(item.callee != link.callee for item in outgoing):
            raise RegionClosedInterproceduralError(
                f"closed REGION return link {link.caller}::{link.point_id} diverged from boundary links"
            )

        caller = lifetime.function(link.caller)
        local_owners = {item.binding: item for item in caller.local.owners}
        destination = local_owners.get(link.destination)
        if destination is None or destination.type != link.type:
            raise RegionClosedInterproceduralError(
                f"closed REGION return destination {link.caller}::{link.destination} lacks matching owner"
            )

        callee_boundary = boundaries.boundaries.function(link.callee)
        if link.callee_return_bindings != callee_boundary.return_bindings:
            raise RegionClosedInterproceduralError(
                f"closed REGION return bindings for {link.callee!r} diverged from function boundary"
            )

    arena_lifetime = build_region_arena_lifetime_graph(
        lifetime,
        boundaries,
        return_links,
    )
    arena_slots = {item.identity for item in arena_lifetime.slots}
    lifetime_slots = {
        (function_plan.function, owner.binding)
        for function_plan in lifetime.functions
        for owner in function_plan.local.owners
    }
    if arena_slots != lifetime_slots:
        raise RegionClosedInterproceduralError(
            "closed REGION arena slots diverged from lifetime owners"
        )

    return RegionClosedInterproceduralPlan(
        lifetime=lifetime,
        boundaries=boundaries,
        return_links=return_links,
        arena_lifetime=arena_lifetime,
    )


def plan_checked_region_closed_interprocedural(
    checked_module: object,
) -> RegionClosedInterproceduralPlan:
    lifetime = plan_checked_region_interprocedural(checked_module)
    boundaries = plan_checked_region_boundary_links(checked_module)
    return_links = plan_checked_region_return_links(checked_module)
    plan = build_region_closed_interprocedural_plan(
        lifetime,
        boundaries,
        return_links,
    )
    checked_sir, _ = build_canonical_checked_ownership_sir(checked_module)
    arena_flow = certify_region_arena_flow(
        plan.lifetime,
        plan.arena_lifetime,
        checked_sir,
    )
    return replace(plan, arena_flow=arena_flow)


__all__ = [
    "RegionClosedInterproceduralError",
    "RegionClosedInterproceduralPlan",
    "build_region_closed_interprocedural_plan",
    "plan_checked_region_closed_interprocedural",
]
