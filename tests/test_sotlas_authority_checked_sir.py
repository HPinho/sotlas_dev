"""Strict checked-SIR composition for Phase-3 Authority Domains."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_checked_sir_package"
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


MATCHING = """module app::authority_checked_sir;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


REPEATED = """module app::authority_checked_sir_repeated;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    configure_pci();
    return;
}
"""


LEGACY = """module app::authority_checked_sir_legacy;
@system
fn raw_hardware() -> void { return; }
@system
fn boot() -> void {
    raw_hardware();
    return;
}
"""


class SotlasAuthorityCheckedSIRTests(unittest.TestCase):
    def test_strict_builder_lowers_named_authority_call_and_certifies_it(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-checked-sir>",
        )
        result = canonical_sir.build_canonical_checked_authority_sir(checked)
        sir = canonical_sir.load_canonical_sir()
        boot = next(
            item for item in result.module.functions if item.name == "boot"
        )
        calls = [
            item
            for block in boot.blocks
            for item in block.instructions
            if isinstance(item, sir.CallInst)
        ]

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].callee, "configure_pci")
        self.assertFalse(calls[0].is_system)
        self.assertEqual(
            result.authority_certificate.function("boot").capabilities,
            ("pci.config",),
        )
        groups = result.authority_certificate.calls_from("boot")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].callee, "configure_pci")
        self.assertEqual(groups[0].sir_call_count, 1)
        self.assertEqual(len(groups[0].source_point_ids), 1)
        self.assertTrue(result.authority_safety.success)

    def test_repeated_named_authority_calls_survive_into_sir_by_count(self):
        checked = package.analyze_source_phase1(
            REPEATED,
            filename="<authority-checked-sir-repeated>",
        )
        result = canonical_sir.build_canonical_checked_authority_sir(checked)
        sir = canonical_sir.load_canonical_sir()
        boot = next(
            item for item in result.module.functions if item.name == "boot"
        )
        calls = [
            item
            for block in boot.blocks
            for item in block.instructions
            if isinstance(item, sir.CallInst)
        ]
        group = result.authority_certificate.calls_from("boot")[0]

        self.assertEqual(len(calls), 2)
        self.assertEqual([item.callee for item in calls], [
            "configure_pci",
            "configure_pci",
        ])
        self.assertEqual(group.sir_call_count, 2)
        self.assertEqual(len(group.source_point_ids), 2)
        self.assertEqual(len(set(group.source_point_ids)), 2)
        self.assertTrue(result.authority_safety.success)

    def test_legacy_authority_call_preserves_old_system_marker(self):
        checked = package.analyze_source_phase1(
            LEGACY,
            filename="<authority-checked-sir-legacy>",
        )
        result = canonical_sir.build_canonical_checked_authority_sir(checked)
        sir = canonical_sir.load_canonical_sir()
        boot = next(
            item for item in result.module.functions if item.name == "boot"
        )
        call = next(
            item
            for block in boot.blocks
            for item in block.instructions
            if isinstance(item, sir.CallInst)
        )

        self.assertTrue(boot.is_system)
        self.assertTrue(call.is_system)
        self.assertTrue(
            result.authority_certificate.function("boot").legacy_unrestricted
        )
        self.assertTrue(
            result.authority_certificate.calls_from("boot")[0]
            .requires_legacy_unrestricted
        )
        self.assertTrue(result.authority_safety.success)

    def test_ownership_only_builder_keeps_compatibility_shape(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-ownership-compat>",
        )
        ownership, plan = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertIsNotNone(ownership.module)
        self.assertIsNotNone(plan)


if __name__ == "__main__":
    unittest.main()
