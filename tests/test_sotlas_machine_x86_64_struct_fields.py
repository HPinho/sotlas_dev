"""M16.4c source-to-native scalar struct field coverage for x86-64 SysV."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_struct_fields_compile"


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
_addressing = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_addressing")
_machine_layout = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_struct_layout"
)


SOURCE = """
module test::machine_struct_fields;
pub struct Mixed {
    pub tag: u8;
    pub value: u32;
    pub tail: u16;
}
pub fn read_value(ptr: *mut Mixed) -> u32 {
    unsafe { return ptr.value; }
}
pub fn read_tail(ptr: *mut Mixed) -> u16 {
    unsafe { return ptr.tail; }
}
"""


def _field_target_ir() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "struct_layouts": [{
            "name": "Mixed",
            "fields": [
                {"name": "tag", "type": "u8"},
                {"name": "value", "type": "u32"},
                {"name": "tail", "type": "u16"},
            ],
        }],
        "functions": [{
            "name": "read_value",
            "parameters": [{"name": "ptr", "type": "Mixed*"}],
            "return_type": "u32",
            "blocks": [{
                "label": "0",
                "instructions": [
                    {
                        "op": "field_address",
                        "result": "value_ptr",
                        "type": "u32*",
                        "operands": ["ptr"],
                        "attributes": {
                            "struct": "Mixed",
                            "field": "value",
                            "field_type": "u32",
                            "source_point_id": "field_address@1:1",
                        },
                    },
                    {
                        "op": "load",
                        "result": "value",
                        "type": "u32",
                        "operands": ["value_ptr"],
                    },
                    {"op": "return", "operands": ["value"]},
                ],
            }],
        }],
    }


class SotlasX8664StructFieldTests(unittest.TestCase):
    def _checked_sir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE, filename="machine_struct_fields.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_checked_source_lowers_struct_pointer_fields_to_canonical_sir(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        layouts = tuple(getattr(module, "struct_layouts", ()) or ())
        self.assertEqual(len(layouts), 1)
        self.assertEqual(layouts[0].name, "Mixed")
        self.assertEqual(
            [(field.name, field.type_name) for field in layouts[0].fields],
            [("tag", "u8"), ("value", "u32"), ("tail", "u16")],
        )

        functions = {function.name: function for function in module.functions}
        for name, field, scalar in (
            ("read_value", "value", "u32"),
            ("read_tail", "tail", "u16"),
        ):
            instructions = [
                instruction
                for block in functions[name].blocks
                for instruction in block.instructions
            ]
            projections = [
                item for item in instructions
                if type(item).__name__ == "StructFieldAddressInst"
            ]
            self.assertEqual(len(projections), 1, name)
            projection = projections[0]
            self.assertEqual(projection.base.type_name, "Mixed*")
            self.assertEqual(projection.struct_name, "Mixed")
            self.assertEqual(projection.field_name, field)
            self.assertEqual(projection.field_type, scalar)
            self.assertEqual(projection.result.type_name, f"{scalar}*")

    def test_target_ir_preserves_field_identity_without_target_offsets(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(self._checked_sir())
        self.assertEqual(target_ir["struct_layouts"], [{
            "name": "Mixed",
            "fields": [
                {"name": "tag", "type": "u8"},
                {"name": "value", "type": "u32"},
                {"name": "tail", "type": "u16"},
            ],
        }])
        functions = {item["name"]: item for item in target_ir["functions"]}
        for name, field, scalar in (
            ("read_value", "value", "u32"),
            ("read_tail", "tail", "u16"),
        ):
            instructions = [
                instruction
                for block in functions[name]["blocks"]
                for instruction in block["instructions"]
            ]
            projection = next(
                item for item in instructions if item["op"] == "field_address"
            )
            self.assertEqual(projection["type"], f"{scalar}*")
            self.assertEqual(projection["attributes"]["struct"], "Mixed")
            self.assertEqual(projection["attributes"]["field"], field)
            self.assertEqual(projection["attributes"]["field_type"], scalar)
            self.assertNotIn("offset_bytes", projection["attributes"])
        self.assertIsNone(_addressing.validate_target_ir_addressing(target_ir))

    def test_x86_64_layout_derives_padding_and_offsets_from_field_types(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(self._checked_sir())
        plan = _machine_layout.plan_x86_64_sysv_struct_layouts(target_ir)["Mixed"]
        self.assertEqual(plan["fields"]["tag"]["offset_bytes"], 0)
        self.assertEqual(plan["fields"]["value"]["offset_bytes"], 4)
        self.assertEqual(plan["fields"]["tail"]["offset_bytes"], 8)
        self.assertEqual(plan["size_bytes"], 12)
        self.assertEqual(plan["alignment_bytes"], 4)

    def test_machine_emits_layout_derived_field_addresses_and_scalar_loads(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_struct_fields.sotlas"
        )
        self.assertIn("lea rax, [rcx+4]", assembly)
        self.assertIn("lea rax, [rcx+8]", assembly)
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertIn("movzx eax, WORD PTR [rcx]", assembly)
        self.assertIn(".globl read_value", assembly)
        self.assertIn(".globl read_tail", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_target_ir_cannot_smuggle_a_struct_field_byte_offset(self):
        target_ir = _field_target_ir()
        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["offset_bytes"] = 123
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "cannot carry a target byte offset",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_field_identity_and_declared_type_mismatch_fail_closed(self):
        target_ir = _field_target_ir()
        projection = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        projection["attributes"]["field"] = "tail"
        with self.assertRaisesRegex(
            _addressing.TargetIRAddressingError,
            "does not match a declared struct field",
        ):
            _addressing.validate_target_ir_addressing(target_ir)

    def test_nominal_struct_pointer_is_transportable_but_not_directly_loadable(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "struct_layouts": [{
                "name": "Mixed",
                "fields": [{"name": "value", "type": "u32"}],
            }],
            "functions": [{
                "name": "bad_direct_aggregate_load",
                "parameters": [{"name": "ptr", "type": "Mixed*"}],
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
            }],
        }
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "indirect load source must be a supported pointer type",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    def test_unsupported_struct_field_type_remains_unlowered(self):
        source = """
