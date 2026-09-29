"""Backend-neutral completion protocol for DEVICE ownership.

This module deliberately models only semantic proof. It does not submit work to
hardware, synchronize a queue, or claim a device runtime exists. Its job is to
make DEVICE -> EXCLUSIVE reacquisition impossible until a matching completion
fact has been recorded for a canonical EXCLUSIVE -> DEVICE handover.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .typed_ast import (
    OwnershipBinding,
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipDomainTransition,
    OwnershipEnv,
    Phase1SemanticError,
    SemanticType,
    VarState,
)


class DeviceTransferState(str, Enum):
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    REACQUIRED = "reacquired"


@dataclass(frozen=True)
class DeviceCompletionToken:
    function: str
    binding: str
    device_binding: str
    type: SemanticType
    submission_point_id: str
    state: DeviceTransferState = DeviceTransferState.SUBMITTED
    completion_point_id: str | None = None
    reacquisition_point_id: str | None = None


@dataclass(frozen=True)
class DeviceReacquisitionPlan:
    function: str
    binding: str
    device_binding: str
    type: SemanticType
    source: OwnershipDomain
    target: OwnershipDomain
    submission_point_id: str
    completion_point_id: str
    reacquisition_point_id: str
    operation: str = "device_reacquire"


def _require_point_id(point_id: str | None, *, operation: str) -> str:
    if point_id is None or not point_id.strip():
        raise Phase1SemanticError(
            f"{operation} requires a non-empty source-stable point id"
        )
    return point_id


def _canonical_device_destination(
    graph: OwnershipDomainGraph,
    transition: OwnershipDomainTransition,
) -> str:
    """Resolve the DEVICE owner created by the canonical handover edge."""
    matches = tuple(
        transfer
        for transfer in graph.transfers
        if transfer.function == transition.function
        and transfer.binding == transition.binding
        and transfer.via == "handover"
        and transfer.point_id == transition.point_id
        and transfer.source_domain is OwnershipDomain.EXCLUSIVE
        and transfer.target_domain is OwnershipDomain.DEVICE
        and transfer.destination_domain is OwnershipDomain.DEVICE
        and isinstance(transfer.destination, str)
        and bool(transfer.destination)
    )
    if not matches:
        raise Phase1SemanticError(
            f"device completion has no canonical handover edge for "
            f"{transition.function}::{transition.binding}"
        )
    if len(matches) != 1:
        raise Phase1SemanticError(
            f"device completion has ambiguous handover edges for "
            f"{transition.function}::{transition.binding}: {len(matches)}"
        )
    return matches[0].destination


def open_device_completion(
    graph: OwnershipDomainGraph,
    *,
    function: str,
    binding: str,
) -> DeviceCompletionToken:
    """Open completion tracking for one canonical EXCLUSIVE -> DEVICE submit."""
    matches = tuple(
        transition
        for transition in graph.planned_transitions
        if transition.function == function
        and transition.binding == binding
        and transition.source is OwnershipDomain.EXCLUSIVE
        and transition.target is OwnershipDomain.DEVICE
        and transition.operation == "handover"
    )
    if not matches:
        raise Phase1SemanticError(
            f"device completion has no canonical submission for "
            f"{function}::{binding}"
        )
    if len(matches) != 1:
        raise Phase1SemanticError(
            f"device completion is ambiguous for {function}::{binding}: "
            f"{len(matches)} submissions"
        )
    submission = matches[0]
    if submission.source_state is not VarState.LIVE:
        raise Phase1SemanticError(
            f"device submission for {function}::{binding} must originate LIVE"
        )
    point_id = _require_point_id(
        submission.point_id,
        operation="device submission",
    )
    device_binding = _canonical_device_destination(graph, submission)
    return DeviceCompletionToken(
        function=function,
        binding=binding,
        device_binding=device_binding,
        type=submission.type,
        submission_point_id=point_id,
    )


def complete_device_transfer(
    token: DeviceCompletionToken,
    *,
    point_id: str,
) -> DeviceCompletionToken:
    """Record that the submitted device work has completed exactly once."""
    if token.state is not DeviceTransferState.SUBMITTED:
        raise Phase1SemanticError(
            f"device completion for {token.function}::{token.binding} requires "
            f"SUBMITTED state, got {token.state.value}"
        )
    completion_point = _require_point_id(
        point_id,
        operation="device completion",
    )
    if completion_point == token.submission_point_id:
        raise Phase1SemanticError(
            "device completion point must be distinct from submission point"
        )
    return replace(
        token,
        state=DeviceTransferState.COMPLETED,
        completion_point_id=completion_point,
    )


def plan_device_reacquisition(
    token: DeviceCompletionToken,
    *,
    point_id: str,
) -> DeviceReacquisitionPlan:
    """Plan DEVICE -> EXCLUSIVE only after a proven completion event."""
    if token.state is not DeviceTransferState.COMPLETED:
        raise Phase1SemanticError(
            f"device reacquisition for {token.function}::{token.binding} "
            f"requires COMPLETED state, got {token.state.value}"
        )
    if token.completion_point_id is None:
        raise Phase1SemanticError(
            "completed device transfer is missing its completion point"
        )
    reacquisition_point = _require_point_id(
        point_id,
        operation="device reacquisition",
    )
    if reacquisition_point in {
        token.submission_point_id,
        token.completion_point_id,
    }:
        raise Phase1SemanticError(
            "device reacquisition point must be distinct from submission "
            "and completion points"
        )
    return DeviceReacquisitionPlan(
        function=token.function,
        binding=token.binding,
        device_binding=token.device_binding,
        type=token.type,
        source=OwnershipDomain.DEVICE,
        target=OwnershipDomain.EXCLUSIVE,
        submission_point_id=token.submission_point_id,
        completion_point_id=token.completion_point_id,
        reacquisition_point_id=reacquisition_point,
    )


def _require_matching_reacquisition(
    token: DeviceCompletionToken,
    plan: DeviceReacquisitionPlan,
) -> None:
    expected = (
        token.function,
        token.binding,
        token.device_binding,
        token.type,
        token.submission_point_id,
        token.completion_point_id,
    )
    actual = (
        plan.function,
        plan.binding,
        plan.device_binding,
        plan.type,
        plan.submission_point_id,
        plan.completion_point_id,
    )
    if expected != actual:
        raise Phase1SemanticError(
            "device reacquisition plan does not match its completion token"
        )
    if (
        plan.source is not OwnershipDomain.DEVICE
        or plan.target is not OwnershipDomain.EXCLUSIVE
        or plan.operation != "device_reacquire"
    ):
        raise Phase1SemanticError("invalid device reacquisition domain plan")


def mark_device_reacquired(
    token: DeviceCompletionToken,
    plan: DeviceReacquisitionPlan,
) -> DeviceCompletionToken:
    """Consume a matching reacquisition plan and close the transfer lifecycle."""
    if token.state is not DeviceTransferState.COMPLETED:
        raise Phase1SemanticError(
            f"device reacquisition commit requires COMPLETED state, got "
            f"{token.state.value}"
        )
    _require_matching_reacquisition(token, plan)
    return replace(
        token,
        state=DeviceTransferState.REACQUIRED,
        reacquisition_point_id=plan.reacquisition_point_id,
    )


def apply_device_reacquisition(
    env: OwnershipEnv,
    token: DeviceCompletionToken,
    plan: DeviceReacquisitionPlan,
    *,
    destination: str,
) -> OwnershipEnv:
    """Rearm one EXCLUSIVE binding after a completed DEVICE lifecycle.

    The DEVICE owner is consumed and becomes MOVED. The destination must be an
    already-consumed EXCLUSIVE slot of the same type, mirroring explicit
    handover semantics rather than creating a hidden owner or alias.
    """
    if token.state is not DeviceTransferState.REACQUIRED:
        raise Phase1SemanticError(
            f"device ownership application requires REACQUIRED state, got "
            f"{token.state.value}"
        )
    _require_matching_reacquisition(token, plan)
    if token.reacquisition_point_id != plan.reacquisition_point_id:
        raise Phase1SemanticError(
            "device reacquisition token and plan have different final identities"
        )
    if not destination or destination == token.device_binding:
        raise Phase1SemanticError(
            "device reacquisition requires a distinct exclusive destination"
        )

    source_index = next(
        (
            index
            for index, item in enumerate(env.bindings)
            if item.name == token.device_binding
        ),
        None,
    )
    destination_index = next(
        (
            index
            for index, item in enumerate(env.bindings)
            if item.name == destination
        ),
        None,
    )
    if source_index is None:
        raise Phase1SemanticError(
            f"device owner {token.device_binding!r} is not tracked"
        )
    if destination_index is None:
        raise Phase1SemanticError(
            f"device reacquisition destination {destination!r} is not tracked"
        )

    source = env.bindings[source_index]
    target = env.bindings[destination_index]
    if (
        source.type != token.type
        or source.domain is not OwnershipDomain.DEVICE
        or source.state is not VarState.LIVE
    ):
        raise Phase1SemanticError(
            f"device owner {token.device_binding!r} is not a live DEVICE owner"
        )
    if (
        target.type != token.type
        or target.domain is not OwnershipDomain.EXCLUSIVE
        or target.state is not VarState.MOVED
        or target.shared_account is not None
    ):
        raise Phase1SemanticError(
            f"device reacquisition destination {destination!r} must be a "
            "moved EXCLUSIVE owner of the same type"
        )

    updated = list(env.bindings)
    updated[source_index] = OwnershipBinding(
        source.name,
        source.type,
        VarState.MOVED,
        OwnershipDomain.DEVICE,
        source.shared_account,
    )
    updated[destination_index] = OwnershipBinding(
        target.name,
        target.type,
        VarState.LIVE,
        OwnershipDomain.EXCLUSIVE,
        target.shared_account,
    )
    return OwnershipEnv(tuple(updated))
