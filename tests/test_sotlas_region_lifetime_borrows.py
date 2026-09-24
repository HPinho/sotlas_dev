"""Real-source coverage for REGION call-scoped lifetime edges."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_lifetime_borrow_package"
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


SOURCE = """module app::region_lifetime_borrows;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn observe(token: whisper Token) -> void { return; }
fn read_region(token: region Token) -> void {
    inspect(&token);
    observe(&token);
    return;
}
"""


class SotlasRegionLifetimeBorrowTests(unittest.TestCase):
    def test_direct_and_whisper_borrows_remain_call_scoped_region_edges(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-lifetime-borrows>",
        )
        plan = frontend.plan_checked_region_lifetime(
            checked,
            function="read_region",
        )

        self.assertEqual(plan.bindings, ("token",))
        self.assertEqual(plan.transfers, ())
        self.assertEqual(
            tuple((item.source, item.mode, item.callee, item.parameter, item.scope)
                  for item in plan.borrows),
            (
                ("token", "direct", "inspect", "token", "call"),
                ("token", "whisper", "observe", "token", "call"),
            ),
        )
        self.assertTrue(plan.borrows[0].point_id.startswith("direct@"))
        self.assertTrue(plan.borrows[1].point_id.startswith("whisper@"))
        self.assertEqual(len(set(plan.point_ids)), len(plan.point_ids))


if __name__ == "__main__":
    unittest.main()
