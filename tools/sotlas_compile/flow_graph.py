"""Canonical dependency graphs for Sotlas Flow.

This backend-neutral layer certifies a finite acyclic computation graph and
derives deterministic parallel stages. It does not schedule work or infer
source expressions yet.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .typed_ast import Phase1SemanticError


class FlowGraphError(Phase1SemanticError):
    """Raised when a Flow dependency graph is malformed or cyclic."""


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class FlowNode:
    name: str


@dataclass(frozen=True)
class FlowDependency:
    producer: str
    consumer: str


@dataclass(frozen=True)
class FlowGraphPlan:
    nodes: tuple[FlowNode, ...]
    dependencies: tuple[FlowDependency, ...]
    parallel_stages: tuple[tuple[str, ...], ...]

    def node(self, name: str) -> FlowNode:
        matches = tuple(item for item in self.nodes if item.name == name)
        if len(matches) != 1:
            raise FlowGraphError(
                f"Flow graph requires exactly one node named {name!r}"
            )
        return matches[0]


def certify_flow_graph(
    nodes: tuple[FlowNode, ...],
    dependencies: tuple[FlowDependency, ...],
) -> FlowGraphPlan:
    """Validate a source-ordered DAG and compute stable ready-node stages."""
    if not isinstance(nodes, tuple) or not nodes:
        raise FlowGraphError("Flow graph requires a non-empty tuple of nodes")
    if not isinstance(dependencies, tuple):
        raise FlowGraphError("Flow dependencies must be provided as a tuple")

    order: dict[str, int] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, FlowNode):
            raise FlowGraphError("Flow graph contains an invalid node")
        if not isinstance(node.name, str) or not _IDENTIFIER.fullmatch(node.name):
            raise FlowGraphError("Flow node name must be a Sotlas identifier")
        if node.name in order:
            raise FlowGraphError(f"Flow graph repeats node {node.name!r}")
        order[node.name] = index

    seen_edges: set[tuple[str, str]] = set()
    indegree = dict.fromkeys(order, 0)
    successors: dict[str, list[str]] = {name: [] for name in order}
    checked: list[FlowDependency] = []
    for edge in dependencies:
        if not isinstance(edge, FlowDependency):
            raise FlowGraphError("Flow graph contains an invalid dependency")
        if edge.producer not in order:
            raise FlowGraphError(
                f"Flow dependency references unknown producer {edge.producer!r}"
            )
        if edge.consumer not in order:
            raise FlowGraphError(
                f"Flow dependency references unknown consumer {edge.consumer!r}"
            )
        key = (edge.producer, edge.consumer)
        if key in seen_edges:
            raise FlowGraphError(
                f"Flow graph repeats dependency {edge.producer} -> {edge.consumer}"
            )
        seen_edges.add(key)
        checked.append(edge)
        successors[edge.producer].append(edge.consumer)
        indegree[edge.consumer] += 1

    stages: list[tuple[str, ...]] = []
    remaining = set(order)
    while remaining:
        ready = tuple(
            name for name in order if name in remaining and indegree[name] == 0
        )
        if not ready:
            cycle_nodes = tuple(name for name in order if name in remaining)
            raise FlowGraphError(
                "Flow dependency graph contains a cycle involving: "
                + ", ".join(cycle_nodes)
            )
        stages.append(ready)
        for name in ready:
            remaining.remove(name)
            for consumer in successors[name]:
                indegree[consumer] -= 1

    return FlowGraphPlan(
        nodes=nodes,
        dependencies=tuple(checked),
        parallel_stages=tuple(stages),
    )


__all__ = [
    "FlowGraphError",
    "FlowNode",
    "FlowDependency",
    "FlowGraphPlan",
    "certify_flow_graph",
]
