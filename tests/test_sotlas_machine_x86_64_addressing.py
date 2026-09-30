"""M16.4b1 exact local-slot address calculation coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_address_compile"


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
_addressing = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_addressing")


def _roundtrip_ir() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "functions": [{
            "name": "roundtrip_local_address",
            "parameters": [{"name": "value", "type": "u32"}],
            "return_type": "u32",
            "linkage": "external",
            "source_visibility": "public",
            "abi_export": False,
            "blocks": [{
                "label": "entry",
                "instructions": [
                    {
                        "op": "alloc_stack",
                        "result": "slot",
                        "type": "u32",
                        "attributes": {"source_name": "local"},
                    },
                    {"op": "store", "operands": ["value", "slot"]},
                    {
                        "op": "address_of",
                        "result": "ptr",
                        "type": "u32*",
                        "operands": ["slot"],
                    },
                    {
                        "op": "load",
                        "result": "loaded",
                        "type": "u32",
                        "operands": ["ptr"],
                    },
                    {"op": "return", "operands": ["loaded"]},
                ],
            }],
        }],
    }


class SotlasX8664AddressCalculationTests(unittest.TestCase):
    def test_target_ir_accepts_exact_local_slot_address(self):
        target_ir = _roundtrip_ir()
        self.assertIsNone(_addressing.validate_target_ir_addressing(target_ir))

    def test_machine_uses_lea_for_local_slot_address(self):
        assembly = _machine.emit_x86_64_sysv_assembly(_roundtrip_ir())
        self.assertRegex(assembly, r"lea rax, \[rbp-[0-9]+\]")
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertIn(".globl roundtrip_local_address", assembly)

    def test_address_of_non_local_value_fails_closed(self):
        target_ir = _roundtrip_ir()
        instructions = target_ir["functions"][0]["blocks"][0]["instructions"]
        address = next(item for item in instructions if item["op"] == "address_of")
        address["operands"] = ["value"]
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "address_of source is not a local stack slot",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    def test_address_of_mismatched_pointer_type_fails_closed(self):
        target_ir = _roundtrip_ir()
        instructions = target_ir["functions"][0]["blocks"][0]["instructions"]
        address = next(item for item in instructions if item["op"] == "address_of")
        address["type"] = "u16*"
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "address_of result type must be 'u32\\*'",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    def test_address_offsets_wait_for_aggregate_layout(self):
        target_ir = _roundtrip_ir()
        instructions = target_ir["functions"][0]["blocks"][0]["instructions"]
        address = next(item for item in instructions if item["op"] == "address_of")
        address["attributes"] = {"offset_bytes": 4}
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "address_of byte offsets wait for aggregate layout",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_roundtrips_through_local_address(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for address calculation gate")

        assembly = _machine.emit_x86_64_sysv_assembly(_roundtrip_ir())
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_address_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_address"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t roundtrip_local_address(uint32_t value);
int main(void) {
    if (roundtrip_local_address(UINT32_C(0x89ABCDEF)) != UINT32_C(0x89ABCDEF)) return 1;
    if (roundtrip_local_address(UINT32_C(0)) != UINT32_C(0)) return 2;
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

    def test_compiler_and_tools_addressing_files_remain_identical(self):
        for relative in (
            "target_ir_addressing.py",
            "_machine_x86_64_call_plan.py",
            "_machine_x86_64_call_instruction_emit.py",
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
