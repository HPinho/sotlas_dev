"""M16.4e1 nullary enum representation coverage for x86-64 SysV."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_enum_repr_compile"


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
_enums = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_enums")


def _enum_target_ir(discriminant: int = 7) -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "enum_layouts": {
            "Command": {
                "tag_type": "u32",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {"name": "Build", "discriminant": 7},
                ],
            },
        },
        "functions": [{
            "name": "command_build_tag",
            "parameters": [],
            "return_type": "u32",
            "blocks": [{
                "label": "0",
                "instructions": [
                    {
                        "op": "enum_const",
                        "result": "tag",
                        "type": "u32",
                        "operands": [],
                        "attributes": {
                            "enum": "Command",
                            "variant": "Build",
                            "discriminant": discriminant,
                            "source_point_id": "enum_const@1:1",
                        },
                    },
                    {"op": "return", "operands": ["tag"]},
                ],
            }],
        }],
    }


class SotlasX8664EnumRepresentationTests(unittest.TestCase):
    def test_target_ir_accepts_explicit_nullary_u32_enum_representation(self):
        target_ir = _enum_target_ir()
        self.assertIsNone(_enums.validate_target_ir_enum_representation(target_ir))
        declaration = target_ir["enum_layouts"]["Command"]
        self.assertEqual(declaration["tag_type"], "u32")
        self.assertEqual(
            [(item["name"], item["discriminant"]) for item in declaration["variants"]],
            [("None", 0), ("Build", 7)],
        )

    def test_enum_discriminants_must_be_unique_u32_values(self):
        duplicate = _enum_target_ir()
        duplicate["enum_layouts"]["Command"]["variants"].append(
            {"name": "AlsoBuild", "discriminant": 7}
        )
        with self.assertRaisesRegex(
            _enums.TargetIREnumError,
            "duplicate discriminant 7",
        ):
            _enums.validate_target_ir_enum_representation(duplicate)

        invalid = _enum_target_ir()
        invalid["enum_layouts"]["Command"]["variants"][1]["discriminant"] = 1 << 32
        with self.assertRaisesRegex(
            _enums.TargetIREnumError,
            "invalid u32 discriminant",
        ):
            _enums.validate_target_ir_enum_representation(invalid)

    def test_payload_and_target_byte_layout_remain_outside_e1(self):
        for key, value in (
            ("payload_type", "u32"),
            ("size_bytes", 4),
            ("alignment_bytes", 4),
            ("payload_offset_bytes", 8),
        ):
            target_ir = _enum_target_ir()
            target_ir["enum_layouts"]["Command"]["variants"][1][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    _enums.TargetIREnumError,
                    "cannot carry payload or target byte layout",
                ):
                    _enums.validate_target_ir_enum_representation(target_ir)

    def test_enum_const_must_match_declared_variant_and_discriminant(self):
        mismatch = _enum_target_ir(discriminant=8)
        with self.assertRaisesRegex(
            _enums.TargetIREnumError,
            "discriminant does not match declaration",
        ):
            _enums.validate_target_ir_enum_representation(mismatch)

        unknown = _enum_target_ir()
        instruction = unknown["functions"][0]["blocks"][0]["instructions"][0]
        instruction["attributes"]["variant"] = "Missing"
        with self.assertRaisesRegex(
            _enums.TargetIREnumError,
            "unknown variant",
        ):
            _enums.validate_target_ir_enum_representation(unknown)

    def test_enum_const_cannot_smuggle_aggregate_abi_layout(self):
        target_ir = _enum_target_ir()
        instruction = target_ir["functions"][0]["blocks"][0]["instructions"][0]
        instruction["attributes"]["size_bytes"] = 4
        with self.assertRaisesRegex(
            _enums.TargetIREnumError,
            "cannot carry payload or target byte layout",
        ):
            _enums.validate_target_ir_enum_representation(target_ir)

    def test_machine_materializes_declared_discriminant_as_u32(self):
        assembly = _machine.emit_x86_64_sysv_assembly(_enum_target_ir())
        self.assertIn(".globl command_build_tag", assembly)
        self.assertIn("mov eax, 7", assembly)
        self.assertNotIn("LLVM", assembly)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_returns_nullary_enum_discriminant(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for enum representation gate")

        assembly = _machine.emit_x86_64_sysv_assembly(_enum_target_ir())
        with tempfile.TemporaryDirectory(prefix="sotlas_enum_repr_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "enum_repr"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t command_build_tag(void);
int main(void) {
    if (command_build_tag() != UINT32_C(7)) return 1;
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

    def test_compiler_and_tools_enum_paths_remain_identical(self):
        relatives = (
            "target_ir_enums.py",
            "_machine_x86_64_enum_emit.py",
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
