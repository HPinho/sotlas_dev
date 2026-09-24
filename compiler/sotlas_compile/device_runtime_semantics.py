"""Frontend semantic bridge from canonical DEVICE graph facts to runtime DAG.

This module composes ``device_lifecycle`` with ``device_runtime_abi`` so callers
can derive the full backend-neutral runtime obligation graph directly from the
canonical ownership graph.  It performs no ABI symbol binding and no backend
execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .device_lifecycle import (
    DeviceLifecycleSemanticPlan,
    DeviceLifecycleSourcePoints,
    plan_device_lifecycle_from_graph,
)
from .device_runtime_abi import (
    DeviceRuntimeOperation,
    DeviceRuntimeRequirementPlan,
    plan_device_runtime_requirements,
)
from .typed_ast import OwnershipDomainGraph, Phase1SemanticError


class DeviceRuntimeSemanticError(Phase1SemanticError):
    """Raised when frontend DEVICE proof and runtime DAG cease to be identical."""


@dataclass(frozen=True)
class DeviceFrontendRuntimePlan:
    """Canonical frontend lifecycle plus its exact backend-neutral runtime DAG."""

    lifecycle: DeviceLifecycleSemanticPlan
    runtime: DeviceRuntimeRequirementPlan

    @property
    def function(self) -> str:
        return self.lifecycle.function

    @property
    def queue(self) -> str:
        return self.lifecycle.queue

    @property
    def point_ids(self) -> tuple[str, ...]:
        return self.lifecycle.point_ids

    @property
    def bindings(self) -> tuple[str, ...]:
        return self.lifecycle.bindings


def plan_device_runtime_from_graph(
    graph: OwnershipDomainGraph,
    *,
    function: str,
    queue: str,
    points: DeviceLifecycleSourcePoints,
    coexecution_certificate: Any = None,
) -> DeviceFrontendRuntimePlan:
    """Derive one exact runtime DAG from frontend canonical ownership facts."""
    lifecycle = plan_device_lifecycle_from_graph(
        graph,
        function=function,
        queue=queue,
        points=points,
        coexecution_certificate=coexecution_certificate,
    )
    runtime = plan_device_runtime_requirements(
        lifecycle.completed_tokens,
        lifecycle.reacquisition,
    )

    if runtime.function != lifecycle.function:
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime DAG changed frontend function identity"
        )
    if runtime.queue != lifecycle.queue:
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime DAG changed frontend queue identity"
        )
    if runtime.point_ids != lifecycle.point_ids:
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime DAG changed source-stable lifecycle point order"
        )

    submissions = runtime.requirements_for(DeviceRuntimeOperation.SUBMIT)
    completions = runtime.requirements_for(DeviceRuntimeOperation.COMPLETE)
    synchronizations = runtime.requirements_for(DeviceRuntimeOperation.SYNCHRONIZE)
    reacquisitions = runtime.requirements_for(DeviceRuntimeOperation.REACQUIRE)
    owner_count = len(lifecycle.submissions)
    if (
        len(submissions) != owner_count
        or len(completions) != owner_count
        or len(reacquisitions) != owner_count
        or len(synchronizations) != 1
    ):
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime DAG changed canonical lifecycle cardinality"
        )

    expected_bindings = lifecycle.bindings
    if tuple(item.binding for item in submissions) != expected_bindings:
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime submissions changed canonical binding order"
        )
    if tuple(item.binding for item in completions) != expected_bindings:
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime completions changed canonical binding order"
        )
    if tuple(item.binding for item in reacquisitions) != expected_bindings:
        raise DeviceRuntimeSemanticError(
            "DEVICE runtime reacquisitions changed canonical binding order"
        )
    if synchronizations[0].binding is not None:
        raise DeviceRuntimeSemanticError(
            "DEVICE synchronization runtime requirement must remain batch-wide"
        )

    return DeviceFrontendRuntimePlan(lifecycle=lifecycle, runtime=runtime)
