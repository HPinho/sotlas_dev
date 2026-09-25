"""Narrow Phase-1 typing bridge for named privileged Authority ABI contracts.

The production bootstrap already owns the canonical intrinsic signatures. This
extension lets the isolated Typed AST consume only ABI symbols that have an
explicit ``authority_abi`` contract, avoiding a second builtin table and keeping
legacy-uncontracted privileged intrinsics fail-closed in the strict Phase-3 path.
"""
from __future__ import annotations

import importlib

from .authority_abi import authority_abi_contract


def _semantic_scalar_type(typed_ast, raw_type, *, symbol: str):
    """Convert the scalar ABI subset into the canonical Phase-1 SemanticType."""
    name = getattr(raw_type, "name", None)
    if not isinstance(name, str) or not name:
        raise typed_ast.Phase1SemanticError(
            f"authority ABI {symbol!r} has a builtin type without canonical name"
        )

    unsupported = (
        bool(getattr(raw_type, "pointer", False))
        or bool(getattr(raw_type, "is_reference", False))
        or bool(getattr(raw_type, "is_array", False))
        or getattr(raw_type, "ownership_domain", None) is not None
    )
    if unsupported:
        raise typed_ast.Phase1SemanticError(
            f"authority ABI {symbol!r} uses a non-scalar type not yet supported "
            "by the Phase-1 ABI typing bridge"
        )
    return typed_ast.SemanticType(name)


def install(bootstrap) -> None:
    """Install named-ABI typing into the isolated Phase-1 expression inferencer."""
    package = bootstrap.__package__ or "sotlas_compile"
    typed_ast = importlib.import_module(f"{package}.typed_ast")
    if getattr(typed_ast, "_AUTHORITY_ABI_TYPING_INSTALLED", False):
        return

    previous_infer = typed_ast.infer_expression_type

    def authority_abi_infer(expr, env, typed_module):
        if type(expr).__name__ == "Call":
            callee = getattr(expr, "callee", None)
            if isinstance(callee, str) and authority_abi_contract(callee) is not None:
                builtin = getattr(bootstrap, "BUILTIN_FUNCTIONS", {}).get(callee)
                if builtin is None:
                    raise typed_ast.Phase1SemanticError(
                        f"authority ABI {callee!r} lacks canonical bootstrap signature"
                    )

                parameters = tuple(getattr(builtin, "params", ()) or ())
                arguments = tuple(getattr(expr, "args", ()) or ())
                if len(arguments) != len(parameters):
                    raise typed_ast.Phase1SemanticError(
                        f"call {callee!r} has wrong argument count"
                    )

                for argument, parameter in zip(arguments, parameters):
                    if not isinstance(parameter, tuple) or len(parameter) != 2:
                        raise typed_ast.Phase1SemanticError(
                            f"authority ABI {callee!r} has malformed bootstrap parameter"
                        )
                    expected = _semantic_scalar_type(
                        typed_ast,
                        parameter[1],
                        symbol=callee,
                    )
                    inferred = authority_abi_infer(argument, env, typed_module)
                    contextual = typed_ast._contextualize_expression(
                        argument,
                        inferred,
                        expected,
                        env,
                        typed_module,
                    )
                    if contextual.type != expected:
                        raise typed_ast.Phase1SemanticError(
                            f"call {callee!r} argument type mismatch: expected "
                            f"{expected.name}, got {contextual.type.name}"
                        )

                result = _semantic_scalar_type(
                    typed_ast,
                    getattr(builtin, "result", None),
                    symbol=callee,
                )
                return typed_ast.TypedExprNode("Call", result, callee)

        return previous_infer(expr, env, typed_module)

    typed_ast.infer_expression_type = authority_abi_infer
    typed_ast._AUTHORITY_ABI_TYPING_INSTALLED = True


__all__ = ["install"]
