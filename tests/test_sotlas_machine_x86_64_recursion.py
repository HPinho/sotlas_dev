"""M16.3e recursion contract gates for the Sotlas-owned x86-64 backend."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_recursion_compile"


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


SOURCE_SELF_RECURSION = """
module test::machine_source_recursion;

fn repeat(value: u32) -> u32 {
    return repeat(value);
}
"""


def _recursive_function(name: str, callee: str) -> dict:
    return {
        "name": name,
        "parameters": [{"name": "value", "type": "u32"}],
        "return_type": "u32",
        "blocks": [
            {
                "label": "entry",
                "instructions": [
                    {
                        "op": "const_int",
                        "result": "zero",
                        "type": "u32",
                        "attributes": {"value": 0},
                    },
                    {
                        "op": "compare",
                        "result": "is_zero",
                        "type": "bool",
                        "operands": ["value", "zero"],
                        "attributes": {"predicate": "EQ"},
                    },
                    {
                        "op": "cond_branch",
                        "operands": ["is_zero"],
                        "targets": ["base", "recur"],
                        "attributes": {},
                    },
                ],
            },
            {
                "label": "base",
                "instructions": [
                    {"op": "return", "operands": ["value"], "attributes": {}},
                ],
            },
            {
                "label": "recur",
                "instructions": [
                    {
                        "op": "const_int",
                        "result": "one",
                        "type": "u32",
                        "attributes": {"value": 1},
                    },
                    {
                        "op": "sub",
                        "result": "next",
                        "type": "u32",
                        "operands": ["value", "one"],
                        "attributes": {},
                    },
                    {
                        "op": "call",
                        "result": "nested",
                        "type": "u32",
                        "operands": ["next"],
                        "attributes": {"callee": callee, "system": False},
                    },
                    {"op": "return", "operands": ["nested"], "attributes": {}},
                ],
            },
        ],
    }


def _self_recursive_module() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "self_recursion",
        "functions": [_recursive_function("countdown", "countdown")],
        "limitations": [],
    }


def _mutual_recursive_module() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "mutual_recursion",
        "functions": [
            _recursive_function("bounce_a", "bounce_b"),
            _recursive_function("bounce_b", "bounce_a"),
        ],
        "limitations": [],
    }


def _execution_recursive_module() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "recursion_execution",
        "functions": [
            _recursive_function("countdown", "countdown"),
            _recursive_function("bounce_a", "bounce_b"),
            _recursive_function("bounce_b", "bounce_a"),
        ],
        "limitations": [],
    }


class SotlasX8664RecursionTests(unittest.TestCase):
    def test_source_self_recursion_survives_sir_and_typed_target_ir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE_SELF_RECURSION,
            filename="machine_source_recursion.sotlas",
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(checked)
        module = checked_sir.module
        self.assertEqual(tuple(module.unlowered_functions), ())

        function = next(item for item in module.functions if item.name == "repeat")
        calls = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
            if type(instruction).__name__ == "CallInst"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].callee, "repeat")
        self.assertEqual([value.name for value in calls[0].arguments], ["value"])

        target_ir = _target_calls.lower_sir_to_typed_target_ir(module)
        lowered = target_ir["functions"][0]
        call = next(
            instruction
            for block in lowered["blocks"]
            for instruction in block["instructions"]
            if instruction["op"] == "call"
        )
        self.assertEqual(call["attributes"]["callee"], "repeat")
        self.assertEqual(call["type"], "u32")
        self.assertEqual(lowered["linkage"], "internal")

    def test_source_self_recursion_reaches_normal_machine_call_abi(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE_SELF_RECURSION,
            "machine_source_recursion.sotlas",
        )
        self.assertIn(".local repeat", assembly)
        self.assertIn("call repeat", assembly)
        self.assertIn("sub rsp, 16", assembly)
        self.assertIn("mov QWORD PTR [rsp], r10", assembly)
        self.assertIn("mov QWORD PTR [rsp+8], r11", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_self_and_mutual_recursion_emit_real_direct_calls(self):
        self_assembly = _machine.emit_x86_64_sysv_assembly(_self_recursive_module())
        mutual_assembly = _machine.emit_x86_64_sysv_assembly(_mutual_recursive_module())

        self.assertIn("call countdown", self_assembly)
        self.assertIn("call bounce_b", mutual_assembly)
        self.assertIn("call bounce_a", mutual_assembly)
        self.assertIn("sub rsp, 16", self_assembly)
        self.assertGreaterEqual(mutual_assembly.count("sub rsp, 16"), 2)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_finite_self_and_mutual_recursion(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for recursion execution gate")

        assembly = _machine.emit_x86_64_sysv_assembly(_execution_recursive_module())

        with tempfile.TemporaryDirectory(prefix="sotlas_machine_recursion_") as temp:
            directory = Path(temp)
            asm_path = directory / "recursion.s"
            caller_path = directory / "caller.c"
            executable = directory / "recursion_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t countdown(uint32_t value);
extern uint32_t bounce_a(uint32_t value);
extern uint32_t bounce_b(uint32_t value);
int main(void) {
    if (countdown(0u) != 0u) return 1;
    if (countdown(16u) != 0u) return 2;
    if (bounce_a(17u) != 0u) return 3;
    if (bounce_b(18u) != 0u) return 4;
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

    def test_compiler_and_tools_recursion_layers_remain_identical(self):
        for relative in (
            "scalar_if_return_cfg_generator.py",
            "_machine_x86_64_call_validation.py",
            "_machine_x86_64_calls.py",
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
