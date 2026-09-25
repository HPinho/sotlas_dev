"""Backend-neutral SIR facts for privileged Authority ABI boundaries."""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRInstruction


@dataclass
class AuthorityABIInst(SIRInstruction):
    """Source-stable privileged ABI fact; has no runtime effect by itself."""

    symbol: str
    point_id: str
    required_capabilities: tuple[str, ...]

    def __str__(self) -> str:
        capabilities = ", ".join(self.required_capabilities)
        return (
            f"  authority_abi @{self.symbol} [{capabilities}]"
            f" // {self.point_id}"
        )


__all__ = ["AuthorityABIInst"]
