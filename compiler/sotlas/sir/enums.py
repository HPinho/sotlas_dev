"""Canonical SIR facts and instructions for enum representation."""
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


@dataclass(frozen=True)
class PayloadEnumVariantFact:
    """One explicit tagged-union variant and its optional logical payload type."""

    name: str
    discriminant: int
    payload_type: str | None = None


@dataclass(frozen=True)
class PayloadEnumFact:
    """Backend-neutral declaration facts for one explicit scalar-payload enum."""

    name: str
    tag_type: str
    storage: str
    variants: tuple[PayloadEnumVariantFact, ...]


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


@dataclass
class EnumConstructInst(SIRInstruction):
    """Construct one logical tagged-union enum value from a checked payload.

    M16.4e3 keeps the canonical tag, payload SSA value, and nominal enum
    identity together without selecting byte offsets, alignment, or an ABI
    transport class. Machine backends must therefore keep nominal enum returns
    fail-closed until the later aggregate-ABI milestone.
    """

    enum_name: str
    variant: str
    discriminant: int
    payload: SIRValue
    payload_type: str
    result: SIRValue
    point_id: str

    def __str__(self) -> str:
        return (
            f"  {self.result} = enum_construct "
            f"{self.enum_name}::{self.variant}({self.payload}) "
            f"tag={self.discriminant} // {self.point_id}"
        )


__all__ = [
    "EnumConstInst",
    "EnumConstructInst",
    "NullaryEnumFact",
    "NullaryEnumVariantFact",
    "PayloadEnumFact",
    "PayloadEnumVariantFact",
]
