"""Phase-1 Typed AST foundation.

This module is intentionally isolated from the production bootstrap pipeline.
It materializes the *declared* semantic types that already exist on the parsed
canonical AST. Function-body expression typing is not claimed here yet.

Maturity: DECLARATIONS_ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass


MATURITY = "DECLARATIONS_ONLY"


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int


@dataclass(frozen=True)
class SemanticType:
    name: str
    pointer: bool = False
    mutable: bool = False
    is_array: bool = False
    array_size: int | str = 0
    is_reference: bool = False


@dataclass(frozen=True)
class TypedField:
    name: str
    type: SemanticType


@dataclass(frozen=True)
class TypedStruct:
    name: str
    fields: tuple[TypedField, ...]
    public: bool
    attributes: tuple[str, ...]
    is_sole: bool


@dataclass(frozen=True)
class TypedParam:
    name: str
    type: SemanticType


@dataclass(frozen=True)
class TypedFunction:
    name: str
    params: tuple[TypedParam, ...]
    result: SemanticType
    public: bool
    attributes: tuple[str, ...]


@dataclass(frozen=True)
class TypedGlobal:
    name: str
    type: SemanticType
    public: bool
    is_const: bool
    is_mut: bool


@dataclass(frozen=True)
class TypedModule:
    name: str
    structs: tuple[TypedStruct, ...]
    globals: tuple[TypedGlobal, ...]
    functions: tuple[TypedFunction, ...]
    filename: str | None
    maturity: str = MATURITY


def semantic_type(type_obj) -> SemanticType:
    """Freeze a canonical bootstrap Type without changing the source AST."""
    return SemanticType(
        name=type_obj.name,
        pointer=bool(type_obj.pointer),
        mutable=bool(type_obj.mutable),
        is_array=bool(type_obj.is_array),
        array_size=type_obj.array_size,
        is_reference=bool(getattr(type_obj, "is_reference", False)),
    )


def build_declaration_typed_ast(module) -> TypedModule:
    """Build the Phase-1 declaration snapshot from an already parsed module.

    Callers remain responsible for running the canonical semantic checker first.
    This function neither calls nor replaces bootstrap.check and never mutates
    the production AST.
    """
    return TypedModule(
        name=module.name,
        structs=tuple(
            TypedStruct(
                name=item.name,
                fields=tuple(
                    TypedField(field.name, semantic_type(field.type))
                    for field in item.fields
                ),
                public=bool(item.public),
                attributes=tuple(item.attributes),
                is_sole=bool(getattr(item, "is_sole", False)),
            )
            for item in module.structs
        ),
        globals=tuple(
            TypedGlobal(
                name=item.name,
                type=semantic_type(item.type),
                public=bool(item.public),
                is_const=bool(item.is_const),
                is_mut=bool(item.is_mut),
            )
            for item in module.globals
        ),
        functions=tuple(
            TypedFunction(
                name=item.name,
                params=tuple(
                    TypedParam(name, semantic_type(type_obj))
                    for name, type_obj in item.params
                ),
                result=semantic_type(item.result),
                public=bool(item.public),
                attributes=tuple(item.attributes),
            )
            for item in module.functions
        ),
        filename=module.filename,
    )


__all__ = [
    "MATURITY", "SourceSpan", "SemanticType", "TypedField", "TypedStruct",
    "TypedParam", "TypedFunction", "TypedGlobal", "TypedModule",
    "semantic_type", "build_declaration_typed_ast",
]
