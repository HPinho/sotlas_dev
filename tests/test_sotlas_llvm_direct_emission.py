"""Testes de emissão direta de código objeto (.obj / .o) e executáveis nativos via LLVM / LLD."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.llvm_toolchain import (
    LLVMToolchain,
    LLVMToolchainError,
    default_toolchain,
    require_llvm_ownership_supported,
)


class TestSotlasLLVMDirectEmission(unittest.TestCase):
    def setUp(self):
        self.toolchain = default_toolchain
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_source_llvm_emission_accepts_execution_target_features(self):
        path = self.tmp_path / "target.ll"
        result = self.toolchain.compile_source_to_native(
            "module target_demo; pub fn main() -> i32 { return 0; }",
            "target_demo",
            path,
            emit_type="llvm",
            target="x86_64-unknown-linux-gnu",
            cpu_features=("avx2",),
        )
        ir = result.read_text(encoding="utf-8")
        self.assertIn('target triple = "x86_64-unknown-linux-gnu"', ir)
        self.assertIn('"target-features"="+sse2,+avx,+avx2"', ir)

    def test_source_llvm_emission_rejects_prototype_fallback_bodies(self):
        local_destination = self.tmp_path / "local_const.ll"
        self.toolchain.compile_source_to_native(
            "module test::llvm_local_const; "
            "fn answer() -> u32 { let value: u32 = 7u32; return value; }",
            "test::llvm_local_const",
            local_destination,
            emit_type="llvm",
            backend="llvm",
        )
        self.assertIn(
            "add i32 0, 7", local_destination.read_text(encoding="utf-8")
        )

        alias_destination = self.tmp_path / "local_parameter_alias.ll"
        self.toolchain.compile_source_to_native(
            "module test::llvm_local_alias; "
            "fn identity(input: u32) -> u32 { "
            "let value: u32 = input; return value; }",
            "test::llvm_local_alias",
            alias_destination,
            emit_type="llvm",
            backend="llvm",
        )
        alias_ir = alias_destination.read_text(encoding="utf-8")
        self.assertIn("ret i32 %input", alias_ir)

        for literal, expected in (("true", "1"), ("false", "0")):
            direct_bool = self.tmp_path / f"direct_bool_{expected}.ll"
            self.toolchain.compile_source_to_native(
                "module test::llvm_bool_direct; "
                f"fn answer() -> bool {{ return {literal}; }}",
                "test::llvm_bool_direct",
                direct_bool,
                emit_type="llvm",
                backend="llvm",
            )
            direct_ir = direct_bool.read_text(encoding="utf-8")
            self.assertIn(f"add i1 0, {expected}", direct_ir)
            direct_object = self.tmp_path / f"direct_bool_{expected}.obj"
            self.toolchain.compile_llvm_ir_to_obj(direct_ir, direct_object)
            self.assertGreater(direct_object.stat().st_size, 0)

            local_bool = self.tmp_path / f"local_bool_{expected}.ll"
            self.toolchain.compile_source_to_native(
                "module test::llvm_bool_local; "
                f"fn answer() -> bool {{ let value: bool = {literal}; "
                "return value; }",
                "test::llvm_bool_local",
                local_bool,
                emit_type="llvm",
                backend="llvm",
            )
            local_ir = local_bool.read_text(encoding="utf-8")
            self.assertIn(f"add i1 0, {expected}", local_ir)
            local_object = self.tmp_path / f"local_bool_{expected}.obj"
            self.toolchain.compile_llvm_ir_to_obj(local_ir, local_object)
            self.assertGreater(local_object.stat().st_size, 0)

        comparison = self.tmp_path / "local_comparison.ll"
        self.toolchain.compile_source_to_native(
            "module test::llvm_local_comparison; "
            "fn is_less(left: u32, right: u32) -> bool { "
            "let result: bool = left < right; return result; }",
            "test::llvm_local_comparison",
            comparison,
            emit_type="llvm",
            backend="llvm",
        )
        comparison_ir = comparison.read_text(encoding="utf-8")
        self.assertIn("icmp ult i32 %left, %right", comparison_ir)
        comparison_object = self.tmp_path / "local_comparison.obj"
        self.toolchain.compile_llvm_ir_to_obj(comparison_ir, comparison_object)
        self.assertGreater(comparison_object.stat().st_size, 0)

        cases = (
            (
                "module test::llvm_unlowered_value; "
                "fn answer(input: u32) -> u32 { "
                "let value: u32 = input + 7u32; return value; }",
                "answer",
            ),
            (
                "module test::llvm_unlowered_void; "
                "fn work() -> void { let value: u32 = 7u32; return; }",
                "work",
            ),
        )
        for source, function_name in cases:
            with self.subTest(function=function_name):
                destination = self.tmp_path / f"{function_name}.ll"
                with self.assertRaisesRegex(
                    LLVMToolchainError,
                    rf"prototype SIR.*'{function_name}'",
                ):
                    self.toolchain.compile_source_to_native(
                        source,
                        f"test::llvm_unlowered_{function_name}",
                        destination,
                        emit_type="llvm",
                        backend="llvm",
                    )
                self.assertFalse(destination.exists())

    def test_sir_prototype_marks_functions_with_unlowered_bodies(self):
        from sotlas.sir.generator import SIRGenerator
        from sotlas_compile import bootstrap

        module = bootstrap.parse(
            "module test::sir_unlowered; "
            "fn answer(input: u32) -> u32 { "
            "let value: u32 = input + 7u32; return value; }"
        )
        sir = SIRGenerator().generate_from_ast(module)
        self.assertEqual(sir.unlowered_functions, ["answer"])

    def test_llvm_toolchain_detected(self):
        self.assertTrue(self.toolchain.is_available(), "LLVM Clang deve ser detectado no ambiente")
        version = self.toolchain.get_version()
        self.assertIn("clang version", version)
        clang_path = self.toolchain.find_tool("clang")
        self.assertIsNotNone(clang_path)
        self.assertTrue(clang_path.exists())

    def test_compile_llvm_ir_to_native_obj(self):
        ir_code = """
