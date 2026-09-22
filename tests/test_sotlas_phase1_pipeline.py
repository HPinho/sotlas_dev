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
        self.assertEqual(result.semantic.maturity, typed_ast.MATURITY)
        self.assertEqual(
            result.semantic.typed_module.maturity, typed_ast.MATURITY
        )
        self.assertEqual(result.semantic.typed_module.structs[0].name, "Token")
        self.assertEqual(result.semantic.bodies[0].name, "read")

    def test_public_phase1_pipeline_exposes_composed_ownership_sir(self):
        source = """module test::phase1_ownership_sir;
sole struct Token { value: u32; }

fn isolate(token: Token) -> void {
    quarantine token;
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-ownership-sir>"
        )

        self.assertEqual(
            tuple(item.function for item in result.ownership_sir.functions),
            ("isolate",),
        )
        function_plan = result.ownership_sir.functions[0]
        self.assertEqual(len(function_plan.domain.instructions), 1)
        transfer = function_plan.domain.instructions[0]
        self.assertEqual(transfer.operation, "quarantine")
        self.assertEqual(transfer.source_domain, "exclusive")
        self.assertEqual(transfer.target_domain, "island")
        self.assertEqual(function_plan.shared.semantic, ())
        graph_transfer = result.semantic.ownership_domains.transfers[0]
        self.assertEqual(graph_transfer.via, "quarantine")
        self.assertEqual(
            transfer.source.name, graph_transfer.binding
        )
        self.assertEqual(
            transfer.point_id, graph_transfer.point_id
        )
        self.assertTrue(transfer.point_id.startswith("quarantine@"))

    def test_public_phase1_pipeline_exposes_empty_ownership_sir_for_plain_code(self):
        source = """module test::phase1_plain_sir;
fn main(value: u32) -> u32 {
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-plain-sir>"
        )
        self.assertEqual(len(result.ownership_sir.functions), 1)
        function_plan = result.ownership_sir.functions[0]
        self.assertEqual(function_plan.domain.instructions, ())
        self.assertEqual(function_plan.shared.semantic, ())
        self.assertEqual(function_plan.shared.cleanup_segments, ())

    def test_public_phase1_pipeline_rejects_non_bool_control_flow_in_bootstrap(self):
        source = """module test::phase1_bool_control_flow;
fn main() -> void {
    if 1 {
        return;
    }
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"condição de if deve ser bool",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-bool-control-flow>"
            )

    def test_public_phase1_pipeline_accepts_raw_pointer_arithmetic_inside_unsafe(self):
        source = """module test::phase1_pointer_arithmetic;
fn advance(ptr: *const u8, offset: usize) -> *const u8 {
    unsafe {
        return ptr + offset;
    }
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-pointer-arithmetic>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "advance"
        )
        result_type = body.statements[0].body[0].expr.type
        self.assertTrue(result_type.pointer)
        self.assertFalse(result_type.is_reference)
        self.assertEqual(result_type.name, "u8")

    def test_public_phase1_pipeline_rejects_mixed_for_bounds_in_bootstrap(self):
        source = """module test::phase1_for_mixed_bounds;
fn main() -> void {
    for i in 0usize..3u32 {
        return;
    }
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"tipos dos limites de for incompatíveis: usize vs u32",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-for-mixed-bounds>"
            )

    def test_public_phase1_pipeline_rejects_explicit_numeric_type_mismatch_in_bootstrap(self):
        source = """module test::phase1_numeric_type_mismatch;
fn main(left: u32, right: u64) -> bool {
    return left < right;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"tipos incompatíveis em operador relacional <: u32 vs u64",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-numeric-type-mismatch>"
            )

    def test_public_phase1_pipeline_rejects_struct_literal_field_type_overflow_in_bootstrap(self):
        source = """module test::phase1_struct_literal_field_type;
struct Pixel { channel: u8; }
fn main() -> Pixel {
    return Pixel { channel: 256 };
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"valor inteiro 256 fora do intervalo para u8 \[0, 255\]",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-struct-literal-field-type>"
            )

    def test_public_phase1_pipeline_rejects_invalid_struct_literal_shape_in_bootstrap(self):
        source = """module test::phase1_struct_literal_shape;
