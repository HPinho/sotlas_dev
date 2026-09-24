"""Certify caller-to-callee REGION ownership boundary links."""
import importlib
import importlib.util
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_boundary_link_package"
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
links = importlib.import_module(f"{package.__name__}.region_boundary_link")
interprocedural = importlib.import_module(f"{package.__name__}.region_interprocedural")
boundaries = importlib.import_module(f"{package.__name__}.region_function_boundary")


SOURCE = """module app::region_boundary_link;
sole struct Token { value: u32; }

fn consume(token: region Token) -> void {
    return;
}

fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionBoundaryLinkTests(unittest.TestCase):
    def test_checked_module_links_caller_calls_to_callee_region_parameter(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-boundary-link>",
        )
        plan = links.plan_checked_region_boundary_links(checked)

        self.assertEqual(len(plan.links), 2)
        first, second = plan.links
        self.assertEqual(first.caller, "run")
        self.assertEqual(first.source_binding, "first")
        self.assertEqual(first.callee, "consume")
        self.assertEqual(first.parameter, "token")
        self.assertEqual(first.argument_index, 0)
        self.assertTrue(first.caller_is_root)
        self.assertFalse(first.caller_is_terminal)

        self.assertEqual(second.caller, "run")
        self.assertEqual(second.source_binding, "second")
        self.assertEqual(second.callee, "consume")
        self.assertEqual(second.parameter, "token")
        self.assertEqual(second.argument_index, 0)
        self.assertFalse(second.caller_is_root)
        self.assertTrue(second.caller_is_terminal)

        self.assertEqual(plan.outgoing("run", first.point_id), (first,))
        self.assertEqual(plan.outgoing("run", second.point_id), (second,))
        self.assertEqual(plan.incoming("consume", "token"), (first, second))

    def test_valid_uncalled_region_parameter_has_empty_incoming_links(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-boundary-link-empty-incoming>",
        )
        plan = links.plan_checked_region_boundary_links(checked)
        self.assertEqual(plan.incoming("run", "first"), ())

    def test_missing_callee_parameter_boundary_fails_closed(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-boundary-link-tampered>",
        )
        inter = interprocedural.plan_checked_region_interprocedural(checked)
        boundary_plan = boundaries.plan_checked_region_function_boundaries(checked)
        tampered = boundaries.RegionFunctionBoundaryPlan(
            tuple(
                replace(item, parameter_bindings=()) if item.function == "consume" else item
                for item in boundary_plan.boundaries
            )
        )
        with self.assertRaisesRegex(
            links.RegionBoundaryLinkError,
            "ownership-taking REGION parameter",
        ):
            links.build_region_boundary_link_plan(inter, tampered)

    def test_unknown_call_point_query_fails_closed(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-boundary-link-missing-point>",
        )
        plan = links.plan_checked_region_boundary_links(checked)
        with self.assertRaisesRegex(
            links.RegionBoundaryLinkError,
            "known call point",
        ):
            plan.outgoing("run", "call@999:999")


if __name__ == "__main__":
    unittest.main()
