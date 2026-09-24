"""Compatibility traversal for the legacy tools bootstrap AST.

The production ``compiler/sotlas_compile`` bootstrap owns newer expression
nodes such as ``ShareExpr``.  The historical ``tools/sotlas_compile`` mirror is
still exercised by compatibility tests and may not expose every one of those
classes.  REGION safety must therefore inspect only node capabilities that are
actually present instead of assuming class parity between the two trees.

This module does not add, alias, or fake AST nodes.  It only makes the existing
REGION method/indirect checker traversal tolerant of an older mirror surface.
"""
from __future__ import annotations

from .region_method_safety import _RegionMethodEscapeChecker


def install() -> None:
    if getattr(_RegionMethodEscapeChecker, "_TOOLS_AST_COMPAT_INSTALLED", False):
        return

    def _children(self, expr):
        b = self.b
        if expr is None:
            return ()

        def is_node(name: str) -> bool:
            node_type = getattr(b, name, None)
            return isinstance(node_type, type) and isinstance(expr, node_type)

        if is_node("Binary"):
            return (expr.left, expr.right)
        if any(
            is_node(name)
            for name in ("Unary", "MoveExpr", "ShareExpr", "UnsafeExpr")
        ):
            return (expr.value,)
        if is_node("Cast"):
            return (expr.expr,)
        if is_node("Member"):
            return (expr.target,)
        if is_node("Index"):
            return (expr.target, expr.index)
        if is_node("Call"):
            return tuple(expr.args)
        if is_node("MethodCall"):
            return (expr.target, *tuple(expr.args))
        if is_node("StructLit"):
            return tuple(value for _, value in expr.fields)
        if is_node("ArrayLit"):
            return tuple(expr.elements)
        if is_node("IfExpr"):
            return (expr.condition, expr.then_expr, expr.else_expr)
        if is_node("TryExpr"):
            return (expr.expr,)
        return ()

    _RegionMethodEscapeChecker._children = _children
    _RegionMethodEscapeChecker._TOOLS_AST_COMPAT_INSTALLED = True


__all__ = ["install"]
