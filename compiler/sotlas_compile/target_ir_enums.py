"""Backend-neutral nullary enum representation and source bridge for M16.4e1/e2.

The enum slices deliberately model only explicit, payload-free variants. Target
IR carries logical enum/variant identity plus a canonical ``u32`` tag; target
byte size/alignment and nominal aggregate ABI classification remain outside this
contract.
"""
from __future__ import annotations

from typing import Any


class TargetIREnumError(ValueError):
    """Malformed M16.4 nullary enum representation."""


_FORBIDDEN_LAYOUT_KEYS = frozenset({
    "size_bytes",
    "alignment_bytes",
    "offset_bytes",
    "payload_offset_bytes",
    "payload_size_bytes",
    "payload_alignment_bytes",
    "payload_type",
})


def _enum_declarations(target_ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    declarations = target_ir.get("enum_layouts", {})
    if not isinstance(declarations, dict):
        raise TargetIREnumError("enum_layouts must be a mapping")
    normalized: dict[str, dict[str, Any]] = {}
    for enum_name, declaration in declarations.items():
        if not isinstance(enum_name, str) or not enum_name:
            raise TargetIREnumError("enum declaration requires a non-empty name")
        if not isinstance(declaration, dict):
            raise TargetIREnumError(f"enum {enum_name!r} declaration must be a mapping")
        forbidden = _FORBIDDEN_LAYOUT_KEYS & set(declaration)
        if forbidden:
            raise TargetIREnumError(
                f"enum {enum_name!r} cannot carry target byte layout or payload metadata"
            )
        if declaration.get("tag_type") != "u32":
            raise TargetIREnumError(
                f"enum {enum_name!r} must use canonical nullary tag_type 'u32'"
            )
        variants = declaration.get("variants")
        if not isinstance(variants, list) or not variants:
            raise TargetIREnumError(f"enum {enum_name!r} requires variants")

        by_name: dict[str, int] = {}
        seen_discriminants: set[int] = set()
        for variant in variants:
            if not isinstance(variant, dict):
                raise TargetIREnumError(
                    f"enum {enum_name!r} has a malformed variant declaration"
                )
            forbidden = _FORBIDDEN_LAYOUT_KEYS & set(variant)
            if forbidden:
                raise TargetIREnumError(
                    f"enum {enum_name!r} variants cannot carry payload or target byte layout"
                )
            variant_name = variant.get("name")
            discriminant = variant.get("discriminant")
            if not isinstance(variant_name, str) or not variant_name:
                raise TargetIREnumError(
                    f"enum {enum_name!r} variant requires a non-empty name"
                )
            if variant_name in by_name:
                raise TargetIREnumError(
                    f"enum {enum_name!r} has duplicate variant {variant_name!r}"
                )
            if (
                not isinstance(discriminant, int)
                or isinstance(discriminant, bool)
                or discriminant < 0
                or discriminant > 0xFFFFFFFF
            ):
                raise TargetIREnumError(
                    f"enum {enum_name!r} variant {variant_name!r} has invalid u32 discriminant"
                )
            if discriminant in seen_discriminants:
                raise TargetIREnumError(
                    f"enum {enum_name!r} has duplicate discriminant {discriminant}"
                )
            by_name[variant_name] = discriminant
            seen_discriminants.add(discriminant)

        normalized[enum_name] = {
            "tag_type": "u32",
            "variants": by_name,
        }
    return normalized


def attach_target_ir_enum_declarations(
    target_ir: dict[str, Any],
    sir_module: Any,
) -> dict[str, Any]:
    """Carry source-proven nullary enum declarations from canonical SIR."""

    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise TargetIREnumError("enum source bridge requires Target IR v1")
    facts = tuple(getattr(sir_module, "nullary_enum_facts", ()) or ())
    if not facts:
        return target_ir

    existing = target_ir.get("enum_layouts")
    if existing not in (None, {}):
        raise TargetIREnumError(
            "enum source bridge refuses to overwrite existing enum_layouts"
        )

    declarations: dict[str, dict[str, Any]] = {}
    for fact in facts:
        if type(fact).__name__ != "NullaryEnumFact":
            raise TargetIREnumError(
                "canonical SIR contains malformed nullary enum declaration"
            )
        enum_name = getattr(fact, "name", None)
        tag_type = getattr(fact, "tag_type", None)
        variants = tuple(getattr(fact, "variants", ()) or ())
        if (
            not isinstance(enum_name, str)
            or not enum_name
            or enum_name in declarations
            or tag_type != "u32"
            or not variants
        ):
            raise TargetIREnumError(
                "canonical SIR contains malformed nullary enum declaration"
            )

        lowered_variants = []
        for variant in variants:
            if type(variant).__name__ != "NullaryEnumVariantFact":
                raise TargetIREnumError(
                    f"enum {enum_name!r} contains malformed SIR variant facts"
                )
            lowered_variants.append({
                "name": getattr(variant, "name", None),
                "discriminant": getattr(variant, "discriminant", None),
            })
        declarations[enum_name] = {
            "tag_type": "u32",
            "variants": lowered_variants,
        }

    target_ir["enum_layouts"] = declarations
    _enum_declarations(target_ir)
    return target_ir


def validate_target_ir_enum_representation(target_ir: dict[str, Any]) -> None:
    """Validate nullary enum declarations and ``enum_const`` materialization."""
    if not isinstance(target_ir, dict):
        raise TargetIREnumError("Target IR must be a mapping")
    declarations = _enum_declarations(target_ir)

    for function in target_ir.get("functions", ()):
        if not isinstance(function, dict):
            continue
        function_name = function.get("name")
        for block in function.get("blocks", ()):
            if not isinstance(block, dict):
                continue
            for instruction in block.get("instructions", ()):
                if not isinstance(instruction, dict) or instruction.get("op") != "enum_const":
                    continue
                if instruction.get("type") != "u32":
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const result must have type 'u32'"
                    )
                operands = instruction.get("operands", ())
                if operands not in ((), []):
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const takes no operands"
                    )
                result = instruction.get("result")
                if not isinstance(result, str) or not result:
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const requires a result"
                    )
                attributes = instruction.get("attributes", {})
                if not isinstance(attributes, dict):
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const attributes must be a mapping"
                    )
                forbidden = _FORBIDDEN_LAYOUT_KEYS & set(attributes)
                if forbidden:
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const cannot carry payload or target byte layout"
                    )
                enum_name = attributes.get("enum")
                variant_name = attributes.get("variant")
                discriminant = attributes.get("discriminant")
                declaration = declarations.get(enum_name)
                if declaration is None:
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const references unknown enum {enum_name!r}"
                    )
                expected = declaration["variants"].get(variant_name)
                if expected is None:
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const references unknown variant {variant_name!r}"
                    )
                if discriminant != expected:
                    raise TargetIREnumError(
                        f"function {function_name!r}: enum_const discriminant does not match declaration"
                    )


__all__ = [
    "TargetIREnumError",
    "attach_target_ir_enum_declarations",
    "validate_target_ir_enum_representation",
]
