"""Canonical Phase-1 typing bridge for explicit nullary enum tag casts.

M16.4e2 exposes one source-level representation operation without pretending
that nominal enum ABI classification is complete: a direct payload-free enum
variant may be explicitly cast to the canonical ``u32`` tag type.  Legality is
derived from the existing backend-neutral ``lower_enum_layout`` contract, so
this bridge does not maintain a second enum-layout policy.
"""
from __future__ import annotations

import importlib


_U32_MAX = (1 << 32) - 1


def install(bootstrap) -> None:
    """Install the narrow ``Enum::Variant as u32`` Phase-1 typing rule."""

    package = bootstrap.__package__ or "sotlas_compile"
    typed_ast = importlib.import_module(f"{package}.typed_ast")
    if getattr(typed_ast, "_ENUM_TAG_CAST_TYPING_INSTALLED", False):
        return

    previous_infer = typed_ast.infer_expression_type

    def enum_tag_cast_infer(expr, env, typed_module):
        if type(expr).__name__ != "Cast":
            return previous_infer(expr, env, typed_module)

        target = typed_ast.semantic_type(getattr(expr, "target_type"))
        if target != typed_ast.SemanticType("u32"):
            return previous_infer(expr, env, typed_module)

        source_expr = getattr(expr, "expr", None)
        if type(source_expr).__name__ != "EnumAccess":
            return previous_infer(expr, env, typed_module)

        source = previous_infer(source_expr, env, typed_module)
        enum_name = getattr(source_expr, "enum_name", None)
        variant_name = getattr(source_expr, "variant", None)
        enum = next(
            (
                item
                for item in tuple(getattr(typed_module, "enums", ()) or ())
                if item.name == enum_name
            ),
            None,
        )
        if enum is None or source.type != typed_ast.SemanticType(enum_name):
            return previous_infer(expr, env, typed_module)

        layout = typed_ast.lower_enum_layout(enum)
        if layout.storage != "tag_only":
            raise typed_ast.Phase1SemanticError(
                f"enum tag cast requires tag_only enum, got {enum_name!r} "
                f"with storage {layout.storage!r}"
            )

        variant = next(
            (item for item in layout.variants if item.name == variant_name),
            None,
        )
        if variant is None:
            raise typed_ast.Phase1SemanticError(
                f"enum {enum_name!r} has no canonical variant {variant_name!r}"
            )
        tag = variant.tag
        if (
            not isinstance(tag, int)
            or isinstance(tag, bool)
            or tag < 0
            or tag > _U32_MAX
        ):
            raise typed_ast.Phase1SemanticError(
                f"enum tag cast requires u32 discriminant, got {tag!r} for "
                f"{enum_name}::{variant_name}"
            )

        return typed_ast.TypedExprNode(
            "Cast",
            target,
            f"enum_tag:{enum_name}::{variant_name}",
        )

    typed_ast.infer_expression_type = enum_tag_cast_infer
    typed_ast._ENUM_TAG_CAST_TYPING_INSTALLED = True


__all__ = ["install"]
