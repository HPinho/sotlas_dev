"""M16.4h2a backend-neutral ownership facts for direct enum payloads."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2a_compile"


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


_SOURCE = """module test::owned_enum_payload_h2a;
sole struct Token {
    value: u32;
}
struct Envelope {
    token: Token;
    count: u32;
}
enum MaybeToken {
    None = 0,
    Some(Token),
}
enum MaybeCount {
    None = 0,
    Some(u32),
}
fn noop() -> void { return; }
"""


class SotlasOwnedEnumPayloadH2ATests(unittest.TestCase):
    def _checked(self):
        return package.analyze_source_phase1(
            _SOURCE,
            filename="<owned-enum-payload-h2a>",
        )

    def test_checked_typed_ast_identifies_direct_sole_enum_payload(self):
        checked = self._checked()
        facts = aggregate.collect_enum_payload_ownership_facts(
            checked.semantic.typed_module
        )

        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertIsInstance(fact, aggregate.EnumPayloadOwnershipFact)
        self.assertEqual(fact.enum_name, "MaybeToken")
        self.assertEqual(fact.variant, "Some")
        self.assertEqual(fact.payload_type, "Token")
        self.assertEqual(fact.domain, "exclusive")
        self.assertEqual(fact.storage, "by_value")

    def test_scalar_enum_payload_is_not_promoted_to_ownership(self):
        checked = self._checked()
        facts = aggregate.collect_enum_payload_ownership_facts(
            checked.semantic.typed_module
        )
        self.assertNotIn("MaybeCount", {fact.enum_name for fact in facts})

    def test_explicit_h2a_bridge_is_idempotent_after_h2b_auto_attachment(self):
        checked = self._checked()
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        module = checked_sir.module

        combined = tuple(module.aggregate_ownership_facts)
        self.assertEqual(len(combined), 2)
        self.assertIsInstance(combined[0], aggregate.StructFieldOwnershipFact)
        self.assertEqual(combined[0].struct_name, "Envelope")
        self.assertEqual(combined[0].field_name, "token")
        self.assertIsInstance(combined[1], aggregate.EnumPayloadOwnershipFact)
        self.assertEqual(combined[1].enum_name, "MaybeToken")
        self.assertEqual(combined[1].variant, "Some")

        enum_facts = aggregate.attach_checked_enum_payload_ownership(
            checked.semantic,
            module,
        )
        self.assertEqual(len(enum_facts), 1)
        self.assertEqual(enum_facts[0], combined[1])
        self.assertEqual(tuple(module.aggregate_ownership_facts), combined)

    def test_owned_enum_payload_reaches_target_ir_with_h2d_projection(self):
        checked = self._checked()
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)
        declaration = target_ir["nominal_enum_payloads"]["MaybeToken"]
        some = next(item for item in declaration["variants"] if item["name"] == "Some")
        self.assertEqual(some["payload_type"], "Token")
        self.assertEqual(some["payload_representation"], "nominal_struct")
        projected = tuple(target_ir.get("aggregate_ownership_facts", ()) or ())
        self.assertTrue(any(
            item.get("kind") == "enum_payload"
            and item.get("enum") == "MaybeToken"
            and item.get("variant") == "Some"
            and item.get("payload_type") == "Token"
            and item.get("domain") == "exclusive"
            and item.get("storage") == "by_value"
            for item in projected
        ))

    def test_missing_checked_typed_module_fails_closed(self):
        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "requires a checked TypedModule",
        ):
            aggregate.collect_enum_payload_ownership_facts(None)

    def test_compiler_and_tools_aggregate_ownership_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "aggregate_ownership.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
