"""Fail-closed source gate for the initial direct LLVM assembly subset."""
from __future__ import annotations

import re


class LLVMAssemblySubsetError(ValueError):
    """Raised when source constructs exceed the verified assembly prototype."""


_INTEGER_TYPES = {
    "u8": 8, "i8": 8, "u16": 16, "i16": 16,
    "u32": 32, "i32": 32, "u64": 64, "i64": 64,
    "usize": 64, "isize": 64,
}
_UNSIGNED_TYPES = {"u8", "u16", "u32", "u64", "usize"}
_LITERAL = re.compile(
    r"(?P<digits>(?:0[xX][0-9a-fA-F_]+)|(?:0[bB][01_]+)|(?:[0-9][0-9_]*))"
    r"(?P<suffix>u8|u16|u32|u64|usize|i8|i16|i32|i64|isize)?$"
)


def _literal_for_return(expression, return_type: str) -> bool:
    if type(expression).__name__ not in ("Number", "LiteralNode"):
        return False
    if type(expression).__name__ == "LiteralNode":
        kind = getattr(getattr(expression, "kind", None), "name", None)
        if kind != "INT_LIT":
            return False
    raw = getattr(expression, "value", None)
    if not isinstance(raw, str):
        return False
    match = _LITERAL.fullmatch(raw)
    if match is None:
        return False
    suffix = match.group("suffix") or return_type
    if suffix != return_type or suffix not in _INTEGER_TYPES:
        return False
    try:
        value = int(match.group("digits").replace("_", ""), 0)
    except ValueError:
        return False
    width = _INTEGER_TYPES[suffix]
    signed = suffix not in _UNSIGNED_TYPES
    lower = -(1 << (width - 1)) if signed else 0
    upper = (1 << (width - 1)) - 1 if signed else (1 << width) - 1
    return lower <= value <= upper


def validate_llvm_assembly_subset(module) -> None:
    """Accept only bodies the current SIR generator lowers completely.

    This gate intentionally supports a small, auditable subset so the native
    assembly command cannot silently turn unlowered bodies into empty code.
    """
    for collection in ("imports", "structs", "classes", "enums", "globals"):
        if getattr(module, collection, ()):
            raise LLVMAssemblySubsetError(
                f"assembly prototype does not lower module {collection}"
            )
    functions = tuple(getattr(module, "functions", ()) or ())
    if not functions:
        raise LLVMAssemblySubsetError(
            "assembly prototype requires at least one supported function"
        )
    for function in functions:
        name = function.name
        if (
            not function.body
            or "@extern(C)" in function.attributes
            or getattr(function, "requires", None) is not None
            or getattr(function, "ensures", None) is not None
        ):
            raise LLVMAssemblySubsetError(
                f"assembly prototype does not lower the full body or contracts of {name!r}"
            )
        body = tuple(function.body)
        if len(body) != 1 or type(body[0]).__name__ not in ("Return", "ReturnNode"):
            raise LLVMAssemblySubsetError(
                f"assembly prototype supports one direct return in {name!r}"
            )
        expression = getattr(body[0], "value", None)
        return_type = getattr(getattr(function, "result", None), "name", None)
        if return_type == "void" and expression is None:
            continue
        if return_type not in _INTEGER_TYPES:
            raise LLVMAssemblySubsetError(
                f"assembly prototype supports integer scalar returns in {name!r}"
            )
        if _literal_for_return(expression, return_type):
            continue
        if type(expression).__name__ not in ("Binary", "BinaryExprNode"):
            raise LLVMAssemblySubsetError(
                f"assembly prototype supports typed integer literals or unsigned parameter arithmetic in {name!r}"
            )
        operation = getattr(expression, "op", None)
        operation_name = getattr(operation, "name", None)
        operation_symbol = operation if isinstance(operation, str) else {
            "PLUS": "+", "MINUS": "-", "STAR": "*",
        }.get(operation_name)
        if return_type not in _UNSIGNED_TYPES or operation_symbol not in {"+", "-", "*"}:
            raise LLVMAssemblySubsetError(
                f"assembly prototype does not lower arithmetic in {name!r}"
            )
        names = []
        for operand in (expression.left, expression.right):
            if type(operand).__name__ not in ("Name", "IdentNode"):
                break
            names.append(
                getattr(operand, "value", None)
                or getattr(operand, "name", None)
            )
        params = dict(function.params)
        if (
            len(names) != 2
            or any(param_name not in params for param_name in names)
            or any(getattr(params[param_name], "name", None) != return_type for param_name in names)
        ):
            raise LLVMAssemblySubsetError(
                f"assembly prototype requires two {return_type} parameters in {name!r}"
            )


__all__ = ["LLVMAssemblySubsetError", "validate_llvm_assembly_subset"]
