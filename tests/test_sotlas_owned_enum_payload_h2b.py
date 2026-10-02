"""M16.4h2b automatic canonical-SIR ownership attachment for enum payloads."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2b_compile"


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
aggregate = importlib.import_module(f"{_PACKAGE}.aggregate_ownership")
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")


_OWNERSHIP_SOURCE = """module test::owned_enum_payload_h2b;
sole struct Token {
    value: u32;
}
enum MaybeToken {
    None = 0,
    Some(Token),
}
fn noop() -> void { return; }
"""

_AUTHORITY_SOURCE = """module test::owned_enum_payload_h2b_authority;
sole struct Token {
    value: u32;
}
enum MaybeToken {
    None = 0,
    Some(Token),
}
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""

_SCALAR_SOURCE = """module test::owned_enum_payload_h2b_scalar;
enum MaybeCount {
    None = 0,
    Some(u32),
}
fn noop() -> void { return; }
"""


def _enum_signatures(module):
    return tuple(
        (
            fact.enum_name,
            fact.variant,
            fact.payload_type,
            fact.domain,
            fact.storage,
        )
        for fact in module.aggregate_ownership_facts
        if isinstance(fact, aggregate.EnumPayloadOwnershipFact)
    )


class SotlasOwnedEnumPayloadH2BTests(unittest.TestCase):
    def test_ownership_builder_attaches_enum_payload_ownership_automatically(self):
        checked = package.analyze_source_phase1(
            _OWNERSHIP_SOURCE,
            filename="<owned-enum-payload-h2b>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(
            _enum_signatures(checked_sir.module),
            (("MaybeToken", "Some", "Token", "exclusive", "by_value"),),
        )

    def test_authority_builder_preserves_same_enum_payload_ownership(self):
        checked = package.analyze_source_phase1(
            _AUTHORITY_SOURCE,
            filename="<owned-enum-payload-h2b-authority>",
        )
        ownership_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        authority_sir = canonical_sir.build_canonical_checked_authority_sir(
            checked
        )

        expected = (("MaybeToken", "Some", "Token", "exclusive", "by_value"),)
        self.assertEqual(_enum_signatures(ownership_sir.module), expected)
        self.assertEqual(_enum_signatures(authority_sir.module), expected)
        self.assertTrue(authority_sir.authority_safety.success)

    def test_scalar_enum_payload_does_not_create_ownership_fact(self):
        checked = package.analyze_source_phase1(
            _SCALAR_SOURCE,
            filename="<owned-enum-payload-h2b-scalar>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(_enum_signatures(checked_sir.module), ())

    def test_automatic_enum_payload_fact_remains_target_ir_fail_closed(self):
        checked = package.analyze_source_phase1(
            _OWNERSHIP_SOURCE,
            filename="<owned-enum-payload-h2b-target-ir>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(len(_enum_signatures(checked_sir.module)), 1)
        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "owned enum payload Target IR projection waits for M16.4h2c",
        ):
            target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)

    def test_compiler_and_tools_h2b_layers_remain_identical(self):
        for relative in (
            Path("sotlas_compile") / "aggregate_ownership.py",
            Path("sotlas_compile") / "canonical_sir.py",
        ):
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