target triple = "x86_64-pc-windows-msvc"

define i32 @add_numbers(i32 %a, i32 %b) {
entry:
    %res = add i32 %a, %b
    ret i32 %res
}
"""
        obj_file = self.tmp_path / "math.obj"
        res_obj = self.toolchain.compile_llvm_ir_to_obj(ir_code, obj_file, opt_level=2)
        self.assertTrue(res_obj.is_file())
        self.assertGreater(res_obj.stat().st_size, 0)

    def test_link_native_executable_and_execute(self):
        ir_code = """
target triple = "x86_64-pc-windows-msvc"

define i32 @main() {
entry:
    ret i32 55
}
"""
        obj_file = self.tmp_path / "main.obj"
        exe_file = self.tmp_path / "main.exe"

        self.toolchain.compile_llvm_ir_to_obj(ir_code, obj_file)
        self.toolchain.link_native_binary([obj_file], exe_file)

        self.assertTrue(exe_file.is_file())
        run_res = subprocess.run([str(exe_file)])
        self.assertEqual(run_res.returncode, 55)

    def test_compile_sotlas_source_to_native_obj(self):
        source = """module test::obj_demo;
pub fn compute(x: u32) -> u32 {
    let factor: u32 = 4;
    return x * factor;
}
"""
        obj_file = self.tmp_path / "compute.obj"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::obj_demo",
            obj_file,
            emit_type="obj",
            backend="c11"
        )
        self.assertTrue(res.is_file())
        self.assertGreater(res.stat().st_size, 100)

    def test_compile_sotlas_source_to_native_exe_and_run(self):
        source = """module test::exe_demo;
