"""Canonical intra-iteration ordering for REGION ownership-taking operations.

Ownership-taking REGION calls and REGION handovers already carry the same
source-stable ``iteration_id`` when they are placed inside one canonical SIR
cycle.  This layer composes those independently certified facts and proves only
their *within-iteration* relation.

The proof deliberately removes exactly the canonical backedge that names the
iteration before computing reachability.  Therefore reachability through the
next loop iteration is never mistaken for ordering inside the current one.
This certificate does not make repeated ownership transfer legal by itself and
does not add runtime/backend behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_sir import load_canonical_sir
from .region_call_cfg import RegionCallCFGCertificate
from .region_cfg import (
    RegionLifetimeCFGCertificate,
    _cut_iteration_backedge,
    _reachable,
    _same_cycle,
    _successors,
)
from .typed_ast import Phase1SemanticError


class RegionIterationOrderError(Phase1SemanticError):
    """Raised when canonical intra-iteration ownership order cannot be proven."""


@dataclass(frozen=True)
class RegionIterationOwnershipPoint:
    function: str
    point_id: str
    kind: str
    block: str
    instruction_index: int
    iteration_id: str


@dataclass(frozen=True)
class RegionIterationOwnershipRelation:
    function: str
    iteration_id: str
    first_point_id: str
    second_point_id: str
    relation: str


@dataclass(frozen=True)
class RegionIterationOwnershipCertificate:
    function: str
    points: tuple[RegionIterationOwnershipPoint, ...]
    relations: tuple[RegionIterationOwnershipRelation, ...]

    def points_for(
        self, iteration_id: str
    ) -> tuple[RegionIterationOwnershipPoint, ...]:
        return tuple(item for item in self.points if item.iteration_id == iteration_id)


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegionIterationOrderError(f"{label} requires a non-empty identity")
    return value


def _unwrap_module(value: object):
    sir = load_canonical_sir()
    module = getattr(value, "module", value)
    if not isinstance(module, sir.SIRModule):
        raise RegionIterationOrderError(
            "REGION iteration ordering requires canonical SIRModule or CheckedOwnershipSIR"
        )
    return sir, module


def _find_function(module: object, function_name: str):
    matches = tuple(
        item
        for item in tuple(getattr(module, "functions", ()) or ())
        if getattr(item, "name", None) == function_name
    )
    if len(matches) != 1:
        raise RegionIterationOrderError(
            f"REGION iteration ordering requires exactly one function {function_name!r}"
        )
    return matches[0]


def _validate_point_location(
    sir,
    function: object,
    point: RegionIterationOwnershipPoint,
) -> None:
    blocks = {
        getattr(block, "label", None): block
        for block in tuple(getattr(function, "blocks", ()) or ())
    }
    block = blocks.get(point.block)
    if block is None:
        raise RegionIterationOrderError(
            f"REGION iteration point {point.point_id!r} refers to unknown block {point.block!r}"
        )
    instructions = tuple(getattr(block, "instructions", ()) or ())
    if point.instruction_index < 0 or point.instruction_index >= len(instructions):
        raise RegionIterationOrderError(
            f"REGION iteration point {point.point_id!r} has invalid instruction index"
        )
    instruction = instructions[point.instruction_index]
    if point.kind == "call":
        if not isinstance(instruction, sir.CallInst):
            raise RegionIterationOrderError(
                f"REGION iteration call {point.point_id!r} no longer refers to a CallInst"
            )
    elif point.kind == "handover":
        if not isinstance(instruction, sir.OwnershipDomainTransferInst):
            raise RegionIterationOrderError(
                f"REGION iteration handover {point.point_id!r} no longer refers to a domain transfer"
            )
        if (
            getattr(instruction, "operation", None) != "handover"
            or getattr(instruction, "source_domain", None) != "region"
            or getattr(instruction, "target_domain", None) != "region"
            or getattr(instruction, "point_id", None) != point.point_id
        ):
            raise RegionIterationOrderError(
                f"REGION iteration handover {point.point_id!r} diverged from canonical SIR"
            )
    else:
        raise RegionIterationOrderError(
            f"unknown REGION iteration ownership point kind {point.kind!r}"
        )


def _relation(
    function: object,
    successors: dict[str, tuple[str, ...]],
    first: RegionIterationOwnershipPoint,
    second: RegionIterationOwnershipPoint,
) -> RegionIterationOwnershipRelation:
    if first.iteration_id != second.iteration_id:
        raise RegionIterationOrderError(
            "REGION intra-iteration ordering requires matching iteration identities"
        )
    iteration_id = first.iteration_id
    if not _same_cycle(successors, first.block, second.block):
        raise RegionIterationOrderError(
            f"REGION iteration {iteration_id!r} points do not belong to one CFG cycle"
        )

    cut = _cut_iteration_backedge(
        function,
        successors,
        iteration_id,
        error_type=RegionIterationOrderError,
        subject="REGION iteration",
    )
    if first.block == second.block:
        if first.instruction_index == second.instruction_index:
            raise RegionIterationOrderError(
                f"REGION iteration {iteration_id!r} has overlapping ownership points"
            )
        if first.instruction_index < second.instruction_index:
            before, after = first, second
        else:
            before, after = second, first
        relation = "ordered_path"
    else:
        forward = _reachable(cut, first.block, second.block)
        reverse = _reachable(cut, second.block, first.block)
        if forward and reverse:
            raise RegionIterationOrderError(
                f"REGION iteration {iteration_id!r} remains cyclic after canonical backedge cut"
            )
        if forward:
            before, after = first, second
            relation = "ordered_path"
        elif reverse:
            before, after = second, first
            relation = "ordered_path"
        else:
            before, after = first, second
            relation = "path_disjoint"

    return RegionIterationOwnershipRelation(
        function=first.function,
        iteration_id=iteration_id,
        first_point_id=before.point_id,
        second_point_id=after.point_id,
        relation=relation,
    )


def certify_region_iteration_order(
    call_cfg: RegionCallCFGCertificate,
    lifetime_cfg: RegionLifetimeCFGCertificate,
    sir_module: object,
) -> RegionIterationOwnershipCertificate:
    """Certify cross-kind call/handover order within one function's loop iterations."""
    if not isinstance(call_cfg, RegionCallCFGCertificate):
        raise RegionIterationOrderError(
            "REGION iteration ordering requires a RegionCallCFGCertificate"
        )
    if not isinstance(lifetime_cfg, RegionLifetimeCFGCertificate):
        raise RegionIterationOrderError(
            "REGION iteration ordering requires a RegionLifetimeCFGCertificate"
        )

    sir, module = _unwrap_module(sir_module)
    function_name = _required_text(
        lifetime_cfg.function, label="REGION iteration function"
    )
    function = _find_function(module, function_name)
    successors = _successors(function)

    points: list[RegionIterationOwnershipPoint] = []
    for point in call_cfg.points:
        if point.function != function_name or point.iteration_id is None:
            continue
        points.append(
            RegionIterationOwnershipPoint(
                function=function_name,
                point_id=_required_text(
                    point.point_id, label="REGION iteration call point"
                ),
                kind="call",
                block=_required_text(point.block, label="REGION iteration call block"),
                instruction_index=point.instruction_index,
                iteration_id=_required_text(
                    point.iteration_id, label="REGION call iteration"
                ),
            )
        )

    for location in lifetime_cfg.locations:
        if location.kind != "handover" or location.iteration_id is None:
            continue
        points.append(
            RegionIterationOwnershipPoint(
                function=function_name,
                point_id=_required_text(
                    location.point_id, label="REGION iteration handover point"
                ),
                kind="handover",
                block=_required_text(
                    location.block, label="REGION iteration handover block"
                ),
                instruction_index=location.instruction_index,
                iteration_id=_required_text(
                    location.iteration_id, label="REGION handover iteration"
                ),
            )
        )

    identities = tuple(item.point_id for item in points)
    if len(set(identities)) != len(identities):
        raise RegionIterationOrderError(
            "REGION iteration ordering contains duplicate ownership point identities"
        )

    for point in points:
        _validate_point_location(sir, function, point)

    call_points = tuple(item for item in points if item.kind == "call")
    handover_points = tuple(item for item in points if item.kind == "handover")
    for call in call_points:
        for handover in handover_points:
            if not _same_cycle(successors, call.block, handover.block):
                continue
            if call.iteration_id != handover.iteration_id:
                raise RegionIterationOrderError(
                    "REGION intra-iteration ordering requires matching iteration identities"
                )

    grouped: dict[str, list[RegionIterationOwnershipPoint]] = {}
    for point in points:
        grouped.setdefault(point.iteration_id, []).append(point)

    relations: list[RegionIterationOwnershipRelation] = []
    for iteration_points in grouped.values():
        for first_index, first in enumerate(iteration_points):
            for second in iteration_points[first_index + 1 :]:
                relations.append(
                    _relation(function, successors, first, second)
                )

    return RegionIterationOwnershipCertificate(
        function=function_name,
        points=tuple(points),
        relations=tuple(relations),
    )


__all__ = [
    "RegionIterationOrderError",
    "RegionIterationOwnershipPoint",
    "RegionIterationOwnershipRelation",
    "RegionIterationOwnershipCertificate",
    "certify_region_iteration_order",
]
