"""Frontend-facing DEVICE lifecycle planning from the canonical ownership graph.

This module closes the semantic gap between the ownership-domain graph produced
by the frontend and the existing DEVICE completion/synchronization machinery.
It derives an EXCLUSIVE -> DEVICE submission directly from
``OwnershipDomainGraph``; callers no longer reconstruct submission transitions
or completion tokens manually.

Important path-safety rule: the current canonical graph records source-stable
transitions but does not yet carry enough CFG path identity to prove that two
DEVICE submissions in the same function co-execute.  Therefore this graph-
derived frontend entrypoint accepts exactly one canonical submission per
function and fails closed when several exist.  Multi-owner synchronization
remains supported by the lower semantic APIs, and this restriction can be
lifted only when a path-sensitive co-execution certificate is available.

The caller still supplies source-stable point identities for completion,
synchronization and reacquisition because those are distinct semantic events.
No runtime symbol is called, no queue is touched and no hardware work is
performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .device_ownership import (
    DeviceCompletionToken,
    DeviceTransferState,
    complete_device_transfer,
    open_device_completion,
)
from .device_sync import (
    DeviceSyncFence,
    DeviceSyncReacquisition,
    DeviceSyncResult,
    consume_device_sync,
    plan_device_sync,
    plan_synced_reacquisitions,
)
from .typed_ast import (
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipDomainTransition,
    Phase1SemanticError,
    VarState,
)


class DeviceLifecycleError(Phase1SemanticError):
    """Raised when canonical graph facts cannot form one DEVICE lifecycle."""


@dataclass(frozen=True)
class DeviceLifecycleSourcePoints:
    """Source-stable identities for post-submission DEVICE lifecycle events."""

    completion_point_ids: tuple[str, ...]
    synchronization_point_id: str
    reacquisition_point_ids: tuple[str, ...]


@dataclass(frozen=True)
class DeviceLifecycleSemanticPlan:
    """Complete semantic DEVICE lifecycle derived from canonical graph facts."""

    function: str
    queue: str
    submissions: tuple[OwnershipDomainTransition, ...]
    completed_tokens: tuple[DeviceCompletionToken, ...]
    fence: DeviceSyncFence
    reacquisition: DeviceSyncReacquisition
    result: DeviceSyncResult

    @property
    def bindings(self) -> tuple[str, ...]:
        return tuple(transition.binding for transition in self.submissions)

    @property
    def submission_point_ids(self) -> tuple[str, ...]:
        return tuple(
            transition.point_id  # type: ignore[misc]
            for transition in self.submissions
        )

    @property
    def completion_point_ids(self) -> tuple[str, ...]:
        return tuple(
            token.completion_point_id  # type: ignore[misc]
            for token in self.completed_tokens
        )

    @property
    def reacquisition_point_ids(self) -> tuple[str, ...]:
        return tuple(
            plan.reacquisition_point_id for plan in self.reacquisition.plans
        )

    @property
    def point_ids(self) -> tuple[str, ...]:
        return (
            self.submission_point_ids
            + self.completion_point_ids
            + (self.fence.sync_point_id,)
            + self.reacquisition_point_ids
        )


def _required_text(value: str | None, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceLifecycleError(f"{label} requires a non-empty identity")
    return value


def _materialize_points(values: Iterable[str], *, label: str) -> tuple[str, ...]:
    points = tuple(values)
    return tuple(_required_text(point, label=label) for point in points)


def _canonical_submissions(
    graph: OwnershipDomainGraph,
    *,
    function: str,
) -> tuple[OwnershipDomainTransition, ...]:
    submissions = tuple(
        transition
        for transition in graph.planned_transitions
        if isinstance(transition, OwnershipDomainTransition)
        and transition.function == function
        and transition.source is OwnershipDomain.EXCLUSIVE
        and transition.target is OwnershipDomain.DEVICE
        and transition.operation == "handover"
    )
    if not submissions:
        raise DeviceLifecycleError(
            f"DEVICE lifecycle has no canonical EXCLUSIVE -> DEVICE submission "
            f"for function {function!r}"
        )

    bindings: set[str] = set()
    point_ids: set[str] = set()
    for transition in submissions:
        binding = _required_text(
            transition.binding, label="DEVICE submission binding"
        )
        if binding in bindings:
            raise DeviceLifecycleError(
                f"DEVICE lifecycle has duplicate submission binding {binding!r}"
            )
        bindings.add(binding)

        if transition.source_state is not VarState.LIVE:
            raise DeviceLifecycleError(
                f"DEVICE submission for {function}::{binding} must originate LIVE"
            )
        point_id = _required_text(
            transition.point_id, label="DEVICE submission point"
        )
        if point_id in point_ids:
            raise DeviceLifecycleError(
                f"DEVICE lifecycle has duplicate submission point {point_id!r}"
            )
        point_ids.add(point_id)

    if len(submissions) != 1:
        raise DeviceLifecycleError(
            "DEVICE graph-derived lifecycle requires path-sensitive co-execution "
            "proof when a function contains multiple canonical submissions"
        )
    return submissions


def plan_device_lifecycle_from_graph(
    graph: OwnershipDomainGraph,
    *,
    function: str,
    queue: str,
    points: DeviceLifecycleSourcePoints,
) -> DeviceLifecycleSemanticPlan:
    """Derive and close one path-unambiguous DEVICE lifecycle from graph facts."""
    if not isinstance(graph, OwnershipDomainGraph):
        raise DeviceLifecycleError(
            "DEVICE lifecycle requires a canonical OwnershipDomainGraph"
        )
    if not isinstance(points, DeviceLifecycleSourcePoints):
        raise DeviceLifecycleError(
            "DEVICE lifecycle requires explicit source-stable lifecycle points"
        )

    function_id = _required_text(function, label="DEVICE lifecycle function")
    queue_id = _required_text(queue, label="DEVICE lifecycle queue")
    submissions = _canonical_submissions(graph, function=function_id)
    owner_count = len(submissions)

    completion_points = _materialize_points(
        points.completion_point_ids,
        label="DEVICE completion point",
    )
    reacquisition_points = _materialize_points(
        points.reacquisition_point_ids,
        label="DEVICE reacquisition point",
    )
    sync_point = _required_text(
        points.synchronization_point_id,
        label="DEVICE synchronization point",
    )
    if len(completion_points) != owner_count:
        raise DeviceLifecycleError(
            "DEVICE lifecycle requires one completion point per canonical submission"
        )
    if len(reacquisition_points) != owner_count:
        raise DeviceLifecycleError(
            "DEVICE lifecycle requires one reacquisition point per canonical submission"
        )

    submission_points = tuple(
        _required_text(item.point_id, label="DEVICE submission point")
        for item in submissions
    )
    lifecycle_points = (
        submission_points
        + completion_points
        + (sync_point,)
        + reacquisition_points
    )
    if len(set(lifecycle_points)) != len(lifecycle_points):
        raise DeviceLifecycleError(
            "DEVICE lifecycle point identities must be globally unique"
        )

    completed: list[DeviceCompletionToken] = []
    for transition, completion_point in zip(
        submissions, completion_points, strict=True
    ):
        token = open_device_completion(
            graph,
            function=function_id,
            binding=transition.binding,
        )
        if token.submission_point_id != transition.point_id:
            raise DeviceLifecycleError(
                "DEVICE completion token lost canonical submission identity"
            )
        completed.append(
            complete_device_transfer(token, point_id=completion_point)
        )
    completed_tokens = tuple(completed)

    fence = plan_device_sync(
        completed_tokens,
        function=function_id,
        queue=queue_id,
        point_id=sync_point,
    )
    reacquisition = plan_synced_reacquisitions(
        completed_tokens,
        fence,
        point_ids=reacquisition_points,
    )
    result = consume_device_sync(completed_tokens, reacquisition)

    if tuple(token.binding for token in completed_tokens) != tuple(
        transition.binding for transition in submissions
    ):
        raise DeviceLifecycleError(
            "DEVICE lifecycle changed canonical submission binding order"
        )
    if any(
        token.state is not DeviceTransferState.REACQUIRED
        for token in result.tokens
    ):
        raise DeviceLifecycleError(
            "DEVICE lifecycle failed to close every synchronized owner"
        )
    if tuple(token.binding for token in result.tokens) != tuple(
        transition.binding for transition in submissions
    ):
        raise DeviceLifecycleError(
            "DEVICE lifecycle reacquisition changed canonical binding order"
        )

    plan = DeviceLifecycleSemanticPlan(
        function=function_id,
        queue=queue_id,
        submissions=submissions,
        completed_tokens=completed_tokens,
        fence=fence,
        reacquisition=reacquisition,
        result=result,
    )
    if plan.point_ids != lifecycle_points:
        raise DeviceLifecycleError(
            "DEVICE lifecycle changed source-stable point ordering"
        )
    return plan
