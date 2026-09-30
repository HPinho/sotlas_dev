"""Executable x86-64 machine backend coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_canonical_compile"


def _load_canonical_machine_backend():
    """Load compiler/sotlas_compile independently of any cached tools package."""
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
    backend = importlib.import_module(f"{_CANONICAL_PACKAGE}.machine_x86_64")
    if Path(backend.__file__).resolve().parent != COMPILER_PACKAGE_DIR.resolve():
        raise RuntimeError("machine backend did not load from compiler/sotlas_compile")
    return backend


_MACHINE_BACKEND = _load_canonical_machine_backend()
MachineBackendError = _MACHINE_BACKEND.MachineBackendError
compile_source_to_x86_64_sysv_assembly = (
    _MACHINE_BACKEND.compile_source_to_x86_64_sysv_assembly
)
emit_x86_64_sysv_assembly = _MACHINE_BACKEND.emit_x86_64_sysv_assembly
plan_x86_64_sysv_allocation = _MACHINE_BACKEND.plan_x86_64_sysv_allocation


class SotlasX8664MachineBackendTests(unittest.TestCase):
    def test_backend_is_loaded_from_canonical_compiler_tree(self):
        self.assertEqual(
            Path(_MACHINE_BACKEND.__file__).resolve().parent,
            COMPILER_PACKAGE_DIR.resolve(),
        )

    def test_source_unsigned_add_reaches_sotlas_owned_machine_assembly(self):
        source = """
module test::machine_add;
fn add_values(left: u32, right: u32) -> u32 {
    return left + right;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(source, "machine_add.sotlas")

        self.assertIn(".local add_values", assembly)
        self.assertNotIn(".globl add_values", assembly)
        self.assertIn("add eax, ecx", assembly)
        self.assertIn("r10", assembly)
        self.assertIn("ret", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_physical_allocation_maps_virtual_registers_and_real_spills(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "machine_spill",
            "functions": [{
                "name": "mix",
                "parameters": [
                    {"name": "a", "type": "u32"},
                    {"name": "b", "type": "u32"},
                    {"name": "c", "type": "u32"},
                    {"name": "d", "type": "u32"},
                ],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {"op": "add", "result": "ab", "type": "u32",
                         "operands": ["a", "b"], "attributes": {}},
                        {"op": "add", "result": "cd", "type": "u32",
                         "operands": ["c", "d"], "attributes": {}},
                        {"op": "mul", "result": "product", "type": "u32",
                         "operands": ["ab", "cd"], "attributes": {}},
                        {"op": "return", "operands": ["product"], "attributes": {}},
                    ],
                }],
            }],
            "limitations": [],
        }

        plan = plan_x86_64_sysv_allocation(target_ir, register_count=1)
        function = plan["functions"][0]
        self.assertEqual(plan["value_registers"], ["r10"])
        self.assertGreater(function["spill_slots"], 0)
        self.assertGreaterEqual(function["frame_size_bytes"], 16)
        self.assertEqual(function["frame_size_bytes"] % 16, 0)

        assembly = emit_x86_64_sysv_assembly(target_ir, register_count=1)
        self.assertIn("sub rsp,", assembly)
        self.assertIn("QWORD PTR [rbp-", assembly)
        self.assertIn("imul eax, ecx", assembly)

    def test_signed_arithmetic_stays_fail_closed_until_overflow_modes_are_defined(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "signed",
            "functions": [{
                "name": "add_signed",
                "parameters": [
                    {"name": "a", "type": "i32"},
                    {"name": "b", "type": "i32"},
                ],
                "return_type": "i32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {"op": "add", "result": "sum", "type": "i32",
                         "operands": ["a", "b"], "attributes": {}},
                        {"op": "return", "operands": ["sum"], "attributes": {}},
                    ],
                }],
            }],
            "limitations": [],
        }
        with self.assertRaisesRegex(
            MachineBackendError,
            "signed integer lowering waits for Sotlas overflow-mode semantics",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_unconditional_branch_lowers_but_unknown_calls_stay_fail_closed(self):
        branching = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "branching",
            "functions": [{
                "name": "choose",
                "parameters": [{"name": "flag", "type": "u8"}],
                "return_type": "u8",
                "blocks": [
                    {
                        "label": "entry",
                        "instructions": [{
                            "op": "branch", "targets": ["exit"], "attributes": {}
                        }],
                    },
                    {
                        "label": "exit",
                        "instructions": [{
                            "op": "return", "operands": ["flag"], "attributes": {}
                        }],
                    },
                ],
            }],
            "limitations": [],
        }
        assembly = emit_x86_64_sysv_assembly(branching)
        self.assertIn(".Lchoose_bb0:", assembly)
        self.assertIn("jmp .Lchoose_bb1", assembly)
        self.assertIn(".Lchoose_bb1:", assembly)

        calling = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "calling",
            "functions": [{
                "name": "caller",
                "parameters": [],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {
                            "op": "call",
                            "result": "value",
                            "type": "u32",
                            "operands": [],
                            "attributes": {"callee": "callee"},
                        },
                        {"op": "return", "operands": ["value"], "attributes": {}},
                    ],
                }],
            }],
            "limitations": [],
        }
        with self.assertRaisesRegex(
            MachineBackendError,
            "direct call target 'callee' is not a module function",
        ):
            emit_x86_64_sysv_assembly(calling)

    def test_machine_register_count_is_bounded_by_real_backend_register_set(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "empty",
            "functions": [],
            "limitations": [],
        }
        with self.assertRaisesRegex(MachineBackendError, "one or two value registers"):
            plan_x86_64_sysv_allocation(target_ir, register_count=3)

    @unittest.skipUnless(sys.platform.startswith("linux"), "x86-64 SysV execution gate is Linux-specific")
    def test_linux_e2e_executes_assembly_selected_by_sotlas_backend(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for x86-64 assembly execution gate")

        source = """
module test::machine_e2e;
pub fn add_values(left: u32, right: u32) -> u32 {
    return left + right;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(source, "machine_e2e.sotlas")

        with tempfile.TemporaryDirectory(prefix="sotlas_machine_x86_64_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t add_values(uint32_t left, uint32_t right);
int main(void) {
    return add_values(20u, 22u) == 42u ? 0 : 1;
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

    def test_compiler_and_tools_machine_backends_remain_identical(self):
        compiler_backend = (
            ROOT / "compiler" / "sotlas_compile" / "machine_x86_64.py"
        ).read_text(encoding="utf-8")
        tools_backend = (
            ROOT / "tools" / "sotlas_compile" / "machine_x86_64.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(compiler_backend, tools_backend)


if __name__ == "__main__":
    unittest.main()
