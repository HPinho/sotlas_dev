"""M16.4h1a backend-neutral ownership-bearing struct field gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_aggregate_ownership_compile"


def _load_compiler_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


sotlas_compile = _load_compiler_package()
_aggregate = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.aggregate_ownership"
)
_canonical_sir = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.canonical_sir"
)


_SOURCE = """module test::aggregate_ownership;
sole struct Token { value: u32; }
struct Envelope {
    token: Token;
    count: u32;
}
fn noop() -> void { return; }
"""


class SotlasAggregateOwnershipFieldTests(unittest.TestCase):
    def test_checked_typed_ast_identifies_only_direct_sole_field_owner(self):
        checked = sotlas_compile.analyze_source_phase1(
            _SOURCE, filename="<aggregate-ownership>"
        )

        facts = _aggregate.collect_struct_field_ownership_facts(
            checked.semantic.typed_module
        )

        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual(fact.struct_name, "Envelope")
        self.assertEqual(fact.field_name, "token")
        self.assertEqual(fact.field_type, "Token")
        self.assertEqual(fact.domain, "exclusive")
        self.assertEqual(fact.storage, "by_value")

    def test_explicit_bridge_attaches_facts_to_real_canonical_sir(self):
        checked = sotlas_compile.analyze_source_phase1(
            _SOURCE, filename="<aggregate-ownership-sir>"
        )
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )

        facts = _aggregate.attach_checked_struct_field_ownership(
            checked.semantic, checked_sir.module
        )

        self.assertEqual(
            tuple(checked_sir.module.aggregate_ownership_facts),
            facts,
        )
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].field_name, "token")

    def test_conflicting_existing_sir_sidecar_fails_closed(self):
        checked = sotlas_compile.analyze_source_phase1(_SOURCE)
        sir_module = SimpleNamespace(
            aggregate_ownership_facts=("contradictory",)
        )
        with self.assertRaisesRegex(
            _aggregate.AggregateOwnershipError,
            "conflicting aggregate ownership facts",
        ):
            _aggregate.attach_checked_struct_field_ownership(
                checked.semantic, sir_module
            )

    def test_missing_checked_typed_module_fails_closed(self):
        with self.assertRaisesRegex(
            _aggregate.AggregateOwnershipError,
            "requires a checked TypedModule",
        ):
            _aggregate.collect_struct_field_ownership_facts(None)

    def test_compiler_and_tools_aggregate_ownership_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "aggregate_ownership.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
