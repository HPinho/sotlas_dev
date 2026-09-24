"""Backend-neutral REGION ownership-transfer facts at typed call sites.

These instructions preserve source-stable interprocedural ownership identity in
SIR. They are semantic facts only: no runtime, ABI, C11 or LLVM behavior is
implied by their presence.
"""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRInstruction, SIRValue


@dataclass
class RegionCallTransferInst(SIRInstruction):
    """One REGION->REGION ownership-taking call argument.

    This is intentionally *not* an OwnershipDomainPointInst: the ownership
    placement pass reserves that class for source markers that it replaces with
    canonical domain-transfer instructions. REGION call transfers are already
    checked semantic facts and must remain independently visible in SIR.
    """

    operation: str
    source_name: str
    destination_name: str
    point_id: str
    source: SIRValue
    callee: str
    parameter: str
    argument_index: int
    source_domain: str
    target_domain: str

    def __post_init__(self) -> None:
        if self.operation != "call_transfer":
            raise ValueError("REGION call transfer requires operation='call_transfer'")
        if not isinstance(self.point_id, str) or not self.point_id.startswith("call@"):
            raise ValueError("REGION call transfer requires source-stable call@ point")
        if self.source_name != self.source.name:
            raise ValueError("REGION call transfer source identity diverged")
        if not self.callee or not self.parameter:
            raise ValueError("REGION call transfer requires callee and parameter identity")
        if self.destination_name != f"{self.callee}.{self.parameter}":
            raise ValueError("REGION call transfer destination identity diverged")
        if self.argument_index < 0:
            raise ValueError("REGION call transfer argument index cannot be negative")
        if self.source_domain != "region" or self.target_domain != "region":
            raise ValueError("REGION call transfer must preserve REGION domain")

    def __str__(self) -> str:
        return (
            f"  region_call_transfer {self.source} -> "
            f"@{self.callee}.{self.parameter} arg#{self.argument_index} "
            f"[{self.source_domain}->{self.target_domain}] // {self.point_id}"
        )


__all__ = ["RegionCallTransferInst"]
