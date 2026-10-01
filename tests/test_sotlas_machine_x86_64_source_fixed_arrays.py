"""M16.4d2 source-to-native fixed-array constant-index coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_source_fixed_array_compile"


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
module test::machine_source_fixed_array;
pub fn read_index2(values: *mut [u32; 4]) -> u32 {
    unsafe { return values[2]; }
}
"""


class SotlasX8664SourceFixedArrayTests(unittest.TestCase):
    def _checked_sir(self, source: str = SOURCE, filename: str = "machine_source_fixed_array.sotlas"):
        checked = _phase1.analyze_source_phase1(source, filename=filename)
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_checked_source_preserves_fixed_array_identity_and_projection(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        function = next(
            fn for fn in module.functions if fn.name == "read_index2"
        )
        self.assertEqual(len(function.parameters), 1)
        self.assertEqual(function.parameters[0].name, "values")
        self.assertEqual(function.parameters[0].type_name, "[u32;4]*")

        instructions = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
        ]
        parameter_slots = [
            instruction
            for instruction in instructions
            if type(instruction).__name__ == "AllocStackInst"
            and instruction.var_name == "values"
        ]
        self.assertEqual(len(parameter_slots), 1)
        self.assertEqual(parameter_slots[0].type_name, "[u32;4]*")
        self.assertEqual(parameter_slots[0].result.type_name, "[u32;4]*")

        projections = [
            instruction
            for instruction in instructions
            if type(instruction).__name__ == "FixedArrayElementAddressInst"
        ]
        self.assertEqual(len(projections), 1)
        projection = projections[0]
        self.assertEqual(projection.base.name, "values")
        self.assertEqual(projection.base.type_name, "[u32;4]*")
        self.assertEqual(projection.result.type_name, "u32*")
        self.assertEqual(projection.element_type, "u32")
        self.assertEqual(projection.length, 4)
        self.assertEqual(projection.index, 2)
        self.assertTrue(projection.point_id.startswith("array_address@"))

        loads = [
            instruction
            for instruction in instructions
            if type(instruction).__name__ == "LoadInst"
            and instruction.result.type_name == "u32"
        ]
        self.assertTrue(any(
            instruction.source.name == projection.result.name
            for instruction in loads
        ))

    def test_target_ir_materializes_array_address_without_byte_layout(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(self._checked_sir())
        function = next(
            item for item in target_ir["functions"]
            if item["name"] == "read_index2"
        )
        self.assertEqual(function["parameters"][0]["type"], "[u32;4]*")
        instructions = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        projections = [
            instruction for instruction in instructions
            if instruction["op"] == "array_address"
        ]
        self.assertEqual(len(projections), 1)
        projection = projections[0]
        self.assertEqual(projection["type"], "u32*")
        self.assertEqual(projection["attributes"]["element_type"], "u32")
        self.assertEqual(projection["attributes"]["length"], 4)
        self.assertEqual(projection["attributes"]["index"], 2)
        self.assertTrue(
            projection["attributes"]["source_point_id"].startswith("array_address@")
        )
        self.assertFalse(
            {"offset_bytes", "stride_bytes", "element_size_bytes"}
            & set(projection["attributes"])
        )

    def test_source_compile_uses_backend_derived_array_stride(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_fixed_array.sotlas"
        )
        self.assertIn("lea rax, [rcx+8]", assembly)
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertIn(".globl read_index2", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_dynamic_index_remains_outside_d2_slice(self):
        source = """
module test::machine_source_fixed_array_dynamic;
pub fn read_dynamic(values: *mut [u32; 4], index: usize) -> u32 {
    unsafe { return values[index]; }
}
"""
        module = self._checked_sir(
            source, "machine_source_fixed_array_dynamic.sotlas"
        )
        self.assertIn("read_dynamic", tuple(module.unlowered_functions))
        instructions = [
            instruction
            for function in module.functions
            if function.name == "read_dynamic"
            for block in function.blocks
            for instruction in block.instructions
        ]
        self.assertFalse(any(
            type(instruction).__name__ == "FixedArrayElementAddressInst"
            for instruction in instructions
        ))

    def test_out_of_bounds_constant_remains_fail_closed(self):
        source = """
module test::machine_source_fixed_array_oob;
pub fn read_oob(values: *mut [u32; 4]) -> u32 {
    unsafe { return values[4]; }
}
"""
        with self.assertRaisesRegex(
            Exception,
            r"array index 4 out of bounds for length 4",
        ) as caught:
            _phase1.analyze_source_phase1(
                source, filename="machine_source_fixed_array_oob.sotlas"
            )
        self.assertEqual(type(caught.exception).__name__, "Phase1SemanticError")

    def test_raw_fixed_array_index_still_requires_unsafe(self):
        source = """
module test::machine_source_fixed_array_safe;
pub fn read_without_unsafe(values: *mut [u32; 4]) -> u32 {
    return values[2];
}
"""
        with self.assertRaisesRegex(Exception, "unsafe"):
            _phase1.analyze_source_phase1(
                source, filename="machine_source_fixed_array_safe.sotlas"
            )

    def test_non_scalar_fixed_array_stays_outside_d2_slice(self):
        source = """
module test::machine_source_fixed_array_bool;
pub fn read_bool(values: *mut [bool; 4]) -> bool {
    unsafe { return values[2]; }
}
"""
        module = self._checked_sir(source, "machine_source_fixed_array_bool.sotlas")
        self.assertIn("read_bool", tuple(module.unlowered_functions))

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_reads_source_fixed_array_index(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for source fixed-array gate")

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_fixed_array.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_source_fixed_array_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_source_fixed_array"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t read_index2(uint32_t (*values)[4]);
int main(void) {
    uint32_t values[4] = {
        UINT32_C(0x11111111),
        UINT32_C(0x22222222),
        UINT32_C(0x89ABCDEF),
        UINT32_C(0x44444444)
    };
    if (read_index2(&values) != UINT32_C(0x89ABCDEF)) return 1;
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

    def test_compiler_and_tools_source_fixed_array_bridge_remain_identical(self):
        pairs = (
            ("sotlas/sir/fixed_arrays.py", "sotlas/sir/fixed_arrays.py"),
            ("sotlas_compile/local_addressing_generator.py", "sotlas_compile/local_addressing_generator.py"),
            ("sotlas_compile/target_ir_struct_fields.py", "sotlas_compile/target_ir_struct_fields.py"),
        )
        for compiler_relative, tools_relative in pairs:
            compiler_path = ROOT / "compiler" / compiler_relative
            tools_path = ROOT / "tools" / tools_relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                compiler_relative,
            )


if __name__ == "__main__":
    unittest.main()
