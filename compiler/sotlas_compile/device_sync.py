"""Backend-neutral synchronization for completed DEVICE ownership transfers.

This module builds on ``device_ownership`` without claiming a hardware queue,
runtime, DMA engine, or synchronization ABI exists.  It proves a narrower
semantic property: a host-side synchronization fence may cover a finite set of
DEVICE submissions only after every member has reached COMPLETED, and batch
reacquisition may consume exactly that synchronized set once.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

from .device_ownership import (
    DeviceCompletionToken,
    DeviceReacquisitionPlan,
    DeviceTransferState,
    mark_device_reacquired,
    plan_device_reacquisition,
)
from .typed_ast import Phase1SemanticError


class DeviceSyncState(str, Enum):
    SYNCHRONIZED = "synchronized"
    CONSUMED = "consumed"


@dataclass(frozen=True)
class DeviceSyncFence:
    function: str
    queue: str
    submission_point_ids: tuple[str, ...]
    completion_point_ids: tuple[str, ...]
    sync_point_id: str
    state: DeviceSyncState = DeviceSyncState.SYNCHRONIZED


@dataclass(frozen=True)
class DeviceSyncReacquisition:
    fence: DeviceSyncFence
    plans: tuple[DeviceReacquisitionPlan, ...]


@dataclass(frozen=True)
class DeviceSyncResult:
    fence: DeviceSyncFence
    tokens: tuple[DeviceCompletionToken, ...]


def _stable_id(value: str | None, *, operation: str) -> str:
    if value is None or not value.strip():
        raise Phase1SemanticError(
            f"{operation} requires a non-empty source-stable point id"
        )
    return value


def _completed_tokens(
    tokens: Iterable[DeviceCompletionToken],
) -> tuple[DeviceCompletionToken, ...]:
    materialized = tuple(tokens)
    if not materialized:
        raise Phase1SemanticError("device synchronization requires at least one token")

    submissions: set[str] = set()
    for token in materialized:
        if token.state is not DeviceTransferState.COMPLETED:
            raise Phase1SemanticError(
                f"device synchronization requires COMPLETED token for "
                f"{token.function}::{token.binding}, got {token.state.value}"
            )
        submission = _stable_id(
            token.submission_point_id,
            operation="device synchronization submission",
        )
        _stable_id(
            token.completion_point_id,
            operation="device synchronization completion",
        )
        if submission in submissions:
            raise Phase1SemanticError(
                f"device synchronization contains duplicate submission {submission!r}"
            )
        submissions.add(submission)
    return materialized


def plan_device_sync(
    tokens: Iterable[DeviceCompletionToken],
    *,
    function: str,
    queue: str,
    point_id: str,
) -> DeviceSyncFence:
    """Create one semantic fence over an exact completed submission set."""
    completed = _completed_tokens(tokens)
    if not function.strip():
        raise Phase1SemanticError("device synchronization requires a function identity")
    if not queue.strip():
        raise Phase1SemanticError("device synchronization requires a queue identity")
    if any(token.function != function for token in completed):
        raise Phase1SemanticError(
            "device synchronization cannot mix submissions from different functions"
        )

    sync_point = _stable_id(point_id, operation="device synchronization")
    occupied = {
        token.submission_point_id
        for token in completed
    } | {
        token.completion_point_id
        for token in completed
    }
    if sync_point in occupied:
        raise Phase1SemanticError(
            "device synchronization point must be distinct from submission and completion points"
        )

    return DeviceSyncFence(
        function=function,
        queue=queue,
        submission_point_ids=tuple(
            token.submission_point_id for token in completed
        ),
        completion_point_ids=tuple(
            token.completion_point_id for token in completed  # type: ignore[arg-type]
        ),
        sync_point_id=sync_point,
    )


def plan_synced_reacquisitions(
    tokens: Iterable[DeviceCompletionToken],
    fence: DeviceSyncFence,
    *,
    point_ids: Iterable[str],
) -> DeviceSyncReacquisition:
    """Plan one DEVICE -> EXCLUSIVE reacquisition per synchronized token."""
    completed = _completed_tokens(tokens)
    if fence.state is not DeviceSyncState.SYNCHRONIZED:
        raise Phase1SemanticError(
            f"device synchronization fence is already {fence.state.value}"
        )
    if any(token.function != fence.function for token in completed):
        raise Phase1SemanticError("device synchronization fence function mismatch")

    submissions = tuple(token.submission_point_id for token in completed)
    completions = tuple(token.completion_point_id for token in completed)
    if submissions != fence.submission_point_ids or completions != fence.completion_point_ids:
        raise Phase1SemanticError(
            "device synchronization fence does not cover the exact token set"
        )

    points = tuple(point_ids)
    if len(points) != len(completed):
        raise Phase1SemanticError(
            "device synchronized reacquisition requires one point per token"
        )
    if len(set(points)) != len(points):
        raise Phase1SemanticError(
            "device synchronized reacquisition point ids must be unique"
        )
    if fence.sync_point_id in points:
        raise Phase1SemanticError(
            "device reacquisition points must be distinct from the synchronization point"
        )

    plans = tuple(
        plan_device_reacquisition(token, point_id=point)
        for token, point in zip(completed, points, strict=True)
    )
    return DeviceSyncReacquisition(fence=fence, plans=plans)


def consume_device_sync(
    tokens: Iterable[DeviceCompletionToken],
    batch: DeviceSyncReacquisition,
) -> DeviceSyncResult:
    """Consume an exact synchronized batch and mark every token REACQUIRED."""
    completed = _completed_tokens(tokens)
    fence = batch.fence
    if fence.state is not DeviceSyncState.SYNCHRONIZED:
        raise Phase1SemanticError(
            f"device synchronization fence is already {fence.state.value}"
        )
    if len(batch.plans) != len(completed):
        raise Phase1SemanticError(
            "device synchronization batch does not contain one plan per token"
        )

    updated = tuple(
        mark_device_reacquired(token, plan)
        for token, plan in zip(completed, batch.plans, strict=True)
    )
    return DeviceSyncResult(
        fence=replace(fence, state=DeviceSyncState.CONSUMED),
        tokens=updated,
    )
