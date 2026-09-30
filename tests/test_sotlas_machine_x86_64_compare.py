"""Unsigned comparison coverage for the Sotlas-owned x86-64 backend."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_compare_canonical_compile"


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
compile_source_to_x86_64_sysv_assembly = (
    _BACKEND.compile_source_to_x86_64_sysv_assembly
)
emit_x86_64_sysv_assembly = _BACKEND.emit_x86_64_sysv_assembly


def _compare_module(
    predicate: str,
    *,
    operand_type: str = "u32",
    result_type: str = "bool",
    right_type: str | None = None,
) -> dict:
    if right_type is None:
        right_type = operand_type
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "machine_compare",
        "functions": [{
            "name": "compare_values",
            "parameters": [
                {"name": "left", "type": operand_type},
                {"name": "right", "type": right_type},
            ],
            "return_type": result_type,
            "blocks": [{
                "label": "entry",
                "instructions": [
                    {
                        "op": "compare",
                        "result": "comparison",
                        "type": result_type,
                        "operands": ["left", "right"],
                        "attributes": {"predicate": predicate},
                    },
                    {
                        "op": "return",
                        "operands": ["comparison"],
                        "attributes": {},
                    },
                ],
            }],
        }],
        "limitations": [],
    }


class SotlasX8664MachineCompareTests(unittest.TestCase):
    def test_unsigned_predicates_select_x86_condition_codes(self):
        predicates = {
            "EQ": "sete al",
            "NEQ": "setne al",
            "LT": "setb al",
            "LTE": "setbe al",
            "GT": "seta al",
            "GTE": "setae al",
        }
        for predicate, expected in predicates.items():
            with self.subTest(predicate=predicate):
                assembly = emit_x86_64_sysv_assembly(
                    _compare_module(predicate)
                )
                self.assertIn("cmp eax, ecx", assembly)
                self.assertIn(expected, assembly)
                self.assertIn("movzx eax, al", assembly)

    def test_unsigned_compare_widths_use_normalized_machine_operands(self):
        for type_name in ("u8", "u16", "u32"):
            with self.subTest(type=type_name):
                assembly = emit_x86_64_sysv_assembly(
                    _compare_module("LT", operand_type=type_name)
                )
                self.assertIn("cmp eax, ecx", assembly)
                self.assertIn("setb al", assembly)
        for type_name in ("u64", "usize"):
            with self.subTest(type=type_name):
                assembly = emit_x86_64_sysv_assembly(
                    _compare_module("LT", operand_type=type_name)
                )
                self.assertIn("cmp rax, rcx", assembly)
                self.assertIn("setb al", assembly)

    def test_compare_contract_fails_closed_for_invalid_shapes(self):
        with self.assertRaisesRegex(
            MachineBackendError, "unsupported compare predicate"
        ):
            emit_x86_64_sysv_assembly(_compare_module("ORDERED"))

        with self.assertRaisesRegex(
            MachineBackendError, "compare result must have type 'bool'"
        ):
            emit_x86_64_sysv_assembly(
                _compare_module("EQ", result_type="u32")
            )

        with self.assertRaisesRegex(
            MachineBackendError, "compare operand types must match"
        ):
            emit_x86_64_sysv_assembly(
                _compare_module("EQ", right_type="u64")
            )

    def test_signed_compare_remains_outside_unsigned_machine_slice(self):
        with self.assertRaisesRegex(
            MachineBackendError,
            "signed integer lowering waits for Sotlas overflow-mode semantics",
        ):
            emit_x86_64_sysv_assembly(
                _compare_module("LT", operand_type="i32")
            )

    def test_source_unsigned_compare_reaches_machine_instruction_selection(self):
        source = """
module test::machine_compare_source;
fn less_than(left: u32, right: u32) -> bool {
    return left < right;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_compare_source.sotlas"
        )
        self.assertIn(".globl less_than", assembly)
        self.assertIn("cmp eax, ecx", assembly)
        self.assertIn("setb al", assembly)
        self.assertIn("movzx eax, al", assembly)
        self.assertIn("ret", assembly)
        self.assertNotIn("LLVM", assembly)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_source_comparison_from_sotlas_backend(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest(
                "native C compiler is required for x86-64 comparison execution gate"
            )

        source = """
module test::machine_compare_e2e;
fn less_than(left: u32, right: u32) -> bool {
    return left < right;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_compare_e2e.sotlas"
        )

        with tempfile.TemporaryDirectory(
            prefix="sotlas_machine_compare_x86_64_"
        ) as temp:
            directory = Path(temp)
            asm_path = directory / "machine_compare.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_compare_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdbool.h>
#include <stdint.h>
extern bool less_than(uint32_t left, uint32_t right);
int main(void) {
    if (!less_than(10u, 20u)) return 1;
    if (less_than(20u, 10u)) return 2;
    if (less_than(20u, 20u)) return 3;
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
            run = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
