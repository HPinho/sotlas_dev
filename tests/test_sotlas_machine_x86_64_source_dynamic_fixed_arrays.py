"""M16.4d3b source-to-native dynamic fixed-array indexing coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_source_dynamic_fixed_array_compile"


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
module test::machine_source_dynamic_fixed_array;
pub fn read_dynamic(values: *mut [u32; 4], index: usize) -> u32 {
    unsafe { return values[index]; }
}
"""


class SotlasX8664SourceDynamicFixedArrayTests(unittest.TestCase):
    def _checked_sir(
        self,
        source: str = SOURCE,
        filename: str = "machine_source_dynamic_fixed_array.sotlas",
    ):
        checked = _phase1.analyze_source_phase1(source, filename=filename)
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_checked_source_lowers_dynamic_index_as_explicit_sir_value(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        function = next(fn for fn in module.functions if fn.name == "read_dynamic")
        self.assertEqual(
            [(value.name, value.type_name) for value in function.parameters],
            [("values", "[u32;4]*"), ("index", "usize")],
        )

        instructions = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
        ]
        parameter_slots = {
            instruction.var_name: instruction
            for instruction in instructions
            if type(instruction).__name__ == "AllocStackInst"
            and instruction.var_name in {"values", "index"}
        }
        self.assertEqual(parameter_slots["values"].type_name, "[u32;4]*")
        self.assertEqual(
            parameter_slots["values"].result.type_name, "[u32;4]*"
        )
        self.assertEqual(parameter_slots["index"].type_name, "usize")

        projections = [
            instruction
            for instruction in instructions
            if type(instruction).__name__
            == "DynamicFixedArrayElementAddressInst"
        ]
        self.assertEqual(len(projections), 1)
        projection = projections[0]
        self.assertEqual(projection.base.name, "values")
        self.assertEqual(projection.base.type_name, "[u32;4]*")
        self.assertEqual(projection.index.name, "index")
        self.assertEqual(projection.index.type_name, "usize")
        self.assertEqual(projection.result.type_name, "u32*")
        self.assertEqual(projection.element_type, "u32")
        self.assertEqual(projection.length, 4)
        self.assertEqual(projection.bounds_policy, "trap")
        self.assertTrue(
            projection.point_id.startswith("array_address_dynamic@")
        )

    def test_target_ir_keeps_dynamic_index_as_operand_and_trap_policy(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(
            self._checked_sir()
        )
        function = next(
            item for item in target_ir["functions"]
            if item["name"] == "read_dynamic"
        )
        self.assertEqual(
            [item["type"] for item in function["parameters"]],
            ["[u32;4]*", "usize"],
        )
        instructions = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        projections = [
            instruction
            for instruction in instructions
            if instruction["op"] == "array_address_dynamic"
        ]
        self.assertEqual(len(projections), 1)
        projection = projections[0]
        self.assertEqual(projection["type"], "u32*")
        self.assertEqual(projection["operands"], ["values", "index"])
        self.assertEqual(projection["attributes"]["element_type"], "u32")
        self.assertEqual(projection["attributes"]["length"], 4)
        self.assertEqual(projection["attributes"]["bounds_policy"], "trap")
        self.assertNotIn("index", projection["attributes"])
        self.assertFalse(
            {"offset_bytes", "stride_bytes", "element_size_bytes"}
            & set(projection["attributes"])
        )

    def test_source_compile_emits_runtime_bounds_and_scaled_address(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_dynamic_fixed_array.sotlas"
        )
        self.assertIn("mov rax, 4", assembly)
        self.assertIn("cmp rdx, rax", assembly)
        self.assertIn("jb 1f", assembly)
        self.assertIn("ud2", assembly)
        self.assertIn("lea rax, [rcx+rdx*4]", assembly)
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_dynamic_raw_pointer_index_still_requires_unsafe(self):
        source = """
module test::machine_source_dynamic_fixed_array_safe;
pub fn read_dynamic(values: *mut [u32; 4], index: usize) -> u32 {
    return values[index];
}
"""
        with self.assertRaisesRegex(Exception, "unsafe"):
            _phase1.analyze_source_phase1(
                source,
                filename="machine_source_dynamic_fixed_array_safe.sotlas",
            )

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_dynamic_source_reads_in_bounds_and_traps_oob(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest(
                "native C compiler is required for source dynamic fixed-array gate"
            )

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_dynamic_fixed_array.sotlas"
        )
        with tempfile.TemporaryDirectory(
            prefix="sotlas_source_dynamic_fixed_array_"
        ) as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            asm_path.write_text(assembly, encoding="utf-8")

            in_bounds_c = directory / "in_bounds.c"
            in_bounds_exe = directory / "in_bounds"
            in_bounds_c.write_text(
                """
#include <stdint.h>
#include <stddef.h>
extern uint32_t read_dynamic(uint32_t (*values)[4], size_t index);
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
                [
                    compiler,
                    str(in_bounds_c),
                    str(asm_path),
                    "-o",
                    str(in_bounds_exe),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                [str(in_bounds_exe)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)

            oob_c = directory / "oob.c"
            oob_exe = directory / "oob"
            oob_c.write_text(
                """
#include <stdint.h>
#include <stddef.h>
extern uint32_t read_dynamic(uint32_t (*values)[4], size_t index);
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
            run = subprocess.run(
                [str(oob_exe)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                run.returncode,
                0,
                "source dynamic out-of-bounds index must trap",
            )

    def test_compiler_and_tools_d3b_paths_remain_identical(self):
        pairs = (
            ("sotlas/sir/fixed_arrays.py", "sotlas/sir/fixed_arrays.py"),
            ("sotlas_compile/local_addressing.py", "sotlas_compile/local_addressing.py"),
            (
                "sotlas_compile/dynamic_fixed_array_generator.py",
                "sotlas_compile/dynamic_fixed_array_generator.py",
            ),
            (
                "sotlas_compile/target_ir_struct_fields.py",
                "sotlas_compile/target_ir_struct_fields.py",
            ),
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
