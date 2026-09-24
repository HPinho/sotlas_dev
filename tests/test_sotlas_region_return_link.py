"""REGION callee-return to caller-owner certification."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_return_link_package"
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
region_call = importlib.import_module(f"{package.__name__}.region_call")
region_call_sir = importlib.import_module(f"{package.__name__}.region_call_sir")
region_boundary = importlib.import_module(f"{package.__name__}.region_boundary_link")
region_interprocedural = importlib.import_module(
    f"{package.__name__}.region_interprocedural"
)
region_return_link = importlib.import_module(f"{package.__name__}.region_return_link")


SOURCE = """module app::region_return_link;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn run(token: region Token) -> void {
    let out: region Token = pass(move token);
    return;
}
"""


class SotlasRegionReturnLinkTests(unittest.TestCase):
    def _checked(self):
        return package.analyze_source_phase1(
            SOURCE,
            filename="<region-return-link>",
        )

    def test_links_callee_region_return_to_caller_owner(self):
        checked = self._checked()
        plan = region_return_link.plan_checked_region_return_links(checked)
        self.assertEqual(len(plan.links), 1)
        link = plan.links[0]
        self.assertEqual(link.caller, "run")
        self.assertTrue(link.point_id.startswith("call@"))
        self.assertEqual(link.callee, "pass")
        self.assertEqual(link.destination, "out")
        self.assertEqual(link.type.name, "Token")
        self.assertEqual(link.callee_return_bindings, ("token",))
        self.assertEqual(plan.at_call("run", link.point_id), link)
        self.assertEqual(plan.destination("run", "out"), link)

    def test_rejects_sir_result_destination_drift(self):
        checked = self._checked()
        interprocedural = region_interprocedural.plan_checked_region_interprocedural(
            checked
        )
        boundaries = region_boundary.plan_checked_region_boundary_links(checked)
        call_plan = region_call.plan_checked_region_calls(checked)
        checked_sir, _ = canonical.build_canonical_checked_ownership_sir(checked)
        bridge = region_call_sir.validate_region_call_sir(call_plan, checked_sir)
        sir = canonical.load_canonical_sir()

        run = next(item for item in checked_sir.module.functions if item.name == "run")
        call = next(
            instruction
            for block in run.blocks
            for instruction in block.instructions
            if isinstance(instruction, sir.CallInst) and instruction.callee == "pass"
        )
        call.result = sir.SIRValue("wrong", "Token")

        with self.assertRaisesRegex(
            region_return_link.RegionReturnLinkError,
            "result diverged from caller owner",
        ):
            region_return_link.build_region_return_link_plan(
                checked.parsed_module,
                interprocedural,
                boundaries,
                bridge,
                checked_sir,
            )


if __name__ == "__main__":
    unittest.main()
