"""Preserve REGION-returning let calls in canonical SIR."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_return_call_sir_package"
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
canonical = importlib.import_module(f"{package.__name__}.canonical_sir")
interprocedural = importlib.import_module(
    f"{package.__name__}.region_interprocedural"
)


SOURCE = """module app::region_return_call_sir;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn run(token: region Token) -> void {
    let out: region Token = pass(move token);
    return;
}
"""


class SotlasRegionReturnCallSIRTests(unittest.TestCase):
    def test_region_returning_let_call_survives_canonical_sir(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-return-call-sir>",
        )
        checked_sir, _ = canonical.build_canonical_checked_ownership_sir(checked)
        sir = canonical.load_canonical_sir()
        run = next(item for item in checked_sir.module.functions if item.name == "run")
        calls = [
            instruction
            for block in run.blocks
            for instruction in block.instructions
            if isinstance(instruction, sir.CallInst)
        ]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call.callee, "pass")
        self.assertEqual([item.name for item in call.arguments], ["token"])
        self.assertIsNotNone(call.result)
        self.assertEqual(call.result.name, "out")
        self.assertEqual(call.result.type_name, "Token")

    def test_interprocedural_plan_keeps_return_destination_owner(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-return-call-lifetime>",
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)
        run = plan.function("run")
        self.assertEqual(run.local.bindings, ("token", "out"))
        self.assertEqual(len(run.calls), 1)
        self.assertEqual(run.calls[0].callee, "pass")
        self.assertEqual(run.calls[0].binding, "token")


if __name__ == "__main__":
    unittest.main()
