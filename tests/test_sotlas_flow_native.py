"""Native C11 execution for the certified serial scalar Flow subset."""
from __future__ import annotations

import os
import importlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.llvm_toolchain import (  # noqa: E402
    canonical_llvm_frontend,
    default_toolchain,
)

bootstrap = canonical_llvm_frontend()


class SotlasFlowNativeTests(unittest.TestCase):
    def test_c11_flow_dispatch_abi_propagates_stage_failure_and_cancellation(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")
        source = """module test::native_dispatch_flow;
fn seed() -> u32 { return 4u32; }
fn increment(value: u32) -> u32 { return value + 1u32; }
fn twice(value: u32) -> u32 { return value * 2u32; }
flow Compute {
    stage first = seed;
    stage second = increment after first;
    stage third = twice after second;
}
"""
        c_source = bootstrap.compile_source(source, "native_dispatch_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_dispatch_flow_Compute_dispatch"
        self.assertIn(f"int32_t {entrypoint}(", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-dispatch-c11-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                "#include <stdint.h>\n#include <string.h>\n"
                "typedef struct { int32_t fail_stage; int32_t cancel_check; "
                "int32_t checks; } Context;\n"
                "typedef int32_t (*Dispatch)(void *, uint32_t, "
                "const char *, const char *, const char *const *, "
                "const void *const *, uint32_t, void *);\n"
                "typedef int32_t (*Cancel)(void *);\n"
                f"extern int32_t {entrypoint}(Dispatch, void *, Cancel, "
                "int32_t *, int32_t *, uint32_t *, uint32_t *, uint32_t *);\n"
                "static int32_t dispatch_stage(void *raw, uint32_t stage, "
                "const char *stage_name, const char *output_type, "
                "const char *const *input_types, const void *const *inputs, "
                "uint32_t count, void *output) {\n"
                "  Context *ctx = (Context *)raw;\n"
                "  if (stage == 0 && strcmp(stage_name, \"first\") == 0 && "
                "strcmp(output_type, \"u32\") == 0 && count == 0) { "
                "*(uint32_t *)output = 4; return 0; }\n"
                "  if (stage == 1 && strcmp(stage_name, \"second\") == 0 && "
                "strcmp(output_type, \"u32\") == 0 && count == 1 && "
                "strcmp(input_types[0], \"u32\") == 0) {\n"
                "    *(uint32_t *)output = *(const uint32_t *)inputs[0] + 1;\n"
                "    return ctx->fail_stage == 1 ? 41 : 0;\n"
                "  }\n"
                "  if (stage == 2 && strcmp(stage_name, \"third\") == 0 && "
                "strcmp(output_type, \"u32\") == 0 && count == 1 && "
                "strcmp(input_types[0], \"u32\") == 0) {\n"
                "    *(uint32_t *)output = *(const uint32_t *)inputs[0] * 2;\n"
                "    return 0;\n"
                "  }\n"
                "  return 99;\n"
                "}\n"
                "static int32_t is_cancelled(void *raw) {\n"
                "  Context *ctx = (Context *)raw;\n"
                "  return ctx->cancel_check >= 0 && ctx->checks++ == ctx->cancel_check;\n"
                "}\n"
                "int main(void) {\n"
                "  uint32_t first = 91, second = 92, third = 93;\n"
                "  int32_t stopped = -9, status = 0;\n"
                "  Context ctx = {1, -1, 0};\n"
                f"  if ({entrypoint}(dispatch_stage, &ctx, is_cancelled, &stopped, "
                "&status, &first, &second, &third) != 3) return 1;\n"
                "  if (stopped != 1 || status != 41 || first != 91 || "
                "second != 92 || third != 93) return 2;\n"
                "  ctx.fail_stage = -1; ctx.cancel_check = 2; ctx.checks = 0;\n"
                f"  if ({entrypoint}(dispatch_stage, &ctx, is_cancelled, &stopped, "
                "&status, &first, &second, &third) != 2) return 3;\n"
                "  if (stopped != 2 || status != 0 || first != 91 || "
                "second != 92 || third != 93) return 4;\n"
                "  ctx.cancel_check = -1; ctx.checks = 0;\n"
                f"  if ({entrypoint}(dispatch_stage, &ctx, is_cancelled, &stopped, "
                "&status, &first, &second, &third) != 0) return 5;\n"
                "  return stopped == -1 && status == 0 && first == 4 && "
                "second == 5 && third == 10 ? 0 : 6;\n"
                "}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_c11_flow_cancel_abi_stops_between_stages_without_partial_outputs(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")
        source = """module test::native_cancel_flow;
fn seed() -> u32 { return 4u32; }
fn increment(value: u32) -> u32 { return value + 1u32; }
fn twice(value: u32) -> u32 { return value * 2u32; }
flow Compute {
    stage first = seed;
    stage second = increment after first;
    stage third = twice after second;
}
"""
        c_source = bootstrap.compile_source(source, "native_cancel_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_cancel_flow_Compute_cancelable"
        self.assertIn(f"int32_t {entrypoint}(", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-cancel-c11-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                "#include <stdint.h>\n"
                f"extern int32_t {entrypoint}(int32_t (*)(void *), void *, "
                "int32_t *, uint32_t *, uint32_t *, uint32_t *);\n"
                "static int32_t cancel_before_second(void *context) {\n"
                "  int32_t *checks = (int32_t *)context;\n"
                "  return (*checks)++ == 1;\n"
                "}\n"
                "static int32_t keep_running(void *context) { (void)context; return 0; }\n"
                "int main(void) {\n"
                "  int32_t checks = 0, cancelled_stage = -9;\n"
                "  uint32_t first = 91, second = 92, third = 93;\n"
                f"  if ({entrypoint}(cancel_before_second, &checks, &cancelled_stage, "
                "&first, &second, &third) != 2) return 1;\n"
                "  if (cancelled_stage != 1 || first != 91 || second != 92 || "
                "third != 93) return 2;\n"
                "  cancelled_stage = -9;\n"
                f"  if ({entrypoint}(keep_running, 0, &cancelled_stage, "
                "&first, &second, &third) != 0) return 3;\n"
                "  return cancelled_stage == -1 && first == 4 && second == 5 && "
                "third == 10 ? 0 : 4;\n"
                "}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_parallel_pure_flow_uses_c11_serial_fallback_with_matching_result(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")
        source = """module test::native_parallel_flow;
fn load() -> u32 { return 4u32; }
fn twice(value: u32) -> u32 { return value * 2u32; }
fn increment(value: u32) -> u32 { return value + 1u32; }
fn combine(left: u32, right: u32) -> u32 { return left + right; }
flow Compute {
    stage seed = load;
    stage doubled = twice after seed;
    stage incremented = increment after seed;
    stage result = combine after doubled, incremented;
}
"""
        package = importlib.import_module(bootstrap.__package__)
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        interpreted = package.execute_interpreted_sir_flow(
            checked_sir.module, "Compute", max_workers=2
        )
        expected_outputs = dict(interpreted.outputs)
        c_source = bootstrap.compile_source(source, "native_parallel_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_parallel_flow_Compute"
        self.assertIn(f"uint32_t {entrypoint}(void)", c_source)
        outputs_entrypoint = f"{entrypoint}_outputs"
        self.assertIn(f"int32_t {outputs_entrypoint}(", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-parallel-c11-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                "#include <stdint.h>\n"
                f"extern uint32_t {entrypoint}(void);\n"
                f"extern int32_t {outputs_entrypoint}(uint32_t *, uint32_t *, "
                "uint32_t *, uint32_t *);\n"
                "int main(void) {\n"
                "  uint32_t seed = 0, doubled = 0, incremented = 0, result = 0;\n"
                f"  if (!{outputs_entrypoint}(&seed, &doubled, &incremented, &result)) return 2;\n"
                f"  if (seed != {expected_outputs['seed']}u || "
                f"doubled != {expected_outputs['doubled']}u || "
                f"incremented != {expected_outputs['incremented']}u || "
                f"result != {expected_outputs['result']}u) return 3;\n"
                f"  if ({outputs_entrypoint}(0, &doubled, &incremented, &result)) return 4;\n"
                f"  return {entrypoint}() == {expected_outputs['result']}u ? 0 : 1;\n"
                "}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_serial_pure_float_flow_executes_through_generated_c_entrypoint(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")

        source = """module test::native_float_flow;
fn first() -> f64 { return 1.25f64; }
fn add(value: f64) -> f64 { return value + 2.25f64; }
fn first_single() -> f32 { return 1.5f32; }
fn add_single(value: f32) -> f32 { return value + 2.25f32; }
flow Sum {
    stage input = first;
    stage result = add after input;
}
flow Single { stage input = first_single; stage result = add_single after input; }
        """
        c_source = bootstrap.compile_source(source, "native_float_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_float_flow_Sum"
        self.assertIn(f"double {entrypoint}(void)", c_source)
        single_entrypoint = "sotlas_flow_test__native_float_flow_Single"
        self.assertIn(f"float {single_entrypoint}(void)", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-float-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                f"extern double {entrypoint}(void);\n"
                f"extern float {single_entrypoint}(void);\n"
                f"int main(void) {{ return {entrypoint}() == 3.5 && "
                f"{single_entrypoint}() == 3.75f ? 0 : 1; }}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_serial_pure_scalar_flow_executes_through_generated_c_entrypoint(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")

        source = """module test::native_flow;
fn first() -> u32 { return 40u32; }
fn add_one(value: u32) -> u32 { return value + 1u32; }
fn ready() -> bool { return true; }
flow Count {
    stage first = first;
    stage second = add_one after first;
    stage final = add_one after second;
}
flow Ready { stage value = ready; }
"""
        package = importlib.import_module(bootstrap.__package__)
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        interpreted = package.execute_interpreted_sir_flow(
            checked_sir.module, "Count"
        ).output("final")
        c_source = bootstrap.compile_source(source, "native_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_flow_Count"
        self.assertIn(f"uint32_t {entrypoint}(void)", c_source)
        bool_entrypoint = "sotlas_flow_test__native_flow_Ready"
        self.assertIn(f"_Bool {bool_entrypoint}(void)", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-native-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                "#include <stdint.h>\n"
                "#include <stdbool.h>\n"
                f"extern uint32_t {entrypoint}(void);\n"
                f"extern _Bool {bool_entrypoint}(void);\n"
                f"int main(void) {{ return {entrypoint}() == {interpreted}u && "
                f"{bool_entrypoint}() ? 0 : 1; }}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_serial_pure_signed_scalar_flow_executes_through_generated_c_entrypoint(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")

        source = """module test::native_signed_flow;
fn first() -> i32 { return 40i32; }
fn identity(value: i32) -> i32 { return value; }
flow Count {
    stage first = first;
    stage final = identity after first;
}
"""
        package = importlib.import_module(bootstrap.__package__)
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        interpreted = package.execute_interpreted_sir_flow(
            checked_sir.module, "Count"
        ).output("final")
        self.assertEqual(interpreted, 40)
        c_source = bootstrap.compile_source(source, "native_signed_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_signed_flow_Count"
        self.assertIn(f"int32_t {entrypoint}(void)", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-signed-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                "#include <stdint.h>\n"
                f"extern int32_t {entrypoint}(void);\n"
                f"int main(void) {{ return {entrypoint}() == {interpreted} ? 0 : 1; }}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_serial_flow_executes_stage_with_branch_and_early_return(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")

        source = """module test::native_branch_flow;
fn first() -> u32 { return 0u32; }
fn choose(value: u32) -> u32 {
    if value == 0u32 {
        return 17u32;
    }
    if value > 0u32 {
        return 23u32;
    }
    return 99u32;
}
flow Select {
    stage input = first;
    stage selected = choose after input;
}
"""
        c_source = bootstrap.compile_source(source, "native_branch_flow.sotlas")
        entrypoint = "sotlas_flow_test__native_branch_flow_Select"
        self.assertIn(f"uint32_t {entrypoint}(void)", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-branch-") as tmpdir:
            root = Path(tmpdir)
            generated = root / "flow.c"
            caller = root / "caller.c"
            executable = root / ("caller.exe" if os.name == "nt" else "caller")
            generated.write_text(c_source, encoding="utf-8")
            caller.write_text(
                "#include <stdint.h>\n"
                f"extern uint32_t {entrypoint}(void);\n"
                f"int main(void) {{ return {entrypoint}() == 17u ? 0 : 1; }}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_sotlas_source_can_call_declared_native_flow_entrypoint(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for native Flow execution")

        entrypoint = "sotlas_flow_test__native_flow_source_call_Count"
        source = f"""module test::native_flow_source_call;
fn first() -> u32 {{ return 41u32; }}
fn increment(value: u32) -> u32 {{ return value + 1u32; }}
flow Count {{
    stage input = first;
    stage output = increment after input;
}}
@extern(C) fn {entrypoint}() -> u32;
@system pub fn main() -> i32 {{
    let mut result: u32 = 0u32;
    unsafe {{ result = {entrypoint}(); }}
    if result == 42u32 {{ return 0; }}
    return 1;
}}
"""
        c_source = bootstrap.compile_source(source, "native_flow_source_call.sotlas")
        self.assertIn(f"uint32_t {entrypoint}(void)", c_source)

        with tempfile.TemporaryDirectory(prefix="sotlas-flow-source-call-") as tmpdir:
            generated = Path(tmpdir) / "flow.c"
            executable = Path(tmpdir) / ("flow.exe" if os.name == "nt" else "flow")
            generated.write_text(c_source, encoding="utf-8")
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", str(generated),
                 "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_source_flow_entrypoint_declaration_must_match_final_type(self):
        entrypoint = "sotlas_flow_test__native_flow_bad_abi_Count"
        source = f"""module test::native_flow_bad_abi;
fn value() -> u32 {{ return 7u32; }}
flow Count {{ stage output = value; }}
@extern(C) fn {entrypoint}() -> i32;
"""
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "collides with an incompatible function declaration",
        ):
            bootstrap.compile_source(source, "native_flow_bad_abi.sotlas")

    def test_effectful_flow_stage_is_rejected_before_c11_lowering(self):
        source = """module test::effectful_native_flow;
static mut counter: u32 = 0;
fn read_value() -> u32 { return counter; }
fn next_value() -> u32 {
    counter = counter + 1u32;
    return read_value();
}
flow Count { stage value = next_value; }
"""
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "does not yet verify global access",
        ):
            bootstrap.compile_source(source, "effectful_native_flow.sotlas")


if __name__ == "__main__":
    unittest.main()
