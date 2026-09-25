"""Composed interprocedural REGION lifetime view.

The local lifetime topology, source-stable owner origins/call contracts, CFG
call-path certificates, intra-iteration ownership order and return contracts are
independently certified. This module composes those proofs without pretending
the prototype SIR already carries interprocedural call ownership markers. It is
a semantic certificate only; no runtime or backend behavior is introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_sir import build_canonical_checked_ownership_sir
from .ownership_origin import OwnershipOriginPlan, plan_checked_ownership_origins
from .region_call import RegionCallTransfer, plan_checked_region_calls
from .region_call_cfg import (
    RegionCallCFGCertificate,
    RegionCallCFGPoint,
    RegionCallCFGRelation,
    certify_region_call_cfg,
)
from .region_call_sir import validate_region_call_sir
from .region_cfg import RegionLifetimeCFGCertificate, certify_region_lifetime_cfg
from .region_frontend import plan_checked_region_lifetime
from .region_iteration_order import (
    RegionIterationOwnershipCertificate,
    certify_region_iteration_order,
)
from .region_lifetime import RegionLifetimePlan
from .region_return import RegionReturnLifetimePlan, plan_checked_region_returns
from .typed_ast import OwnershipDomain, Phase1SemanticError


class RegionInterproceduralLifetimeError(Phase1SemanticError):
    """Raised when certified local/call/CFG/return REGION facts disagree."""


@dataclass(frozen=True)
class RegionInterproceduralFunctionPlan:
    function: str
    local: RegionLifetimePlan
    calls: tuple[RegionCallTransfer, ...]
    lifetime_cfg: RegionLifetimeCFGCertificate
    iteration_order: RegionIterationOwnershipCertificate
    origins: OwnershipOriginPlan


@dataclass(frozen=True)
class RegionInterproceduralCallPathSummary:
    """Stable derived view of certified REGION call-path facts for one function."""

    function: str
    point_ids: tuple[str, ...]
    ordered_relations: tuple[RegionCallCFGRelation, ...]
    path_disjoint_relations: tuple[RegionCallCFGRelation, ...]
    root_point_ids: tuple[str, ...]
    terminal_point_ids: tuple[str, ...]

    def _require_point(self, point_id: str) -> None:
        if point_id not in self.point_ids:
            raise RegionInterproceduralLifetimeError(
                f"REGION interprocedural call summary requires known call point "
                f"{self.function}::{point_id}"
            )

    def ordered_successors(self, point_id: str) -> tuple[str, ...]:
        """Return all certified ordered successors of one call site."""
        self._require_point(point_id)
        return tuple(
            item.second_point_id
            for item in self.ordered_relations
            if item.first_point_id == point_id
        )

    def ordered_predecessors(self, point_id: str) -> tuple[str, ...]:
        """Return all certified ordered predecessors of one call site."""
        self._require_point(point_id)
        return tuple(
            item.first_point_id
            for item in self.ordered_relations
            if item.second_point_id == point_id
        )


@dataclass(frozen=True)
class RegionInterproceduralLifetimePlan:
    functions: tuple[RegionInterproceduralFunctionPlan, ...]
    returns: RegionReturnLifetimePlan
    call_cfg: RegionCallCFGCertificate

    def function(self, name: str) -> RegionInterproceduralFunctionPlan:
        matches = tuple(item for item in self.functions if item.function == name)
        if len(matches) != 1:
            raise RegionInterproceduralLifetimeError(
                f"REGION interprocedural plan requires exactly one function {name!r}"
            )
        return matches[0]

    def iteration_order(
        self, function: str
    ) -> RegionIterationOwnershipCertificate:
        """Return the mandatory intra-iteration ownership certificate."""
        return self.function(function).iteration_order

    def ownership_origins(self, function: str) -> OwnershipOriginPlan:
        """Return the mandatory source-stable owner-origin certificate."""
        return self.function(function).origins

    def call_points(self, function: str) -> tuple[RegionCallCFGPoint, ...]:
        """Return the certified REGION call sites for one known function."""
        self.function(function)
        return tuple(item for item in self.call_cfg.points if item.function == function)

    def call_point(self, function: str, point_id: str) -> RegionCallCFGPoint:
        """Resolve exactly one certified REGION call site by source identity."""
        self.function(function)
        matches = tuple(
            item
            for item in self.call_cfg.points
            if item.function == function and item.point_id == point_id
        )
        if len(matches) != 1:
            raise RegionInterproceduralLifetimeError(
                f"REGION interprocedural plan requires exactly one call point "
                f"{function}::{point_id}"
            )
        return matches[0]

    def call_relations(self, function: str) -> tuple[RegionCallCFGRelation, ...]:
        """Return all certified pairwise REGION call-path relations for a function."""
        self.function(function)
        return tuple(
            item for item in self.call_cfg.relations if item.function == function
        )

    def call_relation(
        self,
        function: str,
        first_point_id: str,
        second_point_id: str,
    ) -> RegionCallCFGRelation:
        """Resolve one directional certified relation between two call sites."""
        self.function(function)
        matches = tuple(
            item
            for item in self.call_cfg.relations
            if (
                item.function == function
                and item.first_point_id == first_point_id
                and item.second_point_id == second_point_id
            )
        )
        if len(matches) != 1:
            raise RegionInterproceduralLifetimeError(
                "REGION interprocedural plan requires exactly one call relation "
                f"{function}::{first_point_id}->{second_point_id}"
            )
        return matches[0]

    def call_path_summary(self, function: str) -> RegionInterproceduralCallPathSummary:
        """Summarize certified call sites, path relations and call-graph boundaries."""
        points = self.call_points(function)
        relations = self.call_relations(function)
        point_ids = tuple(item.point_id for item in points)
        if len(set(point_ids)) != len(point_ids):
            raise RegionInterproceduralLifetimeError(
                f"REGION interprocedural call summary contains duplicate points for {function!r}"
            )
        known_points = set(point_ids)
        ordered: list[RegionCallCFGRelation] = []
        disjoint: list[RegionCallCFGRelation] = []
        for relation in relations:
            if (
                relation.first_point_id not in known_points
                or relation.second_point_id not in known_points
                or relation.first_point_id == relation.second_point_id
            ):
                raise RegionInterproceduralLifetimeError(
                    f"REGION interprocedural call summary has invalid relation endpoints for {function!r}"
                )
            if relation.relation == "ordered_path":
                ordered.append(relation)
            elif relation.relation == "path_disjoint":
                disjoint.append(relation)
            else:
                raise RegionInterproceduralLifetimeError(
                    f"REGION interprocedural call summary has unknown relation {relation.relation!r}"
                )

        ordered_sources = {item.first_point_id for item in ordered}
        ordered_targets = {item.second_point_id for item in ordered}
        root_point_ids = tuple(
            point_id for point_id in point_ids if point_id not in ordered_targets
        )
        terminal_point_ids = tuple(
            point_id for point_id in point_ids if point_id not in ordered_sources
        )
        return RegionInterproceduralCallPathSummary(
            function=function,
            point_ids=point_ids,
            ordered_relations=tuple(ordered),
            path_disjoint_relations=tuple(disjoint),
            root_point_ids=root_point_ids,
            terminal_point_ids=terminal_point_ids,
        )


def plan_checked_region_interprocedural(
    checked_module: object,
) -> RegionInterproceduralLifetimePlan:
    semantic = getattr(checked_module, "semantic", None)
    if semantic is None:
        raise RegionInterproceduralLifetimeError(
            "REGION interprocedural planning requires a Phase1CheckedModule semantic snapshot"
        )
    graph = getattr(semantic, "ownership_domains", None)
    if graph is None:
        raise RegionInterproceduralLifetimeError(
            "REGION interprocedural planning lacks canonical ownership graph"
        )

    call_plan = plan_checked_region_calls(checked_module)
    return_plan = plan_checked_region_returns(checked_module)

    checked_sir, _ = build_canonical_checked_ownership_sir(checked_module)
    call_bridge = validate_region_call_sir(call_plan, checked_sir)
    call_cfg = certify_region_call_cfg(call_bridge, checked_sir)

    expected_call_points = {
        (item.function, item.point_id, item.callee)
        for item in call_plan.transfers
    }
    certified_call_points = {
        (item.function, item.point_id, item.callee)
        for item in call_cfg.points
    }
    if expected_call_points != certified_call_points:
        raise RegionInterproceduralLifetimeError(
            "REGION interprocedural call points diverged from CFG certificate"
        )
    if len(certified_call_points) != len(call_cfg.points):
        raise RegionInterproceduralLifetimeError(
            "REGION interprocedural CFG certificate contains duplicate call points"
        )

    function_names = tuple(dict.fromkeys(
        node.function
        for node in graph.nodes
        if node.domain is OwnershipDomain.REGION
    ))

    functions: list[RegionInterproceduralFunctionPlan] = []
    return_transfers = {(item.function, item.binding) for item in return_plan.transfers}
    for function_name in function_names:
        local = plan_checked_region_lifetime(
            checked_module,
            function=function_name,
        )
        origins = plan_checked_ownership_origins(
            checked_module,
            function=function_name,
            domain=OwnershipDomain.REGION,
        )
        lifetime_cfg = certify_region_lifetime_cfg(local, checked_sir.module)
        iteration_order = certify_region_iteration_order(
            call_cfg,
            lifetime_cfg,
            checked_sir,
        )
        if (
            lifetime_cfg.function != function_name
            or iteration_order.function != function_name
            or origins.function != function_name
        ):
            raise RegionInterproceduralLifetimeError(
                f"REGION function certificates diverged for {function_name!r}"
            )

        owner_by_binding = {item.binding: item for item in local.owners}
        if set(origins.bindings) != set(owner_by_binding):
            raise RegionInterproceduralLifetimeError(
                f"REGION owner origins diverged from lifetime owners for {function_name!r}"
            )
        for origin in origins.origins:
            owner = owner_by_binding[origin.binding]
            if origin.type != owner.type or origin.domain is not OwnershipDomain.REGION:
                raise RegionInterproceduralLifetimeError(
                    f"REGION owner origin {function_name}::{origin.binding} diverged from lifetime owner"
                )

        calls = tuple(
            item for item in call_plan.transfers if item.function == function_name
        )
        local_call_facts = sorted(
            (item.source, item.via)
            for item in local.transfers
            if item.via.startswith("call:")
        )
        certified_call_facts = sorted(
            (item.binding, f"call:{item.callee}") for item in calls
        )
        if local_call_facts != certified_call_facts:
            raise RegionInterproceduralLifetimeError(
                f"REGION call lifetime facts diverged for {function_name!r}"
            )

        local_returns = {
            item.source for item in local.transfers if item.via == "return"
        }
        certified_returns = {
            binding
            for owner_function, binding in return_transfers
            if owner_function == function_name
        }
        if local_returns != certified_returns:
            raise RegionInterproceduralLifetimeError(
                f"REGION return lifetime facts diverged for {function_name!r}"
            )

        local_bindings = set(local.bindings)
        for call in calls:
            if call.binding not in local_bindings:
                raise RegionInterproceduralLifetimeError(
                    f"REGION call source {function_name}::{call.binding} lacks local lifetime owner"
                )

        functions.append(
            RegionInterproceduralFunctionPlan(
                function=function_name,
                local=local,
                calls=calls,
                lifetime_cfg=lifetime_cfg,
                iteration_order=iteration_order,
                origins=origins,
            )
        )

    return RegionInterproceduralLifetimePlan(
        functions=tuple(functions),
        returns=return_plan,
        call_cfg=call_cfg,
    )


__all__ = [
    "RegionInterproceduralLifetimeError",
    "RegionInterproceduralFunctionPlan",
    "RegionInterproceduralCallPathSummary",
    "RegionInterproceduralLifetimePlan",
    "plan_checked_region_interprocedural",
]
