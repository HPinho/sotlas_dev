"""Phase-1 tests for the canonical Typed AST bridge."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile import bootstrap
from sotlas_compile.typed_ast import TypedModule


SOURCE = """module test::typed_ast;

pub fn add(a: u32, b: u32) -> u32 {
    let value: u32 = a + b;
    return value;
}

pub fn main() -> i32 {
    let total: u32 = add(1, 2);
    if total == 3 {
        return 0;
    }
    return 1;
}
"""


def walk_expr(expr):
    yield expr
    for child in expr.children:
        yield from walk_expr(child)


def walk_stmt(stmt):
    yield stmt
    for expr in stmt.expressions:
        yield from walk_expr(expr)
    for block in stmt.blocks:
        for nested in block:
            yield from walk_stmt(nested)


class SotlasTypedAstTests(unittest.TestCase):
    def checked_module(self):
        module = bootstrap.parse(SOURCE, filename="<typed-ast>")
        bootstrap.check(module)
        return module

    def test_check_materializes_typed_ast(self):
        module = self.checked_module()
        self.assertIsInstance(module.typed_ast, TypedModule)
        self.assertEqual(module.typed_ast.name, "test::typed_ast")
        self.assertEqual(module.typed_ast.phase, "phase1-typed-ast-v1")
        self.assertEqual([fn.name for fn in module.typed_ast.functions], ["add", "main"])

    def test_core_body_expressions_carry_semantic_types_and_spans(self):
        typed = self.checked_module().typed_ast
        expressions = [
            node
            for function in typed.functions
            for stmt in function.body
            for node in walk_stmt(stmt)
            if hasattr(node, "type")
        ]
        self.assertTrue(expressions)
        self.assertTrue(all(expr.type is not None for expr in expressions))
        self.assertTrue(all(expr.span.line >= 1 and expr.span.column >= 1 for expr in expressions))

        binary_types = [
            expr.type.name
            for expr in expressions
            if expr.kind == "Binary" and expr.type is not None
        ]
        self.assertIn("u32", binary_types)
        self.assertIn("bool", binary_types)

    def test_typed_ast_is_semantic_snapshot_not_second_checker(self):
        module = self.checked_module()
        add = next(fn for fn in module.typed_ast.functions if fn.name == "add")
        let_stmt = add.body[0]
        self.assertEqual(let_stmt.kind, "Let")
        self.assertEqual(let_stmt.bound_type.name, "u32")
        self.assertEqual(let_stmt.expressions[0].type.name, "u32")


if __name__ == "__main__":
    unittest.main()
