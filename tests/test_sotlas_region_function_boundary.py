"""Certify per-function REGION ownership boundaries."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_function_boundary_package"
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
boundary = importlib.import_module(f"{package.__name__}.region_function_boundary")


SOURCE = """module app::region_function_boundary;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn consume(token: region Token) -> void {
    return;
}

fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionFunctionBoundaryTests(unittest.TestCase):
    def test_checked_module_certifies_function_boundaries(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-function-boundary>",
        )
        plan = boundary.plan_checked_region_function_boundaries(checked)

        passed = plan.function("pass")
        self.assertEqual(passed.parameter_bindings, ("token",))
        self.assertEqual(passed.call_root_point_ids, ())
        self.assertEqual(passed.call_terminal_point_ids, ())
        self.assertEqual(passed.return_bindings, ("token",))

        consume = plan.function("consume")
        self.assertEqual(consume.parameter_bindings, ("token",))
        self.assertEqual(consume.call_root_point_ids, ())
        self.assertEqual(consume.call_terminal_point_ids, ())
        self.assertEqual(consume.return_bindings, ())

        run = plan.function("run")
        self.assertEqual(run.parameter_bindings, ("first", "second"))
        self.assertEqual(len(run.call_root_point_ids), 1)
        self.assertEqual(len(run.call_terminal_point_ids), 1)
        self.assertNotEqual(
            run.call_root_point_ids[0],
            run.call_terminal_point_ids[0],
        )
        self.assertEqual(run.return_bindings, ())

    def test_unknown_function_fails_closed(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-function-boundary-missing>",
        )
        plan = boundary.plan_checked_region_function_boundaries(checked)
        with self.assertRaisesRegex(
            boundary.RegionFunctionBoundaryError,
            "exactly one function",
        ):
            plan.function("missing")

    def test_non_checked_module_is_rejected(self):
        with self.assertRaisesRegex(
            boundary.RegionFunctionBoundaryError,
            "Phase1CheckedModule",
        ):
            boundary.plan_checked_region_function_boundaries(object())


if __name__ == "__main__":
    unittest.main()
