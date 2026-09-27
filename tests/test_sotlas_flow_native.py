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
fn add_one(value: i32) -> i32 { return value + 1i32; }
flow Count {
    stage first = first;
    stage final = add_one after first;
}
"""
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
                f"int main(void) {{ return {entrypoint}() == 41 ? 0 : 1; }}\n",
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
