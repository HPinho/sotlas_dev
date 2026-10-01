"""M16.4d3a runtime-bounded fixed-array addressing coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_dynamic_fixed_arrays_compile"


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


def _dynamic_reader(
    name: str,
    element_type: str = "u32",
    length: int = 4,
    *,
    index_type: str = "usize",
) -> dict:
    return {
        "name": name,
        "parameters": [
            {"name": "ptr", "type": f"[{element_type};{length}]*"},
            {"name": "index", "type": index_type},
        ],
        "return_type": element_type,
        "blocks": [{
            "label": "0",
            "instructions": [
                {
                    "op": "array_address_dynamic",
                    "result": "element_ptr",
                    "type": f"{element_type}*",
                    "operands": ["ptr", "index"],
                    "attributes": {
                        "element_type": element_type,
                        "length": length,
                        "bounds_policy": "trap",
                        "source_point_id": "array_address_dynamic@1:1",
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


class SotlasX8664DynamicFixedArrayTests(unittest.TestCase):
    def test_target_ir_accepts_dynamic_usize_index_with_explicit_trap_policy(self):
        target_ir = _target_ir(_dynamic_reader("read_dynamic"))
        self.assertIsNone(_addressing.validate_target_ir_addressing(target_ir))

    def test_dynamic_index_must_be_usize(self):
        target_ir = _target_ir(_dynamic_reader("read_dynamic", index_type="u32"))
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "index must have type 'usize'",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_dynamic_projection_requires_explicit_trap_policy(self):
        target_ir = _target_ir(_dynamic_reader("read_dynamic"))
        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["bounds_policy"] = "unchecked"
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "requires bounds_policy='trap'",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_dynamic_index_is_an_ssa_operand_not_an_attribute(self):
        target_ir = _target_ir(_dynamic_reader("read_dynamic"))
        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["index"] = 2
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "index must be an SSA operand",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_dynamic_projection_cannot_smuggle_target_layout(self):
        for key in ("offset_bytes", "stride_bytes", "element_size_bytes"):
            target_ir = _target_ir(_dynamic_reader("read_dynamic"))
            projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
            projection["attributes"][key] = 32
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    _addressing.TargetIRAddressingError,
                    "cannot carry target byte layout",
                ):
                    _addressing.validate_target_ir_addressing(target_ir)

    def test_x86_64_rejects_dynamic_length_larger_than_usize(self):
        target_ir = _target_ir(
            _dynamic_reader("too_large", "u8", 1 << 64)
        )
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "length does not fit x86-64 usize",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    def test_x86_64_emits_unsigned_bounds_check_trap_and_scaled_address(self):
        target_ir = _target_ir(
            _dynamic_reader("read_u8", "u8"),
            _dynamic_reader("read_u16", "u16"),
            _dynamic_reader("read_u32", "u32"),
            _dynamic_reader("read_u64", "u64"),
        )
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)
        self.assertGreaterEqual(assembly.count("mov rax, 4"), 4)
        self.assertGreaterEqual(assembly.count("cmp rdx, rax"), 4)
        self.assertGreaterEqual(assembly.count("jb 1f"), 4)
        self.assertGreaterEqual(assembly.count("ud2"), 4)
        self.assertIn("lea rax, [rcx+rdx]", assembly)
        self.assertIn("lea rax, [rcx+rdx*2]", assembly)
        self.assertIn("lea rax, [rcx+rdx*4]", assembly)
        self.assertIn("lea rax, [rcx+rdx*8]", assembly)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_dynamic_index_reads_in_bounds_and_traps_oob(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for dynamic fixed-array gate")

        target_ir = _target_ir(_dynamic_reader("read_dynamic"))
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)
        with tempfile.TemporaryDirectory(prefix="sotlas_dynamic_fixed_arrays_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            asm_path.write_text(assembly, encoding="utf-8")

            in_bounds_c = directory / "in_bounds.c"
            in_bounds_exe = directory / "in_bounds"
            in_bounds_c.write_text(
                """
#include <stdint.h>
#include <stddef.h>
extern uint32_t read_dynamic(uint32_t (*ptr)[4], size_t index);
int main(void) {
    uint32_t values[4] = {
        UINT32_C(0x11111111),
        UINT32_C(0x22222222),
        UINT32_C(0x89ABCDEF),
        UINT32_C(0x44444444)
    };
    if (read_dynamic(&values, 0) != values[0]) return 1;
    if (read_dynamic(&values, 2) != values[2]) return 2;
    if (read_dynamic(&values, 3) != values[3]) return 3;
    return 0;
}
""",
                encoding="utf-8",
            )
            build = subprocess.run(
                [compiler, str(in_bounds_c), str(asm_path), "-o", str(in_bounds_exe)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(in_bounds_exe)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

            oob_c = directory / "oob.c"
            oob_exe = directory / "oob"
            oob_c.write_text(
                """
#include <stdint.h>
#include <stddef.h>
extern uint32_t read_dynamic(uint32_t (*ptr)[4], size_t index);
int main(void) {
    uint32_t values[4] = {1, 2, 3, 4};
    (void)read_dynamic(&values, 4);
    return 0;
}
""",
                encoding="utf-8",
            )
            build = subprocess.run(
                [compiler, str(oob_c), str(asm_path), "-o", str(oob_exe)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(oob_exe)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0, "out-of-bounds dynamic index must trap")

    def test_compiler_and_tools_dynamic_array_paths_remain_identical(self):
        relatives = (
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
