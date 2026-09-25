"""Closed REGION interprocedural ownership-graph certification."""
import importlib
import importlib.util
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_closed_interprocedural_package"
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
closed = importlib.import_module(
    f"{package.__name__}.region_closed_interprocedural"
)
interprocedural = importlib.import_module(
    f"{package.__name__}.region_interprocedural"
)
boundary = importlib.import_module(f"{package.__name__}.region_boundary_link")
return_link = importlib.import_module(f"{package.__name__}.region_return_link")


SOURCE = """module app::region_closed_interprocedural;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn run(token: region Token) -> void {
    let out: region Token = pass(move token);
    return;
}
"""


class SotlasRegionClosedInterproceduralTests(unittest.TestCase):
    def _checked(self):
        return package.analyze_source_phase1(
            SOURCE,
            filename="<region-closed-interprocedural>",
        )

    def test_composes_closed_caller_callee_return_topology(self):
        plan = closed.plan_checked_region_closed_interprocedural(self._checked())
        self.assertEqual(plan.function("run").local.bindings, ("token", "out"))
        links = plan.returns_from("run")
        self.assertEqual(len(links), 1)
        link = links[0]
        self.assertEqual(link.callee, "pass")
        self.assertEqual(link.destination, "out")
        self.assertEqual(link.callee_return_bindings, ("token",))
        self.assertEqual(plan.return_at_call("run", link.point_id), link)

    def test_rejects_return_link_callee_drift(self):
        checked = self._checked()
        lifetime = interprocedural.plan_checked_region_interprocedural(checked)
        boundaries = boundary.plan_checked_region_boundary_links(checked)
        returns = return_link.plan_checked_region_return_links(checked)
        bad = return_link.RegionReturnLinkPlan(
            (replace(returns.links[0], callee="run"),)
        )
        with self.assertRaisesRegex(
            closed.RegionClosedInterproceduralError,
            "callee diverged from call CFG",
        ):
            closed.build_region_closed_interprocedural_plan(
                lifetime,
                boundaries,
                bad,
            )


if __name__ == "__main__":
    unittest.main()
