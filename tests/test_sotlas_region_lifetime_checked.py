"""Integration from real Phase-1 source to REGION lifetime topology."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_lifetime_checked_package"
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
frontend = importlib.import_module(f"{package.__name__}.region_frontend")


SOURCE = """module app::region_lifetime_checked;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run() -> u32 {
    let source: region Token = Token { value: 41u32 };
    let destination: region Token = Token { value: 9u32 };
    consume(move destination);
    handover source to destination;
    return destination.value;
}
"""


class SotlasRegionLifetimeCheckedTests(unittest.TestCase):
    def test_real_source_drives_region_lifetime_plan_without_rebuilding_graph(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-lifetime-checked>",
        )
        plan = frontend.plan_checked_region_lifetime(
            checked,
            function="run",
        )

        self.assertEqual(plan.bindings, ("source", "destination"))
        handovers = tuple(item for item in plan.transfers if item.via == "handover")
        self.assertEqual(len(handovers), 1)
        self.assertEqual(handovers[0].source, "source")
        self.assertEqual(handovers[0].destination, "destination")
        self.assertFalse(handovers[0].terminal)
        self.assertTrue(handovers[0].point_id.startswith("handover@"))
        self.assertEqual(plan.borrows, ())

    def test_checked_bridge_reuses_exact_semantic_graph(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-lifetime-graph-identity>",
        )
        graph = checked.semantic.ownership_domains
        plan = frontend.plan_checked_region_lifetime(checked, function="run")

        graph_region_bindings = tuple(
            node.binding
            for node in graph.nodes
            if node.function == "run" and node.domain.value == "region"
        )
        self.assertEqual(plan.bindings, graph_region_bindings)

    def test_checked_bridge_rejects_non_checked_objects(self):
        with self.assertRaisesRegex(
            frontend.RegionFrontendPlanError,
            "Phase1CheckedModule semantic snapshot",
        ):
            frontend.plan_checked_region_lifetime(object(), function="run")


if __name__ == "__main__":
    unittest.main()
