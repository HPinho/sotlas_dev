"""REGION call transfers need source-stable call-site and parameter identity."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_call_lifetime_package"
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
region_call = importlib.import_module(f"{package.__name__}.region_call")


MULTI_PARAM_SOURCE = """module app::region_call_multi_param;
sole struct Token { value: u32; }
fn consume(left: region Token, right: region Token) -> void { return; }
fn run(left: region Token, right: region Token) -> void {
    consume(move left, move right);
    return;
}
"""

REPEATED_CALLEE_SOURCE = """module app::region_call_repeat;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionCallLifetimeTests(unittest.TestCase):
    def test_same_call_site_is_disambiguated_by_parameter_and_argument_index(self):
        checked = package.analyze_source_phase1(
            MULTI_PARAM_SOURCE, filename="<region-call-multi-param>"
        )
        plan = region_call.plan_checked_region_calls(checked)
        self.assertEqual(len(plan.transfers), 2)
        self.assertEqual(
            tuple((item.binding, item.parameter, item.argument_index) for item in plan.transfers),
            (("left", "left", 0), ("right", "right", 1)),
        )
        self.assertEqual(plan.transfers[0].point_id, plan.transfers[1].point_id)
        self.assertTrue(plan.transfers[0].point_id.startswith("call@"))
        self.assertEqual(len({item.identity for item in plan.transfers}), 2)

    def test_repeated_calls_to_same_callee_have_distinct_source_points(self):
        checked = package.analyze_source_phase1(
            REPEATED_CALLEE_SOURCE, filename="<region-call-repeat>"
        )
        plan = region_call.plan_checked_region_calls(checked)
        self.assertEqual(tuple(item.binding for item in plan.transfers), ("first", "second"))
        self.assertEqual(tuple(item.parameter for item in plan.transfers), ("token", "token"))
        self.assertEqual(len({item.point_id for item in plan.transfers}), 2)

    def test_tampered_graph_callee_is_rejected(self):
        checked = package.analyze_source_phase1(
            REPEATED_CALLEE_SOURCE, filename="<region-call-tampered-callee>"
        )
        graph = checked.semantic.ownership_domains
        index = next(
            i for i, item in enumerate(graph.transfers)
            if item.binding == "first" and item.via == "call:consume"
        )
        transfers = list(graph.transfers)
        transfers[index] = replace(transfers[index], via="call:other")
        tampered = replace(graph, transfers=tuple(transfers))
        with self.assertRaisesRegex(
            region_call.RegionCallLifetimeError,
            "requires exactly one canonical graph transfer|no source-stable call-site",
        ):
            region_call.build_region_call_lifetime_plan(
                checked.semantic.ownership,
                tampered,
                checked.semantic.typed_module,
                checked.parsed_module,
            )

    def test_duplicate_graph_transfer_is_rejected(self):
        checked = package.analyze_source_phase1(
            REPEATED_CALLEE_SOURCE, filename="<region-call-duplicate>"
        )
        graph = checked.semantic.ownership_domains
        duplicate = next(
            item for item in graph.transfers
            if item.binding == "first" and item.via == "call:consume"
        )
        tampered = replace(graph, transfers=graph.transfers + (duplicate,))
        with self.assertRaisesRegex(
            region_call.RegionCallLifetimeError,
            "exactly one canonical graph transfer",
        ):
            region_call.build_region_call_lifetime_plan(
                checked.semantic.ownership,
                tampered,
                checked.semantic.typed_module,
                checked.parsed_module,
            )

    def test_non_checked_module_is_rejected(self):
        with self.assertRaisesRegex(
            region_call.RegionCallLifetimeError,
            "Phase1CheckedModule",
        ):
            region_call.plan_checked_region_calls(object())


if __name__ == "__main__":
    unittest.main()
