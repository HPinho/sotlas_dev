"""Compose local, call and return REGION lifetime proofs."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_interprocedural_lifetime_package"
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


SOURCE = """module app::region_interprocedural;
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


class SotlasRegionInterproceduralLifetimeTests(unittest.TestCase):
    def test_checked_module_composes_local_calls_and_returns(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-interprocedural>"
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)

        run = plan.function("run")
        self.assertEqual(run.local.function, "run")
        self.assertEqual(tuple(item.binding for item in run.calls), ("first", "second"))
        self.assertEqual(len({item.point_id for item in run.calls}), 2)
        self.assertEqual(
            tuple((item.callee, item.parameter) for item in run.calls),
            (("consume", "token"), ("consume", "token")),
        )
        self.assertEqual(
            sorted((item.source, item.via) for item in run.local.transfers),
            [("first", "call:consume"), ("second", "call:consume")],
        )

        passed = plan.function("pass")
        self.assertEqual(
            tuple((item.source, item.via) for item in passed.local.transfers),
            (("token", "return"),),
        )
        self.assertEqual(
            tuple((item.function, item.binding) for item in plan.returns.transfers),
            (("pass", "token"),),
        )

    def test_region_parameter_function_without_transfer_remains_present(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-interprocedural-callee>"
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)
        consume = plan.function("consume")
        self.assertEqual(consume.local.bindings, ("token",))
        self.assertEqual(consume.local.transfers, ())
        self.assertEqual(consume.calls, ())

    def test_non_checked_module_is_rejected(self):
        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "Phase1CheckedModule",
        ):
            interprocedural.plan_checked_region_interprocedural(object())


if __name__ == "__main__":
    unittest.main()
