"""Source-stable interprocedural REGION call-transfer contracts.

Canonical ownership facts encode calls as ``via='call:<callee>'``.  Newer facts
may also carry the exact source ``point_id``; older graph snapshots preserve
only canonical transfer order.  This module derives a stricter backend-neutral
contract by reconciling the parsed AST, Typed AST function signatures, ownership
summaries and the canonical domain graph.  Repeated calls of a re-armed binding
are paired by exact point identity when available, otherwise by the canonical
source order of otherwise-unidentified graph transfers.  It does not change
ownership semantics or backend behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .typed_ast import (
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipModuleAnalysis,
    Phase1SemanticError,
    SemanticType,
    TypedModule,
)


class RegionCallLifetimeError(Phase1SemanticError):
    """Raised when a REGION call transfer lacks one canonical source identity."""


@dataclass(frozen=True)
class RegionCallTransfer:
    function: str
    binding: str
    type: SemanticType
    callee: str
    parameter: str
    argument_index: int
    point_id: str

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return (self.function, self.point_id, self.parameter, self.argument_index)


@dataclass(frozen=True)
class RegionCallLifetimePlan:
    transfers: tuple[RegionCallTransfer, ...]


def _stable_call_point(call: object) -> str:
    token = getattr(call, "token", None)
    line = getattr(token, "line", None)
    column = getattr(token, "column", None)
    if not isinstance(line, int) or line <= 0 or not isinstance(column, int) or column <= 0:
        raise RegionCallLifetimeError("REGION call transfer lacks source-stable call location")
    return f"call@{line}:{column}"


def _walk_calls(value: object) -> Iterable[object]:
    """Yield direct Call nodes in source order without depending on AST classes."""
    stack: list[object] = [value]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current is None or isinstance(current, (str, bytes, int, float, bool)):
            continue
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(current, (list, tuple)):
            stack.extend(reversed(current))
            continue
        if type(current).__name__ == "Call":
            yield current
        children: list[object] = []
        for attr in (
            "value", "args", "condition", "then_body", "else_body", "body",
            "expr", "target", "left", "right", "operand", "index",
        ):
            child = getattr(current, attr, None)
            if child is not None:
                children.append(child)
        stack.extend(reversed(children))


def _select_graph_call_transfer(
    graph: OwnershipDomainGraph,
    graph_call_indices: list[int],
    used_graph_indices: set[int],
    *,
    function: str,
    binding: str,
    callee: str,
    parameter: str,
    point_id: str,
) -> int:
    """Pair one source call with exactly one canonical graph transfer.

    Explicit graph point identities are authoritative.  The source-order
    fallback exists only for legacy call transfers whose point identities are
    all absent; graph tuple order and parsed ``_walk_calls`` order are both
    canonical source order, and every selected graph index is consumed once.
    Mixed identified/unidentified candidates are rejected rather than guessed.
    """
    candidates = [
        index for index in graph_call_indices
        if index not in used_graph_indices
        and graph.transfers[index].function == function
        and graph.transfers[index].binding == binding
        and graph.transfers[index].via == f"call:{callee}"
    ]
    if not candidates:
        raise RegionCallLifetimeError(
            f"REGION call {function}::{binding} -> {callee}.{parameter} "
            "has no canonical graph transfer"
        )

    exact = [
        index for index in candidates
        if getattr(graph.transfers[index], "point_id", None) == point_id
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise RegionCallLifetimeError(
            f"REGION call {function}::{binding} at {point_id} has duplicate "
            "point-identified graph transfers"
        )

    identities = tuple(
        getattr(graph.transfers[index], "point_id", None) for index in candidates
    )
    if any(identity is not None for identity in identities):
        raise RegionCallLifetimeError(
            f"REGION call {function}::{binding} at {point_id} diverges from "
            "source-stable graph transfer identity"
        )

    # Legacy graph transfers without point ids are emitted in canonical source
    # order.  Consume the earliest remaining occurrence; later repeated calls
    # necessarily receive the next occurrence because indices cannot be reused.
    return candidates[0]


def build_region_call_lifetime_plan(
    analysis: OwnershipModuleAnalysis,
    graph: OwnershipDomainGraph,
    typed_module: TypedModule,
    parsed_module: object,
) -> RegionCallLifetimePlan:
    if not isinstance(analysis, OwnershipModuleAnalysis):
        raise RegionCallLifetimeError(
            "REGION call planning requires canonical ownership analysis"
        )
    if not isinstance(graph, OwnershipDomainGraph):
        raise RegionCallLifetimeError(
            "REGION call planning requires the canonical ownership domain graph"
        )
    if not isinstance(typed_module, TypedModule):
        raise RegionCallLifetimeError(
            "REGION call planning requires the canonical TypedModule"
        )

    typed_functions = {item.name: item for item in typed_module.functions}
    summaries = {item.name: item for item in analysis.summaries}
    if len(summaries) != len(analysis.summaries):
        raise RegionCallLifetimeError("duplicate ownership function summary")
    nodes = {(item.function, item.binding): item for item in graph.nodes}

    graph_call_indices = [
        index for index, transfer in enumerate(graph.transfers)
        if transfer.domain is OwnershipDomain.REGION
        and transfer.via.startswith("call:")
    ]
    used_graph_indices: set[int] = set()
    transfers: list[RegionCallTransfer] = []
    seen_identities: set[tuple[str, str, str, int]] = set()

    for parsed_function in getattr(parsed_module, "functions", ()):
        function_name = getattr(parsed_function, "name", None)
        if function_name not in typed_functions:
            continue
        for call in _walk_calls(getattr(parsed_function, "body", ())):
            callee_name = getattr(call, "callee", None)
            callee = typed_functions.get(callee_name)
            callee_summary = summaries.get(callee_name)
            if callee is None or callee_summary is None:
                continue
            arguments = tuple(getattr(call, "args", ()) or ())
            if len(arguments) != len(callee.params):
                raise RegionCallLifetimeError(
                    f"call {function_name}->{callee_name} argument count diverges from Typed AST"
                )
            if len(callee_summary.params) != len(callee.params):
                raise RegionCallLifetimeError(
                    f"ownership summary for {callee_name!r} diverges from Typed AST parameters"
                )
            point_id = _stable_call_point(call)

            for argument_index, (argument, parameter, contract) in enumerate(
                zip(arguments, callee.params, callee_summary.params, strict=True)
            ):
                if parameter.name != contract.name or parameter.ownership_domain is not contract.domain:
                    raise RegionCallLifetimeError(
                        f"parameter ownership contract mismatch for {callee_name}.{parameter.name}"
                    )
                if parameter.ownership_domain is not OwnershipDomain.REGION:
                    continue
                if not contract.takes_ownership:
                    raise RegionCallLifetimeError(
                        f"REGION parameter {callee_name}.{parameter.name} is not ownership-taking"
                    )
                moved = getattr(argument, "value", None)
                if type(argument).__name__ != "MoveExpr" or type(moved).__name__ != "Name":
                    raise RegionCallLifetimeError(
                        f"REGION parameter {callee_name}.{parameter.name} requires move at {point_id}"
                    )
                binding = getattr(moved, "value", None)
                if not isinstance(binding, str) or not binding:
                    raise RegionCallLifetimeError(
                        f"REGION call argument at {point_id} lacks a direct source binding"
                    )
                owner = nodes.get((function_name, binding))
                if owner is None or owner.domain is not OwnershipDomain.REGION:
                    raise RegionCallLifetimeError(
                        f"REGION call source {function_name}::{binding} lacks canonical owner node"
                    )
                if owner.type != parameter.type:
                    raise RegionCallLifetimeError(
                        f"REGION call type mismatch for {function_name}::{binding} -> {callee_name}.{parameter.name}"
                    )

                graph_index = _select_graph_call_transfer(
                    graph,
                    graph_call_indices,
                    used_graph_indices,
                    function=function_name,
                    binding=binding,
                    callee=callee_name,
                    parameter=parameter.name,
                    point_id=point_id,
                )
                graph_transfer = graph.transfers[graph_index]
                if (
                    graph_transfer.source_domain is not OwnershipDomain.REGION
                    or graph_transfer.target_domain is not OwnershipDomain.REGION
                    or graph_transfer.destination is not None
                ):
                    raise RegionCallLifetimeError(
                        f"REGION call transfer {function_name}::{binding} changes domain or destination"
                    )
                used_graph_indices.add(graph_index)
                item = RegionCallTransfer(
                    function=function_name,
                    binding=binding,
                    type=owner.type,
                    callee=callee_name,
                    parameter=parameter.name,
                    argument_index=argument_index,
                    point_id=point_id,
                )
                if item.identity in seen_identities:
                    raise RegionCallLifetimeError(
                        f"duplicate REGION call identity {item.identity!r}"
                    )
                seen_identities.add(item.identity)
                transfers.append(item)

    unmatched = [index for index in graph_call_indices if index not in used_graph_indices]
    if unmatched:
        transfer = graph.transfers[unmatched[0]]
        raise RegionCallLifetimeError(
            f"REGION graph transfer {transfer.function}::{transfer.binding} via {transfer.via} "
            "has no source-stable call-site/parameter identity"
        )

    return RegionCallLifetimePlan(tuple(transfers))


def plan_checked_region_calls(checked_module: object) -> RegionCallLifetimePlan:
    semantic = getattr(checked_module, "semantic", None)
    parsed_module = getattr(checked_module, "parsed_module", None)
    if semantic is None or parsed_module is None:
        raise RegionCallLifetimeError(
            "REGION call planning requires a Phase1CheckedModule with parsed and semantic snapshots"
        )
    return build_region_call_lifetime_plan(
        getattr(semantic, "ownership", None),
        getattr(semantic, "ownership_domains", None),
        getattr(semantic, "typed_module", None),
        parsed_module,
    )


__all__ = [
    "RegionCallLifetimeError",
    "RegionCallTransfer",
    "RegionCallLifetimePlan",
    "build_region_call_lifetime_plan",
    "plan_checked_region_calls",
]