pub fn main() -> i32 {
    let mut a: i32 = 20;
    let b: i32 = 22;
    return a + b;
}
"""
        exe_file = self.tmp_path / "test_app.exe"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::exe_demo",
            exe_file,
            emit_type="exe",
            backend="c11"
        )
        self.assertTrue(res.is_file())
        run_res = subprocess.run([str(res)])
        self.assertEqual(run_res.returncode, 42)

    def test_llvm_integer_literal_executes_in_native_binary(self):
        source = """module test::llvm_unsigned_native;
pub fn main() -> i32 {
    return 42i32;
}
"""
        exe_file = self.tmp_path / "llvm_unsigned_native.exe"
        result = self.toolchain.compile_source_to_native(
            source,
            "test::llvm_unsigned_native",
            exe_file,
            emit_type="exe",
            backend="llvm",
        )
        self.assertTrue(result.is_file())
        run_result = subprocess.run([str(result)])
        self.assertEqual(run_result.returncode, 42)

    def test_llvm_unsigned_parameter_arithmetic_executes_from_native_caller(self):
        source = """module test::llvm_unsigned_native_call;
pub fn add_numbers(left: u32, right: u32) -> u32 {
    return left + right;
}
"""
        object_file = self.tmp_path / "llvm_unsigned_native_call.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_unsigned_native_call",
            object_file,
            emit_type="obj",
            backend="llvm",
        )
        caller_file = self.tmp_path / "native_caller.c"
        caller_file.write_text(
            "extern unsigned int add_numbers(unsigned int, unsigned int);\n"
            "int main(void) { return add_numbers(40u, 2u) == 42u ? 0 : 1; }\n",
            encoding="utf-8",
        )
        executable = self.tmp_path / "llvm_unsigned_native_call.exe"
        clang = self.toolchain.find_tool("clang")
        self.assertIsNotNone(clang)
        subprocess.run(
            [str(clang), str(caller_file), str(object_file), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        )
        run_result = subprocess.run([str(executable)])
        self.assertEqual(run_result.returncode, 0)

    def test_llvm_lowers_and_executes_source_unsigned_accumulation_loop(self):
        source = """module test::llvm_loop_native;
pub fn sum_to(limit: u32) -> u32 {
    let mut index: u32 = 0u32;
    let mut total: u32 = 0u32;
    while index < limit {
        total = total + index;
        index = index + 1u32;
    }
    return total;
}
"""
        llvm_file = self.tmp_path / "llvm_loop_native.ll"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_loop_native",
            llvm_file,
            emit_type="llvm",
            backend="llvm",
        )
        llvm_ir = llvm_file.read_text(encoding="utf-8")
        self.assertIn("phi i32", llvm_ir)
        self.assertIn("br label %bbwhile_", llvm_ir)

        object_file = self.tmp_path / "llvm_loop_native.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_loop_native",
            object_file,
            emit_type="obj",
            backend="llvm",
        )
        caller_file = self.tmp_path / "llvm_loop_caller.c"
        caller_file.write_text(
            "#include <stdint.h>\n"
            "extern uint32_t sum_to(uint32_t);\n"
            "int main(void) { return sum_to(4u) == 6u && "
            "sum_to(1u) == 0u && sum_to(0u) == 0u ? 0 : 1; }\n",
            encoding="utf-8",
        )
        compiler = self.toolchain.find_tool("clang")
        self.assertIsNotNone(compiler)
        executable = self.tmp_path / "llvm_loop_native.exe"
        subprocess.run(
            [str(compiler), str(caller_file), str(object_file), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run([str(executable)], check=False)
        self.assertEqual(result.returncode, 0)

    def test_c11_and_llvm_backends_agree_on_shared_unsigned_arithmetic_input(self):
        source = """module test::backend_differential;
