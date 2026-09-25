"""Authority Domains bridge into the currently representable SIR."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_sir_package"
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
authority_sir = importlib.import_module(f"{package.__name__}.authority_sir")
canonical_sir = importlib.import_module(f"{package.__name__}.canonical_sir")


MATCHING = """module app::authority_sir_matching;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


REPEATED = """module app::authority_sir_repeated;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    configure_pci();
    return;
}
"""


LEGACY = """module app::authority_sir_legacy;
@system
fn raw_hardware() -> void { return; }
@system
fn boot() -> void {
    raw_hardware();
    return;
}
"""


def _sir_module(*, calls: int, legacy: bool = False):
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("authority_sir")
    target_name = "raw_hardware" if legacy else "configure_pci"
    target = sir.SIRFunction(
        target_name,
        [],
        "void",
        is_system=legacy,
    )
    target.add_block("0").add(sir.ReturnInst())
    module.add_function(target)

    boot = sir.SIRFunction("boot", [], "void", is_system=legacy)
    block = boot.add_block("0")
    for _ in range(calls):
        block.add(sir.CallInst(target_name, []))
    block.add(sir.ReturnInst())
    module.add_function(boot)
    return module


class SotlasAuthoritySIRTests(unittest.TestCase):
    def test_named_capabilities_reach_sir_as_sidecar_facts_without_fake_call_ids(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-sir-matching>",
        )
        certificate = authority_sir.certify_authority_sir(
            checked.authority,
            _sir_module(calls=1),
        )
        boot = certificate.function("boot")
        self.assertEqual(boot.capabilities, ("pci.config",))
        self.assertFalse(boot.legacy_unrestricted)
        # Named authority is carried by the certificate even though the legacy
        # SIR boolean cannot represent a capability name.
        self.assertFalse(boot.sir_is_system)

        groups = certificate.calls_from("boot")
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group.callee, "configure_pci")
        self.assertEqual(group.required_capabilities, ("pci.config",))
        self.assertEqual(group.sir_call_count, 1)
        self.assertEqual(len(group.source_point_ids), 1)

    def test_repeated_calls_are_certified_by_group_count_not_list_order(self):
        checked = package.analyze_source_phase1(
            REPEATED,
            filename="<authority-sir-repeated>",
        )
        certificate = authority_sir.certify_authority_sir(
            checked.authority,
            _sir_module(calls=2),
        )
        group = certificate.calls_from("boot")[0]
        self.assertEqual(group.sir_call_count, 2)
        self.assertEqual(len(group.source_point_ids), 2)
        self.assertEqual(len(set(group.source_point_ids)), 2)

    def test_missing_represented_system_call_is_rejected(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-sir-missing>",
        )
        with self.assertRaisesRegex(
            authority_sir.AuthoritySIRError,
            "requires 1 represented calls, got 0",
        ):
            authority_sir.certify_authority_sir(
                checked.authority,
                _sir_module(calls=0),
            )

    def test_extra_lowered_system_call_without_source_edge_is_rejected(self):
        checked = package.analyze_source_phase1(
            MATCHING,
            filename="<authority-sir-extra>",
        )
        with self.assertRaisesRegex(
            authority_sir.AuthoritySIRError,
            "requires 1 represented calls, got 2",
        ):
            authority_sir.certify_authority_sir(
                checked.authority,
                _sir_module(calls=2),
            )

    def test_legacy_system_contract_requires_existing_sir_system_marker(self):
        checked = package.analyze_source_phase1(
            LEGACY,
            filename="<authority-sir-legacy>",
        )
        certificate = authority_sir.certify_authority_sir(
            checked.authority,
            _sir_module(calls=1, legacy=True),
        )
        self.assertTrue(certificate.function("boot").legacy_unrestricted)
        self.assertTrue(certificate.calls_from("boot")[0].requires_legacy_unrestricted)

    def test_legacy_system_marker_loss_is_rejected(self):
        checked = package.analyze_source_phase1(
            LEGACY,
            filename="<authority-sir-legacy-marker>",
        )
        module = _sir_module(calls=1, legacy=True)
        next(item for item in module.functions if item.name == "boot").is_system = False
        with self.assertRaisesRegex(
            authority_sir.AuthoritySIRError,
            "lost its SIR system marker",
        ):
            authority_sir.certify_authority_sir(checked.authority, module)


if __name__ == "__main__":
    unittest.main()
