"""Canonical SIR facts and instruction for nullary enum tag materialization."""
from __future__ import annotations

from dataclasses import dataclass

from .instructions import SIRInstruction, SIRValue


@dataclass(frozen=True)
class NullaryEnumVariantFact:
    """One source-proven payload-free variant and its canonical tag."""

    name: str
    discriminant: int


@dataclass(frozen=True)
class NullaryEnumFact:
    """Backend-neutral declaration facts for one explicit nullary enum."""

    name: str
    tag_type: str
    variants: tuple[NullaryEnumVariantFact, ...]


@dataclass
class EnumConstInst(SIRInstruction):
    """Materialize one source-proven nullary enum variant as its canonical tag.

    The instruction keeps enum and variant identity in canonical SIR while the
    physical value remains the e1 ``u32`` tag. Payload layout, byte size,
    alignment, and nominal aggregate ABI classification are intentionally not
    represented by this slice.
    """

    enum_name: str
    variant: str
    discriminant: int
    result: SIRValue
    point_id: str

    def __str__(self) -> str:
        return (
            f"  {self.result} = enum_const "
            f"{self.enum_name}::{self.variant}({self.discriminant}) "
            f"// {self.point_id}"
        )


__all__ = [
    "EnumConstInst",
    "NullaryEnumFact",
    "NullaryEnumVariantFact",
]