pub fn add_numbers(left: u32, right: u32) -> u32 {
    return left + right;
}
"""
        clang = self.toolchain.find_tool("clang")
        if clang is None:
            self.skipTest("Clang is required for the C11/LLVM differential test")

        caller = self.tmp_path / "backend_caller.c"
        caller.write_text(
            "#include <stdint.h>\n"
            "extern uint32_t add_numbers(uint32_t, uint32_t);\n"
            "int main(void) { return add_numbers(40u, 2u) == 42u ? 0 : 1; }\n",
            encoding="utf-8",
        )
        results = {}
        for backend in ("c11", "llvm"):
            with self.subTest(backend=backend):
                object_file = self.tmp_path / f"{backend}.o"
                self.toolchain.compile_source_to_native(
                    source,
                    "test::backend_differential",
                    object_file,
                    emit_type="obj",
                    backend=backend,
                )
                executable = self.tmp_path / f"{backend}-caller.exe"
                subprocess.run(
                    [str(clang), str(caller), str(object_file), "-o", str(executable)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                results[backend] = subprocess.run(
                    [str(executable)], capture_output=True, text=True, check=False
                ).returncode

        self.assertEqual(results, {"c11": 0, "llvm": 0})

    def test_c11_and_llvm_backends_agree_on_unsigned_literal_arithmetic(self):
        source = """module test::backend_literal_differential;
pub fn add_bias(value: u32) -> u32 {
    return value + 2u32;
}
"""
        clang = self.toolchain.find_tool("clang")
        if clang is None:
            self.skipTest("Clang is required for the C11/LLVM differential test")

        caller = self.tmp_path / "literal_backend_caller.c"
        caller.write_text(
            "#include <stdint.h>\n"
            "extern uint32_t add_bias(uint32_t);\n"
            "int main(void) { return add_bias(40u) == 42u ? 0 : 1; }\n",
            encoding="utf-8",
        )
        results = {}
        for backend in ("c11", "llvm"):
            with self.subTest(backend=backend):
                object_file = self.tmp_path / f"literal-{backend}.o"
                self.toolchain.compile_source_to_native(
                    source,
                    "test::backend_literal_differential",
                    object_file,
                    emit_type="obj",
                    backend=backend,
                )
                executable = self.tmp_path / f"literal-{backend}-caller.exe"
                subprocess.run(
                    [str(clang), str(caller), str(object_file), "-o", str(executable)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                results[backend] = subprocess.run(
                    [str(executable)], capture_output=True, text=True, check=False
                ).returncode
        self.assertEqual(results, {"c11": 0, "llvm": 0})

    def test_c11_and_llvm_match_unsigned_sub_mul_and_wraparound(self):
        source = """module test::backend_unsigned_arithmetic_matrix;
pub fn add_numbers(left: u32, right: u32) -> u32 { return left + right; }
pub fn subtract_numbers(left: u32, right: u32) -> u32 { return left - right; }
pub fn multiply_numbers(left: u32, right: u32) -> u32 { return left * right; }
"""
        clang = self.toolchain.find_tool("clang")
        if clang is None:
            self.skipTest("Clang is required for the C11/LLVM differential test")

        caller = self.tmp_path / "unsigned_matrix_caller.c"
        caller.write_text(
            "#include <stdint.h>\n"
            "#include <limits.h>\n"
            "extern uint32_t add_numbers(uint32_t, uint32_t);\n"
            "extern uint32_t subtract_numbers(uint32_t, uint32_t);\n"
            "extern uint32_t multiply_numbers(uint32_t, uint32_t);\n"
            "int main(void) {\n"
            "  if (add_numbers(40u, 2u) != 42u) return 1;\n"
            "  if (add_numbers(UINT32_MAX, 1u) != 0u) return 2;\n"
            "  if (subtract_numbers(40u, 2u) != 38u) return 3;\n"
            "  if (subtract_numbers(0u, 1u) != UINT32_MAX) return 4;\n"
            "  if (multiply_numbers(6u, 7u) != 42u) return 5;\n"
            "  if (multiply_numbers(65536u, 65536u) != 0u) return 6;\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        results = {}
        for backend in ("c11", "llvm"):
            with self.subTest(backend=backend):
                object_file = self.tmp_path / f"unsigned-matrix-{backend}.o"
                self.toolchain.compile_source_to_native(
                    source,
                    "test::backend_unsigned_arithmetic_matrix",
                    object_file,
                    emit_type="obj",
                    backend=backend,
                )
                executable = self.tmp_path / f"unsigned-matrix-{backend}.exe"
                subprocess.run(
                    [str(clang), str(caller), str(object_file), "-o", str(executable)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                results[backend] = subprocess.run(
                    [str(executable)], capture_output=True, text=True, check=False
                ).returncode

        self.assertEqual(results, {"c11": 0, "llvm": 0})

    def test_c11_and_llvm_backends_agree_on_signed_comparison_inputs(self):
        source = """module test::backend_signed_compare_differential;
