"""Consistency bridge between REGION lifetime topology and canonical ownership SIR.

The Phase-1 pipeline already lowers the canonical OwnershipDomainGraph to an
OwnershipModuleSIRPlan.  REGION lifetime planning must not create a second SIR
or reinterpret source facts.  This module only certifies that REGION handovers
and call-scoped direct/whisper borrows are represented identically on both
sides of that existing boundary.

Ordinary ownership moves through calls/returns are intentionally not required
here: they are ownership-trace facts, not OwnershipDomainTransferInst facts in
the current domain SIR contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .region_lifetime import RegionLifetimePlan
from .typed_ast import Phase1SemanticError


class RegionLifetimeSIRError(Phase1SemanticError):
    """Raised when REGION lifetime topology and ownership SIR diverge."""


@dataclass(frozen=True)
class RegionLifetimeSIRBridge:
    function: str
    handover_point_ids: tuple[str, ...]
    whisper_point_ids: tuple[str, ...]
    direct_point_ids: tuple[str, ...]

    @property
    def point_ids(self) -> tuple[str, ...]:
        return (
            self.handover_point_ids
            + self.whisper_point_ids
            + self.direct_point_ids
        )


def _required_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegionLifetimeSIRError(f"{label} requires a non-empty identity")
    return value


def _function_domain_plan(ownership_sir: object, function: str) -> object:
    functions = tuple(getattr(ownership_sir, "functions", ()) or ())
    matches = tuple(
        item for item in functions if getattr(item, "function", None) == function
    )
    if len(matches) != 1:
        raise RegionLifetimeSIRError(
            "REGION lifetime/SIR bridge requires exactly one matching function plan"
        )
    domain = getattr(matches[0], "domain", None)
    if domain is None or not hasattr(domain, "instructions"):
        raise RegionLifetimeSIRError(
            "REGION lifetime/SIR bridge requires a canonical domain SIR plan"
        )
    return domain


def validate_region_lifetime_sir(
    lifetime: RegionLifetimePlan,
    ownership_sir: object,
) -> RegionLifetimeSIRBridge:
    """Certify that checked REGION topology is preserved exactly in domain SIR."""
    if not isinstance(lifetime, RegionLifetimePlan):
        raise RegionLifetimeSIRError(
            "REGION lifetime/SIR bridge requires a RegionLifetimePlan"
        )
    function = _required_text(lifetime.function, label="REGION SIR function")
    domain = _function_domain_plan(ownership_sir, function)

    # Import at the composition boundary so the instruction classes are the
    # same package instances used by Phase1CheckedModule.ownership_sir.
    from sotlas.sir import (
        DirectAccessInst,
        OwnershipDomainTransferInst,
        WhisperBorrowInst,
    )

    expected_handovers = tuple(
        (
            item.source,
            item.destination,
            item.point_id,
        )
        for item in lifetime.transfers
        if item.via == "handover"
    )
    for source, destination, point_id in expected_handovers:
        _required_text(source, label="REGION lifetime handover source")
        _required_text(destination, label="REGION lifetime handover destination")
        identity = _required_text(point_id, label="REGION lifetime handover point")
        if not identity.startswith("handover@"):
            raise RegionLifetimeSIRError(
                "REGION lifetime handover lost canonical source identity"
            )

    expected_whispers = tuple(
        (item.source, item.callee, item.parameter, item.point_id)
        for item in lifetime.borrows
        if item.mode == "whisper"
    )
    expected_directs = tuple(
        (item.source, item.callee, item.parameter, item.point_id)
        for item in lifetime.borrows
        if item.mode == "direct"
    )
    unknown_modes = tuple(
        item.mode
        for item in lifetime.borrows
        if item.mode not in ("whisper", "direct")
    )
    if unknown_modes:
        raise RegionLifetimeSIRError(
            "REGION lifetime plan contains an unsupported borrow mode"
        )

    actual_handovers: list[tuple[str, str, str]] = []
    actual_whispers: list[tuple[str, str, str, str]] = []
    actual_directs: list[tuple[str, str, str, str]] = []

    for instruction in tuple(domain.instructions):
        if isinstance(instruction, OwnershipDomainTransferInst):
            if (
                getattr(instruction, "source_domain", None) != "region"
                and getattr(instruction, "target_domain", None) != "region"
            ):
                continue
            if (
                instruction.operation != "handover"
                or instruction.source_domain != "region"
                or instruction.target_domain != "region"
                or instruction.destination is None
            ):
                raise RegionLifetimeSIRError(
                    "REGION domain SIR contains an invalid ownership transfer"
                )
            point_id = _required_text(
                instruction.point_id,
                label="REGION SIR handover point",
            )
            if not point_id.startswith("handover@"):
                raise RegionLifetimeSIRError(
                    "REGION SIR handover lost canonical source identity"
                )
            actual_handovers.append(
                (
                    _required_text(
                        instruction.source.name,
                        label="REGION SIR handover source",
                    ),
                    _required_text(
                        instruction.destination.name,
                        label="REGION SIR handover destination",
                    ),
                    point_id,
                )
            )
            continue

        if isinstance(instruction, WhisperBorrowInst):
            if instruction.source_domain != "region":
                continue
            point_id = _required_text(
                instruction.point_id,
                label="REGION SIR whisper point",
            )
            if not point_id.startswith("whisper@"):
                raise RegionLifetimeSIRError(
                    "REGION SIR whisper borrow lost canonical source identity"
                )
            actual_whispers.append(
                (
                    _required_text(instruction.source.name, label="REGION whisper source"),
                    _required_text(instruction.callee, label="REGION whisper callee"),
                    _required_text(instruction.parameter, label="REGION whisper parameter"),
                    point_id,
                )
            )
            continue

        if isinstance(instruction, DirectAccessInst):
            if instruction.source_domain != "region":
                continue
            point_id = _required_text(
                instruction.point_id,
                label="REGION SIR direct point",
            )
            if not point_id.startswith("direct@"):
                raise RegionLifetimeSIRError(
                    "REGION SIR direct access lost canonical source identity"
                )
            actual_directs.append(
                (
                    _required_text(instruction.source.name, label="REGION direct source"),
                    _required_text(instruction.callee, label="REGION direct callee"),
                    _required_text(instruction.parameter, label="REGION direct parameter"),
                    point_id,
                )
            )

    if tuple(actual_handovers) != expected_handovers:
        raise RegionLifetimeSIRError(
            "REGION lifetime handovers diverged from canonical ownership SIR"
        )
    if tuple(actual_whispers) != expected_whispers:
        raise RegionLifetimeSIRError(
            "REGION whisper lifetime edges diverged from canonical ownership SIR"
        )
    if tuple(actual_directs) != expected_directs:
        raise RegionLifetimeSIRError(
            "REGION direct lifetime edges diverged from canonical ownership SIR"
        )

    all_points = tuple(
        point
        for group in (actual_handovers, actual_whispers, actual_directs)
        for point in (group_item[-1] for group_item in group)
    )
    if len(set(all_points)) != len(all_points):
        raise RegionLifetimeSIRError(
            "REGION lifetime/SIR point identities must be globally unique"
        )

    return RegionLifetimeSIRBridge(
        function=function,
        handover_point_ids=tuple(item[-1] for item in actual_handovers),
        whisper_point_ids=tuple(item[-1] for item in actual_whispers),
        direct_point_ids=tuple(item[-1] for item in actual_directs),
    )


__all__ = [
    "RegionLifetimeSIRError",
    "RegionLifetimeSIRBridge",
    "validate_region_lifetime_sir",
]
