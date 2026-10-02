"""Explicit backend-neutral nominal enum payload facts for M16.4h2c1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .typed_ast import lower_module_enum_layouts


class NominalEnumPayloadError(ValueError):
    """Malformed or contradictory h2c1 nominal enum payload facts."""


_SCALARS = frozenset({
    "bool", "u8", "i8", "u16", "i16", "u32", "i32",
    "u64", "i64", "usize", "isize", "f32", "f64",
})
_PHYSICAL_KEYS = frozenset({
    "size_bytes", "alignment_bytes", "offset_bytes",
    "payload_offset_bytes", "payload_size_bytes", "payload_alignment_bytes",
    "abi_class", "register_class",
})


@dataclass(frozen=True)
class NominalEnumPayloadVariantFact:
    name: str
    discriminant: int
    payload_type: str | None = None
    payload_representation: str | None = None


@dataclass(frozen=True)
class NominalEnumPayloadFact:
    enum_name: str
    tag_type: str
    storage: str
    variants: tuple[NominalEnumPayloadVariantFact, ...]


def _payload_shape(type_info: Any, structs: frozenset[str]) -> tuple[str, str] | None:
    if type_info is None:
        return None
    if any(bool(getattr(type_info, key, False)) for key in ("pointer", "is_reference", "is_array")):
        raise NominalEnumPayloadError("h2c1 nominal enum payloads must be direct by-value values")
    name = getattr(type_info, "name", None)
    if not isinstance(name, str) or not name:
        raise NominalEnumPayloadError("h2c1 enum payload has a malformed checked type")
    if name in _SCALARS:
        return name, "scalar"
    if name in structs:
        return name, "nominal_struct"
    raise NominalEnumPayloadError(
        f"h2c1 cannot classify enum payload type {name!r} as scalar or nominal struct"
    )


def collect_nominal_enum_payload_facts(typed_module: Any) -> tuple[NominalEnumPayloadFact, ...]:
    if typed_module is None:
        raise NominalEnumPayloadError("nominal enum payload collection requires a checked TypedModule")
    structs = frozenset(
        name for item in tuple(getattr(typed_module, "structs", ()) or ())
        if isinstance((name := getattr(item, "name", None)), str) and name
    )
    facts: list[NominalEnumPayloadFact] = []
    for layout in lower_module_enum_layouts(typed_module):
        enum_name = getattr(layout, "enum_name", None)
        variants = tuple(getattr(layout, "variants", ()) or ())
        if not isinstance(enum_name, str) or not enum_name or not variants:
            raise NominalEnumPayloadError("checked enum layout is malformed for h2c1")
        if getattr(layout, "storage", None) != "tagged_union":
            continue
        lowered: list[NominalEnumPayloadVariantFact] = []
        seen_names: set[str] = set()
        seen_tags: set[int] = set()
        saw_nominal = False
        for variant in variants:
            name = getattr(variant, "name", None)
            tag = getattr(variant, "tag", None)
            if (
                not isinstance(name, str) or not name or name in seen_names
                or not isinstance(tag, int) or isinstance(tag, bool)
                or tag < 0 or tag > 0xFFFFFFFF or tag in seen_tags
            ):
                raise NominalEnumPayloadError(f"enum {enum_name!r} has malformed checked variant facts")
            seen_names.add(name)
            seen_tags.add(tag)
            shape = _payload_shape(getattr(variant, "payload_type", None), structs)
            if shape is None:
                lowered.append(NominalEnumPayloadVariantFact(name, tag))
                continue
            payload_type, representation = shape
            saw_nominal |= representation == "nominal_struct"
            lowered.append(NominalEnumPayloadVariantFact(name, tag, payload_type, representation))
        if saw_nominal:
            facts.append(NominalEnumPayloadFact(enum_name, "u32", "tagged_union", tuple(lowered)))
    return tuple(facts)


def attach_checked_nominal_enum_payloads(semantic: Any, sir_module: Any) -> tuple[NominalEnumPayloadFact, ...]:
    facts = collect_nominal_enum_payload_facts(getattr(semantic, "typed_module", None))
    existing = tuple(getattr(sir_module, "nominal_enum_payload_facts", ()) or ())
    if existing and existing != facts:
        raise NominalEnumPayloadError("canonical SIR already contains conflicting nominal enum payload facts")
    sir_module.nominal_enum_payload_facts = facts
    return facts


def _lower_fact(fact: NominalEnumPayloadFact) -> dict[str, Any]:
    if not isinstance(fact, NominalEnumPayloadFact) or fact.tag_type != "u32" or fact.storage != "tagged_union":
        raise NominalEnumPayloadError("canonical SIR contains malformed nominal enum payload facts")
    variants: list[dict[str, Any]] = []
    saw_nominal = False
    for variant in fact.variants:
        item: dict[str, Any] = {"name": variant.name, "discriminant": variant.discriminant}
        if variant.payload_type is not None:
            if variant.payload_representation not in {"scalar", "nominal_struct"}:
                raise NominalEnumPayloadError("canonical SIR contains invalid nominal enum payload representation")
            item["payload_type"] = variant.payload_type
            item["payload_representation"] = variant.payload_representation
            saw_nominal |= variant.payload_representation == "nominal_struct"
        elif variant.payload_representation is not None:
            raise NominalEnumPayloadError("canonical SIR contains payload representation without payload")
        variants.append(item)
    if not saw_nominal:
        raise NominalEnumPayloadError(f"enum {fact.enum_name!r} h2c1 fact contains no nominal payload")
    return {"tag_type": "u32", "storage": "tagged_union", "variants": variants}


def validate_target_ir_nominal_enum_payloads(target_ir: dict[str, Any]) -> None:
    declarations = target_ir.get("nominal_enum_payloads", {})
    if not isinstance(declarations, dict):
        raise NominalEnumPayloadError("Target IR nominal_enum_payloads must be a mapping")
    for enum_name, declaration in declarations.items():
        if not isinstance(enum_name, str) or not enum_name or not isinstance(declaration, dict):
            raise NominalEnumPayloadError("Target IR nominal enum payload declaration is malformed")
        if _PHYSICAL_KEYS & set(declaration):
            raise NominalEnumPayloadError(
                f"enum {enum_name!r} h2c1 declaration cannot carry physical layout or ABI metadata"
            )
        if declaration.get("tag_type") != "u32" or declaration.get("storage") != "tagged_union":
            raise NominalEnumPayloadError(f"enum {enum_name!r} h2c1 declaration has invalid logical storage")
        variants = declaration.get("variants")
        if not isinstance(variants, list) or not variants:
            raise NominalEnumPayloadError(f"enum {enum_name!r} h2c1 declaration requires variants")
        saw_nominal = False
        for variant in variants:
            if not isinstance(variant, dict) or _PHYSICAL_KEYS & set(variant):
                raise NominalEnumPayloadError(f"enum {enum_name!r} has malformed or physical h2c1 variant metadata")
            payload_type = variant.get("payload_type")
            representation = variant.get("payload_representation")
            if payload_type is None:
                if representation is not None:
                    raise NominalEnumPayloadError(f"enum {enum_name!r} has representation without payload")
                continue
            if not isinstance(payload_type, str) or not payload_type or representation not in {"scalar", "nominal_struct"}:
                raise NominalEnumPayloadError(f"enum {enum_name!r} has invalid h2c1 payload identity")
            saw_nominal |= representation == "nominal_struct"
        if not saw_nominal:
            raise NominalEnumPayloadError(f"enum {enum_name!r} h2c1 declaration contains no nominal payload")


def attach_target_ir_nominal_enum_payloads(target_ir: dict[str, Any], sir_module: Any) -> dict[str, Any]:
    if not isinstance(target_ir, dict) or target_ir.get("schema") != "sotlas.target-ir.v1":
        raise NominalEnumPayloadError("nominal enum payload bridge requires Target IR v1")
    facts = tuple(getattr(sir_module, "nominal_enum_payload_facts", ()) or ())
    if not facts:
        return target_ir
    declarations = {fact.enum_name: _lower_fact(fact) for fact in facts}
    if len(declarations) != len(facts):
        raise NominalEnumPayloadError("canonical SIR repeats a nominal enum payload declaration")
    existing = target_ir.get("nominal_enum_payloads")
    if existing not in (None, {}, declarations):
        raise NominalEnumPayloadError("Target IR already contains conflicting nominal enum payload declarations")
    target_ir["nominal_enum_payloads"] = declarations
    validate_target_ir_nominal_enum_payloads(target_ir)
    return target_ir


__all__ = [
    "NominalEnumPayloadError",
    "NominalEnumPayloadFact",
    "NominalEnumPayloadVariantFact",
    "attach_checked_nominal_enum_payloads",
    "attach_target_ir_nominal_enum_payloads",
    "collect_nominal_enum_payload_facts",
    "validate_target_ir_nominal_enum_payloads",
]