struct Pair { left: u32; right: u32; }
fn main() -> Pair {
    return Pair { left: 1 };
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"campo\(s\) ausente\(s\) em struct literal Pair: right",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-struct-literal-shape>"
            )

    def test_public_phase1_pipeline_rejects_invalid_unary_operator_domain_in_bootstrap(self):
        source = """module test::phase1_unary_operator_domain;
fn main(value: u32) -> u32 {
    return -value;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"operador - unário exige inteiro signed ou float",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-unary-operator-domain>"
            )

    def test_public_phase1_pipeline_rejects_invalid_numeric_operator_domain_in_bootstrap(self):
        source = """module test::phase1_numeric_operator_domain;
fn main(flag: bool) -> bool {
    return flag + flag;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"operador aritmético \+ exige operandos numéricos escalares",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-numeric-operator-domain>"
            )

    def test_public_phase1_pipeline_types_valid_function_field_call(self):
        source = """module test::phase1_fn_field_valid;
struct Dispatch {
    call: fn(u16) -> u32;
}
fn invoke(dispatch: &Dispatch) -> u32 {
    return dispatch.call(7);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-fn-field-valid>"
        )
        body = next(
            item for item in result.semantic.bodies
            if item.name == "invoke"
        )
        self.assertEqual(body.statements[0].expr.type.name, "u32")

    def test_public_phase1_pipeline_rejects_function_field_contract_in_bootstrap(self):
        source = """module test::phase1_fn_field_bad_type;
struct Dispatch {
    call: fn(u32) -> u32;
}
fn invoke(dispatch: &Dispatch, flag: bool) -> u32 {
    return dispatch.call(flag);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em campo de função "
            r"Dispatch\.call: esperado u32, recebido bool",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-fn-field-bad-type>"
            )

    def test_public_phase1_pipeline_rejects_explicit_method_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_method_explicit_numeric_mismatch;
