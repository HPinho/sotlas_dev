"""REGION interprocedural call transfers must preserve canonical CFG facts."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_call_cfg_package"
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
canonical_sir = importlib.import_module(f"{package.__name__}.canonical_sir")
region_call = importlib.import_module(f"{package.__name__}.region_call")
region_call_sir = importlib.import_module(f"{package.__name__}.region_call_sir")
region_call_cfg = importlib.import_module(f"{package.__name__}.region_call_cfg")


SOURCE = """module app::region_call_cfg;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionCallCFGTests(unittest.TestCase):
    def test_checked_sequential_calls_form_ordered_path(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-call-cfg>"
        )
        calls = region_call.plan_checked_region_calls(checked)
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        bridge = region_call_sir.validate_region_call_sir(calls, checked_sir)
        certificate = region_call_cfg.certify_region_call_cfg(bridge, checked_sir)

        self.assertEqual(len(certificate.points), 2)
        self.assertTrue(all(item.iteration_id is None for item in certificate.points))
        self.assertEqual(len(certificate.relations), 1)
        relation = certificate.relations[0]
        self.assertEqual(relation.relation, "ordered_path")
        self.assertEqual(
            (relation.first_point_id, relation.second_point_id),
            (bridge.sites[0].point_id, bridge.sites[1].point_id),
        )

    def test_calls_on_opposite_branch_arms_are_path_disjoint(self):
        sir = canonical_sir.load_canonical_sir()
        module = sir.SIRModule("synthetic_branch")
        function = sir.SIRFunction("run", [], "void")
        module.add_function(function)
        entry = function.add_block("entry")
        left = function.add_block("left")
        right = function.add_block("right")
        entry.add(
            sir.CondBranchInst(
                sir.SIRValue("flag", "bool"),
                "left",
                "right",
            )
        )
        left.add(sir.CallInst("consume", [sir.SIRValue("left", "Token")]))
        left.add(sir.ReturnInst())
        right.add(sir.CallInst("consume", [sir.SIRValue("right", "Token")]))
        right.add(sir.ReturnInst())

        bridge = region_call_sir.RegionCallSIRBridge(
            (
                region_call_sir.RegionCallSIRSite(
                    "run", "left", "consume", "token", 0,
                    "call@10:5", "left", 0,
                ),
                region_call_sir.RegionCallSIRSite(
                    "run", "right", "consume", "token", 0,
                    "call@12:5", "right", 0,
                ),
            )
        )
        certificate = region_call_cfg.certify_region_call_cfg(bridge, module)
        self.assertEqual(len(certificate.relations), 1)
        self.assertEqual(certificate.relations[0].relation, "path_disjoint")

    def test_ownership_taking_call_inside_cycle_requires_iteration_identity(self):
        sir = canonical_sir.load_canonical_sir()
        module = sir.SIRModule("synthetic_loop")
        function = sir.SIRFunction("run", [], "void")
        module.add_function(function)
        entry = function.add_block("entry")
        loop = function.add_block("loop")
        entry.add(sir.BranchInst("loop"))
        loop.add(sir.CallInst("consume", [sir.SIRValue("token", "Token")]))
        loop.add(sir.BranchInst("loop"))

        bridge = region_call_sir.RegionCallSIRBridge(
            (
                region_call_sir.RegionCallSIRSite(
                    "run", "token", "consume", "token", 0,
                    "call@8:9", "loop", 0,
                ),
            )
        )
        with self.assertRaisesRegex(
            region_call_cfg.RegionCallCFGError,
            "requires iteration identity",
        ):
            region_call_cfg.certify_region_call_cfg(bridge, module)

    def test_ownership_taking_call_uses_canonical_backedge_iteration_identity(self):
        sir = canonical_sir.load_canonical_sir()
        module = sir.SIRModule("synthetic_loop_identity")
        function = sir.SIRFunction("run", [], "void")
        module.add_function(function)
        entry = function.add_block("entry")
        loop = function.add_block("loop")
        entry.add(sir.BranchInst("loop"))
        loop.add(sir.CallInst("consume", [sir.SIRValue("token", "Token")]))
        loop.add(
            sir.BranchInst(
                "loop",
                point_id="while_backedge@7:5",
                control_kind="backedge",
            )
        )

        bridge = region_call_sir.RegionCallSIRBridge(
            (
                region_call_sir.RegionCallSIRSite(
                    "run", "token", "consume", "token", 0,
                    "call@8:9", "loop", 0,
                ),
            )
        )
        certificate = region_call_cfg.certify_region_call_cfg(bridge, module)
        self.assertEqual(len(certificate.points), 1)
        self.assertEqual(
            certificate.points[0].iteration_id,
            "while_backedge@7:5",
        )
        self.assertEqual(certificate.relations, ())


if __name__ == "__main__":
    unittest.main()
