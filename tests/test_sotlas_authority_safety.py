"""Safety enforcement for certified Authority Domains at SIR level."""
from __future__ import annotations

from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_authority_safety_package"
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
authority_safety = importlib.import_module(f"{package.__name__}.authority_safety")
canonical_sir = importlib.import_module(f"{package.__name__}.canonical_sir")


MATCHING = """module app::authority_safety;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


def _module(*, calls: int = 1):
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("authority_safety")

    target = sir.SIRFunction("configure_pci", [], "void", is_system=False)
    target.add_block("0").add(sir.ReturnInst())
    module.add_function(target)

    boot = sir.SIRFunction("boot", [], "void", is_system=False)
    block = boot.add_block("0")
    for _ in range(calls):
        block.add(sir.CallInst("configure_pci", []))
    block.add(sir.ReturnInst())
    module.add_function(boot)
    return sir, module


def _certificate(module):
    checked = package.analyze_source_phase1(
        MATCHING,
        filename="<authority-safety>",
    )
    return authority_sir.certify_authority_sir(
        checked.authority,
        module,
    )


class SotlasAuthoritySafetyTests(unittest.TestCase):
    def test_named_capability_passes_without_legacy_system_boolean(self):
        _, module = _module()
        certificate = _certificate(module)
        self.assertFalse(certificate.function("boot").sir_is_system)

        result = authority_safety.enforce_authority_sir_safety(
            certificate,
            module,
        )

        self.assertTrue(result.success, result.errors)

    def test_tampered_caller_capability_is_rejected(self):
        _, module = _module()
        certificate = _certificate(module)
        functions = tuple(
            replace(fact, capabilities=("io.port",))
            if fact.function == "boot" else fact
            for fact in certificate.functions
        )
        tampered = replace(certificate, functions=functions)

        result = authority_safety.enforce_authority_sir_safety(
            tampered,
            module,
        )

        self.assertFalse(result.success)
        self.assertTrue(any(
            "missing capabilities: pci.config" in error
            for error in result.errors
        ))

    def test_stale_certificate_rejects_extra_lowered_call(self):
        sir, module = _module()
        certificate = _certificate(module)
        boot = next(item for item in module.functions if item.name == "boot")
        boot.blocks[0].instructions.insert(
            -1,
            sir.CallInst("configure_pci", []),
        )

        result = authority_safety.enforce_authority_sir_safety(
            certificate,
            module,
        )

        self.assertFalse(result.success)
        self.assertTrue(any(
            "expects 1 calls, got 2" in error
            for error in result.errors
        ))

    def test_system_call_without_source_edge_is_rejected(self):
        sir, module = _module()
        certificate = _certificate(module)
        helper = sir.SIRFunction("helper", [], "void", is_system=False)
        helper_block = helper.add_block("0")
        helper_block.add(sir.CallInst("configure_pci", []))
        helper_block.add(sir.ReturnInst())
        module.add_function(helper)

        result = authority_safety.enforce_authority_sir_safety(
            certificate,
            module,
        )

        self.assertFalse(result.success)
        self.assertTrue(any(
            "no certified source authority edge" in error
            for error in result.errors
        ))

    def test_external_system_call_remains_legacy_fail_closed(self):
        sir, module = _module()
        certificate = _certificate(module)
        boot = next(item for item in module.functions if item.name == "boot")
        boot.blocks[0].instructions.insert(
            -1,
            sir.CallInst("__raw_io", [], is_system=True),
        )

        result = authority_safety.enforce_authority_sir_safety(
            certificate,
            module,
        )

        self.assertFalse(result.success)
        self.assertTrue(any(
            "em função não-privilegiada 'boot'" in error
            for error in result.errors
        ))

    def test_require_success_raises_phase3_safety_error(self):
        sir, module = _module()
        certificate = _certificate(module)
        boot = next(item for item in module.functions if item.name == "boot")
        boot.blocks[0].instructions.insert(
            -1,
            sir.CallInst("configure_pci", []),
        )
        result = authority_safety.enforce_authority_sir_safety(
            certificate,
            module,
        )

        with self.assertRaises(authority_safety.AuthoritySIRSafetyError):
            result.require_success()


if __name__ == "__main__":
    unittest.main()
