"""Backend-neutral SIR lowering for synchronized DEVICE ownership batches.

This layer records semantic synchronization proof only. It does not submit work,
wait on hardware, synchronize a physical queue, or claim a DEVICE runtime/ABI
exists. A synchronized batch is lowered in proof order:

    completion(s) -> synchronization fence -> reacquisition(s)

The specialized fence instruction inherits ``OwnershipDomainPointInst`` so
backends that already fail closed on ownership runtime operations continue to
reject it until a real synchronization ABI exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Tuple

from .device import (
    DeviceReacquisitionInst,
    DeviceSIRLoweringError,
    lower_device_completion,
    lower_device_reacquisition,
)
from .instructions import OwnershipDomainPointInst, SIRInstruction, SIRValue


class DeviceSyncSIRLoweringError(DeviceSIRLoweringError):
    """Raised when synchronized DEVICE proof is incomplete or inconsistent."""


@dataclass
class DeviceSyncFenceInst(OwnershipDomainPointInst):
    """Source-stable semantic fence over an exact completed DEVICE set."""

    queue: str = ""
    submission_point_ids: Tuple[str, ...] = ()
    completion_point_ids: Tuple[str, ...] = ()

    def __str__(self) -> str:
        submissions = ",".join(self.submission_point_ids)
        completions = ",".join(self.completion_point_ids)
        return (
            f"  device_sync_fence {self.queue} "
            f"[submitted={submissions}] [completed={completions}] "
            f"// {self.point_id}"
        )


@dataclass(frozen=True)
class DeviceSyncSIRPlan:
    instructions: Tuple[SIRInstruction, ...]


def _enum_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceSyncSIRLoweringError(
            f"{label} requires a non-empty source-stable identity"
        )
    return value


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    materialized = tuple(values)
    if not materialized:
        raise DeviceSyncSIRLoweringError(f"{label} requires at least one item")
    return materialized


def lower_device_sync_fence(fence: Any) -> DeviceSyncFenceInst:
    """Lower a SYNCHRONIZED semantic fence into a backend-neutral SIR fact."""
    state = _enum_value(getattr(fence, "state", None))
    if state != "synchronized":
        raise DeviceSyncSIRLoweringError(
            f"DEVICE sync fence lowering requires SYNCHRONIZED state, got {state!r}"
        )

    function = _required_text(
        getattr(fence, "function", None), label="DEVICE sync function"
    )
    queue = _required_text(
        getattr(fence, "queue", None), label="DEVICE sync queue"
    )
    sync_point = _required_text(
        getattr(fence, "sync_point_id", None), label="DEVICE sync point"
    )
    submissions = tuple(getattr(fence, "submission_point_ids", ()) or ())
    completions = tuple(getattr(fence, "completion_point_ids", ()) or ())
    if not submissions or len(submissions) != len(completions):
        raise DeviceSyncSIRLoweringError(
            "DEVICE sync fence requires one completion for every submission"
        )
    submissions = tuple(
        _required_text(value, label="DEVICE submission") for value in submissions
    )
    completions = tuple(
        _required_text(value, label="DEVICE completion") for value in completions
    )
    if len(set(submissions)) != len(submissions):
        raise DeviceSyncSIRLoweringError(
            "DEVICE sync fence contains duplicate submission identities"
        )
    if len(set(completions)) != len(completions):
        raise DeviceSyncSIRLoweringError(
            "DEVICE sync fence contains duplicate completion identities"
        )
    if sync_point in set(submissions) | set(completions):
        raise DeviceSyncSIRLoweringError(
            "DEVICE sync point must differ from submission and completion points"
        )

    return DeviceSyncFenceInst(
        operation="device_sync_fence",
        source_name=function,
        destination_name=None,
        point_id=sync_point,
        queue=queue,
        submission_point_ids=submissions,
        completion_point_ids=completions,
    )


def lower_device_sync_batch(
    batch: Any,
    tokens: Iterable[Any],
    sources: Iterable[SIRValue],
    destinations: Iterable[SIRValue],
) -> DeviceSyncSIRPlan:
    """Lower one exact synchronized batch without inventing runtime execution."""
    fence = getattr(batch, "fence", None)
    plans = _materialize(getattr(batch, "plans", ()) or (), label="DEVICE sync plans")
    semantic_tokens = _materialize(tokens, label="DEVICE sync tokens")
    source_values = _materialize(sources, label="DEVICE sync sources")
    destination_values = _materialize(
        destinations, label="DEVICE sync destinations"
    )

    expected_count = len(semantic_tokens)
    if not (
        len(plans)
        == len(source_values)
        == len(destination_values)
        == expected_count
    ):
        raise DeviceSyncSIRLoweringError(
            "DEVICE sync SIR requires one token, plan, source and destination per owner"
        )

    fence_inst = lower_device_sync_fence(fence)
    submissions = tuple(
        _required_text(
            getattr(token, "submission_point_id", None),
            label="DEVICE token submission",
        )
        for token in semantic_tokens
    )
    completions = tuple(
        _required_text(
            getattr(token, "completion_point_id", None),
            label="DEVICE token completion",
        )
        for token in semantic_tokens
    )
    if (
        submissions != fence_inst.submission_point_ids
        or completions != fence_inst.completion_point_ids
    ):
        raise DeviceSyncSIRLoweringError(
            "DEVICE sync fence does not cover the exact token identities"
        )

    for token in semantic_tokens:
        state = _enum_value(getattr(token, "state", None))
        if state != "completed":
            raise DeviceSyncSIRLoweringError(
                f"DEVICE sync batch requires COMPLETED tokens, got {state!r}"
            )

    completion_insts = tuple(
        lower_device_completion(token, source)
        for token, source in zip(semantic_tokens, source_values, strict=True)
    )
    reacquisition_insts: tuple[DeviceReacquisitionInst, ...] = tuple(
        lower_device_reacquisition(plan, source, destination)
        for plan, source, destination in zip(
            plans, source_values, destination_values, strict=True
        )
    )

    for token, plan, reacquisition in zip(
        semantic_tokens, plans, reacquisition_insts, strict=True
    ):
        if getattr(token, "function", None) != getattr(plan, "function", None):
            raise DeviceSyncSIRLoweringError(
                "DEVICE sync token and reacquisition plan function identities differ"
            )
        if getattr(token, "binding", None) != getattr(plan, "binding", None):
            raise DeviceSyncSIRLoweringError(
                "DEVICE sync token and reacquisition plan binding identities differ"
            )
        if token.submission_point_id != reacquisition.submission_point_id:
            raise DeviceSyncSIRLoweringError(
                "DEVICE sync submission identity differs across lifecycle facts"
            )
        if token.completion_point_id != reacquisition.completion_point_id:
            raise DeviceSyncSIRLoweringError(
                "DEVICE sync completion identity differs across lifecycle facts"
            )
        if reacquisition.point_id == fence_inst.point_id:
            raise DeviceSyncSIRLoweringError(
                "DEVICE reacquisition point must differ from synchronization point"
            )

    reacquisition_points = tuple(inst.point_id for inst in reacquisition_insts)
    if len(set(reacquisition_points)) != len(reacquisition_points):
        raise DeviceSyncSIRLoweringError(
            "DEVICE synchronized reacquisition points must be unique"
        )

    return DeviceSyncSIRPlan(
        completion_insts + (fence_inst,) + reacquisition_insts
    )
