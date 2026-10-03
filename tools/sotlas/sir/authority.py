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
    arguments: list[object] | None = None
    result: object | None = None

    def __str__(self) -> str:
        capabilities = ", ".join(self.required_capabilities)
        prefix = f"{self.result} = " if self.result else ""
        arguments = ", ".join(map(str, self.arguments or ()))
        return (
            f"  {prefix}authority_abi @{self.symbol}({arguments}) "
            f"[{capabilities}] // {self.point_id}"
        )


__all__ = ["AuthorityABIInst"]