pub fn less(left: i32, right: i32) -> bool {
    return left < right;
}
"""
        clang = self.toolchain.find_tool("clang")
        if clang is None:
            self.skipTest("Clang is required for the C11/LLVM differential test")

        caller = self.tmp_path / "signed_compare_backend_caller.c"
        caller.write_text(
            "#include <stdbool.h>\n"
            "extern bool less(int, int);\n"
            "int main(void) {\n"
            "  if (!less(-10, 2)) return 1;\n"
            "  if (less(2, -10)) return 2;\n"
            "  if (less(-4, -4)) return 3;\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        results = {}
        for backend in ("c11", "llvm"):
            with self.subTest(backend=backend):
                object_file = self.tmp_path / f"signed-compare-{backend}.o"
                self.toolchain.compile_source_to_native(
                    source,
                    "test::backend_signed_compare_differential",
                    object_file,
                    emit_type="obj",
                    backend=backend,
                )
                executable = self.tmp_path / f"signed-compare-{backend}.exe"
                subprocess.run(
                    [str(clang), str(caller), str(object_file), "-o", str(executable)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                results[backend] = subprocess.run(
                    [str(executable)], capture_output=True, text=True, check=False
                ).returncode

        self.assertEqual(results, {"c11": 0, "llvm": 0})

    def test_c11_and_llvm_match_f64_arithmetic_and_comparison(self):
        source = """module test::backend_f64_differential;
