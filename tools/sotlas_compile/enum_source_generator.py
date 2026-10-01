"""Narrow source/SIR bridge for explicit enum representation (M16.4e2/e3)."""
from __future__ import annotations

import importlib
from typing import Any


_U32_MAX = (1 << 32) - 1
_SCALAR_PAYLOAD_TYPES = frozenset({
    "bool",
    "u8", "i8",
    "u16", "i16",
    "u32", "i32",
    "u64", "i64",
    "usize", "isize",
    "f32", "f64",
})


def _semantic_type_name(type_info: Any) -> str | None:
    if type_info is None:
        return None
    name = getattr(type_info, "name", None)
    if not isinstance(name, str) or not name:
        return None
    if (
        bool(getattr(type_info, "pointer", False))
        or bool(getattr(type_info, "is_reference", False))
        or bool(getattr(type_info, "is_array", False))
        or getattr(type_info, "declared_ownership_domain", None) is not None
    ):
        return None
    return name


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


def _scalar_payload_enum_fact_from_layout(layout: Any, enum_sir: Any):
    """Admit a checked tagged union whose logical payloads are direct scalars."""

    name = getattr(layout, "enum_name", None)
    storage = getattr(layout, "storage", None)
    variants = tuple(getattr(layout, "variants", ()) or ())
    if (
        not isinstance(name, str)
        or not name
        or storage != "tagged_union"
        or not variants
    ):
        return None

    seen_names: set[str] = set()
    seen_tags: set[int] = set()
    lowered = []
    saw_payload = False
    for variant in variants:
        variant_name = getattr(variant, "name", None)
        discriminant = getattr(variant, "tag", None)
        raw_payload_type = getattr(variant, "payload_type", None)
        payload_type = _semantic_type_name(raw_payload_type)
        if raw_payload_type is not None:
            if payload_type not in _SCALAR_PAYLOAD_TYPES:
                return None
            saw_payload = True
        if (
            not isinstance(variant_name, str)
            or not variant_name
            or variant_name in seen_names
            or not isinstance(discriminant, int)
            or isinstance(discriminant, bool)
            or discriminant < 0
            or discriminant > _U32_MAX
            or discriminant in seen_tags
        ):
            return None
        seen_names.add(variant_name)
        seen_tags.add(discriminant)
        lowered.append(enum_sir.PayloadEnumVariantFact(
            name=variant_name,
            discriminant=discriminant,
            payload_type=payload_type,
        ))

    if not saw_payload:
        return None
    return enum_sir.PayloadEnumFact(
        name=name,
        tag_type="u32",
        storage="tagged_union",
        variants=tuple(lowered),
    )


def _parameter_prologue_before_fallback(
    block: Any,
    sir_fn: Any,
    *,
    expected_return_type: str,
) -> list[Any] | None:
    """Return the canonical parameter prologue before one prototype fallback.

    Unsupported non-void functions currently contain the honest parameter
    materialization produced by the base SIR generator followed by a synthetic
    ``ret_val*`` ReturnInst sentinel.  M16.4e3 may replace only that sentinel;
    every alloc/store pair must still exactly match the declared SIR parameters.
    """

    existing = list(getattr(block, "instructions", ()) or ())
    if not existing or type(existing[-1]).__name__ != "ReturnInst":
        return None

    fallback = existing[-1]
    fallback_value = getattr(fallback, "value", None)
    fallback_name = getattr(fallback_value, "name", None)
    fallback_type = getattr(fallback_value, "type_name", None)
    if (
        not isinstance(fallback_name, str)
        or not fallback_name.startswith("ret_val")
        or fallback_type != expected_return_type
    ):
        return None

    prefix = existing[:-1]
    parameters = tuple(getattr(sir_fn, "parameters", ()) or ())
    if len(prefix) != 2 * len(parameters):
        return None

    for index, parameter in enumerate(parameters):
        alloc = prefix[2 * index]
        store = prefix[2 * index + 1]
        if (
            type(alloc).__name__ != "AllocStackInst"
            or type(store).__name__ != "StoreInst"
            or getattr(alloc, "var_name", None) != getattr(parameter, "name", None)
            or getattr(alloc, "type_name", None)
            != getattr(parameter, "type_name", None)
        ):
            return None

        slot = getattr(alloc, "result", None)
        destination = getattr(store, "destination", None)
        source = getattr(store, "source", None)
        if (
            getattr(slot, "name", None) != getattr(destination, "name", None)
            or getattr(slot, "type_name", None)
            != getattr(destination, "type_name", None)
            or getattr(source, "name", None) != getattr(parameter, "name", None)
            or getattr(source, "type_name", None)
            != getattr(parameter, "type_name", None)
        ):
            return None

    return prefix


