"""x86-64 SysV emission for the M16.4e1 nullary enum tag representation."""
from __future__ import annotations

from typing import Any

from . import _machine_x86_64_core as _core
from ._machine_x86_64_call_validation import MachineBackendError


def emit_enum_const(
    lines: list[str],
    *,
    function: dict[str, Any],
    instruction: dict[str, Any],
    locations: dict[str, dict[str, Any]],
    enum_layouts: dict[str, Any],
) -> None:
    """Materialize a validated nullary enum discriminant as canonical ``u32``."""
    name = function.get("name")
    if instruction.get("type") != "u32":
        raise MachineBackendError(
            f"function {name!r}: enum_const result must have type 'u32'"
        )
    operands = instruction.get("operands", ())
    if operands not in ((), []):
        raise MachineBackendError(f"function {name!r}: enum_const takes no operands")
    result = instruction.get("result")
    if not isinstance(result, str) or not result:
        raise MachineBackendError(f"function {name!r}: enum_const requires a result")

    attributes = instruction.get("attributes", {})
    enum_name = attributes.get("enum")
    variant_name = attributes.get("variant")
    discriminant = attributes.get("discriminant")
    declaration = enum_layouts.get(enum_name)
    if not isinstance(declaration, dict) or declaration.get("tag_type") != "u32":
        raise MachineBackendError(
            f"function {name!r}: enum_const has no validated enum declaration"
        )
    variants = declaration.get("variants", ())
    expected = None
    for variant in variants:
        if isinstance(variant, dict) and variant.get("name") == variant_name:
            expected = variant.get("discriminant")
            break
    if discriminant != expected or not isinstance(discriminant, int):
        raise MachineBackendError(
            f"function {name!r}: enum_const discriminant does not match declaration"
        )

    lines.append(f"    mov eax, {discriminant}")
    _core._store_value(lines, result, "rax", locations)


__all__ = ["emit_enum_const"]
