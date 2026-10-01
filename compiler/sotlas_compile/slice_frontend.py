"""Explicit frontend and Typed-AST identity for Sotlas slices (M16.4f2).

This extension makes ``&[T]`` and ``&mut [T]`` distinct source/semantic
types without pretending executable slice lowering or aggregate ABI
classification already exists.  Production checking remains fail-closed until
the later source-to-SIR slice bridge is certified.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib


_SLICE_ELEMENT_TYPES = frozenset({"u8", "u16", "u32", "u64", "usize"})
_PREVIEW_ERROR = (
    "slice types are M16.4f2 frontend/Typed-AST preview; "
    "executable slice lowering is not implemented yet"
)


def _outer_reference_starts_slice(parser) -> bool:
    """Recognize ``&[T]``/``&mut [T]`` without stealing ``&[T; N]``."""

    tokens = parser.tokens
    index = parser.at
    if index >= len(tokens) or tokens[index].kind != "&":
        return False
    index += 1
    if index < len(tokens) and tokens[index].kind == "mut":
        index += 1
    if index >= len(tokens) or tokens[index].kind != "[":
        return False

    depth = 0
    for token in tokens[index:]:
        if token.kind == "[":
            depth += 1
            continue
        if token.kind == "]":
            depth -= 1
            if depth == 0:
                return True
            continue
        if token.kind == ";" and depth == 1:
            return False

    # Let the slice parser issue the canonical missing-']' diagnostic.
    return True


def install(bootstrap) -> None:
    """Install explicit slice source/semantic type identity."""

    if getattr(bootstrap, "_SLICE_FRONTEND_INSTALLED", False):
        return

    package = bootstrap.__package__ or "sotlas_compile"
    typed_ast = importlib.import_module(f"{package}.typed_ast")

    @dataclass(frozen=True)
    class SliceType(bootstrap.Type):
        """Source type for one non-owning pointer+length slice view."""

        is_slice: bool = True

        def display(self) -> str:
            element = (
                self.elem_type.display()
                if self.elem_type is not None
                else self.name
            )
            qualifier = "&mut " if self.mutable else "&"
            return f"{qualifier}[{element}]"

        def base_c(self) -> str:
            raise bootstrap.SotlasBootstrapError(_PREVIEW_ERROR)

        def c(self) -> str:
            raise bootstrap.SotlasBootstrapError(_PREVIEW_ERROR)

        def c_decl(self, var_name: str) -> str:
            raise bootstrap.SotlasBootstrapError(_PREVIEW_ERROR)

    @dataclass(frozen=True)
    class SliceSemanticType(typed_ast.SemanticType):
        """Phase-1 identity for a pointer+length slice view."""

        is_slice: bool = True

    def is_slice_type(type_obj) -> bool:
        return isinstance(type_obj, SliceType)

    def is_slice_semantic_type(type_obj) -> bool:
        return isinstance(type_obj, SliceSemanticType)

    previous_type = bootstrap.Parser.type

    def slice_type(parser):
        if not _outer_reference_starts_slice(parser):
            return previous_type(parser)

        anchor = parser.expect("&")
        mutable = bool(parser.accept("mut"))
        parser.expect("[")
        element = parser.type()
        parser.expect("]")

        if (
            is_slice_type(element)
            or getattr(element, "name", None) not in _SLICE_ELEMENT_TYPES
            or bool(getattr(element, "pointer", False))
            or bool(getattr(element, "is_reference", False))
            or bool(getattr(element, "is_array", False))
            or bool(getattr(element, "is_fn_ptr", False))
            or getattr(element, "ownership_domain", None) is not None
        ):
            supported = ", ".join(sorted(_SLICE_ELEMENT_TYPES))
            raise bootstrap.SotlasBootstrapError(
                "M16.4f2 slice element must be one direct unsigned scalar "
                f"({supported})",
                anchor.line,
                anchor.column,
                parser.filename,
                parser.source,
            )

        return SliceType(
            name=element.name,
            pointer=True,
            mutable=mutable,
            is_array=False,
            array_size=0,
            elem_type=element,
            is_fn_ptr=False,
            fn_params=(),
            fn_ret=None,
            is_reference=True,
            ownership_domain=None,
            state_space=element.state_space,
            state_name=element.state_name,
        )

    previous_same_type = bootstrap.same_type

    def slice_same_type(left, right) -> bool:
        left_slice = is_slice_type(left)
        right_slice = is_slice_type(right)
        if left_slice or right_slice:
            return bool(
                left_slice
                and right_slice
                and left.mutable == right.mutable
                and left.elem_type is not None
                and right.elem_type is not None
                and previous_same_type(left.elem_type, right.elem_type)
            )
        return previous_same_type(left, right)

    previous_assignable = bootstrap.assignable

    def slice_assignable(actual, expected) -> bool:
        actual_slice = is_slice_type(actual)
        expected_slice = is_slice_type(expected)
        if actual_slice or expected_slice:
            if not (actual_slice and expected_slice):
                return False
            if actual.elem_type is None or expected.elem_type is None:
                return False
            if not previous_same_type(actual.elem_type, expected.elem_type):
                return False
            # A mutable view can be consumed where an immutable view is
            # expected, but immutable -> mutable would invent write authority.
            return not (expected.mutable and not actual.mutable)
        return previous_assignable(actual, expected)

    previous_semantic_type = typed_ast.semantic_type

    def slice_semantic_type(type_obj):
        base = previous_semantic_type(type_obj)
        if not is_slice_type(type_obj):
            return base
        return SliceSemanticType(**base.__dict__)

    def type_contains_slice(type_obj) -> bool:
        if type_obj is None:
            return False
        if is_slice_type(type_obj):
            return True
        if type_contains_slice(getattr(type_obj, "elem_type", None)):
            return True
        if any(
            type_contains_slice(item)
            for item in tuple(getattr(type_obj, "fn_params", ()) or ())
        ):
            return True
        return type_contains_slice(getattr(type_obj, "fn_ret", None))

    def module_contains_slice(module) -> bool:
        if any(
            type_contains_slice(field.type)
            for struct in tuple(getattr(module, "structs", ()) or ())
            for field in tuple(getattr(struct, "fields", ()) or ())
        ):
            return True
        if any(
            type_contains_slice(field.type)
            for class_decl in tuple(getattr(module, "classes", ()) or ())
            for field in tuple(getattr(class_decl, "fields", ()) or ())
        ):
            return True
        if any(
            type_contains_slice(getattr(variant, "payload_type", None))
            for enum in tuple(getattr(module, "enums", ()) or ())
            for variant in tuple(getattr(enum, "variants", ()) or ())
        ):
            return True
        if any(
            type_contains_slice(item.type)
            for item in tuple(getattr(module, "globals", ()) or ())
        ):
            return True
        return any(
            type_contains_slice(type_obj)
            for function in tuple(getattr(module, "functions", ()) or ())
            for type_obj in (
                *(typ for _, typ in tuple(getattr(function, "params", ()) or ())),
                getattr(function, "result", None),
            )
        )

    previous_check = bootstrap.check

    def slice_checked(module, *args, **kwargs):
        if module_contains_slice(module):
            raise bootstrap.SotlasBootstrapError(
                _PREVIEW_ERROR,
                1,
                1,
                getattr(module, "filename", None),
                getattr(module, "source", None),
            )
        return previous_check(module, *args, **kwargs)

    bootstrap.SliceType = SliceType
    bootstrap.is_slice_type = is_slice_type
    bootstrap.Parser.type = slice_type
    bootstrap.same_type = slice_same_type
    bootstrap.assignable = slice_assignable
    bootstrap.check = slice_checked

    typed_ast.SliceSemanticType = SliceSemanticType
    typed_ast.is_slice_semantic_type = is_slice_semantic_type
    typed_ast.semantic_type = slice_semantic_type

    bootstrap._SLICE_FRONTEND_INSTALLED = True
    typed_ast._SLICE_FRONTEND_INSTALLED = True


__all__ = ["install"]
