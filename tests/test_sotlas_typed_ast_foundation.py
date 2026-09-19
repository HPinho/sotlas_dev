"""Isolated Phase-1 tests for the declaration Typed AST foundation."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = _load(
    "sotlas_phase1_bootstrap",
    ROOT / "compiler" / "sotlas_compile" / "bootstrap.py",
)
typed_ast = _load(
    "sotlas_phase1_typed_ast",
    ROOT / "compiler" / "sotlas_compile" / "typed_ast.py",
)


SOURCE = """module test::phase1;

sole struct Handle {
    fd: u32;
}

pub const LIMIT: u32 = 8;

pub fn consume(h: Handle, count: usize) -> bool {
    if count > 0 {
        return true;
    }
    return false;
}
"""


class SotlasTypedAstFoundationTests(unittest.TestCase):
    def checked_ast(self):
        module = bootstrap.parse(SOURCE, filename="<phase1>")
        bootstrap.check(module)
        return module

    def test_builder_is_explicit_and_does_not_patch_production_checker(self):
        check_before = bootstrap.check
        module = self.checked_ast()
        typed = typed_ast.build_declaration_typed_ast(module)
        self.assertIs(bootstrap.check, check_before)
        self.assertFalse(hasattr(module, "typed_ast"))
        self.assertEqual(typed.maturity, "DECLARATIONS_ONLY")

    def test_declared_struct_and_sole_fact_are_preserved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        handle = typed.structs[0]
        self.assertEqual(handle.name, "Handle")
        self.assertTrue(handle.is_sole)
        self.assertEqual(handle.fields[0].name, "fd")
        self.assertEqual(handle.fields[0].type.name, "u32")

    def test_function_signature_types_are_frozen(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        consume = typed.functions[0]
        self.assertEqual(consume.name, "consume")
        self.assertEqual(
            [(param.name, param.type.name) for param in consume.params],
            [("h", "Handle"), ("count", "usize")],
        )
        self.assertEqual(consume.result.name, "bool")

    def typed_from(self, source: str):
        module = bootstrap.parse(source, filename="<phase1-recursion>")
        bootstrap.check(module)
        return typed_ast.build_declaration_typed_ast(module)

    def test_sole_move_state_transitions_live_to_moved(self):
        state = typed_ast.move_state("handle", typed_ast.VarState.LIVE)
        self.assertIs(state, typed_ast.VarState.MOVED)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'handle' after move",
        ):
            typed_ast.move_state("handle", state)

    def test_branch_merge_marks_one_sided_move_as_maybe_moved(self):
        state = typed_ast.merge_branch_states(
            typed_ast.VarState.MOVED,
            typed_ast.VarState.LIVE,
        )
        self.assertIs(state, typed_ast.VarState.MAYBE_MOVED)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"after conditional move",
        ):
            typed_ast.require_live("token", state)

    def test_branch_merge_keeps_two_sided_move_as_moved(self):
        state = typed_ast.merge_branch_states(
            typed_ast.VarState.MOVED,
            typed_ast.VarState.MOVED,
        )
        self.assertIs(state, typed_ast.VarState.MOVED)

    def test_live_state_remains_usable(self):
        typed_ast.require_live("value", typed_ast.VarState.LIVE)

    def test_unsigned_integer_bounds_are_exact(self):
        u8 = typed_ast.SemanticType("u8")
        self.assertEqual(typed_ast.integer_bounds(u8), (0, 255))
        typed_ast.validate_integer_value(0, u8)
        typed_ast.validate_integer_value(255, u8)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.validate_integer_value(256, u8)

    def test_signed_integer_bounds_are_exact(self):
        i8 = typed_ast.SemanticType("i8")
        self.assertEqual(typed_ast.integer_bounds(i8), (-128, 127))
        typed_ast.validate_integer_value(-128, i8)
        typed_ast.validate_integer_value(127, i8)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value -129 out of range for i8",
        ):
            typed_ast.validate_integer_value(-129, i8)

    def test_integer_validator_rejects_non_integer_type(self):
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer type expected, got bool",
        ):
            typed_ast.integer_bounds(typed_ast.SemanticType("bool"))

    def test_direct_recursive_value_type_is_rejected(self):
        typed = self.typed_from("""module test::recursive;
struct Node {
    next: Node;
}
fn main() -> void { return; }
""")
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: Node -> Node",
        ):
            typed_ast.validate_no_recursive_value_types(typed)

    def test_indirect_recursive_value_type_is_rejected(self):
        typed = self.typed_from("""module test::recursive_indirect;
struct Left {
    right: Right;
}
struct Right {
    left: Left;
}
fn main() -> void { return; }
""")
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: (Left -> Right -> Left|Right -> Left -> Right)",
        ):
            typed_ast.validate_no_recursive_value_types(typed)

    def test_pointer_indirection_breaks_recursive_value_cycle(self):
        typed = self.typed_from("""module test::recursive_pointer;
struct Node {
    next: *mut Node;
}
fn main() -> void { return; }
""")
        typed_ast.validate_no_recursive_value_types(typed)
        self.assertTrue(typed.structs[0].fields[0].type.pointer)

    def test_global_type_and_storage_facts_are_preserved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        limit = typed.globals[0]
        self.assertEqual(limit.name, "LIMIT")
        self.assertEqual(limit.type.name, "u32")
        self.assertTrue(limit.is_const)
        self.assertFalse(limit.is_mut)


if __name__ == "__main__":
    unittest.main()