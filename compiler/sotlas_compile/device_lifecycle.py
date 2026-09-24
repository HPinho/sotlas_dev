"""Frontend-facing DEVICE lifecycle planning from the canonical ownership graph.

This module closes the semantic gap between the ownership-domain graph produced
by the frontend and the existing DEVICE completion/synchronization machinery.
It derives EXCLUSIVE -> DEVICE submissions directly from
``OwnershipDomainGraph``; callers no longer reconstruct submission transitions
or completion tokens manually.

Important path-safety rule: the canonical graph itself does not prove that two
DEVICE submissions in one function co-execute.  A single submission therefore
needs no extra proof, while multiple submissions require a source-stable SIR
co-execution certificate whose function, points and bindings match the graph
exactly.  The certificate is consumed structurally here so the semantic package
remains independent from SIR imports.

The caller still supplies source-stable point identities for completion,
synchronization and reacquisition because those are distinct semantic events.
No runtime symbol is called, no queue is touched and no hardware work is
performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

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


def _validate_coexecution_certificate(
    certificate: Any,
    *,
    function: str,
    submissions: tuple[OwnershipDomainTransition, ...],
) -> None:
    if certificate is None:
        raise DeviceLifecycleError(
            "DEVICE graph-derived lifecycle requires path-sensitive co-execution "
            "proof when a function contains multiple canonical submissions"
        )
    expected_points = tuple(
        _required_text(item.point_id, label="DEVICE submission point")
        for item in submissions
    )
    expected_bindings = tuple(item.binding for item in submissions)
    if getattr(certificate, "function", None) != function:
        raise DeviceLifecycleError(
            "DEVICE co-execution certificate crosses function identity"
        )
    if tuple(getattr(certificate, "point_ids", ()) or ()) != expected_points:
        raise DeviceLifecycleError(
            "DEVICE co-execution certificate point set/order diverges from graph"
        )
    if tuple(getattr(certificate, "bindings", ()) or ()) != expected_bindings:
        raise DeviceLifecycleError(
            "DEVICE co-execution certificate binding order diverges from graph"
        )
    if getattr(certificate, "acyclic", None) is not True:
        raise DeviceLifecycleError(
            "DEVICE multi-submission lifecycle requires an acyclic co-execution certificate"
        )
    locations = tuple(getattr(certificate, "locations", ()) or ())
    if len(locations) != len(submissions):
        raise DeviceLifecycleError(
            "DEVICE co-execution certificate lost submission locations"
        )
    for index, location in enumerate(locations):
        if getattr(location, "point_id", None) != expected_points[index]:
            raise DeviceLifecycleError(
                "DEVICE co-execution certificate location point diverges from graph"
            )
        if getattr(location, "binding", None) != expected_bindings[index]:
            raise DeviceLifecycleError(
                "DEVICE co-execution certificate location binding diverges from graph"
            )
        _required_text(
            getattr(location, "block", None),
            label="DEVICE co-execution block",
        )
        instruction_index = getattr(location, "instruction_index", None)
        if (
            not isinstance(instruction_index, int)
            or isinstance(instruction_index, bool)
            or instruction_index < 0
        ):
            raise DeviceLifecycleError(
                "DEVICE co-execution certificate has invalid instruction location"
            )
    block_path = tuple(getattr(certificate, "block_path", ()) or ())
    if not block_path:
        raise DeviceLifecycleError(
            "DEVICE co-execution certificate requires a non-empty block path"
        )
    for block in block_path:
        _required_text(block, label="DEVICE co-execution path block")


def _canonical_submissions(
    graph: OwnershipDomainGraph,
    *,
    function: str,
    coexecution_certificate: Any = None,
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

    if len(submissions) > 1:
        _validate_coexecution_certificate(
            coexecution_certificate,
            function=function,
            submissions=submissions,
        )
    elif coexecution_certificate is not None:
        # A certificate for one owner is allowed only if it refers exactly to it.
        _validate_coexecution_certificate(
            coexecution_certificate,
            function=function,
            submissions=submissions,
        )
    return submissions


def plan_device_lifecycle_from_graph(
    graph: OwnershipDomainGraph,
    *,
    function: str,
    queue: str,
    points: DeviceLifecycleSourcePoints,
    coexecution_certificate: Any = None,
) -> DeviceLifecycleSemanticPlan:
    """Derive and close one path-proven DEVICE lifecycle from canonical graph facts."""
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
    submissions = _canonical_submissions(
        graph,
        function=function_id,
        coexecution_certificate=coexecution_certificate,
    )
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
