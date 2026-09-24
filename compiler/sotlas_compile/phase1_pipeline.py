"""Opt-in canonical Phase-1 semantic pipeline.

This module composes the production bootstrap parser/checker with the isolated
Phase-1 Typed AST and ownership passes. It is explicit by design: importing the
package does not change bootstrap.check and callers must opt in to this API.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from . import bootstrap
from .typed_ast import (
    OwnershipDomainTransition,
    Phase1ModuleSnapshot,
    Phase1SemanticError,
    VarState,
    build_phase1_semantic_snapshot,
)


@dataclass(frozen=True)
class Phase1CheckedModule:
    parsed_module: object
    semantic: Phase1ModuleSnapshot
    ownership_sir: object


def _restore_checked_handover_transitions(
    semantic: Phase1ModuleSnapshot,
) -> Phase1ModuleSnapshot:
    """Preserve every validated explicit handover as a planned transition.

    ``build_ownership_domain_graph`` already validates explicit handover edges
    and stores them in ``graph.transfers``.  A regression left those same facts
    out of ``planned_transitions`` even though downstream DEVICE lifecycle
    planning consumes that canonical transition collection.  Reconcile the two
    representations at the public checked-module boundary without inventing
    source facts or weakening the graph validators.

    This bridge is deliberately idempotent so the Typed-AST graph builder can
    later restore the transition directly without changing this public API.
    """
    graph = semantic.ownership_domains
    planned = list(graph.planned_transitions)
    nodes = {
        (node.function, node.binding): node
        for node in graph.nodes
    }
    existing_by_point = {
        (transition.function, transition.point_id): transition
        for transition in planned
        if transition.function is not None and transition.point_id is not None
    }

    for transfer in graph.transfers:
        if transfer.via != "handover" or transfer.destination is None:
            continue
        point_id = transfer.point_id
        if not isinstance(point_id, str) or not point_id.startswith("handover@"):
            raise Phase1SemanticError(
                f"checked handover {transfer.function}::{transfer.binding} "
                "lacks canonical source identity"
            )
        source_domain = transfer.source_domain
        target_domain = transfer.target_domain
        destination_domain = transfer.destination_domain
        if (
            source_domain is None
            or target_domain is None
            or destination_domain is not target_domain
        ):
            raise Phase1SemanticError(
                f"checked handover {transfer.function}::{transfer.binding} "
                "has incomplete domain facts"
            )

        source_node = nodes.get((transfer.function, transfer.binding))
        destination_node = nodes.get((transfer.function, transfer.destination))
        if source_node is None or destination_node is None:
            raise Phase1SemanticError(
                f"checked handover {transfer.function}::{transfer.binding} "
                "is detached from ownership-domain nodes"
            )
        if (
            source_node.domain is not source_domain
            or destination_node.domain is not destination_domain
            or source_node.type != destination_node.type
        ):
            raise Phase1SemanticError(
                f"checked handover {transfer.function}::{transfer.binding} "
                "does not match canonical node facts"
            )

        transition = OwnershipDomainTransition(
            binding=transfer.binding,
            type=source_node.type,
            source=source_domain,
            target=target_domain,
            source_state=VarState.LIVE,
            operation="handover",
            function=transfer.function,
            point_id=point_id,
        )
        identity = (transfer.function, point_id)
        existing = existing_by_point.get(identity)
        if existing is not None:
            if (
                existing.binding != transition.binding
                or existing.type != transition.type
                or existing.source is not transition.source
                or existing.target is not transition.target
                or existing.source_state is not VarState.LIVE
                or existing.operation != "handover"
            ):
                raise Phase1SemanticError(
                    f"checked handover point {point_id!r} conflicts with an "
                    "existing planned transition"
                )
            continue

        planned.append(transition)
        existing_by_point[identity] = transition

    if tuple(planned) == graph.planned_transitions:
        return semantic
    return replace(
        semantic,
        ownership_domains=replace(
            graph,
            planned_transitions=tuple(planned),
        ),
    )


def analyze_module_phase1(parsed_module) -> Phase1CheckedModule:
    """Run the canonical checker, semantic snapshot, and ownership SIR bridge."""
    try:
        bootstrap.check(parsed_module)
    except bootstrap.SotlasBootstrapError as error:
        # The production checker now runs the shared whisper escape validator.
        # Keep Phase-1 callers' semantic error type stable while preserving the
        # production diagnostic for the CLI and direct bootstrap API.
        if "whisper" in error.message:
            raise Phase1SemanticError(error.message) from error
        raise
    semantic = _restore_checked_handover_transitions(
        build_phase1_semantic_snapshot(parsed_module)
    )

    # Keep the Typed AST package independent from SIR imports. The public
    # pipeline is the composition boundary between canonical semantic facts
    # and the backend-neutral intermediate representation.
    from sotlas.sir import lower_ownership_module_semantics

    ownership_sir = lower_ownership_module_semantics(
        semantic.ownership,
        semantic.ownership_domains,
    )
    return Phase1CheckedModule(
        parsed_module=parsed_module,
        semantic=semantic,
        ownership_sir=ownership_sir,
    )


def analyze_source_phase1(
    source: str, filename: str | None = None
) -> Phase1CheckedModule:
    """Parse source through the canonical frontend and run opt-in Phase 1."""
    parsed_module = bootstrap.parse(source, filename=filename)
    return analyze_module_phase1(parsed_module)


__all__ = [
    "Phase1CheckedModule",
    "analyze_module_phase1",
    "analyze_source_phase1",
]
