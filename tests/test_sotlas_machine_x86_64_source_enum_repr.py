"""M16.4e2 source-to-native nullary enum tag coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_source_enum_repr_compile"


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
_enums = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_enums")


SOURCE = """
module test::machine_source_enum;
pub enum Command {
    None = 0,
    Build = 7
}
pub fn command_build_tag() -> u32 {
    return Command::Build as u32;
}
"""


class SotlasX8664SourceEnumRepresentationTests(unittest.TestCase):
    def _checked_sir(
        self,
        source: str = SOURCE,
        filename: str = "machine_source_enum.sotlas",
    ):
        checked = _phase1.analyze_source_phase1(source, filename=filename)
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_checked_source_preserves_enum_identity_in_canonical_sir(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        self.assertEqual(len(module.nullary_enum_facts), 1)
        declaration = module.nullary_enum_facts[0]
        self.assertEqual(declaration.name, "Command")
        self.assertEqual(declaration.tag_type, "u32")
        self.assertEqual(
            [(item.name, item.discriminant) for item in declaration.variants],
            [("None", 0), ("Build", 7)],
        )

        function = next(
            item for item in module.functions
            if item.name == "command_build_tag"
        )
        instructions = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
        ]
        constants = [
            instruction for instruction in instructions
            if type(instruction).__name__ == "EnumConstInst"
        ]
        self.assertEqual(len(constants), 1)
        constant = constants[0]
        self.assertEqual(constant.enum_name, "Command")
        self.assertEqual(constant.variant, "Build")
        self.assertEqual(constant.discriminant, 7)
        self.assertEqual(constant.result.type_name, "u32")
        self.assertTrue(constant.point_id.startswith("enum_const@"))

    def test_target_ir_preserves_enum_declaration_and_enum_const(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(
            self._checked_sir()
        )
        self.assertEqual(
            target_ir["enum_layouts"]["Command"],
            {
                "tag_type": "u32",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {"name": "Build", "discriminant": 7},
                ],
            },
        )
        function = next(
            item for item in target_ir["functions"]
            if item["name"] == "command_build_tag"
        )
        self.assertEqual(function["return_type"], "u32")
        instructions = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        constants = [
            instruction for instruction in instructions
            if instruction["op"] == "enum_const"
        ]
        self.assertEqual(len(constants), 1)
        constant = constants[0]
        self.assertEqual(constant["type"], "u32")
        self.assertEqual(constant["operands"], [])
        self.assertEqual(constant["attributes"]["enum"], "Command")
        self.assertEqual(constant["attributes"]["variant"], "Build")
        self.assertEqual(constant["attributes"]["discriminant"], 7)
        self.assertFalse(
            {
                "payload_type",
                "size_bytes",
                "alignment_bytes",
                "payload_offset_bytes",
                "payload_size_bytes",
            } & set(constant["attributes"])
        )
        self.assertIsNone(
            _enums.validate_target_ir_enum_representation(target_ir)
        )

    def test_source_compile_emits_explicit_nullary_enum_tag(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_enum.sotlas"
        )
        self.assertIn(".globl command_build_tag", assembly)
        self.assertIn("mov eax, 7", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_nominal_enum_return_remains_outside_e2_abi_subset(self):
        source = """
module test::machine_source_enum_nominal;
pub enum Command {
    None = 0,
    Build = 7
}
pub fn command() -> Command {
    return Command::Build;
}
"""
        checked = _phase1.analyze_source_phase1(
            source,
            filename="machine_source_enum_nominal.sotlas",
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        self.assertIn("command", checked_sir.module.unlowered_functions)
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "cannot lower source bodies for: command",
        ):
            _machine.compile_source_to_x86_64_sysv_assembly(
                source,
                "machine_source_enum_nominal.sotlas",
            )

    def test_implicit_discriminant_does_not_enter_explicit_e2_contract(self):
        source = """
module test::machine_source_enum_implicit;
pub enum Command {
    None,
    Build
}
pub fn command_build_tag() -> u32 {
    return Command::Build as u32;
}
"""
        module = self._checked_sir(
            source,
            "machine_source_enum_implicit.sotlas",
        )
        self.assertEqual(tuple(module.nullary_enum_facts), ())
        self.assertIn("command_build_tag", module.unlowered_functions)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_returns_source_enum_discriminant(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest(
                "native C compiler is required for source enum representation gate"
            )

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_enum.sotlas"
        )
        with tempfile.TemporaryDirectory(
            prefix="sotlas_source_enum_repr_"
        ) as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "enum_source_repr"
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
            run = subprocess.run(
                [str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_compiler_and_tools_e2_paths_remain_identical(self):
        pairs = (
            ("sotlas/sir/enums.py", "sotlas/sir/enums.py"),
            (
                "sotlas_compile/enum_source_generator.py",
                "sotlas_compile/enum_source_generator.py",
            ),
            (
                "sotlas_compile/local_addressing.py",
                "sotlas_compile/local_addressing.py",
            ),
            (
                "sotlas_compile/target_ir_struct_fields.py",
                "sotlas_compile/target_ir_struct_fields.py",
            ),
            (
                "sotlas_compile/target_ir_enums.py",
                "sotlas_compile/target_ir_enums.py",
            ),
            (
                "sotlas_compile/target_ir_calls.py",
                "sotlas_compile/target_ir_calls.py",
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
