"""Path-sensitive REGION lifetime certification over canonical SIR CFG.

This layer does not create ownership facts.  It consumes a checked
``RegionLifetimePlan`` plus the already generated SIR CFG and proves that the
source-stable REGION handover/direct/whisper points are placed exactly once and
that a borrow of an owner is never reachable after that owner has been handed
over.  Explicit branch terminators are the only control-flow edges; block list
order is never treated as fallthrough.

Lifetime points inside CFG cycles remain fail-closed until iteration identity is
part of the canonical lifetime model.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .region_frontend import plan_checked_region_lifetime
from .region_lifetime import RegionLifetimePlan
from .region_sir import validate_region_lifetime_sir
from .typed_ast import Phase1SemanticError


class RegionLifetimeCFGError(Phase1SemanticError):
    """Raised when REGION lifetime facts cannot be certified on the SIR CFG."""


@dataclass(frozen=True)
class RegionLifetimeCFGLocation:
    point_id: str
    kind: str
    source: str
    block: str
    instruction_index: int


@dataclass(frozen=True)
class RegionLifetimeCFGCertificate:
    function: str
    locations: tuple[RegionLifetimeCFGLocation, ...]
    acyclic_points: bool = True

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


def _expected_points(lifetime: RegionLifetimePlan) -> dict[str, tuple[str, ...]]:
    expected: dict[str, tuple[str, ...]] = {}
    for transfer in lifetime.transfers:
        if transfer.via != "handover" or transfer.point_id is None:
            continue
        point = _required_text(
            transfer.point_id, label="REGION CFG handover point"
        )
        destination = _required_text(
            transfer.destination, label="REGION CFG handover destination"
        )
        expected[point] = ("handover", transfer.source, destination)
    for borrow in lifetime.borrows:
        point = _required_text(borrow.point_id, label="REGION CFG borrow point")
        expected[point] = (
            borrow.mode,
            borrow.source,
            borrow.callee,
            borrow.parameter,
        )
    if len(expected) != len(tuple(expected)):
        raise RegionLifetimeCFGError("REGION CFG point identities must be unique")
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
                mode = "whisper" if instruction_kind == "WhisperBorrowInst" else "direct"
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
            by_point[point].append(
                RegionLifetimeCFGLocation(
                    point_id=point,
                    kind=actual[0],
                    source=source_name,
                    block=block_label,
                    instruction_index=index,
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

    successors = _successors(function)
    for location in locations:
        if _block_is_cyclic(successors, location.block):
            raise RegionLifetimeCFGError(
                "REGION lifetime points inside CFG cycles require iteration identity"
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
        acyclic_points=True,
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
    ownership_sir = getattr(checked_module, "ownership_sir", None)
    validate_region_lifetime_sir(lifetime, ownership_sir)

    from sotlas.sir import generate_checked_ownership_sir

    checked_sir = generate_checked_ownership_sir(checked_module)
    return certify_region_lifetime_cfg(lifetime, checked_sir.module)


__all__ = [
    "RegionLifetimeCFGError",
    "RegionLifetimeCFGLocation",
    "RegionLifetimeCFGCertificate",
    "certify_region_lifetime_cfg",
    "certify_checked_region_lifetime_cfg",
]
