"""Conservative CFG certificate for co-executing DEVICE submissions.

Canonical ownership graphs preserve source-stable DEVICE handovers but do not
encode enough path identity to distinguish sequential submissions from mutually
exclusive branch submissions.  This module reuses the already-placed SIR CFG to
prove a narrow property: a requested ordered set of EXCLUSIVE -> DEVICE handover
points occurs along one acyclic forward path.

The certificate is intentionally conservative. Cyclic CFGs are rejected for
multi-submission certificates until loop iteration identity is modeled, and
block list order is never treated as an implicit control-flow edge. This module
does not create completion/sync/reacquisition facts and does not enable a
runtime/backend by itself.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from .instructions import (
    BranchInst,
    CondBranchInst,
    OwnershipDomainTransferInst,
    ReturnInst,
    SIRFunction,
    SIRModule,
)


class DeviceCoexecutionError(ValueError):
    """Raised when DEVICE submissions cannot be proven on one ordered CFG path."""


@dataclass(frozen=True)
class DeviceSubmissionLocation:
    point_id: str
    binding: str
    block: str
    instruction_index: int


@dataclass(frozen=True)
class DeviceSubmissionCoexecutionCertificate:
    function: str
    point_ids: tuple[str, ...]
    bindings: tuple[str, ...]
    locations: tuple[DeviceSubmissionLocation, ...]
    block_path: tuple[str, ...]
    acyclic: bool = True


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeviceCoexecutionError(f"{label} requires a non-empty identity")
    return value


def _successors(function: SIRFunction) -> dict[str, tuple[str, ...]]:
    labels = tuple(block.label for block in function.blocks)
    if len(set(labels)) != len(labels):
        raise DeviceCoexecutionError("DEVICE coexecution CFG has duplicate block labels")
    known = set(labels)
    result: dict[str, tuple[str, ...]] = {}
    for block in function.blocks:
        terminator = block.instructions[-1] if block.instructions else None
        if isinstance(terminator, BranchInst):
            targets = (terminator.target_block,)
        elif isinstance(terminator, CondBranchInst):
            targets = (terminator.true_block, terminator.false_block)
        elif isinstance(terminator, ReturnInst):
            targets = ()
        else:
            # The SIR does not define block-list order as a control-flow edge.
            # Missing terminators therefore prove no cross-block reachability.
            targets = ()
        missing = tuple(target for target in targets if target not in known)
        if missing:
            raise DeviceCoexecutionError(
                "DEVICE coexecution CFG branches to an unknown block"
            )
        result[block.label] = targets
    return result


def _reject_cycles(successors: dict[str, tuple[str, ...]]) -> None:
    state: dict[str, int] = {label: 0 for label in successors}

    def visit(label: str) -> None:
        if state[label] == 1:
            raise DeviceCoexecutionError(
                "DEVICE multi-submission coexecution requires an acyclic CFG"
            )
        if state[label] == 2:
            return
        state[label] = 1
        for target in successors[label]:
            visit(target)
        state[label] = 2

    for label in successors:
        if state[label] == 0:
            visit(label)


def _path(
    successors: dict[str, tuple[str, ...]],
    start: str,
    goal: str,
) -> tuple[str, ...] | None:
    if start == goal:
        return (start,)
    queue = deque([(start, (start,))])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        for target in successors[current]:
            if target in visited:
                continue
            candidate = path + (target,)
            if target == goal:
                return candidate
            visited.add(target)
            queue.append((target, candidate))
    return None


def certify_device_submission_coexecution(
    module: SIRModule,
    *,
    function: str,
    point_ids: Iterable[str],
) -> DeviceSubmissionCoexecutionCertificate:
    """Prove requested DEVICE submissions are ordered along one acyclic CFG path."""
    if not isinstance(module, SIRModule):
        raise DeviceCoexecutionError("DEVICE coexecution requires a canonical SIRModule")
    function_id = _required_text(function, label="DEVICE coexecution function")
    requested = tuple(
        _required_text(point, label="DEVICE coexecution submission point")
        for point in point_ids
    )
    if not requested:
        raise DeviceCoexecutionError(
            "DEVICE coexecution requires at least one submission point"
        )
    if len(set(requested)) != len(requested):
        raise DeviceCoexecutionError(
            "DEVICE coexecution submission point identities must be unique"
        )

    matches = [item for item in module.functions if item.name == function_id]
    if len(matches) != 1:
        raise DeviceCoexecutionError(
            "DEVICE coexecution requires exactly one matching SIR function"
        )
    sir_function = matches[0]
    if not isinstance(sir_function, SIRFunction):
        raise DeviceCoexecutionError("DEVICE coexecution function is not canonical SIR")

    by_point: dict[str, list[DeviceSubmissionLocation]] = {point: [] for point in requested}
    for block in sir_function.blocks:
        for index, instruction in enumerate(block.instructions):
            if not isinstance(instruction, OwnershipDomainTransferInst):
                continue
            if (
                instruction.operation != "handover"
                or instruction.source_domain != "exclusive"
                or instruction.target_domain != "device"
                or instruction.point_id not in by_point
            ):
                continue
            binding = _required_text(
                instruction.source.name,
                label="DEVICE coexecution source binding",
            )
            by_point[instruction.point_id].append(
                DeviceSubmissionLocation(
                    point_id=instruction.point_id,
                    binding=binding,
                    block=block.label,
                    instruction_index=index,
                )
            )

    locations: list[DeviceSubmissionLocation] = []
    for point in requested:
        entries = by_point[point]
        if not entries:
            raise DeviceCoexecutionError(
                f"DEVICE submission point {point!r} is not placed in the SIR CFG"
            )
        if len(entries) != 1:
            raise DeviceCoexecutionError(
                f"DEVICE submission point {point!r} is placed more than once"
            )
        locations.append(entries[0])

    bindings = tuple(location.binding for location in locations)
    if len(set(bindings)) != len(bindings):
        raise DeviceCoexecutionError(
            "DEVICE coexecution submissions must refer to unique source bindings"
        )

    successors = _successors(sir_function)
    if len(locations) > 1:
        _reject_cycles(successors)

    combined_path: list[str] = [locations[0].block]
    for previous, current in zip(locations, locations[1:], strict=True):
        if previous.block == current.block:
            if previous.instruction_index >= current.instruction_index:
                raise DeviceCoexecutionError(
                    "DEVICE submissions are not ordered within their SIR block"
                )
            continue
        segment = _path(successors, previous.block, current.block)
        if segment is None:
            raise DeviceCoexecutionError(
                "DEVICE submissions are not co-executable in requested source order"
            )
        combined_path.extend(segment[1:])

    return DeviceSubmissionCoexecutionCertificate(
        function=function_id,
        point_ids=requested,
        bindings=bindings,
        locations=tuple(locations),
        block_path=tuple(combined_path),
        acyclic=True,
    )
