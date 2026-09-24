"""Backend-neutral SIR facts for DEVICE completion and reacquisition.

This layer deliberately carries semantic proof only.  It does not submit work,
wait on hardware, synchronize queues, or claim a DEVICE runtime exists.  The
specialized instructions inherit the existing ownership-domain instructions so
backends that already fail closed on ownership runtime operations continue to
reject them until a real ABI/runtime contract is implemented.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from .instructions import (
    OwnershipDomainPointInst,
    OwnershipDomainTransferInst,
    SIRInstruction,
    SIRValue,
)


class DeviceSIRLoweringError(ValueError):
    """Raised when DEVICE semantic proof is incomplete or inconsistent."""


@dataclass
class DeviceCompletionInst(OwnershipDomainPointInst):
    """Source-stable proof that a prior DEVICE submission completed."""

    submission_point_id: str = ""

    def __str__(self) -> str:
        return (
            f"  device_completion {self.source_name} "
            f"[submitted={self.submission_point_id}] // {self.point_id}"
        )


@dataclass
class DeviceReacquisitionInst(OwnershipDomainTransferInst):
    """Completion-gated DEVICE -> EXCLUSIVE ownership reacquisition fact."""

    submission_point_id: str = ""
    completion_point_id: str = ""

    def __str__(self) -> str:
        destination = (
            f" -> {self.destination}" if self.destination is not None else ""
        )
        return (
            f"  device_reacquire {self.source}{destination} "
            f"[{self.source_domain}->{self.target_domain}] "
            f"[submitted={self.submission_point_id}, "
            f"completed={self.completion_point_id}] // {self.point_id}"
        )


@dataclass(frozen=True)
class DeviceOwnershipSIRPlan:
    instructions: Tuple[SIRInstruction, ...]


def _enum_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceSIRLoweringError(f"{label} requires a non-empty point id")
    return value


def _semantic_type_name(value: Any) -> str:
    semantic_type = getattr(value, "type", None)
    name = getattr(semantic_type, "name", None)
    if not isinstance(name, str) or not name:
        raise DeviceSIRLoweringError("DEVICE semantic fact is missing its type")
    return name


def _require_sir_type(value: SIRValue, semantic: Any, *, role: str) -> None:
    expected = _semantic_type_name(semantic)
    if value.type_name != expected:
        raise DeviceSIRLoweringError(
            f"{role} SIR value has type {value.type_name!r}, expected {expected!r}"
        )


def lower_device_completion(token: Any, source: SIRValue) -> DeviceCompletionInst:
    """Lower a COMPLETED/REACQUIRED token to a SIR completion proof."""
    state = _enum_value(getattr(token, "state", None))
    if state not in {"completed", "reacquired"}:
        raise DeviceSIRLoweringError(
            f"DEVICE completion lowering requires COMPLETED state, got {state!r}"
        )
    _require_sir_type(source, token, role="DEVICE completion source")
    submission = _required_text(
        getattr(token, "submission_point_id", None),
        label="DEVICE submission",
    )
    completion = _required_text(
        getattr(token, "completion_point_id", None),
        label="DEVICE completion",
    )
    if submission == completion:
        raise DeviceSIRLoweringError(
            "DEVICE completion point must differ from submission point"
        )
    return DeviceCompletionInst(
        operation="device_completion",
        source_name=source.name,
        destination_name=None,
        point_id=completion,
        submission_point_id=submission,
    )


def lower_device_reacquisition(
    plan: Any,
    source: SIRValue,
    destination: SIRValue,
) -> DeviceReacquisitionInst:
    """Lower a validated DEVICE -> EXCLUSIVE reacquisition plan to SIR."""
    source_domain = _enum_value(getattr(plan, "source", None))
    target_domain = _enum_value(getattr(plan, "target", None))
    operation = getattr(plan, "operation", None)
    if (
        source_domain != "device"
        or target_domain != "exclusive"
        or operation != "device_reacquire"
    ):
        raise DeviceSIRLoweringError(
            "DEVICE reacquisition SIR requires device->exclusive device_reacquire"
        )
    _require_sir_type(source, plan, role="DEVICE reacquisition source")
    _require_sir_type(destination, plan, role="DEVICE reacquisition destination")
    submission = _required_text(
        getattr(plan, "submission_point_id", None),
        label="DEVICE submission",
    )
    completion = _required_text(
        getattr(plan, "completion_point_id", None),
        label="DEVICE completion",
    )
    reacquisition = _required_text(
        getattr(plan, "reacquisition_point_id", None),
        label="DEVICE reacquisition",
    )
    if len({submission, completion, reacquisition}) != 3:
        raise DeviceSIRLoweringError(
            "DEVICE submission, completion and reacquisition points must be distinct"
        )
    return DeviceReacquisitionInst(
        operation="device_reacquire",
        source=source,
        source_domain="device",
        target_domain="exclusive",
        destination=destination,
        point_id=reacquisition,
        submission_point_id=submission,
        completion_point_id=completion,
    )


def lower_device_lifecycle(
    token: Any,
    plan: Any,
    source: SIRValue,
    destination: SIRValue,
) -> DeviceOwnershipSIRPlan:
    """Lower a fully reacquired DEVICE lifecycle without inventing runtime work."""
    state = _enum_value(getattr(token, "state", None))
    if state != "reacquired":
        raise DeviceSIRLoweringError(
            f"DEVICE lifecycle lowering requires REACQUIRED state, got {state!r}"
        )
    token_reacquisition = _required_text(
        getattr(token, "reacquisition_point_id", None),
        label="DEVICE token reacquisition",
    )
    plan_reacquisition = _required_text(
        getattr(plan, "reacquisition_point_id", None),
        label="DEVICE plan reacquisition",
    )
    if token_reacquisition != plan_reacquisition:
        raise DeviceSIRLoweringError(
            "DEVICE lifecycle token and reacquisition plan have different identities"
        )
    completion = lower_device_completion(token, source)
    reacquisition = lower_device_reacquisition(plan, source, destination)
    if (
        completion.submission_point_id != reacquisition.submission_point_id
        or completion.point_id != reacquisition.completion_point_id
    ):
        raise DeviceSIRLoweringError(
            "DEVICE completion and reacquisition SIR facts do not share one lifecycle"
        )
    return DeviceOwnershipSIRPlan((completion, reacquisition))
