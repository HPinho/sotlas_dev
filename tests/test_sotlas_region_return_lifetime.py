"""REGION return contracts must agree across Typed AST, summaries and graph."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_return_lifetime_package"
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
region_return = importlib.import_module(f"{package.__name__}.region_return")
typed_ast = importlib.import_module(f"{package.__name__}.typed_ast")


SOURCE = """module app::region_return_lifetime;
sole struct Token { value: u32; }
fn pass(token: region Token) -> region Token {
    return token;
}
"""


class SotlasRegionReturnLifetimeTests(unittest.TestCase):
    def _checked(self):
        return package.analyze_source_phase1(
            SOURCE,
            filename="<region-return-lifetime>",
        )

    def test_real_source_region_return_is_certified(self):
        checked = self._checked()
        plan = region_return.plan_checked_region_returns(checked)
        self.assertEqual(len(plan.contracts), 1)
        self.assertEqual(plan.contracts[0].function, "pass")
        self.assertEqual(plan.contracts[0].type.name, "Token")
        self.assertEqual(len(plan.transfers), 1)
        self.assertEqual(plan.transfers[0].function, "pass")
        self.assertEqual(plan.transfers[0].binding, "token")
        self.assertEqual(plan.transfers[0].type, plan.contracts[0].type)

    def test_tampered_region_return_domain_change_is_rejected(self):
        checked = self._checked()
        graph = checked.semantic.ownership_domains
        index = next(
            i for i, item in enumerate(graph.transfers)
            if item.function == "pass" and item.via == "return"
        )
        transfers = list(graph.transfers)
        transfers[index] = replace(
            transfers[index],
            target_domain=typed_ast.OwnershipDomain.EXCLUSIVE,
        )
        tampered = replace(graph, transfers=tuple(transfers))
        with self.assertRaisesRegex(
            region_return.RegionReturnLifetimeError,
            r"changes domain",
        ):
            region_return.build_region_return_lifetime_plan(
                checked.semantic.ownership,
                tampered,
                checked.semantic.typed_module,
            )


if __name__ == "__main__":
    unittest.main()
