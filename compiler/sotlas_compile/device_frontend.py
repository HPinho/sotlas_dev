"""Phase-1 checked-module entrypoint for DEVICE runtime semantic planning.

This module is the composition boundary from real canonical frontend output to
DEVICE lifecycle/runtime semantics.  It does not parse a second time, rebuild
ownership facts, or inspect source text.  The only accepted source of DEVICE
submission truth is ``Phase1CheckedModule.semantic.ownership_domains``.

For one DEVICE submission the canonical graph is sufficient.  When a function
contains several submissions, this checked-module entrypoint asks the already-
placed SIR CFG for an ordered acyclic co-execution certificate.  Alternative
branches and cyclic multi-submission paths therefore remain fail-closed rather
than being grouped speculatively.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .device_coexecution import (
    DeviceCoexecutionError,
    certify_device_submission_coexecution,
)
from .device_lifecycle import DeviceLifecycleSourcePoints
from .device_runtime_semantics import (
    DeviceFrontendRuntimePlan,
    plan_device_runtime_from_graph,
)
from .typed_ast import (
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipDomainTransition,
    Phase1SemanticError,
)


class DeviceFrontendPlanError(Phase1SemanticError):
    """Raised when a checked frontend result cannot supply canonical DEVICE facts."""


@dataclass(frozen=True)
class DeviceCheckedRuntimePlan:
    """Runtime semantic plan anchored to one canonical checked-module graph."""

    graph: OwnershipDomainGraph
    runtime: DeviceFrontendRuntimePlan
    coexecution_certificate: object | None = None

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


def _device_submissions(
    graph: OwnershipDomainGraph,
    *,
    function: str,
) -> tuple[OwnershipDomainTransition, ...]:
    return tuple(
        transition
        for transition in graph.planned_transitions
        if isinstance(transition, OwnershipDomainTransition)
        and transition.function == function
        and transition.source is OwnershipDomain.EXCLUSIVE
        and transition.target is OwnershipDomain.DEVICE
        and transition.operation == "handover"
    )


def _certify_checked_coexecution(
    checked_module: Any,
    *,
    function: str,
    submissions: tuple[OwnershipDomainTransition, ...],
) -> object | None:
    if len(submissions) <= 1:
        return None
    points = tuple(transition.point_id for transition in submissions)
    if any(not isinstance(point, str) or not point.strip() for point in points):
        raise DeviceFrontendPlanError(
            "DEVICE checked submissions require source-stable point identities"
        )
    try:
        # SIR generation may come from the installed compiler package or from
        # the legacy tooling mirror already present in sys.modules.  The
        # coexecution proof itself is deliberately package-neutral, so class
        # identity from either tree cannot change semantic acceptance.
        from sotlas.sir import generate_checked_ownership_sir
    except ImportError as error:
        raise DeviceFrontendPlanError(
            "DEVICE multi-owner frontend planning requires canonical SIR generation"
        ) from error

    try:
        checked_sir = generate_checked_ownership_sir(checked_module)
        return certify_device_submission_coexecution(
            checked_sir.module,
            function=function,
            point_ids=points,  # type: ignore[arg-type]
        )
    except DeviceCoexecutionError as error:
        raise DeviceFrontendPlanError(
            f"DEVICE frontend cannot prove submission co-execution: {error}"
        ) from error
    except ValueError as error:
        # SIR generation/placement failure is not evidence of coexecution.
        # Preserve fail-closed behavior while surfacing the real boundary.
        raise DeviceFrontendPlanError(
            f"DEVICE frontend cannot prove submission co-execution: {error}"
        ) from error


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

    submissions = _device_submissions(graph, function=function)
    certificate = _certify_checked_coexecution(
        checked_module,
        function=function,
        submissions=submissions,
    )
    runtime = plan_device_runtime_from_graph(
        graph,
        function=function,
        queue=queue,
        points=points,
        coexecution_certificate=certificate,
    )
    if any(
        transition not in graph.planned_transitions
        for transition in runtime.lifecycle.submissions
    ):
        raise DeviceFrontendPlanError(
            "DEVICE frontend runtime plan detached from checked ownership graph"
        )
    if len(runtime.lifecycle.submissions) > 1 and certificate is None:
        raise DeviceFrontendPlanError(
            "DEVICE multi-owner runtime plan escaped co-execution certification"
        )
    return DeviceCheckedRuntimePlan(
        graph=graph,
        runtime=runtime,
        coexecution_certificate=certificate,
    )
