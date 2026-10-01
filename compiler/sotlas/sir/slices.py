"""Canonical SIR logical slice facts and address projections."""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRInstruction, SIRValue


@dataclass(frozen=True)
class SliceViewFact:
    """Backend-neutral logical slice view over an existing pointer + length pair.

    Byte size, alignment, field offsets, register classes, and calling-convention
    transport remain outside this fact until the aggregate-ABI milestone.
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


@dataclass
class SliceElementAddressInst(SIRInstruction):
    """Project one checked slice element address without target byte layout.

    ``length`` remains an SSA ``usize`` value. A preceding ``BoundsCheckInst``
    proves ``index < length``; this instruction carries only logical element
    identity and therefore does not choose stride, byte offset, ABI class, or
    machine trap instruction.
    """

    base: SIRValue
    index: SIRValue
    length: SIRValue
    result: SIRValue
    element_type: str
    bounds_policy: str
    point_id: str

    def __str__(self) -> str:
        return (
            f"  {self.result} = slice_address {self.base}[{self.index}] "
            f"len={self.length} element={self.element_type} "
            f"bounds={self.bounds_policy} // {self.point_id}"
        )


__all__ = ["SliceElementAddressInst", "SliceViewFact"]
