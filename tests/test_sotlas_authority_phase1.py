"""Checked Phase-1 integration for encapsulated Authority Domains."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_phase1_package"
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
authority = importlib.import_module(f"{package.__name__}.authority")


MATCHING = """module app::authority_phase1_matching;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


SAFE_WRAPPER = """module app::authority_phase1_safe_wrapper;
@system(pci.config)
fn configure_pci() -> void { return; }
fn application() -> void {
    configure_pci();
    return;
}
"""


CROSS = """module app::authority_phase1_cross;
@system(io.port)
fn keyboard_write() -> void { return; }
@system(pci.config)
fn configure_pci() -> void {
    keyboard_write();
    return;
}
"""


LEGACY = """module app::authority_phase1_legacy;
@system(io.port)
fn keyboard_write() -> void { return; }
@system
fn legacy_boot() -> void {
    keyboard_write();
    return;
}
"""


class SotlasAuthorityPhase1Tests(unittest.TestCase):
    def test_checked_module_carries_mandatory_authority_certificate(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-phase1-matching>",
        )
        self.assertIsInstance(checked.authority, authority.AuthorityDomainPlan)
        self.assertEqual(
            checked.authority.contract("boot").capabilities,
            ("pci.config",),
        )
        self.assertEqual(len(checked.authority.calls_from("boot")), 1)

    def test_checked_pipeline_preserves_safe_wrapper_boundary(self):
        checked = package.analyze_source_phase1(
            SAFE_WRAPPER,
            filename="<authority-phase1-safe-wrapper>",
        )
        self.assertFalse(checked.authority.contract("application").is_system)
        edge = checked.authority.calls_from("application")[0]
        self.assertEqual(edge.callee, "configure_pci")
        self.assertEqual(edge.required_capabilities, ("pci.config",))
        self.assertEqual(edge.target_kind, "source")

    def test_checked_pipeline_allows_cross_capability_source_abstraction(self):
        checked = package.analyze_source_phase1(
            CROSS,
            filename="<authority-phase1-cross>",
        )
        edge = checked.authority.calls_from("configure_pci")[0]
        self.assertEqual(edge.callee, "keyboard_write")
        self.assertEqual(edge.required_capabilities, ("io.port",))
        self.assertEqual(edge.target_kind, "source")

    def test_checked_pipeline_preserves_bare_system_compatibility(self):
        checked = package.analyze_source_phase1(
            LEGACY,
            filename="<authority-phase1-legacy>",
        )
        self.assertTrue(
            checked.authority.contract("legacy_boot").legacy_unrestricted
        )
        self.assertEqual(len(checked.authority.calls_from("legacy_boot")), 1)


if __name__ == "__main__":
    unittest.main()
