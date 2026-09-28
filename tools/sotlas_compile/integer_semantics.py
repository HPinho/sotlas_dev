"""Backend-neutral integer arithmetic semantics for Sotlas.

This module makes overflow behavior explicit instead of inheriting backend
behavior.  It intentionally contains no C/LLVM-specific logic: callers choose
one of the language-level policies and receive the same result on every
backend.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntegerSemanticsError(ValueError):
    """Raised when an integer operation is outside the supported contract."""


class IntegerOverflowError(IntegerSemanticsError):
    """Raised when ``checked`` arithmetic cannot represent its result."""


class OverflowMode(str, Enum):
    CHECKED = "checked"
    WRAPPING = "wrapping"
    SATURATING = "saturating"


@dataclass(frozen=True)
class IntegerTypeSemantics:
    type_name: str
    bits: int
    signed: bool
    minimum: int
    maximum: int


@dataclass(frozen=True)
class IntegerArithmeticResult:
    value: int
    overflowed: bool
    mode: OverflowMode
    type_name: str


_FIXED_TYPES: dict[str, tuple[int, bool]] = {
    "u8": (8, False),
    "u16": (16, False),
    "u32": (32, False),
    "u64": (64, False),
    "i8": (8, True),
    "i16": (16, True),
    "i32": (32, True),
    "i64": (64, True),
}


def integer_type_semantics(
    type_name: str,
    *,
    pointer_bits: int = 64,
) -> IntegerTypeSemantics:
    """Return the canonical range for a Sotlas integer type.

    ``usize``/``isize`` are target-sized and therefore require an explicit,
    validated pointer width.  The preview currently supports 32- and 64-bit
    target widths here; target selection remains responsible for choosing the
    real width.
    """

    if type_name in {"usize", "isize"}:
        if pointer_bits not in {32, 64}:
            raise IntegerSemanticsError(
                f"unsupported pointer width for {type_name}: {pointer_bits}"
            )
        bits = pointer_bits
        signed = type_name == "isize"
    else:
        spec = _FIXED_TYPES.get(type_name)
        if spec is None:
            raise IntegerSemanticsError(
                f"unsupported Sotlas integer type: {type_name!r}"
            )
        bits, signed = spec

    if signed:
        minimum = -(1 << (bits - 1))
        maximum = (1 << (bits - 1)) - 1
    else:
        minimum = 0
        maximum = (1 << bits) - 1
    return IntegerTypeSemantics(type_name, bits, signed, minimum, maximum)


def _require_operand(value: int, spec: IntegerTypeSemantics, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if not spec.minimum <= value <= spec.maximum:
        raise IntegerSemanticsError(
            f"{name}={value} is outside the range of {spec.type_name}"
        )
    return value


def _mathematical_result(operation: str, left: int, right: int) -> int:
    if operation == "add":
        return left + right
    if operation == "sub":
        return left - right
    if operation == "mul":
        return left * right
    raise IntegerSemanticsError(
        f"unsupported integer arithmetic operation: {operation!r}"
    )


def _wrap(value: int, spec: IntegerTypeSemantics) -> int:
    modulus = 1 << spec.bits
    wrapped = value % modulus
    if spec.signed and wrapped >= (1 << (spec.bits - 1)):
        wrapped -= modulus
    return wrapped


def evaluate_integer_binary(
    operation: str,
    left: int,
    right: int,
    type_name: str,
    mode: OverflowMode | str,
    *,
    pointer_bits: int = 64,
) -> IntegerArithmeticResult:
    """Evaluate one typed Sotlas integer operation with explicit overflow.

    ``checked`` rejects overflow, ``wrapping`` uses the type's finite bit
    representation, and ``saturating`` clamps to the nearest representable
    endpoint.  This function never relies on C signed-overflow behavior.
    """

    try:
        normalized_mode = mode if isinstance(mode, OverflowMode) else OverflowMode(mode)
    except ValueError as exc:
        raise IntegerSemanticsError(f"unsupported overflow mode: {mode!r}") from exc

    spec = integer_type_semantics(type_name, pointer_bits=pointer_bits)
    lhs = _require_operand(left, spec, "left operand")
    rhs = _require_operand(right, spec, "right operand")
    mathematical = _mathematical_result(operation, lhs, rhs)
    overflowed = not spec.minimum <= mathematical <= spec.maximum

    if normalized_mode is OverflowMode.CHECKED:
        if overflowed:
            raise IntegerOverflowError(
                f"checked {operation} overflows {type_name}: {left}, {right}"
            )
        value = mathematical
    elif normalized_mode is OverflowMode.WRAPPING:
        value = _wrap(mathematical, spec)
    else:
        value = min(spec.maximum, max(spec.minimum, mathematical))

    return IntegerArithmeticResult(
        value=value,
        overflowed=overflowed,
        mode=normalized_mode,
        type_name=type_name,
    )
