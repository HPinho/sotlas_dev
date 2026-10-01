"""Canonical SIR instruction for fixed-array element address projection."""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRInstruction, SIRValue


@dataclass
class FixedArrayElementAddressInst(SIRInstruction):
    """Project one constant-index element address from a fixed-array pointer.

    The instruction carries logical array identity only: element type, declared
    length, and compile-time index. It deliberately carries no byte stride or
    offset; the selected target backend owns physical layout.
    """

    base: SIRValue
    result: SIRValue
    element_type: str
    length: int
    index: int
    point_id: str

    def __str__(self) -> str:
        return (
            f"  {self.result} = fixed_array_address {self.base}[{self.index}] "
            f"[{self.element_type}; {self.length}] // {self.point_id}"
        )


__all__ = ["FixedArrayElementAddressInst"]