pub fn product(left: f64, right: f64) -> f64 {
    return left * right;
}
pub fn sum(left: f64, right: f64) -> f64 {
    return left + right;
}
pub fn difference(left: f64, right: f64) -> f64 {
    return left - right;
}
pub fn quotient(left: f64, right: f64) -> f64 {
    return left / right;
}
pub fn product_f32(left: f32, right: f32) -> f32 {
    return left * right;
}
pub fn identity(value: f64) -> f64 {
    return value;
}
pub fn below(value: f64, limit: f64) -> bool {
    return value < limit;
}
pub fn same(left: f64, right: f64) -> bool {
    return left == right;
}
pub fn different(left: f64, right: f64) -> bool {
    return left != right;
}
pub fn at_most(left: f64, right: f64) -> bool {
    return left <= right;
}
pub fn above(left: f64, right: f64) -> bool {
    return left > right;
}
pub fn at_least(left: f64, right: f64) -> bool {
    return left >= right;
}
"""
        clang = self.toolchain.find_tool("clang")
        if clang is None:
            self.skipTest("Clang is required for the C11/LLVM differential test")

        caller = self.tmp_path / "f64_backend_caller.c"
        caller.write_text(
            "#include <stdbool.h>\n"
            "#include <math.h>\n"
            "extern double product(double, double);\n"
            "extern double sum(double, double);\n"
            "extern double difference(double, double);\n"
            "extern double quotient(double, double);\n"
            "extern float product_f32(float, float);\n"
            "extern double identity(double);\n"
            "extern bool below(double, double);\n"
            "extern bool same(double, double);\n"
            "extern bool different(double, double);\n"
            "extern bool at_most(double, double);\n"
            "extern bool above(double, double);\n"
            "extern bool at_least(double, double);\n"
            "int main(void) {\n"
            "  if (product(1.5, 2.0) != 3.0) return 1;\n"
            "  if (product(-1.25, 2.0) != -2.5) return 2;\n"
            "  if (sum(1.25, 2.75) != 4.0) return 10;\n"
            "  if (difference(-1.0, 2.5) != -3.5) return 11;\n"
            "  if (quotient(7.5, 2.5) != 3.0) return 12;\n"
            "  if (product_f32(1.5f, 2.0f) != 3.0f) return 13;\n"
            "  if (identity(-3.75) != -3.75) return 9;\n"
            "  if (!below(-1.0, 0.0)) return 3;\n"
            "  if (below(0.0, -1.0)) return 4;\n"
            "  if (below(2.5, 2.5)) return 5;\n"
            "  if (!at_most(2.5, 2.5)) return 14;\n"
            "  if (!above(3.0, 2.5)) return 15;\n"
            "  if (!at_least(2.5, 2.5)) return 16;\n"
            "  if (below(NAN, 0.0)) return 6;\n"
            "  if (!same(2.5, 2.5)) return 7;\n"
            "  if (same(NAN, NAN)) return 8;\n"
            "  if (!different(NAN, NAN)) return 17;\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        results = {}
        for backend in ("c11", "llvm"):
            with self.subTest(backend=backend):
                object_file = self.tmp_path / f"f64-{backend}.o"
                self.toolchain.compile_source_to_native(
                    source,
                    "test::backend_f64_differential",
                    object_file,
                    emit_type="obj",
                    backend=backend,
                )
                executable = self.tmp_path / f"f64-{backend}-caller.exe"
                subprocess.run(
                    [str(clang), str(caller), str(object_file), "-o", str(executable)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                results[backend] = subprocess.run(
                    [str(executable)], capture_output=True, text=True, check=False
                ).returncode

        self.assertEqual(results, {"c11": 0, "llvm": 0})

    def test_llvm_signed_parameter_comparison_executes_from_native_caller(self):
        source = """module test::llvm_signed_native_compare;
pub fn less(left: i32, right: i32) -> bool {
    return left < right;
}
"""
        object_file = self.tmp_path / "llvm_signed_native_compare.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_signed_native_compare",
            object_file,
            emit_type="obj",
            backend="llvm",
        )
        caller_file = self.tmp_path / "native_signed_compare_caller.c"
        caller_file.write_text(
            "#include <stdbool.h>\n"
            "extern bool less(int, int);\n"
            "int main(void) { return less(-10, 2) && !less(2, -10) ? 0 : 1; }\n",
            encoding="utf-8",
        )
        executable = self.tmp_path / "llvm_signed_native_compare.exe"
        clang = self.toolchain.find_tool("clang")
        self.assertIsNotNone(clang)
        subprocess.run(
            [str(clang), str(caller_file), str(object_file), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        )
        run_result = subprocess.run([str(executable)])
        self.assertEqual(run_result.returncode, 0)

    def test_compile_sotlas_source_to_llvm_ir(self):
        source = """module test::ir_demo;
pub fn answer() -> i32 {
    return 42;
}
"""
        ll_file = self.tmp_path / "answer.ll"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::ir_demo",
            ll_file,
            emit_type="llvm",
            backend="llvm"
        )
        self.assertTrue(res.is_file())
        content = res.read_text(encoding="utf-8")
        self.assertIn("ModuleID", content)
        self.assertIn("@answer", content)

    def test_llvm_source_backend_emits_nested_if_return_cfg(self):
        source = """module test::llvm_nested_if_return;
