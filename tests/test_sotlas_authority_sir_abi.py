"""Strict checked-SIR representation for named privileged ABI authority."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_sir_abi_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = _load_package()
canonical_sir = importlib.import_module(f"{package.__name__}.canonical_sir")
authority_safety = importlib.import_module(f"{package.__name__}.authority_safety")


INTERRUPT_SOURCE = """module app::authority_sir_interrupt;
@system(cpu.interrupts)
fn disable_interrupts() -> void {
    __cli();
    return;
}
"""


class SotlasAuthoritySIRABITests(unittest.TestCase):
    def _build(self):
        checked = package.analyze_source_phase1(
            INTERRUPT_SOURCE,
            filename="<authority-sir-abi>",
        )
        return package.build_canonical_checked_authority_sir(checked)

    def test_strict_builder_preserves_named_abi_authority_as_sir_fact(self):
        result = self._build()
        sir = canonical_sir.load_canonical_sir()
        function = next(
            item for item in result.module.functions
            if item.name == "disable_interrupts"
        )
        abi = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
            if isinstance(instruction, sir.AuthorityABIInst)
        ]
        self.assertEqual(len(abi), 1)
        self.assertEqual(abi[0].symbol, "__cli")
        self.assertEqual(abi[0].required_capabilities, ("cpu.interrupts",))
        self.assertTrue(abi[0].point_id.startswith("call@"))

        facts = result.authority_certificate.abi_from("disable_interrupts")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].symbol, "__cli")
        self.assertEqual(facts[0].point_id, abi[0].point_id)
        self.assertEqual(facts[0].required_capabilities, ("cpu.interrupts",))
        self.assertTrue(result.authority_safety.success)

    def test_safety_detects_abi_fact_removed_after_certification(self):
        result = self._build()
        sir = canonical_sir.load_canonical_sir()
        function = next(
            item for item in result.module.functions
            if item.name == "disable_interrupts"
        )
        for block in function.blocks:
            block.instructions = [
                instruction
                for instruction in block.instructions
                if not isinstance(instruction, sir.AuthorityABIInst)
            ]

        safety = authority_safety.enforce_authority_sir_safety(
            result.authority_certificate,
            result.module,
        )
        self.assertFalse(safety.success)
        self.assertTrue(
            any("is missing from SIR" in error for error in safety.errors),
            safety.errors,
        )

    def test_safety_detects_abi_capability_widening_after_certification(self):
        result = self._build()
        sir = canonical_sir.load_canonical_sir()
        function = next(
            item for item in result.module.functions
            if item.name == "disable_interrupts"
        )
        fact = next(
            instruction
            for block in function.blocks
            for instruction in block.instructions
            if isinstance(instruction, sir.AuthorityABIInst)
        )
        fact.required_capabilities = ("cpu.interrupts", "cpu.msr")

        safety = authority_safety.enforce_authority_sir_safety(
            result.authority_certificate,
            result.module,
        )
        self.assertFalse(safety.success)
        self.assertTrue(
            any("diverged after certification" in error for error in safety.errors),
            safety.errors,
        )


if __name__ == "__main__":
    unittest.main()
