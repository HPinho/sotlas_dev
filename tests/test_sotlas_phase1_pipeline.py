"""Public opt-in Phase-1 pipeline integration tests."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    """Load the production package under a unique test name.

    Some legacy tests prepend ROOT/tools to sys.path, where a compatibility
    package with the same top-level name exists. Loading by explicit package
    path keeps this integration test pinned to compiler/sotlas_compile without
    mutating or depending on global test discovery order.
    """
    name = "sotlas_phase1_public_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sotlas_compile = _load_canonical_package()
typed_ast = importlib.import_module(f"{sotlas_compile.__name__}.typed_ast")


class SotlasPhase1PipelineTests(unittest.TestCase):
    def test_public_phase1_pipeline_is_explicit_and_preserves_bootstrap_check(self):
        source = """module test::phase1_public;
sole struct Token { value: u32; }

fn read(t: Token) -> u32 {
    return t.value;
}
"""
        check_before = sotlas_compile.bootstrap.check
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-public>"
        )
        self.assertIs(sotlas_compile.bootstrap.check, check_before)
        self.assertEqual(result.semantic.maturity, "ISOLATED_PHASE1")
        self.assertEqual(result.semantic.typed_module.structs[0].name, "Token")
        self.assertEqual(result.semantic.bodies[0].name, "read")

    def test_public_phase1_pipeline_reuses_canonical_parse_and_check(self):
        source = """module test::phase1_public_invalid;
fn main() -> void {
    let value: i64 = 1;
    value = true;
    return;
}
"""
        with self.assertRaises(sotlas_compile.SotlasBootstrapError):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-public-invalid>"
            )

    def test_public_phase1_pipeline_rejects_constant_integer_overflow(self):
        source = """module test::phase1_integer_overflow;
fn main() -> u8 {
    return 255u8 + 1u8;
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-integer-overflow>"
            )

    def test_public_phase1_pipeline_accepts_in_range_constant_integer_arithmetic(self):
        source = """module test::phase1_integer_in_range;
fn main() -> u8 {
    return 254u8 + 1u8;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-integer-in-range>"
        )
        body = result.semantic.bodies[0]
        self.assertEqual(body.statements[0].expr.type.name, "u8")

    def test_public_phase1_pipeline_rejects_sole_use_after_move(self):
        source = """module test::phase1_sole_use_after_move;
sole struct Token { value: u32; }

fn consume(token: Token) -> void { return; }
fn main(token: Token) -> u32 {
    consume(move token);
    return token.value;
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-sole-use-after-move>"
            )

    def test_public_phase1_pipeline_accepts_consumed_sole_without_reuse(self):
        source = """module test::phase1_sole_move_valid;
sole struct Token { value: u32; }

fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    consume(move token);
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-sole-move-valid>"
        )
        traces = dict(result.semantic.ownership.traces)
        self.assertIs(
            traces["main"].final_env.state_of("token"),
            typed_ast.VarState.MOVED,
        )

    def test_public_phase1_pipeline_rejects_constant_array_index_oob(self):
        source = """module test::phase1_bounds_oob;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1 + 2];
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index 3 out of bounds for length 3",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-bounds-oob>"
            )

    def test_public_phase1_pipeline_accepts_constant_array_index_in_range(self):
        source = """module test::phase1_bounds_in_range;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1 + 1];
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-bounds-in-range>"
        )
        body = result.semantic.bodies[0]
        self.assertEqual(body.statements[-1].expr.type.name, "i64")

    def test_public_phase1_pipeline_system_does_not_replace_unsafe(self):
        source = """module test::phase1_system_requires_unsafe;
@system
fn read(ptr: *mut u32) -> u32 {
    return *ptr;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"desreferenciamento de ponteiro exige bloco unsafe",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-system-requires-unsafe>"
            )

    def test_public_phase1_pipeline_accepts_system_pointer_deref_inside_unsafe(self):
        source = """module test::phase1_system_with_unsafe;
@system
fn read(ptr: *mut u32) -> u32 {
    unsafe {
        return *ptr;
    }
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-system-with-unsafe>"
        )
        body = result.semantic.bodies[0]
        self.assertEqual(body.statements[0].kind, "Unsafe")
        self.assertEqual(body.statements[0].body[0].kind, "Return")
        self.assertEqual(body.statements[0].body[0].expr.type.name, "u32")

    def test_public_phase1_pipeline_forms_safe_references_with_address_of(self):
        source = """module test::phase1_address_of_reference;
