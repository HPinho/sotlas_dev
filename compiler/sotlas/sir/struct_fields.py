"""Canonical SIR instruction for source-identified struct field projection."""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRInstruction, SIRValue


@dataclass
class StructFieldAddressInst(SIRInstruction):
    """Project one declared field address from a typed struct pointer.

    The instruction carries source/semantic identity only. It deliberately does
    not carry a byte offset; target layout owns that decision.
    """

    base: SIRValue
    result: SIRValue
    struct_name: str
    field_name: str
    field_type: str
    point_id: str

    def __str__(self) -> str:
        return (
            f"  {self.result} = struct_field_address {self.base}."
            f"{self.field_name} [{self.struct_name}] // {self.point_id}"
        )


__all__ = ["StructFieldAddressInst"]
