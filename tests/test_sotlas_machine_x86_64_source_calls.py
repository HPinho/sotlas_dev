"""Source-to-native direct-call coverage for the Sotlas-owned x86-64 backend."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_machine_source_calls_compile"


def _load_compiler_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            COMPILER_PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(COMPILER_PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


_load_compiler_package()
_machine = importlib.import_module(f"{_CANONICAL_PACKAGE}.machine_x86_64")
_phase1 = importlib.import_module(f"{_CANONICAL_PACKAGE}.phase1_pipeline")
_canonical_sir = importlib.import_module(f"{_CANONICAL_PACKAGE}.canonical_sir")
_target_calls = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_calls")


SOURCE = """
module test::machine_source_call;
fn add_pair(left: u32, right: u32) -> u32 {
    return left + right;
}
fn call_pair(left: u32, right: u32) -> u32 {
    return add_pair(left, right);
}
"""


class SotlasX8664SourceCallTests(unittest.TestCase):
    def _checked_sir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE, filename="machine_source_call.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_source_call_has_typed_sir_result(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        caller = next(fn for fn in module.functions if fn.name == "call_pair")
        calls = [
            instruction
            for block in caller.blocks
            for instruction in block.instructions
            if type(instruction).__name__ == "CallInst"
        ]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call.callee, "add_pair")
        self.assertIsNotNone(call.result)
        self.assertEqual(call.result.type_name, "u32")
        self.assertEqual([value.name for value in call.arguments], ["left", "right"])

    def test_typed_target_ir_preserves_call_result_type(self):
        module = self._checked_sir()
        target_ir = _target_calls.lower_sir_to_typed_target_ir(module)
        caller = next(
            function
            for function in target_ir["functions"]
            if function["name"] == "call_pair"
        )
        calls = [
            instruction
            for block in caller["blocks"]
            for instruction in block["instructions"]
            if instruction["op"] == "call"
        ]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["attributes"]["callee"], "add_pair")
        self.assertEqual(call["type"], "u32")
        self.assertIsInstance(call["result"], str)

    def test_source_call_reaches_sysv_machine_assembly(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_call.sotlas"
        )
        self.assertIn(".globl add_pair", assembly)
        self.assertIn(".globl call_pair", assembly)
        self.assertIn("call add_pair", assembly)
        self.assertIn("sub rsp, 16", assembly)
        self.assertIn("mov QWORD PTR [rsp], r10", assembly)
        self.assertIn("mov QWORD PTR [rsp+8], r11", assembly)
        self.assertNotIn("LLVM", assembly)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_source_level_direct_call(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for source-call execution gate")

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_call.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_source_call_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_source_call"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t call_pair(uint32_t left, uint32_t right);
int main(void) {
    if (call_pair(20u, 22u) != 42u) return 1;
    if (call_pair(7u, 9u) != 16u) return 2;
    return 0;
}
""",
                encoding="utf-8",
            )
            build = subprocess.run(
                [compiler, str(caller_path), str(asm_path), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_compiler_and_tools_source_call_bridges_remain_identical(self):
        for relative in (
            "scalar_if_return_cfg_generator.py",
            "target_ir_calls.py",
            "machine_x86_64.py",
        ):
            compiler_path = ROOT / "compiler" / "sotlas_compile" / relative
            tools_path = ROOT / "tools" / "sotlas_compile" / relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
