"""Phase 3 foundation: named Authority Domains and least-authority calls."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_domains_package"
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
bootstrap = importlib.import_module(f"{package.__name__}.bootstrap")
authority = importlib.import_module(f"{package.__name__}.authority")


MATCHING_CAPABILITY = """module app::authority_matching;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


MISSING_CAPABILITY = """module app::authority_missing;
@system(pci.config)
fn configure_pci() -> void { return; }
fn application() -> void {
    configure_pci();
    return;
}
"""


CROSS_CAPABILITY = """module app::authority_cross;
@system(io.port)
fn keyboard_write() -> void { return; }
@system(pci.config)
fn configure_pci() -> void {
    keyboard_write();
    return;
}
"""


LEGACY_UNRESTRICTED = """module app::authority_legacy;
@system(io.port)
fn keyboard_write() -> void { return; }
@system
fn legacy_boot() -> void {
    keyboard_write();
    return;
}
"""


RESTRICTED_TO_LEGACY = """module app::authority_restricted_legacy;
@system
fn raw_hardware() -> void { return; }
@system(pci.config)
fn configure_pci() -> void {
    raw_hardware();
    return;
}
"""


MULTI_CAPABILITY = """module app::authority_multi;
@system(pci.config, io.port)
fn privileged_boot() -> void { return; }
"""


INVALID_CAPABILITY = """module app::authority_invalid;
@system(pci..config)
fn configure_pci() -> void { return; }
"""


class SotlasAuthorityDomainsTests(unittest.TestCase):
    def _plan(self, source: str):
        parsed = bootstrap.parse(source, filename="<authority-domains>")
        return authority.plan_authority_domains(parsed)

    def test_matching_named_capability_certifies_direct_call(self):
        plan = self._plan(MATCHING_CAPABILITY)
        boot = plan.contract("boot")
        self.assertEqual(boot.capabilities, ("pci.config",))
        self.assertFalse(boot.legacy_unrestricted)
        self.assertEqual(len(plan.calls_from("boot")), 1)
        edge = plan.calls_from("boot")[0]
        self.assertEqual(edge.callee, "configure_pci")
        self.assertEqual(edge.required_capabilities, ("pci.config",))
        self.assertTrue(edge.point_id.startswith("call@"))

    def test_normal_function_cannot_call_named_system_capability(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "missing capabilities: pci.config",
        ):
            self._plan(MISSING_CAPABILITY)

    def test_one_named_capability_does_not_grant_another(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "missing capabilities: io.port",
        ):
            self._plan(CROSS_CAPABILITY)

    def test_bare_system_remains_legacy_unrestricted_for_compatibility(self):
        plan = self._plan(LEGACY_UNRESTRICTED)
        contract = plan.contract("legacy_boot")
        self.assertTrue(contract.legacy_unrestricted)
        self.assertTrue(contract.grants("io.port"))
        self.assertTrue(contract.grants("pci.config"))
        self.assertEqual(len(plan.calls_from("legacy_boot")), 1)

    def test_restricted_capability_cannot_escalate_into_legacy_unrestricted(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "requires legacy unrestricted @system authority",
        ):
            self._plan(RESTRICTED_TO_LEGACY)

    def test_multiple_capabilities_are_preserved_in_source_order(self):
        plan = self._plan(MULTI_CAPABILITY)
        self.assertEqual(
            plan.contract("privileged_boot").capabilities,
            ("pci.config", "io.port"),
        )

    def test_malformed_capability_is_rejected(self):
        with self.assertRaisesRegex(
            authority.AuthorityDomainError,
            "invalid authority capability",
        ):
            self._plan(INVALID_CAPABILITY)


if __name__ == "__main__":
    unittest.main()
