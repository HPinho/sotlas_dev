"""Canonical SIR logical slice facts (M16.4f1)."""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRValue


@dataclass(frozen=True)
class SliceViewFact:
    """Backend-neutral logical slice view over an existing pointer + length pair.

    M16.4f1 deliberately records only semantic representation. Byte size,
    alignment, field offsets, register classes, and calling-convention transport
    remain outside this fact until the aggregate-ABI milestone.
    """

    function: str
    name: str
    element_type: str
    mutable: bool
    data: SIRValue
    length: SIRValue
    point_id: str

    @property
    def logical_type(self) -> str:
        prefix = "&mut " if self.mutable else "&"
        return f"{prefix}[{self.element_type}]"


__all__ = ["SliceViewFact"]
