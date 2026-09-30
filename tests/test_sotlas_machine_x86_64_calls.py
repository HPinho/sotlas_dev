"""M16.3a direct-call ABI coverage for the Sotlas-owned x86-64 backend."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_calls_canonical_compile"


def _load_backend():
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


_BACKEND = _load_backend()
MachineBackendError = _BACKEND.MachineBackendError
emit_x86_64_sysv_assembly = _BACKEND.emit_x86_64_sysv_assembly
plan_x86_64_sysv_allocation = _BACKEND.plan_x86_64_sysv_allocation


def _module() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "machine_calls",
        "functions": [
            {
                "name": "add_pair",
                "parameters": [
                    {"name": "a", "type": "u32"},
                    {"name": "b", "type": "u32"},
                ],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {
                            "op": "add", "result": "sum", "type": "u32",
                            "operands": ["a", "b"], "attributes": {},
                        },
                        {"op": "return", "operands": ["sum"], "attributes": {}},
                    ],
                }],
            },
            {
                "name": "call_and_mix",
                "parameters": [
                    {"name": "left", "type": "u32"},
                    {"name": "right", "type": "u32"},
                ],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {
                            "op": "mul", "result": "product", "type": "u32",
                            "operands": ["left", "right"], "attributes": {},
                        },
                        {
                            "op": "call", "result": "sum", "type": "u32",
                            "operands": ["left", "right"],
                            "attributes": {"callee": "add_pair", "system": False},
                        },
                        {
                            "op": "add", "result": "mixed", "type": "u32",
                            "operands": ["product", "sum"], "attributes": {},
                        },
                        {"op": "return", "operands": ["mixed"], "attributes": {}},
                    ],
                }],
            },
        ],
        "limitations": [],
    }


class SotlasX8664DirectCallTests(unittest.TestCase):
    def test_direct_call_uses_sysv_registers_and_preserves_value_registers(self):
        assembly = emit_x86_64_sysv_assembly(_module())

        self.assertIn("call add_pair", assembly)
        self.assertIn("mov edi, eax", assembly)
        self.assertIn("mov esi, eax", assembly)
        self.assertIn("sub rsp, 16", assembly)
        self.assertIn("mov QWORD PTR [rsp], r10", assembly)
        self.assertIn("mov QWORD PTR [rsp+8], r11", assembly)
        self.assertIn("mov r10, QWORD PTR [rsp]", assembly)
        self.assertIn("mov r11, QWORD PTR [rsp+8]", assembly)
        self.assertIn("mov rdx, rax", assembly)

    def test_allocation_accepts_typed_direct_call_result(self):
        plan = plan_x86_64_sysv_allocation(_module())
        caller = next(item for item in plan["functions"] if item["name"] == "call_and_mix")
        values = {item["value"]: item for item in caller["values"]}
        self.assertEqual(values["sum"]["type"], "u32")

    def test_unknown_direct_call_target_is_fail_closed(self):
        target_ir = _module()
        target_ir["functions"][1]["blocks"][0]["instructions"][1]["attributes"]["callee"] = "missing"
        with self.assertRaisesRegex(
            MachineBackendError,
            "direct call target 'missing' is not a module function",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_direct_call_argument_types_must_match_callee_signature(self):
        target_ir = _module()
        target_ir["functions"][1]["parameters"][1]["type"] = "u16"
        with self.assertRaisesRegex(
            MachineBackendError,
            "call argument 2 to 'add_pair' has type 'u16', expected 'u32'",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_recursive_call_cycle_is_fail_closed(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "recursive",
            "functions": [{
                "name": "again",
                "parameters": [],
                "return_type": "void",
                "blocks": [{
                    "label": "entry",
                    "instructions": [
                        {
                            "op": "call", "result": None, "operands": [],
                            "attributes": {"callee": "again", "system": False},
                        },
                        {"op": "return", "operands": [], "attributes": {}},
                    ],
                }],
            }],
            "limitations": [],
        }
        with self.assertRaisesRegex(
            MachineBackendError,
            "recursive direct calls remain outside the M16.3a machine contract",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_system_call_is_not_smuggled_through_direct_call_abi(self):
        target_ir = _module()
        target_ir["functions"][1]["blocks"][0]["instructions"][1]["attributes"]["system"] = True
        with self.assertRaisesRegex(
            MachineBackendError,
            "system/foreign call 'add_pair' is outside M16.3a",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_multi_function_direct_call(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for x86-64 call execution gate")

        assembly = emit_x86_64_sysv_assembly(_module())
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_calls_x86_64_") as temp:
            directory = Path(temp)
            asm_path = directory / "calls.s"
            caller_path = directory / "caller.c"
            executable = directory / "calls_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t call_and_mix(uint32_t left, uint32_t right);
int main(void) {
    return call_and_mix(6u, 7u) == 55u ? 0 : 1;
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

    def test_compiler_and_tools_call_layers_remain_identical(self):
        compiler_path = ROOT / "compiler" / "sotlas_compile" / "_machine_x86_64_calls.py"
        tools_path = ROOT / "tools" / "sotlas_compile" / "_machine_x86_64_calls.py"
        self.assertEqual(
            compiler_path.read_text(encoding="utf-8"),
            tools_path.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
