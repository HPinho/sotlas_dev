"""M16.4h2c2a automatic canonical-SIR nominal enum payload attachment."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2c2a_compile"


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
nominal = importlib.import_module(f"{_PACKAGE}.enum_nominal_payloads")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")


_OWNERSHIP_SOURCE = """module test::owned_enum_payload_h2c2a;
sole struct Token {
    value: u32;
}
enum MaybeToken {
    None = 0,
    Some(Token),
}
fn noop() -> void { return; }
"""

_AUTHORITY_SOURCE = """module test::owned_enum_payload_h2c2a_authority;
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

_SCALAR_SOURCE = """module test::owned_enum_payload_h2c2a_scalar;
enum MaybeCount {
    None = 0,
    Some(u32),
}
fn noop() -> void { return; }
"""


def _signatures(module):
    return tuple(
        (
            fact.enum_name,
            fact.tag_type,
            fact.storage,
            tuple(
                (
                    variant.name,
                    variant.discriminant,
                    variant.payload_type,
                    variant.payload_representation,
                )
                for variant in fact.variants
            ),
        )
        for fact in tuple(getattr(module, "nominal_enum_payload_facts", ()) or ())
    )


class SotlasOwnedEnumPayloadH2C2ATests(unittest.TestCase):
    def test_ownership_builder_attaches_nominal_payload_facts_automatically(self):
        checked = package.analyze_source_phase1(
            _OWNERSHIP_SOURCE,
            filename="<owned-enum-payload-h2c2a>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(
            _signatures(checked_sir.module),
            (
                (
                    "MaybeToken",
                    "u32",
                    "tagged_union",
                    (
                        ("None", 0, None, None),
                        ("Some", 1, "Token", "nominal_struct"),
                    ),
                ),
            ),
        )

    def test_authority_builder_preserves_same_nominal_payload_facts(self):
        checked = package.analyze_source_phase1(
            _AUTHORITY_SOURCE,
            filename="<owned-enum-payload-h2c2a-authority>",
        )
        ownership_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        authority_sir = canonical_sir.build_canonical_checked_authority_sir(
            checked
        )

        self.assertEqual(
            _signatures(authority_sir.module),
            _signatures(ownership_sir.module),
        )
        self.assertTrue(authority_sir.authority_safety.success)

    def test_scalar_only_payload_does_not_create_nominal_payload_facts(self):
        checked = package.analyze_source_phase1(
            _SCALAR_SOURCE,
            filename="<owned-enum-payload-h2c2a-scalar>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(_signatures(checked_sir.module), ())

    def test_explicit_bridge_is_idempotent_after_automatic_attachment(self):
        checked = package.analyze_source_phase1(
            _OWNERSHIP_SOURCE,
            filename="<owned-enum-payload-h2c2a-idempotent>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        before = tuple(checked_sir.module.nominal_enum_payload_facts)

        returned = nominal.attach_checked_nominal_enum_payloads(
            checked.semantic,
            checked_sir.module,
        )

        self.assertEqual(returned, before)
        self.assertEqual(tuple(checked_sir.module.nominal_enum_payload_facts), before)

    def test_target_ir_boundary_remains_fail_closed_until_h2c2b(self):
        checked = package.analyze_source_phase1(
            _OWNERSHIP_SOURCE,
            filename="<owned-enum-payload-h2c2a-target-ir>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        self.assertEqual(len(_signatures(checked_sir.module)), 1)
        with self.assertRaises(aggregate.AggregateOwnershipError):
            target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)

    def test_compiler_and_tools_canonical_sir_remain_identical(self):
        relative = Path("sotlas_compile") / "canonical_sir.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