struct Counter {
    value: u32;
    fn increment(self: *mut Counter, amount: u32) -> u32 {
        return amount;
    }
}
fn main(counter: Counter) -> u32 {
    return counter.increment(1u64);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em método Counter\.increment: "
            r"esperado u32, recebido u64",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-method-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_rejects_method_contract_mismatch_in_bootstrap(self):
        source = """module test::phase1_method_contract;
struct Counter {
    value: u32;
    fn increment(self: *mut Counter, amount: u32) -> u32 {
        return amount;
    }
}
fn main(counter: Counter, flag: bool) -> u32 {
    return counter.increment(flag);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em método Counter\.increment",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-method-contract>"
            )

    def test_public_phase1_pipeline_rejects_explicit_call_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_call_explicit_numeric_mismatch;
fn take(value: u32) -> u32 {
    return value;
}
fn main() -> u32 {
    return take(1u64);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em chamada take: "
            r"esperado u32, recebido u64",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-call-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_rejects_call_contract_mismatch_in_bootstrap(self):
        source = """module test::phase1_call_contract;
fn consume(value: u32) -> void {
    return;
}
fn main(flag: bool) -> void {
    consume(flag);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em chamada consume",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-call-contract>"
            )

    def test_public_phase1_pipeline_rejects_explicit_return_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_return_explicit_numeric_mismatch;
fn main() -> u32 {
    return 1u64;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-return-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_rejects_explicit_assignment_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_assignment_explicit_numeric_mismatch;
fn main() -> void {
    let value: u32 = 1u32;
    value = 2u64;
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"atribuição incompatível",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-assignment-explicit-numeric-mismatch>",
            )

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

    def test_public_phase1_pipeline_rejects_constant_left_shift_overflow_in_bootstrap(self):
        source = """module test::phase1_left_shift_overflow;
fn main() -> u8 {
    return 128u8 << 1u8;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"valor inteiro 256 fora do intervalo para u8 \[0, 255\]",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-left-shift-overflow>"
            )

    def test_public_phase1_pipeline_rejects_out_of_range_shift_in_bootstrap(self):
        source = """module test::phase1_shift_width;
fn main(value: u32) -> u32 {
    return value << 32;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"contador de deslocamento 32 fora do intervalo para u32 de largura 32",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-shift-width>"
            )

    def test_public_phase1_pipeline_rejects_signed_minimum_division_overflow_in_bootstrap(self):
        source = """module test::phase1_i8_div_overflow;
fn main() -> i8 {
    return -128i8 / -1i8;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"overflow de divisão inteira para mínimo de i8 dividido por -1",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-i8-div-overflow>"
            )

    def test_public_phase1_pipeline_rejects_constant_integer_division_by_zero_in_bootstrap(self):
        source = """module test::phase1_integer_div_zero;
fn main(value: u32) -> u32 {
    return value / (2 - 2);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"divisão inteira por zero não é permitida",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-integer-div-zero>"
            )

    def test_public_phase1_pipeline_rejects_constant_integer_overflow_in_bootstrap(self):
        source = """module test::phase1_integer_overflow;
fn main() -> u8 {
    return 255u8 + 1u8;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"valor inteiro 256 fora do intervalo para u8 \[0, 255\]",
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

    def test_public_phase1_pipeline_preserves_mutable_local_metadata(self):
        source = """module test::phase1_binding_mutability_metadata;
fn main() -> u32 {
    let mut value: u32 = 7u32;
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-binding-mutability-metadata>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "main"
        )
        binding = body.statements[0]
        self.assertEqual(binding.kind, "Let")
        self.assertTrue(binding.is_mut)
        self.assertEqual(binding.name, "value")

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

    def test_public_phase1_pipeline_rejects_mut_borrow_of_immutable_binding(self):
        source = """module test::phase1_mut_borrow_immutable_binding;
fn write(value: &mut u32) -> void {
    *value = 9u32;
    return;
}
fn main() -> void {
    let value: u32 = 7u32;
    write(&mut value);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"referência mutável exige binding mutável",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-mut-borrow-immutable-binding>",
            )

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

    def test_public_phase1_pipeline_rejects_pointer_comparison_type_mismatch_in_bootstrap(self):
        source = """module test::phase1_pointer_compare_mismatch;
fn same(left: *mut u32, right: *const u32) -> bool {
    return left == right;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"tipos incompatíveis em comparação ==: u32 vs u32",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-pointer-compare-mismatch>"
            )

    def test_public_phase1_pipeline_rejects_reference_null_comparison(self):
        source = """module test::phase1_reference_null_comparison;
fn is_null(value: &u32) -> bool {
    return value == null;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"referência segura não pode ser comparada a null",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-reference-null-comparison>"
            )

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



    def test_public_phase1_pipeline_accepts_function_values_with_exact_signature(self):
        source = """module test::phase1_function_value;
fn bump(value: u32) -> u32 {
    return value + 1;
}
fn install(callback: fn(u32) -> u32) -> void {
    return;
}
fn main() -> void {
    let local: fn(u32) -> u32 = bump;
    install(local);
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-function-value>"
        )
        emitted = sotlas_compile.bootstrap.emit_c(result.parsed_module)
        self.assertIn("uint32_t (*callback)(uint32_t)", emitted)
        self.assertIn("uint32_t (*local)(uint32_t) = bump;", emitted)

    def test_public_phase1_pipeline_rejects_function_value_signature_mismatch(self):
        source = """module test::phase1_function_value_mismatch;
fn wrong(value: u64) -> u32 {
    return 1;
}
fn install(callback: fn(u32) -> u32) -> void {
    return;
}
fn main() -> void {
    install(wrong);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em chamada install",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-function-value-mismatch>"
            )



    def test_public_phase1_pipeline_deref_value_does_not_inherit_pointer_mutability(self):
        source = """module test::phase1_deref_value_type;
struct Boxed {
    value: u32;
}
fn consume(value: Boxed) -> u32 {
    return value.value;
}
fn read(ptr: *mut Boxed) -> u32 {
    unsafe {
        return consume(*ptr);
    }
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-deref-value-type>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "read"
        )
        self.assertEqual(body.statements[0].body[0].expr.type.name, "u32")


if __name__ == "__main__":
    unittest.main()