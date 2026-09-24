"""Phase-1 checked-module entrypoint for DEVICE runtime semantic planning.

This module is the composition boundary from real canonical frontend output to
DEVICE lifecycle/runtime semantics.  It does not parse a second time, rebuild
ownership facts, or inspect source text.  The only accepted source of DEVICE
submission truth is ``Phase1CheckedModule.semantic.ownership_domains``.

The graph-derived lifecycle remains deliberately path-safe: until canonical
CFG path certificates exist, functions with multiple DEVICE submissions fail
closed in ``device_lifecycle`` rather than being grouped speculatively.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .device_lifecycle import DeviceLifecycleSourcePoints
from .device_runtime_semantics import (
    DeviceFrontendRuntimePlan,
    plan_device_runtime_from_graph,
)
from .typed_ast import OwnershipDomainGraph, Phase1SemanticError


class DeviceFrontendPlanError(Phase1SemanticError):
    """Raised when a checked frontend result cannot supply canonical DEVICE facts."""


@dataclass(frozen=True)
class DeviceCheckedRuntimePlan:
    """Runtime semantic plan anchored to one canonical checked-module graph."""

    graph: OwnershipDomainGraph
    runtime: DeviceFrontendRuntimePlan

    @property
    def function(self) -> str:
        return self.runtime.function

    @property
    def queue(self) -> str:
        return self.runtime.queue

    @property
    def bindings(self) -> tuple[str, ...]:
        return self.runtime.bindings

    @property
    def point_ids(self) -> tuple[str, ...]:
        return self.runtime.point_ids


def plan_checked_device_runtime(
    checked_module: Any,
    *,
    function: str,
    queue: str,
    points: DeviceLifecycleSourcePoints,
) -> DeviceCheckedRuntimePlan:
    """Plan DEVICE runtime semantics only from a canonical Phase-1 checked result."""
    semantic = getattr(checked_module, "semantic", None)
    if semantic is None:
        raise DeviceFrontendPlanError(
            "DEVICE frontend planning requires a Phase1CheckedModule semantic snapshot"
        )
    graph = getattr(semantic, "ownership_domains", None)
    if not isinstance(graph, OwnershipDomainGraph):
        raise DeviceFrontendPlanError(
            "DEVICE frontend planning requires canonical ownership-domain graph facts"
        )
    if getattr(checked_module, "ownership_sir", None) is None:
        raise DeviceFrontendPlanError(
            "DEVICE frontend planning requires the canonical ownership SIR bridge"
        )

    runtime = plan_device_runtime_from_graph(
        graph,
        function=function,
        queue=queue,
        points=points,
    )
    if runtime.lifecycle.submissions[0] not in graph.planned_transitions:
        raise DeviceFrontendPlanError(
            "DEVICE frontend runtime plan detached from checked ownership graph"
        )
    return DeviceCheckedRuntimePlan(graph=graph, runtime=runtime)