def extend_nullary_enum_generator(base, sir):
    """Add checked enum representation without opening aggregate machine ABI."""

    enum_sir = importlib.import_module(f"{sir.__name__}.enums")

    class NullaryEnumSIRGenerator(base):
        def generate_from_ast(self, ast: Any):
            nullary_facts = tuple(
                fact
                for enum in tuple(getattr(ast, "enums", ()) or ())
                if (fact := _explicit_nullary_enum_fact(enum, enum_sir)) is not None
            )

            source_enum_names = {
                getattr(enum, "name", None)
                for enum in tuple(getattr(ast, "enums", ()) or ())
            }
            checked_layouts = tuple(
                getattr(self, "_checked_enum_layouts", ()) or ()
            )
            payload_facts = tuple(
                fact
                for layout in checked_layouts
                if getattr(layout, "enum_name", None) in source_enum_names
                if (
                    fact := _scalar_payload_enum_fact_from_layout(
                        layout, enum_sir
                    )
                ) is not None
            )

            module = super().generate_from_ast(ast)
            module.nullary_enum_facts = nullary_facts
            module.payload_enum_facts = payload_facts
            if not nullary_facts and not payload_facts:
                return module

            unlowered = list(getattr(module, "unlowered_functions", ()) or ())
            if not unlowered:
                return module

            functions_by_name = {
                function.name: function
                for function in tuple(getattr(module, "functions", ()) or ())
            }
            parsed_functions = tuple(getattr(ast, "functions", ()) or ())

            nullary_by_name = {fact.name: fact for fact in nullary_facts}
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
                declaration = nullary_by_name.get(enum_name)
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
                if sir_fn is None:
                    continue
                blocks = tuple(getattr(sir_fn, "blocks", ()) or ())
                if len(blocks) != 1:
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

            payload_by_name = {fact.name: fact for fact in payload_facts}
            for fn in parsed_functions:
                fn_name = getattr(fn, "name", None)
                if fn_name not in unlowered:
                    continue

                return_type = (
                    getattr(fn, "ret", None)
                    or getattr(fn, "result", None)
                    or getattr(fn, "return_type", None)
                )
                enum_name = self._type_name(return_type, "void")
                declaration = payload_by_name.get(enum_name)
                if declaration is None:
                    continue

                body = list(getattr(fn, "body", None) or ())
                if len(body) != 1 or type(body[0]).__name__ not in (
                    "Return", "ReturnNode"
                ):
                    continue
                return_statement = body[0]
                constructor = getattr(return_statement, "value", None)
                if type(constructor).__name__ != "Call":
                    continue
                arguments = tuple(getattr(constructor, "args", ()) or ())
                if len(arguments) != 1 or type(arguments[0]).__name__ != "Name":
                    continue

                variant = next(
                    (
                        item
                        for item in declaration.variants
                        if f"{enum_name}_{item.name}"
                        == getattr(constructor, "callee", None)
                    ),
                    None,
                )
                if variant is None or variant.payload_type is None:
                    continue

                payload_name = getattr(arguments[0], "value", None)
                sir_fn = functions_by_name.get(fn_name)
                if sir_fn is None:
                    continue
                payload = next(
                    (
                        parameter
                        for parameter in tuple(
                            getattr(sir_fn, "parameters", ()) or ()
                        )
                        if getattr(parameter, "name", None) == payload_name
                    ),
                    None,
                )
                if (
                    payload is None
                    or getattr(payload, "type_name", None) != variant.payload_type
                ):
                    continue

                blocks = tuple(getattr(sir_fn, "blocks", ()) or ())
                if len(blocks) != 1:
                    continue
                block = blocks[0]
                prefix = _parameter_prologue_before_fallback(
                    block,
                    sir_fn,
                    expected_return_type=enum_name,
                )
                if prefix is None:
                    continue

                result = self._next_val(
                    f"enum_{enum_name}_{variant.name}",
                    enum_name,
                )
                block.instructions = [
                    *prefix,
                    enum_sir.EnumConstructInst(
                        enum_name=enum_name,
                        variant=variant.name,
                        discriminant=variant.discriminant,
                        payload=payload,
                        payload_type=variant.payload_type,
                        result=result,
                        point_id=self._statement_point_id(
                            constructor, "enum_construct"
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