pub fn choose(flag: bool, left: u32, right: u32) -> void {
    if flag {
        if left < right { return; } else { return; }
    } else {
        return;
    }
}
"""
        ll_file = self.tmp_path / "nested_if_return.ll"
        result = self.toolchain.compile_source_to_native(
            source,
            "test::llvm_nested_if_return",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        self.assertTrue(result.is_file())
        content = result.read_text(encoding="utf-8")
        self.assertIn("icmp ult i32 %left, %right", content)
        self.assertEqual(content.count("ret void"), 3)
        object_file = self.tmp_path / "nested_if_return.obj"
        object_result = self.toolchain.compile_source_to_native(
            source,
            "test::llvm_nested_if_return",
            object_file,
            emit_type="obj",
            backend="llvm",
        )
        self.assertTrue(object_result.is_file())
        self.assertGreater(object_result.stat().st_size, 100)

    def test_llvm_source_backend_lowers_if_expression_return_phi(self):
        source = """module test::llvm_if_expression_return;
pub fn choose(flag: bool, yes: u32, no: u32) -> u32 {
    return if flag { yes } else { no };
}
"""
        ll_file = self.tmp_path / "if_expression_return.ll"
        result = self.toolchain.compile_source_to_native(
            source,
            "test::llvm_if_expression_return",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        content = result.read_text(encoding="utf-8")
        self.assertIn(" = phi i32 ", content)
        self.assertIn("ret i32 %if_value", content)
        object_file = self.tmp_path / "if_expression_return.obj"
        object_result = self.toolchain.compile_source_to_native(
            source,
            "test::llvm_if_expression_return",
            object_file,
            emit_type="obj",
            backend="llvm",
        )
        self.assertTrue(object_result.is_file())
        self.assertGreater(object_result.stat().st_size, 100)

    def test_llvm_source_backend_lowers_trivial_call_scoped_direct_domain(self):
        source = """module test::llvm_direct;
sole struct Token { value: u32; }
fn inspect(left: direct Token, right: direct Token) -> void { return; }
fn main(left: Token, right: Token) -> void {
    inspect(&left, &right);
    return;
}
"""
        ll_file = self.tmp_path / "direct.ll"
        obj_file = self.tmp_path / "direct.obj"

        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )

        ir = ll_file.read_text(encoding="utf-8")
        self.assertEqual(ir.count("direct access"), 2)
        self.assertIn("call void @inspect(ptr %slot_left2, ptr %slot_right3)", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_lowers_verified_call_scoped_whisper_domain(self):
        source = """module test::llvm_whisper;
sole struct Token { value: u32; }
fn inspect(primary: direct Token, observer: whisper Token) -> void { return; }
fn caller(token: Token) -> void { inspect(&token, &token); return; }
"""
        ll_file = self.tmp_path / "whisper.ll"
        obj_file = self.tmp_path / "whisper.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_whisper",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertIn("direct access %token -> @inspect.primary", ir)
        self.assertIn("whisper borrow %token -> @inspect.observer", ir)
        self.assertIn("call void @inspect(ptr %slot_token", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_forwards_direct_borrow_to_whisper(self):
        source = """module test::llvm_direct_to_whisper;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> void { return; }
fn forward(token: direct Token) -> void { inspect(token); return; }
fn caller(token: Token) -> void { forward(&token); return; }
"""
        ll_file = self.tmp_path / "direct_to_whisper.ll"
        obj_file = self.tmp_path / "direct_to_whisper.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct_to_whisper",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertIn("whisper borrow %token -> @inspect.token [whisper@", ir)
        self.assertIn("call void @inspect(ptr %direct_token", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_accepts_direct_borrow_from_island(self):
        source = """module test::llvm_direct_island;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn read_island(token: island Token) -> void {
    inspect(&token);
    return;
}
"""
        ll_file = self.tmp_path / "direct_island.ll"
        obj_file = self.tmp_path / "direct_island.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct_island",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertIn("direct access %token -> @inspect.token", ir)
        self.assertIn("call void @inspect(ptr %slot_token", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_lowers_integer_comparison_condition(self):
        source = """module test::llvm_integer_compare_condition;
