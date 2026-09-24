"""Backend-neutral REGION return lifetime contracts.

Function summaries already freeze parameter/return ownership domains and the
canonical ownership graph already records ``via='return'`` transfers.  This
module certifies those two representations agree for REGION returns without
inventing call-site identity or backend behavior.

Interprocedural call transfers are deliberately not certified here: the current
call-transfer facts do not yet carry a source-stable call-site/parameter
identity, so correlating multiple calls by callee name would be ambiguous.
"""
from __future__ import annotations

from dataclasses import dataclass

from .typed_ast import (
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipModuleAnalysis,
    Phase1SemanticError,
    SemanticType,
    TypedModule,
)


class RegionReturnLifetimeError(Phase1SemanticError):
    """Raised when REGION return contracts diverge from canonical ownership."""


@dataclass(frozen=True)
class RegionReturnContract:
    function: str
    type: SemanticType


@dataclass(frozen=True)
class RegionReturnTransfer:
    function: str
    binding: str
    type: SemanticType


@dataclass(frozen=True)
class RegionReturnLifetimePlan:
    contracts: tuple[RegionReturnContract, ...]
    transfers: tuple[RegionReturnTransfer, ...]


def build_region_return_lifetime_plan(
    analysis: OwnershipModuleAnalysis,
    graph: OwnershipDomainGraph,
    typed_module: TypedModule,
) -> RegionReturnLifetimePlan:
    if not isinstance(analysis, OwnershipModuleAnalysis):
        raise RegionReturnLifetimeError(
            "REGION return planning requires canonical ownership analysis"
        )
    if not isinstance(graph, OwnershipDomainGraph):
        raise RegionReturnLifetimeError(
            "REGION return planning requires the canonical ownership domain graph"
        )
    if not isinstance(typed_module, TypedModule):
        raise RegionReturnLifetimeError(
            "REGION return planning requires the canonical TypedModule"
        )

    typed_functions = {item.name: item for item in typed_module.functions}
    summaries = {item.name: item for item in analysis.summaries}
    if len(summaries) != len(analysis.summaries):
        raise RegionReturnLifetimeError("duplicate ownership function summary")

    contracts: list[RegionReturnContract] = []
    contract_by_function: dict[str, RegionReturnContract] = {}
    for summary in analysis.summaries:
        typed_function = typed_functions.get(summary.name)
        if typed_function is None:
            raise RegionReturnLifetimeError(
                f"ownership summary {summary.name!r} lacks a typed function"
            )
        typed_domain = typed_function.return_ownership_domain
        if summary.return_domain is not typed_domain:
            raise RegionReturnLifetimeError(
                f"return domain mismatch for {summary.name!r}"
            )
        if typed_domain is not OwnershipDomain.REGION:
            continue
        contract = RegionReturnContract(
            function=summary.name,
            type=typed_function.result,
        )
        contracts.append(contract)
        contract_by_function[summary.name] = contract

    nodes = {
        (node.function, node.binding): node
        for node in graph.nodes
    }
    transfers: list[RegionReturnTransfer] = []
    seen: set[tuple[str, str]] = set()
    for transfer in graph.transfers:
        if transfer.via != "return":
            continue
        if transfer.domain is not OwnershipDomain.REGION:
            continue
        contract = contract_by_function.get(transfer.function)
        if contract is None:
            raise RegionReturnLifetimeError(
                f"REGION return transfer in {transfer.function!r} lacks a REGION return contract"
            )
        if (
            transfer.source_domain is not OwnershipDomain.REGION
            or transfer.target_domain is not OwnershipDomain.REGION
        ):
            raise RegionReturnLifetimeError(
                f"REGION return transfer {transfer.function}::{transfer.binding} changes domain"
            )
        node = nodes.get((transfer.function, transfer.binding))
        if node is None or node.domain is not OwnershipDomain.REGION:
            raise RegionReturnLifetimeError(
                f"REGION return source {transfer.function}::{transfer.binding} lacks canonical owner node"
            )
        if node.type != contract.type:
            raise RegionReturnLifetimeError(
                f"REGION return type mismatch for {transfer.function}::{transfer.binding}"
            )
        identity = (transfer.function, transfer.binding)
        if identity in seen:
            raise RegionReturnLifetimeError(
                f"duplicate REGION return transfer for {transfer.function}::{transfer.binding}"
            )
        seen.add(identity)
        transfers.append(
            RegionReturnTransfer(
                function=transfer.function,
                binding=transfer.binding,
                type=node.type,
            )
        )

    return RegionReturnLifetimePlan(
        contracts=tuple(contracts),
        transfers=tuple(transfers),
    )


def plan_checked_region_returns(checked_module: object) -> RegionReturnLifetimePlan:
    semantic = getattr(checked_module, "semantic", None)
    if semantic is None:
        raise RegionReturnLifetimeError(
            "REGION return planning requires a Phase1CheckedModule semantic snapshot"
        )
    return build_region_return_lifetime_plan(
        getattr(semantic, "ownership", None),
        getattr(semantic, "ownership_domains", None),
        getattr(semantic, "typed_module", None),
    )


__all__ = [
    "RegionReturnLifetimeError",
    "RegionReturnContract",
    "RegionReturnTransfer",
    "RegionReturnLifetimePlan",
    "build_region_return_lifetime_plan",
    "plan_checked_region_returns",
]
