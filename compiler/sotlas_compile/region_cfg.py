"""Path-sensitive REGION lifetime certification over canonical SIR CFG.

This layer does not create ownership facts. It consumes a checked
``RegionLifetimePlan`` plus the already generated SIR CFG and proves that the
source-stable REGION handover/direct/whisper points are placed exactly once and
that a borrow of an owner is never reachable after that owner has been handed
over. Explicit branch terminators are the only control-flow edges; block list
order is never treated as fallthrough.

Call-scoped direct/whisper points may execute inside CFG cycles because they do
not transfer ownership and end at the call boundary. REGION handovers inside a
cycle are accepted only when that cycle exposes exactly one source-stable
canonical backedge identity. The identity freezes loop topology; it does not by
itself make repeated ownership transfer legal.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .canonical_sir import build_canonical_checked_ownership_sir
from .region_frontend import plan_checked_region_lifetime
from .region_lifetime import RegionLifetimePlan
from .region_sir import validate_region_lifetime_sir
from .typed_ast import Phase1SemanticError


class RegionLifetimeCFGError(Phase1SemanticError):
    """Raised when REGION lifetime facts cannot be certified on the SIR CFG."""


_BACKEDGE_PREFIXES = (
    "while_backedge@",
    "for_backedge@",
    "loop_backedge@",
)


@dataclass(frozen=True)
class RegionLifetimeCFGLocation:
    point_id: str
    kind: str
    source: str
    block: str
    instruction_index: int
    iteration_id: str | None = None


@dataclass(frozen=True)
class RegionLifetimeCFGCertificate:
    function: str
    locations: tuple[RegionLifetimeCFGLocation, ...]
    acyclic_points: bool = True
    cyclic_borrow_point_ids: tuple[str, ...] = ()
    cyclic_handover_point_ids: tuple[str, ...] = ()

    @property
    def point_ids(self) -> tuple[str, ...]:
        return tuple(item.point_id for item in self.locations)


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegionLifetimeCFGError(f"{label} requires a non-empty identity")
    return value


def _kind(value: object) -> str:
    return type(value).__name__


def _successors(function: Any) -> dict[str, tuple[str, ...]]:
    blocks = tuple(getattr(function, "blocks", ()) or ())
    labels = tuple(
        _required_text(getattr(block, "label", None), label="REGION CFG block")
        for block in blocks
    )
    if len(set(labels)) != len(labels):
        raise RegionLifetimeCFGError("REGION CFG contains duplicate block labels")
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
                    label="REGION CFG branch target",
                ),
            )
        elif terminator_kind == "CondBranchInst":
            targets = (
                _required_text(
                    getattr(terminator, "true_block", None),
                    label="REGION CFG true target",
                ),
                _required_text(
                    getattr(terminator, "false_block", None),
                    label="REGION CFG false target",
                ),
            )
        elif terminator_kind == "ReturnInst":
            targets = ()
        else:
            targets = ()
        if any(target not in known for target in targets):
            raise RegionLifetimeCFGError("REGION CFG branches to an unknown block")
        result[label] = targets
    return result


def _reachable(
    successors: dict[str, tuple[str, ...]], start: str, goal: str
) -> bool:
    if start == goal:
        return True
    queue = deque([start])
    visited = {start}
    while queue:
        current = queue.popleft()
        for target in successors[current]:
            if target == goal:
                return True
            if target in visited:
                continue
            visited.add(target)
            queue.append(target)
    return False


def _block_is_cyclic(
    successors: dict[str, tuple[str, ...]], block: str
) -> bool:
    return any(
        target == block or _reachable(successors, target, block)
        for target in successors[block]
    )


def _same_cycle(
    successors: dict[str, tuple[str, ...]], first: str, second: str
) -> bool:
    if first == second:
        return _block_is_cyclic(successors, first)
    return _reachable(successors, first, second) and _reachable(
        successors, second, first
    )


def _iteration_identity(
    function: object,
    successors: dict[str, tuple[str, ...]],
    point_block: str,
    point_id: str,
    *,
    error_type: type[Exception] = RegionLifetimeCFGError,
    subject: str = "REGION lifetime point",
) -> str | None:
    """Resolve one canonical source-stable backedge identity for a CFG cycle."""
    if not _block_is_cyclic(successors, point_block):
        return None

    candidates: list[str] = []
    for block in tuple(getattr(function, "blocks", ()) or ()):
        block_label = _required_text(
            getattr(block, "label", None), label="REGION CFG block"
        )
        if not _same_cycle(successors, point_block, block_label):
            continue
        for instruction in tuple(getattr(block, "instructions", ()) or ()):
            if _kind(instruction) != "BranchInst":
                continue
            if getattr(instruction, "control_kind", None) != "backedge":
                continue
            backedge_id = getattr(instruction, "point_id", None)
            if (
                isinstance(backedge_id, str)
                and backedge_id.startswith(_BACKEDGE_PREFIXES)
            ):
                candidates.append(backedge_id)

    unique = tuple(dict.fromkeys(candidates))
    if len(unique) == 0:
        raise error_type(
            f"{subject} {point_id!r} inside a CFG cycle requires iteration identity"
        )
    if len(unique) != 1:
        raise error_type(
            f"{subject} {point_id!r} inside a CFG cycle has ambiguous iteration identity"
        )
    return unique[0]


def _expected_points(lifetime: RegionLifetimePlan) -> dict[str, tuple[str, ...]]:
    expected: dict[str, tuple[str, ...]] = {}

    def insert(point: str, payload: tuple[str, ...]) -> None:
        if point in expected:
            raise RegionLifetimeCFGError(
                f"duplicate REGION lifetime point identity {point!r}"
            )
        expected[point] = payload

    for transfer in lifetime.transfers:
        if transfer.via != "handover" or transfer.point_id is None:
            continue
        point = _required_text(
            transfer.point_id, label="REGION CFG handover point"
        )
        destination = _required_text(
            transfer.destination, label="REGION CFG handover destination"
        )
        insert(point, ("handover", transfer.source, destination))
    for borrow in lifetime.borrows:
        point = _required_text(borrow.point_id, label="REGION CFG borrow point")
        insert(
            point,
            (borrow.mode, borrow.source, borrow.callee, borrow.parameter),
        )
    return expected


def certify_region_lifetime_cfg(
    lifetime: RegionLifetimePlan,
    module: object,
) -> RegionLifetimeCFGCertificate:
    """Certify REGION lifetime placement and borrow-after-handover safety."""
    if not isinstance(lifetime, RegionLifetimePlan):
        raise RegionLifetimeCFGError(
            "REGION CFG certification requires a RegionLifetimePlan"
        )
    function_name = _required_text(lifetime.function, label="REGION CFG function")
    functions = tuple(getattr(module, "functions", ()) or ())
    matches = tuple(
        item for item in functions if getattr(item, "name", None) == function_name
    )
    if len(matches) != 1:
        raise RegionLifetimeCFGError(
            "REGION CFG certification requires exactly one matching SIR function"
        )
    function = matches[0]
    expected = _expected_points(lifetime)
    successors = _successors(function)
    by_point: dict[str, list[RegionLifetimeCFGLocation]] = {
        point: [] for point in expected
    }

    for block in tuple(getattr(function, "blocks", ()) or ()):
        block_label = _required_text(
            getattr(block, "label", None), label="REGION CFG block"
        )
        for index, instruction in enumerate(
            tuple(getattr(block, "instructions", ()) or ())
        ):
            instruction_kind = _kind(instruction)
            actual: tuple[str, ...] | None = None
            source_name: str | None = None
            point_id = getattr(instruction, "point_id", None)

            if instruction_kind == "OwnershipDomainTransferInst" and (
                getattr(instruction, "operation", None) == "handover"
                and getattr(instruction, "source_domain", None) == "region"
                and getattr(instruction, "target_domain", None) == "region"
            ):
                source = getattr(instruction, "source", None)
                destination = getattr(instruction, "destination", None)
                source_name = _required_text(
                    getattr(source, "name", None), label="REGION CFG handover source"
                )
                destination_name = _required_text(
                    getattr(destination, "name", None),
                    label="REGION CFG handover destination",
                )
                actual = ("handover", source_name, destination_name)
            elif instruction_kind in ("WhisperBorrowInst", "DirectAccessInst") and (
                getattr(instruction, "source_domain", None) == "region"
            ):
                source = getattr(instruction, "source", None)
                source_name = _required_text(
                    getattr(source, "name", None), label="REGION CFG borrow source"
                )
                mode = (
                    "whisper"
                    if instruction_kind == "WhisperBorrowInst"
                    else "direct"
                )
                actual = (
                    mode,
                    source_name,
                    _required_text(
                        getattr(instruction, "callee", None),
                        label="REGION CFG borrow callee",
                    ),
                    _required_text(
                        getattr(instruction, "parameter", None),
                        label="REGION CFG borrow parameter",
                    ),
                )
            else:
                continue

            point = _required_text(point_id, label="REGION CFG source point")
            if point not in expected:
                raise RegionLifetimeCFGError(
                    f"REGION CFG contains unexpected lifetime point {point!r}"
                )
            if actual != expected[point]:
                raise RegionLifetimeCFGError(
                    f"REGION CFG point {point!r} diverged from lifetime topology"
                )
            iteration_id = None
            if actual[0] == "handover":
                iteration_id = _iteration_identity(
                    function,
                    successors,
                    block_label,
                    point,
                    subject="REGION handover",
                )
            by_point[point].append(
                RegionLifetimeCFGLocation(
                    point_id=point,
                    kind=actual[0],
                    source=source_name,
                    block=block_label,
                    instruction_index=index,
                    iteration_id=iteration_id,
                )
            )

    locations: list[RegionLifetimeCFGLocation] = []
    for point in expected:
        entries = by_point[point]
        if not entries:
            raise RegionLifetimeCFGError(
                f"REGION lifetime point {point!r} is not placed in the SIR CFG"
            )
        if len(entries) != 1:
            raise RegionLifetimeCFGError(
                f"REGION lifetime point {point!r} is placed more than once"
            )
        locations.append(entries[0])

    cyclic_borrows: list[str] = []
    cyclic_handovers: list[str] = []
    handovers_by_iteration: dict[str, list[RegionLifetimeCFGLocation]] = {}
    for location in locations:
        if not _block_is_cyclic(successors, location.block):
            continue
        if location.kind == "handover":
            if location.iteration_id is None:
                raise RegionLifetimeCFGError(
                    "REGION handover inside a CFG cycle requires iteration identity"
                )
            cyclic_handovers.append(location.point_id)
            handovers_by_iteration.setdefault(location.iteration_id, []).append(location)
        if location.kind in ("direct", "whisper"):
            cyclic_borrows.append(location.point_id)

    for iteration_id, loop_handovers in handovers_by_iteration.items():
        if len(loop_handovers) > 1:
            raise RegionLifetimeCFGError(
                f"REGION iteration {iteration_id!r} contains multiple handovers and "
                "requires explicit intra-iteration ordering"
            )

    handovers = tuple(item for item in locations if item.kind == "handover")
    borrows = tuple(
        item for item in locations if item.kind in ("direct", "whisper")
    )
    for handover in handovers:
        for borrow in borrows:
            if handover.source != borrow.source:
                continue
            if handover.block == borrow.block:
                unsafe = handover.instruction_index < borrow.instruction_index
            else:
                unsafe = _reachable(successors, handover.block, borrow.block)
            if unsafe:
                raise RegionLifetimeCFGError(
                    f"REGION borrow point {borrow.point_id!r} is reachable after "
                    f"handover of owner {handover.source!r}"
                )

    return RegionLifetimeCFGCertificate(
        function=function_name,
        locations=tuple(locations),
        acyclic_points=not (cyclic_borrows or cyclic_handovers),
        cyclic_borrow_point_ids=tuple(cyclic_borrows),
        cyclic_handover_point_ids=tuple(cyclic_handovers),
    )


def certify_checked_region_lifetime_cfg(
    checked_module: object,
    *,
    function: str,
) -> RegionLifetimeCFGCertificate:
    """Build and certify REGION lifetime facts from one checked source module."""
    lifetime = plan_checked_region_lifetime(
        checked_module,
        function=function,
    )

    # The checked-module plan is still validated at its original composition
    # boundary.  CFG generation, however, must never depend on whichever public
    # ``sotlas`` package happened to be imported first in this Python process.
    ownership_sir = getattr(checked_module, "ownership_sir", None)
    validate_region_lifetime_sir(lifetime, ownership_sir)

    checked_sir, _ = build_canonical_checked_ownership_sir(checked_module)
    return certify_region_lifetime_cfg(lifetime, checked_sir.module)


__all__ = [
    "RegionLifetimeCFGError",
    "RegionLifetimeCFGLocation",
    "RegionLifetimeCFGCertificate",
    "certify_region_lifetime_cfg",
    "certify_checked_region_lifetime_cfg",
]
