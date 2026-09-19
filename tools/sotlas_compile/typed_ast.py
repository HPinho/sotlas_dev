"""Typed AST snapshot produced by the canonical Stage-0 semantic pass.

This is the Phase-1 bridge between the parsed bootstrap AST and future SIR2.
It contains source spans plus semantic types already established by the
canonical checker. It does not perform a second typecheck.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int


@dataclass(frozen=True)
class TypedType:
    name: str
    pointer: bool = False
    mutable: bool = False
    is_array: bool = False
    array_size: int | str = 0
    is_reference: bool = False


@dataclass(frozen=True)
class TypedExpr:
    kind: str
    type: TypedType | None
    span: SourceSpan
    detail: str | None = None
    children: tuple["TypedExpr", ...] = ()


@dataclass(frozen=True)
class TypedStmt:
    kind: str
    span: SourceSpan
    bound_type: TypedType | None = None
    expressions: tuple[TypedExpr, ...] = ()
    blocks: tuple[tuple["TypedStmt", ...], ...] = ()


@dataclass(frozen=True)
class TypedParam:
    name: str
    type: TypedType


@dataclass(frozen=True)
class TypedField:
    name: str
    type: TypedType


@dataclass(frozen=True)
class TypedStruct:
    name: str
    fields: tuple[TypedField, ...]
    public: bool = False
    attributes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TypedGlobal:
    name: str
    type: TypedType
    public: bool = False


@dataclass(frozen=True)
class TypedFunction:
    name: str
    params: tuple[TypedParam, ...]
    result: TypedType
    body: tuple[TypedStmt, ...]
    public: bool = False
    attributes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TypedModule:
    name: str
    structs: tuple[TypedStruct, ...]
    globals: tuple[TypedGlobal, ...]
    functions: tuple[TypedFunction, ...]
    filename: str | None = None
    phase: str = field(default="phase1-typed-ast-v1", init=False)


def _type(type_obj) -> TypedType | None:
    if type_obj is None:
        return None
    return TypedType(
        name=getattr(type_obj, "name", "<unknown>"),
        pointer=bool(getattr(type_obj, "pointer", False)),
        mutable=bool(getattr(type_obj, "mutable", False)),
        is_array=bool(getattr(type_obj, "is_array", False)),
        array_size=getattr(type_obj, "array_size", 0),
        is_reference=bool(
            getattr(type_obj, "is_reference", False)
            or getattr(type_obj, "_sotlas_reference", False)
        ),
    )


def _span(node) -> SourceSpan:
    token = getattr(node, "token", None)
    return SourceSpan(
        line=int(getattr(token, "line", 1)),
        column=int(getattr(token, "column", 1)),
    )


def _detail(expr) -> str | None:
    for name in ("value", "callee", "op", "field", "method", "variant", "struct_name"):
        value = getattr(expr, name, None)
        if isinstance(value, (str, int, float, bool)):
            return str(value)
    return None


def _expr_children(expr) -> tuple:
    kind = type(expr).__name__
    fields = {
        "UnsafeExpr": ("value",),
        "Unary": ("value",),
        "Binary": ("left", "right"),
        "Call": ("args",),
        "Index": ("target", "index"),
        "Member": ("target",),
        "MethodCall": ("target", "args"),
        "Cast": ("expr",),
        "ArrayLit": ("elements",),
        "StructLit": ("fields",),
        "IfExpr": ("condition", "then_expr", "else_expr"),
        "TryExpr": ("expr",),
    }.get(kind, ())
    result = []
    for field_name in fields:
        value = getattr(expr, field_name, None)
        if field_name == "fields" and value:
            value = [item[1] for item in value]
        if isinstance(value, (list, tuple)):
            result.extend(item for item in value if hasattr(item, "token"))
        elif hasattr(value, "token"):
            result.append(value)
    return tuple(result)


def _typed_expr(expr) -> TypedExpr:
    return TypedExpr(
        kind=type(expr).__name__,
        type=_type(getattr(expr, "_sotlas_type", None)),
        span=_span(expr),
        detail=_detail(expr),
        children=tuple(_typed_expr(child) for child in _expr_children(expr)),
    )


def _typed_stmt(stmt) -> TypedStmt:
    kind = type(stmt).__name__
    expressions = []
    blocks = []
    bound_type = None

    if kind == "Let":
        expressions.append(stmt.value)
        bound_type = _type(getattr(stmt, "type", None) or getattr(stmt.value, "_sotlas_type", None))
    elif kind == "Assign":
        expressions.extend((stmt.target, stmt.value))
    elif kind in ("Return", "Expression"):
        value = getattr(stmt, "value", None)
        if value is not None:
            expressions.append(value)
    elif kind == "If":
        expressions.append(stmt.condition)
        blocks.extend((stmt.then_body, stmt.else_body))
    elif kind == "While":
        expressions.append(stmt.condition)
        blocks.append(stmt.body)
    elif kind == "Loop":
        blocks.append(stmt.body)
    elif kind == "For":
        expressions.extend((stmt.start, stmt.end))
        blocks.append(stmt.body)
    elif kind == "Unsafe":
        blocks.append(stmt.body)
    elif kind == "Defer":
        if getattr(stmt, "body", None) is not None:
            blocks.append(stmt.body)
        elif getattr(stmt, "value", None) is not None:
            value = stmt.value
            if type(value).__name__ == "Assign":
                expressions.extend((value.target, value.value))
            elif hasattr(value, "token"):
                expressions.append(value)
    elif kind == "Asm":
        expressions.extend(getattr(stmt, "outputs", ()) or ())
        expressions.extend(getattr(stmt, "inputs", ()) or ())

    return TypedStmt(
        kind=kind,
        span=_span(stmt),
        bound_type=bound_type,
        expressions=tuple(_typed_expr(expr) for expr in expressions),
        blocks=tuple(tuple(_typed_stmt(item) for item in block) for block in blocks),
    )


def install(bootstrap) -> None:
    """Attach Typed AST materialization after the canonical semantic checker."""
    if getattr(bootstrap, "_TYPED_AST_INSTALLED", False):
        return

    semantic_check = bootstrap.check

    def checked_with_typed_ast(module, imported_fns=None, imported_types=None,
                               imported_enums=None, imported_globals=None):
        result = semantic_check(
            module, imported_fns, imported_types, imported_enums, imported_globals
        )
        module.typed_ast = build_typed_module(module)
        return result

    bootstrap.check = checked_with_typed_ast
    bootstrap._TYPED_AST_INSTALLED = True


def build_typed_module(module) -> TypedModule:
    """Materialize checked semantic information without re-running inference."""
    structs = tuple(
        TypedStruct(
            name=item.name,
            fields=tuple(TypedField(field.name, _type(field.type)) for field in item.fields),
            public=bool(getattr(item, "public", False)),
            attributes=tuple(getattr(item, "attributes", ())),
        )
        for item in module.structs
    )
    globals_ = tuple(
        TypedGlobal(
            name=item.name,
            type=_type(item.type),
            public=bool(getattr(item, "public", False)),
        )
        for item in module.globals
    )
    functions = tuple(
        TypedFunction(
            name=function.name,
            params=tuple(TypedParam(name, _type(typ)) for name, typ in function.params),
            result=_type(function.result),
            body=tuple(_typed_stmt(stmt) for stmt in function.body),
            public=bool(getattr(function, "public", False)),
            attributes=tuple(getattr(function, "attributes", ())),
        )
        for function in module.functions
    )
    return TypedModule(
        name=module.name,
        structs=structs,
        globals=globals_,
        functions=functions,
        filename=getattr(module, "filename", None),
    )


__all__ = [
    "SourceSpan", "TypedType", "TypedExpr", "TypedStmt", "TypedParam",
    "TypedField", "TypedStruct", "TypedGlobal", "TypedFunction", "TypedModule",
    "build_typed_module", "install",
]