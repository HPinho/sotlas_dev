"""Narrow source/SIR bridge for explicit payload-free enum tags (M16.4e2)."""
from __future__ import annotations

import importlib
from typing import Any


_U32_MAX = (1 << 32) - 1


def _explicit_nullary_enum_fact(enum: Any, enum_sir: Any):
    name = getattr(enum, "name", None)
    variants = tuple(getattr(enum, "variants", ()) or ())
    if not isinstance(name, str) or not name or not variants:
        return None

    seen_names: set[str] = set()
    seen_tags: set[int] = set()
    lowered = []
    for variant in variants:
        variant_name = getattr(variant, "name", None)
        discriminant = getattr(variant, "value", None)
        payload_type = getattr(variant, "payload_type", None)
        if (
            not isinstance(variant_name, str)
            or not variant_name
            or variant_name in seen_names
            or payload_type is not None
            or not isinstance(discriminant, int)
            or isinstance(discriminant, bool)
            or discriminant < 0
            or discriminant > _U32_MAX
            or discriminant in seen_tags
        ):
            return None
        seen_names.add(variant_name)
        seen_tags.add(discriminant)
        lowered.append(enum_sir.NullaryEnumVariantFact(
            name=variant_name,
            discriminant=discriminant,
        ))

    return enum_sir.NullaryEnumFact(
        name=name,
        tag_type="u32",
        variants=tuple(lowered),
    )


def extend_nullary_enum_generator(base, sir):
    """Add ``return Enum::Variant as u32`` without opening nominal enum ABI."""

    enum_sir = importlib.import_module(f"{sir.__name__}.enums")

    class NullaryEnumSIRGenerator(base):
        def generate_from_ast(self, ast: Any):
            facts = tuple(
                fact
                for enum in tuple(getattr(ast, "enums", ()) or ())
                if (fact := _explicit_nullary_enum_fact(enum, enum_sir)) is not None
            )
            module = super().generate_from_ast(ast)
            module.nullary_enum_facts = facts
            if not facts:
                return module

            facts_by_name = {fact.name: fact for fact in facts}
            unlowered = list(getattr(module, "unlowered_functions", ()) or ())
            if not unlowered:
                return module

            functions_by_name = {
                function.name: function
                for function in tuple(getattr(module, "functions", ()) or ())
            }
            parsed_functions = tuple(getattr(ast, "functions", ()) or ())
            for fn in parsed_functions:
                fn_name = getattr(fn, "name", None)
                if fn_name not in unlowered:
                    continue

                params = tuple(getattr(fn, "params", ()) or ())
                return_type = (
                    getattr(fn, "ret", None)
                    or getattr(fn, "result", None)
                    or getattr(fn, "return_type", None)
                )
                if params or self._type_name(return_type, "void") != "u32":
                    continue

                body = list(getattr(fn, "body", None) or ())
                if len(body) != 1 or type(body[0]).__name__ not in (
                    "Return", "ReturnNode"
                ):
                    continue
                return_statement = body[0]
                cast = getattr(return_statement, "value", None)
                if type(cast).__name__ not in ("Cast", "CastExprNode"):
                    continue
                target_type = getattr(cast, "target_type", None)
                if self._type_name(target_type, "any") != "u32":
                    continue

                enum_access = getattr(cast, "expr", None)
                if type(enum_access).__name__ != "EnumAccess":
                    continue
                enum_name = getattr(enum_access, "enum_name", None)
                variant_name = getattr(enum_access, "variant", None)
                declaration = facts_by_name.get(enum_name)
                if declaration is None:
                    continue
                variant = next(
                    (
                        item
                        for item in declaration.variants
                        if item.name == variant_name
                    ),
                    None,
                )
                if variant is None:
                    continue

                sir_fn = functions_by_name.get(fn_name)
                blocks = tuple(getattr(sir_fn, "blocks", ()) or ())
                if sir_fn is None or len(blocks) != 1:
                    continue
                block = blocks[0]
                existing = list(getattr(block, "instructions", ()) or ())
                if (
                    len(existing) != 1
                    or type(existing[0]).__name__ != "ReturnInst"
                ):
                    continue

                result = self._next_val(
                    f"enum_{enum_name}_{variant_name}",
                    "u32",
                )
                block.instructions = [
                    enum_sir.EnumConstInst(
                        enum_name=enum_name,
                        variant=variant_name,
                        discriminant=variant.discriminant,
                        result=result,
                        point_id=self._statement_point_id(
                            enum_access, "enum_const"
                        ),
                    ),
                    sir.ReturnInst(
                        value=result,
                        point_id=self._statement_point_id(
                            return_statement, "return"
                        ),
                    ),
                ]
                module.unlowered_functions.remove(fn_name)
                unlowered.remove(fn_name)

            return module

    NullaryEnumSIRGenerator.__name__ = "NullaryEnumSIRGenerator"
    return NullaryEnumSIRGenerator


__all__ = ["extend_nullary_enum_generator"]
