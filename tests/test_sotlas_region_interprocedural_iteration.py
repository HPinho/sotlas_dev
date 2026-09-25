"""Intra-iteration REGION ordering is a mandatory interprocedural certificate."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_interprocedural_iteration_package"
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
interprocedural = importlib.import_module(
    f"{package.__name__}.region_interprocedural"
)
iteration_order = importlib.import_module(
    f"{package.__name__}.region_iteration_order"
)


SOURCE = """module app::region_interprocedural_iteration;
sole struct Token { value: u32; }
fn pass(token: region Token) -> region Token {
    return token;
}
fn consume(token: region Token) -> void { return; }
fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionInterproceduralIterationTests(unittest.TestCase):
    def test_each_region_function_carries_mandatory_iteration_certificate(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-interprocedural-iteration>",
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)

        for function_name in ("pass", "consume", "run"):
            function = plan.function(function_name)
            self.assertEqual(function.lifetime_cfg.function, function_name)
            self.assertEqual(function.iteration_order.function, function_name)
            self.assertIs(plan.iteration_order(function_name), function.iteration_order)

        run_order = plan.iteration_order("run")
        self.assertEqual(run_order.points, ())
        self.assertEqual(run_order.relations, ())

    def test_iteration_order_failure_is_not_optional_in_interprocedural_plan(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-interprocedural-iteration-fail-closed>",
        )

        with mock.patch.object(
            interprocedural,
            "certify_region_iteration_order",
            side_effect=iteration_order.RegionIterationOrderError(
                "sentinel iteration-order failure"
            ),
        ):
            with self.assertRaisesRegex(
                iteration_order.RegionIterationOrderError,
                "sentinel iteration-order failure",
            ):
                interprocedural.plan_checked_region_interprocedural(checked)


if __name__ == "__main__":
    unittest.main()