fn choose(left: u32, right: u32) -> void {
    if left < right { return; }
    return;
}
"""
        ll_file = self.tmp_path / "integer_compare_condition.ll"
        obj_file = self.tmp_path / "integer_compare_condition.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_integer_compare_condition",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertRegex(ir, r"icmp ult i32 %left, %right")
        self.assertRegex(ir, r"br i1 %cmp\d+, label %bb")
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)


    def test_llvm_source_backend_preserves_forwarded_direct_access(self):
        source = """module test::llvm_direct_forward;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn forward(token: direct Token) -> void { inspect(token); return; }
fn caller(token: Token) -> void { forward(&token); return; }
"""
        ll_file = self.tmp_path / "direct_forward.ll"
        obj_file = self.tmp_path / "direct_forward.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct_forward",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertIn("direct access %token -> @inspect.token", ir)
        self.assertRegex(ir, r"call void @inspect\(ptr %direct_token\d+\)")
        self.assertIn("call void @forward(ptr %slot_token", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_places_deferred_direct_call_before_return(self):
        source = """module test::llvm_direct_defer;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn deferred(token: direct Token) -> void {
    defer inspect(token);
    return;
}
fn caller(token: Token) -> void { deferred(&token); return; }
"""
        ll_file = self.tmp_path / "direct_defer.ll"
        obj_file = self.tmp_path / "direct_defer.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct_defer",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        deferred_body = ir.split("define void @deferred(", 1)[1].split(
            "define void @caller(", 1
        )[0]
        self.assertLess(deferred_body.index("direct access"), deferred_body.index("call void @inspect"))
        self.assertLess(deferred_body.index("call void @inspect"), deferred_body.index("ret void"))
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_fails_closed_for_unverified_direct_domain(self):
        module = SimpleNamespace(
            structs=(),
            functions=(SimpleNamespace(
                params=(("token", SimpleNamespace(
                    name="Token", ownership_domain="direct",
                    pointer=True, is_reference=True,
                )),),
                result=SimpleNamespace(name="u32"),
            ),),
            classes=(),
            globals=(),
            enums=(),
        )
        frontend = SimpleNamespace(check=lambda parsed: None)
        with self.assertRaisesRegex(
            LLVMToolchainError,
            "LLVM backend does not lower canonical Ownership Domains yet",
        ):
            require_llvm_ownership_supported(module, frontend)

    def test_llvm_direct_backend_rejects_unlowered_control_flow(self):
        source = """module test::llvm_direct_cfg;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn main(token: Token) -> void {
    if true { inspect(&token); }
    return;
}
"""

        with self.assertRaisesRegex(
            LLVMToolchainError,
            "LLVM backend does not lower canonical Ownership Domains yet",
        ):
            self.toolchain.compile_source_to_native(
                source,
                "test::llvm_direct_cfg",
                self.tmp_path / "direct_cfg.ll",
                emit_type="llvm",
                backend="llvm",
            )

    def test_llvm_backend_fails_closed_for_unlowered_region_device_external(self):
        for domain in ("region", "device", "external"):
            with self.subTest(domain=domain):
                source = (
                    "module test::llvm_domain_gate; "
                    "sole struct Resource { value: u32; } "
                    f"fn use(resource: {domain} Resource) -> void {{ return; }}"
                )
                with self.assertRaisesRegex(
                    LLVMToolchainError,
                    "LLVM backend does not lower canonical Ownership Domains yet",
                ):
                    self.toolchain.compile_source_to_native(
                        source,
                        f"test::llvm_{domain}_gate",
                        self.tmp_path / f"{domain}.ll",
                        emit_type="llvm",
                        backend="llvm",
                    )


if __name__ == "__main__":
    unittest.main()
