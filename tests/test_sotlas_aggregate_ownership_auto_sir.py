"""M16.4h1b automatic canonical-SIR aggregate ownership attachment gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_aggregate_ownership_auto_compile"


def _load_package():
    package = sys.modules.get(_PACKAGE)
    if package is not None:
        return package
    spec = importlib.util.spec_from_file_location(
        _PACKAGE,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical sotlas_compile package")
    package = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE] = package
    spec.loader.exec_module(package)
    return package


package = _load_package()
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")


_OWNERSHIP_SOURCE = """module test::aggregate_ownership_auto;
sole struct Token { value: u32; }
struct Envelope {
    token: Token;
    count: u32;
}
fn noop() -> void { return; }
"""


_AUTHORITY_SOURCE = """module test::aggregate_ownership_authority;
sole struct Token { value: u32; }
struct Envelope {
    token: Token;
    count: u32;
}
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


def _fact_signature(module):
    return tuple(
        (
            fact.struct_name,
            fact.field_name,
            fact.field_type,
            fact.domain,
            fact.storage,
        )
        for fact in module.aggregate_ownership_facts
    )


class SotlasAutomaticAggregateOwnershipSIRTests(unittest.TestCase):
    def test_ownership_builder_attaches_checked_field_ownership_automatically(self):
        checked = package.analyze_source_phase1(
            _OWNERSHIP_SOURCE,
            filename="<aggregate-ownership-auto>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(
            _fact_signature(checked_sir.module),
            (("Envelope", "token", "Token", "exclusive", "by_value"),),
        )

    def test_authority_builder_preserves_same_aggregate_ownership_facts(self):
        checked = package.analyze_source_phase1(
            _AUTHORITY_SOURCE,
            filename="<aggregate-ownership-authority>",
        )
        ownership_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        authority_sir = canonical_sir.build_canonical_checked_authority_sir(
            checked
        )

        self.assertEqual(
            _fact_signature(authority_sir.module),
            _fact_signature(ownership_sir.module),
        )
        self.assertEqual(
            _fact_signature(authority_sir.module),
            (("Envelope", "token", "Token", "exclusive", "by_value"),),
        )
        self.assertTrue(authority_sir.authority_safety.success)

    def test_non_ownership_module_gets_explicit_empty_sidecar(self):
        checked = package.analyze_source_phase1(
            "module test::aggregate_no_owner;\n"
            "struct Plain { value: u32; }\n"
            "fn noop() -> void { return; }\n"
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertTrue(
            hasattr(checked_sir.module, "aggregate_ownership_facts")
        )
        self.assertEqual(
            tuple(checked_sir.module.aggregate_ownership_facts),
            (),
        )

    def test_compiler_and_tools_canonical_sir_remain_identical(self):
        relative = Path("sotlas_compile") / "canonical_sir.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
