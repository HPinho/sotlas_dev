"""M16.3d1 source visibility and machine-linkage coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_linkage_compile"


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
_target_ir = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir")
_linkage = importlib.import_module(f"{_CANONICAL_PACKAGE}.symbol_linkage")


SOURCE = """
module test::machine_linkage;

fn hidden_identity(value: u32) -> u32 {
    return value;
}

pub fn public_identity(value: u32) -> u32 {
    return value;
}

@export
fn c_identity(value: u32) -> u32 {
    return value;
}
"""


class SotlasX8664LinkageTests(unittest.TestCase):
    def _module_and_target_ir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE, filename="machine_linkage.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        module = checked_sir.module
        self.assertEqual(tuple(module.unlowered_functions), ())
        target_ir = _target_ir.lower_sir_to_target_ir(module)
        _linkage.attach_target_ir_symbol_linkage(target_ir, module)
        return module, target_ir

    def test_checked_source_visibility_is_preserved_in_canonical_sir(self):
        module, _ = self._module_and_target_ir()
        facts = {fact.symbol: fact for fact in module.symbol_linkage}

        self.assertEqual(facts["hidden_identity"].linkage, "internal")
        self.assertEqual(
            facts["hidden_identity"].source_visibility, "private"
        )
        self.assertFalse(facts["hidden_identity"].abi_export)

        self.assertEqual(facts["public_identity"].linkage, "external")
        self.assertEqual(
            facts["public_identity"].source_visibility, "public"
        )
        self.assertFalse(facts["public_identity"].abi_export)

        self.assertEqual(facts["c_identity"].linkage, "external")
        self.assertEqual(facts["c_identity"].source_visibility, "private")
        self.assertTrue(facts["c_identity"].abi_export)

        functions = {function.name: function for function in module.functions}
        self.assertEqual(functions["hidden_identity"].linkage, "internal")
        self.assertEqual(functions["public_identity"].linkage, "external")
        self.assertEqual(functions["c_identity"].linkage, "external")

    def test_target_ir_preserves_linkage_without_machine_side_inference(self):
        _, target_ir = self._module_and_target_ir()
        functions = {
            function["name"]: function for function in target_ir["functions"]
        }

        self.assertEqual(functions["hidden_identity"]["linkage"], "internal")
        self.assertEqual(
            functions["hidden_identity"]["source_visibility"], "private"
        )
        self.assertFalse(functions["hidden_identity"]["abi_export"])

        self.assertEqual(functions["public_identity"]["linkage"], "external")
        self.assertEqual(
            functions["public_identity"]["source_visibility"], "public"
        )
        self.assertEqual(functions["c_identity"]["linkage"], "external")
        self.assertTrue(functions["c_identity"]["abi_export"])

    def test_machine_emitter_uses_local_and_global_symbol_bindings(self):
        _, target_ir = self._module_and_target_ir()
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)

        self.assertIn(".local hidden_identity", assembly)
        self.assertNotIn(".globl hidden_identity", assembly)
        self.assertIn(".globl public_identity", assembly)
        self.assertIn(".globl c_identity", assembly)
        self.assertIn(".type hidden_identity, @function", assembly)
        self.assertIn(".size hidden_identity, .-hidden_identity", assembly)

    def test_legacy_target_ir_without_linkage_keeps_external_contract(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "legacy_linkage",
            "functions": [{
                "name": "legacy_api",
                "parameters": [{"name": "value", "type": "u32"}],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [{
                        "op": "return",
                        "operands": ["value"],
                        "attributes": {},
                    }],
                }],
            }],
            "limitations": [],
        }
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)
        self.assertIn(".globl legacy_api", assembly)
        self.assertNotIn(".local legacy_api", assembly)

    def test_contradictory_public_internal_linkage_fails_closed(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "bad_linkage",
            "functions": [{
                "name": "bad_api",
                "linkage": "internal",
                "source_visibility": "public",
                "abi_export": False,
                "parameters": [{"name": "value", "type": "u32"}],
                "return_type": "u32",
                "blocks": [{
                    "label": "entry",
                    "instructions": [{
                        "op": "return",
                        "operands": ["value"],
                        "attributes": {},
                    }],
                }],
            }],
            "limitations": [],
        }
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "public source visibility requires external linkage",
        ):
            _machine.emit_x86_64_sysv_assembly(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_links_only_declared_external_apis(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for linkage execution gate")

        _, target_ir = self._module_and_target_ir()
        assembly = _machine.emit_x86_64_sysv_assembly(target_ir)
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_linkage_") as temp:
            directory = Path(temp)
            asm_path = directory / "linkage.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_linkage"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t public_identity(uint32_t value);
extern uint32_t c_identity(uint32_t value);
int main(void) {
    if (public_identity(41u) != 41u) return 1;
    if (c_identity(42u) != 42u) return 2;
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

    def test_compiler_and_tools_linkage_layers_remain_identical(self):
        for relative in (
            "symbol_linkage.py",
            "canonical_sir.py",
            "_machine_x86_64_call_validation.py",
            "_machine_x86_64_call_emit.py",
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
