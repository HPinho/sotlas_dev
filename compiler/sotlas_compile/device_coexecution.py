"""Package-neutral DEVICE co-execution proof over canonical SIR structure.

The test/tooling tree can still load the legacy ``tools/sotlas`` package before
the installed ``compiler/sotlas`` package.  DEVICE semantic planning must not
therefore depend on Python class identity from one concrete SIR package copy.

This module consumes the stable structural SIR contract only: module/functions,
basic blocks, explicit branch terminators, and source-stable ownership transfer
instructions.  It never treats block list order as control flow, and it rejects
cyclic multi-submission paths until iteration identity is modeled.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable


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


def _kind(value: object) -> str:
    return type(value).__name__


def _functions(module: Any) -> tuple[Any, ...]:
    functions = tuple(getattr(module, "functions", ()) or ())
    if not functions:
        raise DeviceCoexecutionError(
            "DEVICE coexecution requires a canonical SIR module with functions"
        )
    return functions


def _successors(function: Any) -> dict[str, tuple[str, ...]]:
    blocks = tuple(getattr(function, "blocks", ()) or ())
    labels = tuple(
        _required_text(getattr(block, "label", None), label="DEVICE CFG block")
        for block in blocks
    )
    if len(set(labels)) != len(labels):
        raise DeviceCoexecutionError("DEVICE coexecution CFG has duplicate block labels")
    known = set(labels)
    result: dict[str, tuple[str, ...]] = {}
    for block, label in zip(blocks, labels, strict=True):
        instructions = tuple(getattr(block, "instructions", ()) or ())
        terminator = instructions[-1] if instructions else None
        terminator_kind = _kind(terminator) if terminator is not None else ""
        if terminator_kind == "BranchInst":
            targets = (
                _required_text(
                    getattr(terminator, "target_block", None),
                    label="DEVICE CFG branch target",
                ),
            )
        elif terminator_kind == "CondBranchInst":
            targets = (
                _required_text(
                    getattr(terminator, "true_block", None),
                    label="DEVICE CFG true target",
                ),
                _required_text(
                    getattr(terminator, "false_block", None),
                    label="DEVICE CFG false target",
                ),
            )
        elif terminator_kind == "ReturnInst":
            targets = ()
        else:
            # Block order is presentation, not a control-flow edge.
            targets = ()
        if any(target not in known for target in targets):
            raise DeviceCoexecutionError(
                "DEVICE coexecution CFG branches to an unknown block"
            )
        result[label] = targets
    return result


def _reject_cycles(successors: dict[str, tuple[str, ...]]) -> None:
    state = {label: 0 for label in successors}

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
    successors: dict[str, tuple[str, ...]], start: str, goal: str
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
    module: Any,
    *,
    function: str,
    point_ids: Iterable[str],
) -> DeviceSubmissionCoexecutionCertificate:
    """Prove requested DEVICE handovers lie on one ordered acyclic SIR path."""
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

    matches = [
        item for item in _functions(module)
        if getattr(item, "name", None) == function_id
    ]
    if len(matches) != 1:
        raise DeviceCoexecutionError(
            "DEVICE coexecution requires exactly one matching SIR function"
        )
    sir_function = matches[0]

    by_point: dict[str, list[DeviceSubmissionLocation]] = {
        point: [] for point in requested
    }
    for block in tuple(getattr(sir_function, "blocks", ()) or ()):
        block_label = _required_text(
            getattr(block, "label", None), label="DEVICE coexecution block"
        )
        for index, instruction in enumerate(
            tuple(getattr(block, "instructions", ()) or ())
        ):
            if _kind(instruction) != "OwnershipDomainTransferInst":
                continue
            if (
                getattr(instruction, "operation", None) != "handover"
                or getattr(instruction, "source_domain", None) != "exclusive"
                or getattr(instruction, "target_domain", None) != "device"
                or getattr(instruction, "point_id", None) not in by_point
            ):
                continue
            source = getattr(instruction, "source", None)
            binding = _required_text(
                getattr(source, "name", None),
                label="DEVICE coexecution source binding",
            )
            point_id = instruction.point_id
            by_point[point_id].append(
                DeviceSubmissionLocation(
                    point_id=point_id,
                    binding=binding,
                    block=block_label,
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

    combined_path = [locations[0].block]
    for index in range(len(locations) - 1):
        previous = locations[index]
        current = locations[index + 1]
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