fn read(value: &u32) -> u32 {
    return *value;
}
fn main() -> u32 {
    let value: u32 = 7u32;
    return read(&value);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-address-of-reference>"
        )
        main = next(
            item for item in result.semantic.bodies if item.name == "main"
        )
        self.assertEqual(main.statements[-1].expr.type.name, "u32")

    def test_public_phase1_pipeline_forms_mut_references_with_address_of_mut(self):
        source = """module test::phase1_address_of_mut_reference;
fn write(value: &mut u32) -> void {
    *value = 9u32;
    return;
}
fn main() -> u32 {
    let mut value: u32 = 7u32;
    write(&mut value);
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-address-of-mut-reference>"
        )
        main = next(
            item for item in result.semantic.bodies if item.name == "main"
        )
        self.assertEqual(main.statements[-1].expr.type.name, "u32")

    def test_public_phase1_pipeline_accepts_reference_mutability_weakening(self):
        source = """module test::phase1_reference_mutability_weakening;
fn view(value: &mut u32) -> &u32 {
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-reference-mutability-weakening>"
        )
        body = result.semantic.bodies[0]
        returned = body.statements[0].expr.type
        self.assertTrue(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_public_phase1_pipeline_accepts_string_literal_const_u8_pointer(self):
        source = """module test::phase1_string_literal;
fn consume(value: *const u8) -> *const u8 {
    return value;
}
fn text() -> *const u8 {
    return consume("sotlas");
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-string-literal>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "text"
        )
        returned = body.statements[0].expr.type
        self.assertEqual(returned.name, "u8")
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.mutable)
        self.assertFalse(returned.is_reference)

    def test_public_phase1_pipeline_accepts_null_raw_pointer_return(self):
        source = """module test::phase1_null_raw_pointer;
fn empty() -> *mut u32 {
    return null;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-null-raw-pointer>"
        )
        returned = result.semantic.bodies[0].statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertTrue(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_public_phase1_pipeline_accepts_raw_pointer_mutability_weakening(self):
        source = """module test::phase1_raw_pointer_mutability_weakening;
fn view(value: *const u32) -> *const u32 {
    return value;
}
fn expose(value: *mut u32) -> *const u32 {
    return view(value);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-raw-pointer-mutability-weakening>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "expose"
        )
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_public_phase1_pipeline_accepts_raw_void_pointer_compatibility(self):
        source = """module test::phase1_raw_void_pointer_compatibility;
fn erase(value: *const void) -> *const void {
    return value;
}
fn expose(value: *mut u32) -> *const void {
    return erase(value);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-raw-void-pointer-compatibility>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "expose"
        )
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "void")

    def test_public_phase1_pipeline_rejects_recursive_value_type(self):
        source = """module test::phase1_recursive_value;
struct Node {
    next: Node;
}
fn main() -> void { return; }
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: Node -> Node",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-recursive-value>"
            )

    def test_public_phase1_pipeline_allows_recursive_pointer_indirection(self):
        source = """module test::phase1_recursive_pointer;
struct Node {
    next: *mut Node;
}
fn main() -> void { return; }
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-recursive-pointer>"
        )
        field_type = result.semantic.typed_module.structs[0].fields[0].type
        self.assertTrue(field_type.pointer)
        self.assertEqual(field_type.name, "Node")

    def test_normal_package_import_does_not_auto_attach_phase1_state(self):
        source = """module test::phase1_no_side_effect;
fn main() -> void { return; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<phase1-no-side-effect>"
        )
        sotlas_compile.bootstrap.check(parsed)
        self.assertFalse(hasattr(parsed, "typed_ast"))
        self.assertFalse(hasattr(parsed, "phase1"))


if __name__ == "__main__":
    unittest.main()