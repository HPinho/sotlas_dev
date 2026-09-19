"""Phase-1 Typed AST foundation.

This module is intentionally isolated from the production bootstrap pipeline.
It materializes the *declared* semantic types that already exist on the parsed
canonical AST. Function-body expression typing is not claimed here yet.

Maturity: DECLARATIONS_ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


MATURITY = "DECLARATIONS_ONLY"


class Phase1SemanticError(ValueError):
    """Raised by isolated Phase-1 semantic validators."""


class VarState(str, Enum):
    LIVE = "LIVE"
    MOVED = "MOVED"
    MAYBE_MOVED = "MAYBE_MOVED"
    BORROWED_IMMUT = "BORROWED_IMMUT"
    BORROWED_MUT = "BORROWED_MUT"


def sole_type_names(module: TypedModule) -> frozenset[str]:
    """Return declaration names that carry exclusive sole ownership."""
    return frozenset(item.name for item in module.structs if item.is_sole)


def is_sole_type(type_info: SemanticType, module: TypedModule) -> bool:
    """Resolve a semantic type against the module's sole declarations."""
    return (
        not type_info.pointer
        and not type_info.is_reference
        and type_info.name in sole_type_names(module)
    )


def initial_ownership_state(
    type_info: SemanticType, module: TypedModule
) -> VarState | None:
    """Create ownership tracking only for declarations that are actually sole."""
    return VarState.LIVE if is_sole_type(type_info, module) else None


def require_sole_transfer(
    name: str, type_info: SemanticType, module: TypedModule
) -> VarState:
    """Validate an explicit ownership transfer target from declaration facts."""
    state = initial_ownership_state(type_info, module)
    if state is None:
        raise Phase1SemanticError(
            f"handover target {name!r} is not a sole value"
        )
    return move_state(name, state)


def require_live(name: str, state: VarState) -> None:
    """Reject uses of values whose ownership is no longer definitely live."""
    if state is VarState.LIVE:
        return
    if state is VarState.MOVED:
        raise Phase1SemanticError(
            f"use of sole value {name!r} after move"
        )
    if state is VarState.MAYBE_MOVED:
        raise Phase1SemanticError(
            f"use of sole value {name!r} after conditional move"
        )
    raise Phase1SemanticError(
        f"use of sole value {name!r} while borrowed as {state.value}"
    )


def move_state(name: str, state: VarState) -> VarState:
    """Apply one ownership transfer to a sole variable state."""
    require_live(name, state)
    return VarState.MOVED


def merge_branch_states(left: VarState, right: VarState) -> VarState:
    """Join ownership facts at an if/else convergence point."""
    if left is right:
        return left
    moved_like = {VarState.MOVED, VarState.MAYBE_MOVED}
    if left in moved_like or right in moved_like:
        return VarState.MAYBE_MOVED
    if {left, right} == {VarState.BORROWED_IMMUT, VarState.LIVE}:
        return VarState.LIVE
    if {left, right} == {VarState.BORROWED_MUT, VarState.LIVE}:
        return VarState.LIVE
    if left in (VarState.BORROWED_IMMUT, VarState.BORROWED_MUT) or right in (
        VarState.BORROWED_IMMUT, VarState.BORROWED_MUT
    ):
        raise Phase1SemanticError(
            f"incompatible ownership branch states: {left.value} vs {right.value}"
        )
    return VarState.LIVE


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


_INTEGER_WIDTHS = {
    "u8": (8, False), "u16": (16, False), "u32": (32, False),
    "u64": (64, False), "usize": (64, False),
    "i8": (8, True), "i16": (16, True), "i32": (32, True),
    "i64": (64, True), "isize": (64, True),
}


def integer_bounds(type_info: SemanticType) -> tuple[int, int]:
    """Return the inclusive range for a fixed-width Sotlas integer type."""
    try:
        width, signed = _INTEGER_WIDTHS[type_info.name]
    except KeyError as error:
        raise Phase1SemanticError(
            f"integer type expected, got {type_info.name}"
        ) from error
    if signed:
        limit = 1 << (width - 1)
        return -limit, limit - 1
    return 0, (1 << width) - 1


def validate_integer_value(value: int, type_info: SemanticType) -> None:
    """Reject a compile-time integer value that cannot fit its declared type."""
    lower, upper = integer_bounds(type_info)
    if value < lower or value > upper:
        raise Phase1SemanticError(
            f"integer value {value} out of range for {type_info.name} "
            f"[{lower}, {upper}]"
        )


def validate_no_recursive_value_types(module: TypedModule) -> None:
    """Reject infinitely-sized struct cycles while allowing indirection.

    Only by-value struct fields participate in the dependency graph. Raw
    pointers and references break the size cycle and are therefore permitted.
    Fixed arrays remain by-value and keep their element-type dependency.
    """
    structs = {item.name: item for item in module.structs}
    edges: dict[str, tuple[str, ...]] = {}
    for item in module.structs:
        deps = []
        for field in item.fields:
            type_info = field.type
            if type_info.pointer or type_info.is_reference:
                continue
            if type_info.name in structs:
                deps.append(type_info.name)
        edges[item.name] = tuple(deps)

    visiting: list[str] = []
    active: set[str] = set()
    done: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name in active:
            start = visiting.index(name)
            cycle = visiting[start:] + [name]
            raise Phase1SemanticError(
                "recursive value type: " + " -> ".join(cycle)
            )
        active.add(name)
        visiting.append(name)
        for dependency in edges.get(name, ()):
            visit(dependency)
        visiting.pop()
        active.remove(name)
        done.add(name)

    for name in edges:
        visit(name)


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
    "MATURITY", "Phase1SemanticError", "VarState", "sole_type_names", "is_sole_type",
    "initial_ownership_state", "require_sole_transfer", "require_live", "move_state",
    "merge_branch_states", "SourceSpan", "SemanticType", "TypedField", "TypedStruct",
    "TypedParam", "TypedFunction", "TypedGlobal", "TypedModule",
    "semantic_type", "integer_bounds", "validate_integer_value",
    "validate_no_recursive_value_types",
    "build_declaration_typed_ast",
]