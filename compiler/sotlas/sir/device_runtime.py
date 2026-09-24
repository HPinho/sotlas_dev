"""Fail-closed bridge between DEVICE synchronization SIR and runtime requirements.

This module validates that a backend-neutral ``DeviceSyncSIRPlan`` and a
backend-neutral runtime requirement plan describe the exact same proven
DEVICE lifecycle.  It intentionally does not import the frontend/runtime
planning package: the bridge consumes its contract structurally so the SIR
layer remains backend-neutral and does not create a frontend dependency cycle.

The synchronization SIR does not repeat submission instructions. Submission
identity is therefore proven through the ``submission_point_id`` carried by
completion, synchronization-fence and reacquisition facts.  A valid bridge
must preserve this lifecycle exactly:

    submit -> completion -> synchronization fence -> reacquisition

Validation only freezes proof correspondence.  It does not call runtime
symbols, wait on hardware, move bytes, synchronize a physical queue, or enable
DEVICE execution in C11/LLVM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from .device import DeviceCompletionInst, DeviceReacquisitionInst
from .device_sync import DeviceSyncFenceInst, DeviceSyncSIRPlan


class DeviceRuntimeSIRBridgeError(ValueError):
    """Raised when runtime requirements and DEVICE SIR are not identical proof."""


class _RuntimeRequirementLike(Protocol):
    operation: Any
    function: str
    point_id: str
    binding: str | None
    queue: str | None
    depends_on: tuple[str, ...]


class _RuntimeRequirementPlanLike(Protocol):
    function: str
    queue: str
    requirements: tuple[_RuntimeRequirementLike, ...]


@dataclass(frozen=True)
class DeviceRuntimeSIRBridgePlan:
    """Validated identity bridge; contains no executable runtime operation."""

    function: str
    queue: str
    runtime_point_ids: tuple[str, ...]
    sir_point_ids: tuple[str, ...]
    submission_point_ids: tuple[str, ...]
    completion_point_ids: tuple[str, ...]
    synchronization_point_id: str
    reacquisition_point_ids: tuple[str, ...]


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceRuntimeSIRBridgeError(
            f"{label} requires a non-empty source-stable identity"
        )
    return value


def _materialize(values: Iterable[Any], *, label: str) -> tuple[Any, ...]:
    materialized = tuple(values)
    if not materialized:
        raise DeviceRuntimeSIRBridgeError(f"{label} requires at least one item")
    return materialized


def _operation_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None


def _requirements_for(
    requirements: tuple[Any, ...], operation: str
) -> tuple[Any, ...]:
    return tuple(
        requirement
        for requirement in requirements
        if _operation_value(getattr(requirement, "operation", None)) == operation
    )


def validate_device_runtime_sir_plan(
    sir_plan: DeviceSyncSIRPlan,
    runtime_plan: _RuntimeRequirementPlanLike,
) -> DeviceRuntimeSIRBridgePlan:
    """Prove SIR/runtime plans are one source-stable lifecycle, fail closed."""
    function = _required_text(
        getattr(runtime_plan, "function", None), label="DEVICE runtime function"
    )
    queue = _required_text(
        getattr(runtime_plan, "queue", None), label="DEVICE runtime queue"
    )
    requirements = _materialize(
        getattr(runtime_plan, "requirements", ()) or (),
        label="DEVICE runtime requirements",
    )

    allowed_operations = {"submit", "complete", "synchronize", "reacquire"}
    for requirement in requirements:
        operation = _operation_value(getattr(requirement, "operation", None))
        if operation not in allowed_operations:
            raise DeviceRuntimeSIRBridgeError(
                f"DEVICE runtime/SIR bridge received unsupported operation {operation!r}"
            )
        if getattr(requirement, "function", None) != function:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime requirement crosses function identity"
            )
        if getattr(requirement, "queue", None) != queue:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime requirement crosses queue identity"
            )

    submissions = _requirements_for(requirements, "submit")
    completions = _requirements_for(requirements, "complete")
    synchronizations = _requirements_for(requirements, "synchronize")
    reacquisitions = _requirements_for(requirements, "reacquire")
    owner_count = len(submissions)
    if owner_count == 0:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE runtime/SIR bridge requires at least one submission"
        )
    if len(synchronizations) != 1:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE runtime/SIR bridge requires exactly one synchronization fence"
        )
    if len(completions) != owner_count or len(reacquisitions) != owner_count:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE runtime/SIR bridge requires one completion and reacquisition per submission"
        )

    runtime_point_ids = tuple(
        _required_text(
            getattr(requirement, "point_id", None),
            label="DEVICE runtime lifecycle point",
        )
        for requirement in requirements
    )
    if len(set(runtime_point_ids)) != len(runtime_point_ids):
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE runtime/SIR bridge requires globally unique runtime point ids"
        )

    submission_points = tuple(
        _required_text(item.point_id, label="DEVICE runtime submission point")
        for item in submissions
    )
    completion_points = tuple(
        _required_text(item.point_id, label="DEVICE runtime completion point")
        for item in completions
    )
    sync_requirement = synchronizations[0]
    sync_point = _required_text(
        sync_requirement.point_id, label="DEVICE runtime synchronization point"
    )
    reacquisition_points = tuple(
        _required_text(item.point_id, label="DEVICE runtime reacquisition point")
        for item in reacquisitions
    )

    for index, (submission, completion, reacquisition) in enumerate(
        zip(submissions, completions, reacquisitions, strict=True)
    ):
        submission_binding = _required_text(
            getattr(submission, "binding", None),
            label=f"DEVICE runtime submission binding {index}",
        )
        if getattr(completion, "binding", None) != submission_binding:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime completion binding diverges from submission"
            )
        if getattr(reacquisition, "binding", None) != submission_binding:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime reacquisition binding diverges from submission"
            )
        if tuple(getattr(submission, "depends_on", ()) or ()):
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime submission cannot depend on a later lifecycle point"
            )
        if tuple(getattr(completion, "depends_on", ()) or ()) != (
            submission_points[index],
        ):
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime completion dependency diverges from submission"
            )
        if tuple(getattr(reacquisition, "depends_on", ()) or ()) != (sync_point,):
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE runtime reacquisition dependency diverges from synchronization"
            )

    if tuple(getattr(sync_requirement, "depends_on", ()) or ()) != completion_points:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE runtime synchronization dependencies diverge from completions"
        )
    if getattr(sync_requirement, "binding", None) is not None:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE synchronization requirement must cover the batch, not one binding"
        )

    instructions = _materialize(
        getattr(sir_plan, "instructions", ()) or (), label="DEVICE synchronization SIR"
    )
    expected_instruction_count = owner_count * 2 + 1
    if len(instructions) != expected_instruction_count:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE synchronization SIR does not contain the exact completion/fence/reacquisition set"
        )

    completion_insts = instructions[:owner_count]
    fence_inst = instructions[owner_count]
    reacquisition_insts = instructions[owner_count + 1 :]
    if not all(isinstance(inst, DeviceCompletionInst) for inst in completion_insts):
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE synchronization SIR must place every completion before the fence"
        )
    if not isinstance(fence_inst, DeviceSyncFenceInst):
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE synchronization SIR must contain exactly one fence after completions"
        )
    if not all(
        isinstance(inst, DeviceReacquisitionInst) for inst in reacquisition_insts
    ):
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE synchronization SIR must place reacquisitions after the fence"
        )

    sir_point_ids = tuple(
        _required_text(getattr(inst, "point_id", None), label="DEVICE SIR point")
        for inst in instructions
    )
    expected_sir_points = completion_points + (sync_point,) + reacquisition_points
    if sir_point_ids != expected_sir_points:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE synchronization SIR point order diverges from runtime requirements"
        )

    for index, (completion_inst, reacquisition_inst) in enumerate(
        zip(completion_insts, reacquisition_insts, strict=True)
    ):
        if completion_inst.operation != "device_completion":
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE SIR completion has an invalid operation identity"
            )
        if completion_inst.submission_point_id != submission_points[index]:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE SIR completion lost its submission identity"
            )
        if reacquisition_inst.operation != "device_reacquire":
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE SIR reacquisition has an invalid operation identity"
            )
        if (
            reacquisition_inst.source_domain != "device"
            or reacquisition_inst.target_domain != "exclusive"
        ):
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE SIR reacquisition must remain DEVICE -> EXCLUSIVE"
            )
        if reacquisition_inst.submission_point_id != submission_points[index]:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE SIR reacquisition lost its submission identity"
            )
        if reacquisition_inst.completion_point_id != completion_points[index]:
            raise DeviceRuntimeSIRBridgeError(
                "DEVICE SIR reacquisition lost its completion identity"
            )

    if fence_inst.operation != "device_sync_fence":
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE SIR synchronization fence has an invalid operation identity"
        )
    if fence_inst.source_name != function:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE SIR synchronization fence crosses function identity"
        )
    if fence_inst.queue != queue:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE SIR synchronization fence crosses queue identity"
        )
    if fence_inst.submission_point_ids != submission_points:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE SIR synchronization fence lost exact submission coverage"
        )
    if fence_inst.completion_point_ids != completion_points:
        raise DeviceRuntimeSIRBridgeError(
            "DEVICE SIR synchronization fence lost exact completion coverage"
        )

    return DeviceRuntimeSIRBridgePlan(
        function=function,
        queue=queue,
        runtime_point_ids=runtime_point_ids,
        sir_point_ids=sir_point_ids,
        submission_point_ids=submission_points,
        completion_point_ids=completion_points,
        synchronization_point_id=sync_point,
        reacquisition_point_ids=reacquisition_points,
    )
