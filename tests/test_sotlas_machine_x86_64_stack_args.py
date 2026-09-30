"""M16.3c SysV stack-argument coverage for the Sotlas-owned x86-64 backend."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_stack_args_compile"


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
module test::machine_stack_args;

fn pick7(a: u64, b: u64, c: u64, d: u64, e: u64, f: u64, g: u64) -> u64 {
    return g;
}

pub fn call7(a: u64, b: u64, c: u64, d: u64, e: u64, f: u64, g: u64) -> u64 {
    return pick7(a, b, c, d, e, f, g);
}

fn pick8(a: u64, b: u64, c: u64, d: u64, e: u64, f: u64, g: u64, h: u64) -> u64 {
    return h;
}

pub fn call8(a: u64, b: u64, c: u64, d: u64, e: u64, f: u64, g: u64, h: u64) -> u64 {
    return pick8(a, b, c, d, e, f, g, h);
}

fn pick9(a: u64, b: u64, c: u64, d: u64, e: u64, f: u64, g: u64, h: u64, i: u64) -> u64 {
    return i;
}

pub fn call9(a: u64, b: u64, c: u64, d: u64, e: u64, f: u64, g: u64, h: u64, i: u64) -> u64 {
    return pick9(a, b, c, d, e, f, g, h, i);
}

fn pick7_u16(a: u16, b: u16, c: u16, d: u16, e: u16, f: u16, g: u16) -> u16 {
    return g;
}

pub fn call7_u16(a: u16, b: u16, c: u16, d: u16, e: u16, f: u16, g: u16) -> u16 {
    return pick7_u16(a, b, c, d, e, f, g);
}
"""


class SotlasX8664StackArgumentTests(unittest.TestCase):
    def _module_and_target_ir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE, filename="machine_stack_args.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        module = checked_sir.module
        self.assertEqual(tuple(module.unlowered_functions), ())
        return module, _target_calls.lower_sir_to_typed_target_ir(module)

    def test_source_calls_preserve_seventh_eighth_and_ninth_arguments(self):
        module, target_ir = self._module_and_target_ir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        functions = {item["name"]: item for item in target_ir["functions"]}
        for name, expected_count in (("call7", 7), ("call8", 8), ("call9", 9)):
            function = functions[name]
            call = next(
                instruction
                for block in function["blocks"]
                for instruction in block["instructions"]
                if instruction["op"] == "call"
            )
            self.assertEqual(len(call["operands"]), expected_count)
            self.assertEqual(call["type"], "u64")
            self.assertEqual(function["linkage"], "external")
        self.assertEqual(functions["pick7"]["linkage"], "internal")
        self.assertEqual(functions["pick8"]["linkage"], "internal")
        self.assertEqual(functions["pick9"]["linkage"], "internal")
        self.assertEqual(functions["pick7_u16"]["linkage"], "internal")
        self.assertEqual(functions["call7_u16"]["linkage"], "external")

    def test_allocation_reports_incoming_stack_argument_count(self):
        _, target_ir = self._module_and_target_ir()
        plan = _machine.plan_x86_64_sysv_allocation(target_ir)
        by_name = {function["name"]: function for function in plan["functions"]}
        self.assertEqual(by_name["pick7"]["incoming_stack_arguments"], 1)
        self.assertEqual(by_name["pick8"]["incoming_stack_arguments"], 2)
        self.assertEqual(by_name["pick9"]["incoming_stack_arguments"], 3)
        self.assertEqual(by_name["call9"]["incoming_stack_arguments"], 3)

    def test_stack_arguments_use_sysv_offsets_and_aligned_outgoing_areas(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_stack_args.sotlas"
        )
        self.assertIn(".local pick7", assembly)
        self.assertIn(".globl call7", assembly)
        self.assertIn("mov rax, QWORD PTR [rbp+16]", assembly)
        self.assertIn("mov rax, QWORD PTR [rbp+24]", assembly)
        self.assertIn("mov rax, QWORD PTR [rbp+32]", assembly)
        self.assertIn("mov QWORD PTR [rsp], rax", assembly)
        self.assertIn("mov QWORD PTR [rsp+8], rax", assembly)
        self.assertIn("mov QWORD PTR [rsp+16], rax", assembly)
        self.assertIn("sub rsp, 32", assembly)
        self.assertIn("sub rsp, 48", assembly)
        self.assertIn("and eax, 65535", assembly)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_seven_to_nine_source_arguments(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for stack-argument execution gate")

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_stack_args.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_stack_args_") as temp:
            directory = Path(temp)
            asm_path = directory / "stack_args.s"
            caller_path = directory / "caller.c"
            executable = directory / "stack_args"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint64_t call7(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
extern uint64_t call8(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
extern uint64_t call9(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
extern uint16_t call7_u16(uint16_t, uint16_t, uint16_t, uint16_t, uint16_t, uint16_t, uint16_t);
int main(void) {
    if (call7(1, 2, 3, 4, 5, 6, 7) != 7) return 1;
    if (call8(1, 2, 3, 4, 5, 6, 7, 8) != 8) return 2;
    if (call9(1, 2, 3, 4, 5, 6, 7, 8, 9) != 9) return 3;
    if (call7_u16(1, 2, 3, 4, 5, 6, 0xBEEF) != 0xBEEF) return 4;
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

    def test_compiler_and_tools_stack_call_layers_remain_identical(self):
        compiler_path = ROOT / "compiler" / "sotlas_compile" / "_machine_x86_64_calls.py"
        tools_path = ROOT / "tools" / "sotlas_compile" / "_machine_x86_64_calls.py"
        self.assertEqual(
            compiler_path.read_text(encoding="utf-8"),
            tools_path.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
