"""M16.4d1 fixed-array address projection coverage for x86-64 SysV."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_fixed_arrays_compile"


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
_types = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_types")


def _array_reader(
    name: str,
    element_type: str,
    length: int,
    index: int,
) -> dict:
    return {
        "name": name,
        "parameters": [{"name": "ptr", "type": f"[{element_type};{length}]*"}],
        "return_type": element_type,
        "blocks": [{
            "label": "0",
            "instructions": [
                {
                    "op": "array_address",
                    "result": "element_ptr",
                    "type": f"{element_type}*",
                    "operands": ["ptr"],
                    "attributes": {
                        "element_type": element_type,
                        "length": length,
                        "index": index,
                        "source_point_id": "array_address@1:1",
                    },
                },
                {
                    "op": "load",
                    "result": "value",
                    "type": element_type,
                    "operands": ["element_ptr"],
                },
                {"op": "return", "operands": ["value"]},
            ],
        }],
    }


def _target_ir(*functions: dict) -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "functions": list(functions),
    }


class SotlasX8664FixedArrayTests(unittest.TestCase):
    def test_fixed_array_pointer_is_an_opaque_gp64_abi_value(self):
        self.assertEqual(_types.fixed_array_pointee("[u32;4]*"), ("u32", 4))
        self.assertEqual(_types.pointer_pointee("[u32;4]*"), "[u32;4]")
        self.assertEqual(
            _types.require_abi_scalar("[u32;4]*", context="test"),
            64,
        )
        self.assertIsNone(_types.fixed_array_pointee("[bool;4]*"))
        self.assertIsNone(_types.fixed_array_pointee("[u32;0]*"))
        self.assertIsNone(_types.fixed_array_pointee("[u32;4]**"))

    def test_target_ir_accepts_only_constant_in_bounds_array_projection(self):
        target_ir = _target_ir(_array_reader("read_2", "u32", 4, 2))
        self.assertIsNone(_addressing.validate_target_ir_addressing(target_ir))

        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["index"] = 4
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            r"index 4 is outside \[0, 4\)",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

        projection["attributes"]["index"] = -1
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            r"index -1 is outside \[0, 4\)",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_target_ir_cannot_smuggle_array_byte_layout(self):
        for key in ("offset_bytes", "stride_bytes", "element_size_bytes"):
            target_ir = _target_ir(_array_reader("read_2", "u32", 4, 2))
            projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
            projection["attributes"][key] = 123
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    _addressing.TargetIRAddressingError,
                    "cannot carry target byte layout",
                ):
                    _addressing.validate_target_ir_addressing(target_ir)

    def test_declared_length_and_element_type_must_match_base_pointer(self):
        target_ir = _target_ir(_array_reader("read_2", "u32", 4, 2))
        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["length"] = 8
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "base does not match fixed-array type",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

        target_ir = _target_ir(_array_reader("read_2", "u32", 4, 2))
        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["element_type"] = "u16"
        projection["type"] = "u16*"
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "base does not match fixed-array type",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_machine_derives_scalar_stride_only_at_x86_64_emission(self):
        target_ir = _target_ir(
            _array_reader("read_u8_3", "u8", 4, 3),
            _array_reader("read_u16_2", "u16", 4, 2),
            _array_reader("read_u32_2", "u32", 4, 2),
            _array_reader("read_u64_2", "u64", 4, 2),
        )
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)
        self.assertIn("lea rax, [rcx+3]", assembly)
        self.assertIn("lea rax, [rcx+4]", assembly)
        self.assertIn("lea rax, [rcx+8]", assembly)
        self.assertIn("lea rax, [rcx+16]", assembly)
        self.assertIn("movzx eax, BYTE PTR [rcx]", assembly)
        self.assertIn("movzx eax, WORD PTR [rcx]", assembly)
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertIn("mov rax, QWORD PTR [rcx]", assembly)

    def test_fixed_array_pointer_cannot_be_loaded_as_an_element_directly(self):
        target_ir = _target_ir({
            "name": "bad_direct_array_load",
            "parameters": [{"name": "ptr", "type": "[u32;4]*"}],
            "return_type": "u32",
            "blocks": [{
                "label": "0",
                "instructions": [
                    {
                        "op": "load",
                        "result": "value",
                        "type": "u32",
                        "operands": ["ptr"],
                    },
                    {"op": "return", "operands": ["value"]},
                ],
            }],
        })
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "indirect load source must be a supported pointer type",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_reads_constant_index_from_real_c_fixed_array(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for fixed-array execution gate")

        target_ir = _target_ir(_array_reader("read_index2", "u32", 4, 2))
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)
        with tempfile.TemporaryDirectory(prefix="sotlas_fixed_arrays_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "fixed_arrays"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t read_index2(uint32_t (*ptr)[4]);
int main(void) {
    uint32_t values[4] = {
        UINT32_C(0x11111111),
        UINT32_C(0x22222222),
        UINT32_C(0x89ABCDEF),
        UINT32_C(0x44444444)
    };
    if (read_index2(&values) != values[2]) return 1;
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

    def test_compiler_and_tools_fixed_array_paths_remain_identical(self):
        relatives = (
            "_machine_x86_64_types.py",
            "target_ir_addressing.py",
            "_machine_x86_64_fixed_array_emit.py",
            "_machine_x86_64_call_emit.py",
        )
        for relative in relatives:
            compiler_path = ROOT / "compiler" / "sotlas_compile" / relative
            tools_path = ROOT / "tools" / "sotlas_compile" / relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
