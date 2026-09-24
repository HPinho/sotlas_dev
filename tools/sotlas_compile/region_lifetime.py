"""Backend-neutral lifetime topology for REGION ownership.

The canonical ownership graph already proves individual REGION moves, handovers
and call-scoped direct/whisper borrows.  This module collects those facts into a
single function-scoped lifetime plan so later analyses/backends do not have to
reconstruct REGION topology independently.

This is deliberately *not* an arena allocator, runtime lifetime system, or an
interprocedural escape proof.  It preserves and revalidates semantic facts that
already exist in the checked OwnershipDomainGraph.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .typed_ast import (
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipDomainNode,
    OwnershipDomainTransfer,
    Phase1SemanticError,
)


class RegionLifetimeError(Phase1SemanticError):
    """Raised when canonical REGION lifetime facts cease to agree."""


@dataclass(frozen=True)
class RegionLifetimeOwner:
    function: str
    binding: str
    type: Any
    final_state: Any


@dataclass(frozen=True)
class RegionLifetimeTransfer:
    source: str
    destination: str | None
    via: str
    point_id: str | None
    terminal: bool


@dataclass(frozen=True)
class RegionLifetimeBorrow:
    source: str
    mode: str
    callee: str
    parameter: str
    point_id: str
    scope: str = "call"


@dataclass(frozen=True)
class RegionLifetimePlan:
    function: str
    owners: tuple[RegionLifetimeOwner, ...]
    transfers: tuple[RegionLifetimeTransfer, ...]
    borrows: tuple[RegionLifetimeBorrow, ...]

    @property
    def bindings(self) -> tuple[str, ...]:
        return tuple(owner.binding for owner in self.owners)

    @property
    def point_ids(self) -> tuple[str, ...]:
        transfer_points = tuple(
            transfer.point_id
            for transfer in self.transfers
            if transfer.point_id is not None
        )
        return transfer_points + tuple(borrow.point_id for borrow in self.borrows)


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegionLifetimeError(f"{label} requires a non-empty identity")
    return value


def _region_nodes(
    graph: OwnershipDomainGraph,
    function: str,
) -> tuple[OwnershipDomainNode, ...]:
    nodes = tuple(
        node
        for node in graph.nodes
        if node.function == function and node.domain is OwnershipDomain.REGION
    )
    bindings = tuple(node.binding for node in nodes)
    if len(set(bindings)) != len(bindings):
        raise RegionLifetimeError(
            "REGION lifetime graph contains duplicate owner bindings"
        )
    return nodes


def _is_region_transfer(transfer: OwnershipDomainTransfer) -> bool:
    return any(
        domain is OwnershipDomain.REGION
        for domain in (
            transfer.domain,
            transfer.source_domain,
            transfer.target_domain,
            transfer.destination_domain,
        )
    )


def build_region_lifetime_plan(
    graph: OwnershipDomainGraph,
    *,
    function: str,
) -> RegionLifetimePlan:
    """Freeze one function's checked REGION ownership/lifetime topology."""
    if not isinstance(graph, OwnershipDomainGraph):
        raise RegionLifetimeError(
            "REGION lifetime planning requires a canonical OwnershipDomainGraph"
        )
    function_id = _required_text(function, label="REGION lifetime function")
    nodes = _region_nodes(graph, function_id)
    by_binding = {node.binding: node for node in nodes}

    transfers: list[RegionLifetimeTransfer] = []
    borrows: list[RegionLifetimeBorrow] = []
    seen_points: set[str] = set()

    for transfer in graph.transfers:
        if transfer.function != function_id or not _is_region_transfer(transfer):
            continue
        source = _required_text(
            transfer.binding,
            label="REGION lifetime transfer source",
        )
        owner = by_binding.get(source)
        if owner is None:
            raise RegionLifetimeError(
                f"REGION transfer source {source!r} has no REGION owner node"
            )
        if transfer.domain is not OwnershipDomain.REGION:
            raise RegionLifetimeError(
                f"REGION transfer {source!r} lost its canonical domain"
            )
        for label, domain in (
            ("source", transfer.source_domain),
            ("target", transfer.target_domain),
            ("destination", transfer.destination_domain),
        ):
            if domain is not None and domain is not OwnershipDomain.REGION:
                raise RegionLifetimeError(
                    f"REGION transfer {source!r} has non-region {label} domain"
                )

        destination = transfer.destination
        if transfer.via == "handover" and destination is None:
            raise RegionLifetimeError(
                "REGION handover requires an explicit destination binding"
            )
        if destination is not None:
            destination = _required_text(
                destination,
                label="REGION lifetime transfer destination",
            )
            target = by_binding.get(destination)
            if target is None:
                raise RegionLifetimeError(
                    f"REGION transfer destination {destination!r} has no REGION owner node"
                )
            if target.type != owner.type:
                raise RegionLifetimeError(
                    "REGION transfer source/destination types diverged"
                )
            if transfer.destination_domain is not OwnershipDomain.REGION:
                raise RegionLifetimeError(
                    "REGION transfer destination lost REGION domain identity"
                )

        point_id = transfer.point_id
        if point_id is not None:
            point_id = _required_text(
                point_id,
                label="REGION lifetime transfer point",
            )
            if point_id in seen_points:
                raise RegionLifetimeError(
                    f"duplicate REGION lifetime point identity {point_id!r}"
                )
            seen_points.add(point_id)

        transfers.append(
            RegionLifetimeTransfer(
                source=source,
                destination=destination,
                via=_required_text(transfer.via, label="REGION transfer operation"),
                point_id=point_id,
                terminal=destination is None,
            )
        )

    for mode, edges in (
        ("whisper", graph.whisper_borrows),
        ("direct", graph.direct_accesses),
    ):
        for edge in edges:
            if edge.function != function_id or edge.source_domain is not OwnershipDomain.REGION:
                continue
            source = _required_text(edge.source, label=f"REGION {mode} borrow source")
            owner = by_binding.get(source)
            if owner is None:
                raise RegionLifetimeError(
                    f"REGION {mode} borrow source {source!r} has no REGION owner node"
                )
            if edge.type != owner.type:
                raise RegionLifetimeError(
                    f"REGION {mode} borrow source type diverged from owner node"
                )
            point_id = _required_text(
                edge.point_id,
                label=f"REGION {mode} borrow point",
            )
            if point_id in seen_points:
                raise RegionLifetimeError(
                    f"duplicate REGION lifetime point identity {point_id!r}"
                )
            seen_points.add(point_id)
            borrows.append(
                RegionLifetimeBorrow(
                    source=source,
                    mode=mode,
                    callee=_required_text(edge.callee, label=f"REGION {mode} callee"),
                    parameter=_required_text(
                        edge.parameter,
                        label=f"REGION {mode} parameter",
                    ),
                    point_id=point_id,
                )
            )

    return RegionLifetimePlan(
        function=function_id,
        owners=tuple(
            RegionLifetimeOwner(
                function=node.function,
                binding=node.binding,
                type=node.type,
                final_state=node.final_state,
            )
            for node in nodes
        ),
        transfers=tuple(transfers),
        borrows=tuple(borrows),
    )


__all__ = [
    "RegionLifetimeError",
    "RegionLifetimeOwner",
    "RegionLifetimeTransfer",
    "RegionLifetimeBorrow",
    "RegionLifetimePlan",
    "build_region_lifetime_plan",
]