module test::machine_struct_fields_unsupported;
pub struct Unsupported { pub flag: bool; }
pub fn read_flag(ptr: *mut Unsupported) -> bool {
    unsafe { return ptr.flag; }
}
"""
        checked = _phase1.analyze_source_phase1(
            source, filename="machine_struct_fields_unsupported.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        self.assertIn(
            "read_flag", tuple(checked_sir.module.unlowered_functions)
        )
        self.assertEqual(
            tuple(getattr(checked_sir.module, "struct_layouts", ()) or ()), ()
        )

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_reads_c_struct_fields_at_derived_offsets(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for struct field execution gate")

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_struct_fields.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_struct_fields_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_struct_fields"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
struct Mixed {
    uint8_t tag;
    uint32_t value;
    uint16_t tail;
};
extern uint32_t read_value(struct Mixed *ptr);
extern uint16_t read_tail(struct Mixed *ptr);
int main(void) {
    struct Mixed item = { UINT8_C(0xA5), UINT32_C(0x89ABCDEF), UINT16_C(0xBEEF) };
    if (read_value(&item) != item.value) return 1;
    if (read_tail(&item) != item.tail) return 2;
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

    def test_compiler_and_tools_struct_field_paths_remain_identical(self):
        compile_relatives = (
            "local_addressing_generator.py",
            "struct_layout.py",
            "target_ir_struct_fields.py",
            "target_ir_calls.py",
            "target_ir_addressing.py",
            "_machine_x86_64_types.py",
            "_machine_x86_64_register_view.py",
            "_machine_x86_64_struct_layout.py",
            "_machine_x86_64_struct_field_emit.py",
            "_machine_x86_64_call_plan.py",
            "_machine_x86_64_call_emit.py",
        )
        for relative in compile_relatives:
            compiler_path = ROOT / "compiler" / "sotlas_compile" / relative
            tools_path = ROOT / "tools" / "sotlas_compile" / relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                relative,
            )
        self.assertEqual(
            (ROOT / "compiler" / "sotlas" / "sir" / "struct_fields.py").read_text(
                encoding="utf-8"
            ),
            (ROOT / "tools" / "sotlas" / "sir" / "struct_fields.py").read_text(
                encoding="utf-8"
            ),
        )


if __name__ == "__main__":
    unittest.main()
