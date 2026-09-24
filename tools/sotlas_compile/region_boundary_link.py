"""Certified caller-to-callee REGION ownership boundary links.

This layer connects already certified source-stable REGION call transfers to the
ownership-taking REGION parameter boundary of the callee.  It derives topology
only; no SIR mutation, ABI, runtime or backend behavior is introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .region_function_boundary import (
    RegionFunctionBoundaryPlan,
    RegionFunctionBoundaryError,
    plan_checked_region_function_boundaries,
)
from .region_interprocedural import (
    RegionInterproceduralLifetimePlan,
    plan_checked_region_interprocedural,
)
from .typed_ast import Phase1SemanticError


class RegionBoundaryLinkError(Phase1SemanticError):
    """Raised when caller/callee REGION boundaries cannot be linked canonically."""


@dataclass(frozen=True)
class RegionCallBoundaryLink:
    caller: str
    point_id: str
    source_binding: str
    callee: str
    parameter: str
    argument_index: int
    caller_is_root: bool
    caller_is_terminal: bool

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return (self.caller, self.point_id, self.parameter, self.argument_index)


@dataclass(frozen=True)
class RegionBoundaryLinkPlan:
    boundaries: RegionFunctionBoundaryPlan
    links: tuple[RegionCallBoundaryLink, ...]

    def outgoing(self, caller: str, point_id: str) -> tuple[RegionCallBoundaryLink, ...]:
        self.boundaries.function(caller)
        matches = tuple(
            item for item in self.links
            if item.caller == caller and item.point_id == point_id
        )
        if not matches:
            raise RegionBoundaryLinkError(
                f"REGION boundary links require known call point {caller}::{point_id}"
            )
        return matches

    def incoming(self, callee: str, parameter: str) -> tuple[RegionCallBoundaryLink, ...]:
        boundary = self.boundaries.function(callee)
        if parameter not in boundary.parameter_bindings:
            raise RegionBoundaryLinkError(
                f"REGION boundary links require ownership-taking parameter {callee}.{parameter}"
            )
        return tuple(
            item for item in self.links
            if item.callee == callee and item.parameter == parameter
        )


def build_region_boundary_link_plan(
    interprocedural: RegionInterproceduralLifetimePlan,
    boundaries: RegionFunctionBoundaryPlan,
) -> RegionBoundaryLinkPlan:
    if not isinstance(interprocedural, RegionInterproceduralLifetimePlan):
        raise RegionBoundaryLinkError(
            "REGION boundary linking requires a certified interprocedural lifetime plan"
        )
    if not isinstance(boundaries, RegionFunctionBoundaryPlan):
        raise RegionBoundaryLinkError(
            "REGION boundary linking requires a certified function-boundary plan"
        )

    known_functions = {item.function for item in interprocedural.functions}
    boundary_functions = {item.function for item in boundaries.boundaries}
    if len(boundary_functions) != len(boundaries.boundaries):
        raise RegionBoundaryLinkError("duplicate REGION function boundary")
    if known_functions != boundary_functions:
        raise RegionBoundaryLinkError(
            "REGION function boundaries diverged from interprocedural functions"
        )

    links: list[RegionCallBoundaryLink] = []
    seen: set[tuple[str, str, str, int]] = set()
    grouped_indices: dict[tuple[str, str], set[int]] = {}

    for function_plan in interprocedural.functions:
        caller = function_plan.function
        caller_boundary = boundaries.function(caller)
        local_bindings = set(function_plan.local.bindings)

        for transfer in function_plan.calls:
            if transfer.function != caller:
                raise RegionBoundaryLinkError(
                    f"REGION call transfer escaped caller function {caller!r}"
                )
            if transfer.binding not in local_bindings:
                raise RegionBoundaryLinkError(
                    f"REGION call source {caller}::{transfer.binding} lacks local lifetime owner"
                )

            point = interprocedural.call_point(caller, transfer.point_id)
            if point.callee != transfer.callee:
                raise RegionBoundaryLinkError(
                    f"REGION call point {caller}::{transfer.point_id} callee diverged"
                )
            if transfer.argument_index not in point.argument_indices:
                raise RegionBoundaryLinkError(
                    f"REGION call point {caller}::{transfer.point_id} lacks argument index "
                    f"{transfer.argument_index}"
                )

            try:
                callee_boundary = boundaries.function(transfer.callee)
            except RegionFunctionBoundaryError as exc:
                raise RegionBoundaryLinkError(
                    f"REGION call {caller}::{transfer.point_id} targets uncertified callee "
                    f"{transfer.callee!r}"
                ) from exc
            if transfer.parameter not in callee_boundary.parameter_bindings:
                raise RegionBoundaryLinkError(
                    f"REGION call {caller}::{transfer.point_id} does not target an "
                    f"ownership-taking REGION parameter {transfer.callee}.{transfer.parameter}"
                )

            item = RegionCallBoundaryLink(
                caller=caller,
                point_id=transfer.point_id,
                source_binding=transfer.binding,
                callee=transfer.callee,
                parameter=transfer.parameter,
                argument_index=transfer.argument_index,
                caller_is_root=transfer.point_id in caller_boundary.call_root_point_ids,
                caller_is_terminal=transfer.point_id in caller_boundary.call_terminal_point_ids,
            )
            if item.identity in seen:
                raise RegionBoundaryLinkError(
                    f"duplicate REGION caller/callee boundary link {item.identity!r}"
                )
            seen.add(item.identity)
            links.append(item)
            grouped_indices.setdefault((caller, transfer.point_id), set()).add(
                transfer.argument_index
            )

    for point in interprocedural.call_cfg.points:
        actual = grouped_indices.get((point.function, point.point_id), set())
        expected = set(point.argument_indices)
        if actual != expected:
            raise RegionBoundaryLinkError(
                f"REGION boundary links for {point.function}::{point.point_id} "
                "diverged from certified REGION call arguments"
            )

    if len(links) != sum(len(item.calls) for item in interprocedural.functions):
        raise RegionBoundaryLinkError(
            "REGION caller/callee boundary linking did not account for every call transfer"
        )

    return RegionBoundaryLinkPlan(boundaries=boundaries, links=tuple(links))


def plan_checked_region_boundary_links(checked_module: object) -> RegionBoundaryLinkPlan:
    interprocedural = plan_checked_region_interprocedural(checked_module)
    boundaries = plan_checked_region_function_boundaries(checked_module)
    return build_region_boundary_link_plan(interprocedural, boundaries)


__all__ = [
    "RegionBoundaryLinkError",
    "RegionCallBoundaryLink",
    "RegionBoundaryLinkPlan",
    "build_region_boundary_link_plan",
    "plan_checked_region_boundary_links",
]
