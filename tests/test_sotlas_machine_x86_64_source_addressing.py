"""M16.4b2 source-to-native non-escaping local address coverage."""
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
_CANONICAL_PACKAGE = "_sotlas_machine_source_address_compile"


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
module test::machine_source_address;
pub fn roundtrip_local(value: u32) -> u32 {
    let local: u32 = value;
    unsafe { return *&local; }
}
"""


class SotlasX8664SourceAddressingTests(unittest.TestCase):
    def _checked_sir(self):
        checked = _phase1.analyze_source_phase1(
            SOURCE, filename="machine_source_address.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_checked_source_preserves_non_escaping_local_address_fact(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        facts = tuple(getattr(module, "local_address_facts", ()) or ())
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual(fact.function, "roundtrip_local")
        self.assertEqual(fact.source_name, "local")
        self.assertEqual(fact.pointee_type, "u32")
        self.assertTrue(fact.pointer_value.startswith("addr_local"))

        function = next(
            fn for fn in module.functions if fn.name == "roundtrip_local"
        )
        instructions = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
        ]
        local_slots = [
            instruction
            for instruction in instructions
            if type(instruction).__name__ == "AllocStackInst"
            and instruction.var_name == "local"
        ]
        self.assertEqual(len(local_slots), 1)
        self.assertEqual(local_slots[0].result.name, fact.slot_value)
        loads = [
            instruction
            for instruction in instructions
            if type(instruction).__name__ == "LoadInst"
            and instruction.result.name == fact.load_result
        ]
        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0].source.name, fact.slot_value)

    def test_target_ir_materializes_address_of_before_indirect_load(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(self._checked_sir())
        function = next(
            item for item in target_ir["functions"]
            if item["name"] == "roundtrip_local"
        )
        instructions = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        addresses = [item for item in instructions if item["op"] == "address_of"]
        self.assertEqual(len(addresses), 1)
        address = addresses[0]
        self.assertEqual(address["type"], "u32*")
        self.assertEqual(address["attributes"]["offset_bytes"], 0)
        self.assertEqual(address["attributes"]["source_name"], "local")

        loads = [
            item for item in instructions
            if item["op"] == "load" and item["type"] == "u32"
        ]
        self.assertTrue(any(
            item["operands"] == [address["result"]]
            for item in loads
        ))

    def test_source_compile_uses_lea_then_width_correct_indirect_read(self):
        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_address.sotlas"
        )
        self.assertRegex(assembly, r"lea rax, \[rbp-[0-9]+\]")
        self.assertIn("mov eax, DWORD PTR [rcx]", assembly)
        self.assertIn(".globl roundtrip_local", assembly)
        self.assertNotIn("LLVM", assembly)

    def test_frontend_still_rejects_local_reference_escape(self):
        leaking_source = """
module test::machine_source_address_escape;
pub fn leak(value: u32) -> *mut u32 {
    let local: u32 = value;
    return &local;
}
"""
        with self.assertRaisesRegex(Exception, "local"):
            _phase1.analyze_source_phase1(
                leaking_source,
                filename="machine_source_address_escape.sotlas",
            )

    def test_literal_initialized_local_address_remains_outside_b2_slice(self):
        source = """
module test::machine_source_address_literal;
pub fn literal_roundtrip(value: u32) -> u32 {
    let local: u32 = 7u32;
    unsafe { return *&local; }
}
"""
        checked = _phase1.analyze_source_phase1(
            source, filename="machine_source_address_literal.sotlas"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        self.assertIn(
            "literal_roundtrip",
            tuple(checked_sir.module.unlowered_functions),
        )
        self.assertEqual(
            tuple(getattr(checked_sir.module, "local_address_facts", ()) or ()),
            (),
        )

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_roundtrips_source_local_address(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for source address gate")

        assembly = _machine.compile_source_to_x86_64_sysv_assembly(
            SOURCE, "machine_source_address.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_source_address_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_source_address"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t roundtrip_local(uint32_t value);
int main(void) {
    if (roundtrip_local(UINT32_C(0x89ABCDEF)) != UINT32_C(0x89ABCDEF)) return 1;
    if (roundtrip_local(UINT32_C(0)) != UINT32_C(0)) return 2;
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

    def test_compiler_and_tools_source_address_bridge_remain_identical(self):
        for relative in (
            "local_addressing.py",
            "canonical_sir.py",
            "target_ir_calls.py",
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
