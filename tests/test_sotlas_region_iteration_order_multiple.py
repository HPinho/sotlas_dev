"""REGION iteration ordering supports N ownership-taking operations per loop."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_iteration_multiple_package"
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
region_call_cfg = importlib.import_module(f"{package.__name__}.region_call_cfg")
region_call_sir = importlib.import_module(f"{package.__name__}.region_call_sir")
region_cfg = importlib.import_module(f"{package.__name__}.region_cfg")
region_iteration_order = importlib.import_module(
    f"{package.__name__}.region_iteration_order"
)
region_lifetime = importlib.import_module(f"{package.__name__}.region_lifetime")


def _site(*, binding, point_id, instruction_index, block="loop"):
    return region_call_sir.RegionCallSIRSite(
        function="run",
        binding=binding,
        callee="consume",
        parameter="value",
        argument_index=0,
        point_id=point_id,
        block=block,
        instruction_index=instruction_index,
    )


def _transfer(*, source, destination, point_id):
    return region_lifetime.RegionLifetimeTransfer(
        source=source,
        destination=destination,
        via="handover",
        point_id=point_id,
        terminal=False,
    )


def _handover(sir, *, source, destination, point_id):
    return sir.OwnershipDomainTransferInst(
        operation="handover",
        source=sir.SIRValue(source, "Token"),
        source_domain="region",
        target_domain="region",
        destination=sir.SIRValue(destination, "Token"),
        point_id=point_id,
    )


def _four_point_loop():
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("synthetic_region_iteration_multiple")
    function = sir.SIRFunction("run", [], "void")
    module.add_function(function)
    entry = function.add_block("entry")
    loop = function.add_block("loop")
    entry.add(sir.BranchInst("loop"))

    loop.add(sir.CallInst("consume", [sir.SIRValue("first", "Token")]))
    loop.add(
        _handover(
            sir,
            source="source_a",
            destination="destination_a",
            point_id="handover@9:9",
        )
    )
    loop.add(sir.CallInst("consume", [sir.SIRValue("second", "Token")]))
    loop.add(
        _handover(
            sir,
            source="source_b",
            destination="destination_b",
            point_id="handover@11:9",
        )
    )
    loop.add(
        sir.BranchInst(
            "loop",
            point_id="while_backedge@7:5",
            control_kind="backedge",
        )
    )

    bridge = region_call_sir.RegionCallSIRBridge(
        (
            _site(binding="first", point_id="call@8:9", instruction_index=0),
            _site(binding="second", point_id="call@10:9", instruction_index=2),
        )
    )
    lifetime = region_lifetime.RegionLifetimePlan(
        function="run",
        owners=(),
        transfers=(
            _transfer(
                source="source_a",
                destination="destination_a",
                point_id="handover@9:9",
            ),
            _transfer(
                source="source_b",
                destination="destination_b",
                point_id="handover@11:9",
            ),
        ),
        borrows=(),
    )
    return module, bridge, lifetime


def _branch_calls():
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("synthetic_region_iteration_branch_calls")
    function = sir.SIRFunction("run", [], "void")
    module.add_function(function)
    entry = function.add_block("entry")
    header = function.add_block("header")
    left = function.add_block("left")
    right = function.add_block("right")
    latch = function.add_block("latch")

    entry.add(sir.BranchInst("header"))
    header.add(
        sir.CondBranchInst(
            sir.SIRValue("flag", "bool"),
            "left",
            "right",
        )
    )
    left.add(sir.CallInst("consume", [sir.SIRValue("first", "Token")]))
    left.add(sir.BranchInst("latch"))
    right.add(sir.CallInst("consume", [sir.SIRValue("second", "Token")]))
    right.add(sir.BranchInst("latch"))
    latch.add(
        sir.BranchInst(
            "header",
            point_id="while_backedge@20:5",
            control_kind="backedge",
        )
    )

    bridge = region_call_sir.RegionCallSIRBridge(
        (
            _site(
                binding="first",
                point_id="call@8:9",
                instruction_index=0,
                block="left",
            ),
            _site(
                binding="second",
                point_id="call@9:9",
                instruction_index=0,
                block="right",
            ),
        )
    )
    lifetime = region_lifetime.RegionLifetimePlan(
        function="run",
        owners=(),
        transfers=(),
        borrows=(),
    )
    return module, bridge, lifetime


class SotlasRegionIterationMultipleTests(unittest.TestCase):
    def test_multiple_calls_and_handovers_share_one_canonical_iteration_order(self):
        module, bridge, lifetime = _four_point_loop()
        call_cfg = region_call_cfg.certify_region_call_cfg(bridge, module)
        lifetime_cfg = region_cfg.certify_region_lifetime_cfg(lifetime, module)
        certificate = region_iteration_order.certify_region_iteration_order(
            call_cfg,
            lifetime_cfg,
            module,
        )

        self.assertEqual(len(call_cfg.points), 2)
        self.assertEqual(len(call_cfg.relations), 1)
        self.assertEqual(call_cfg.relations[0].relation, "ordered_path")
        self.assertEqual(
            (
                call_cfg.relations[0].first_point_id,
                call_cfg.relations[0].second_point_id,
            ),
            ("call@8:9", "call@10:9"),
        )

        self.assertEqual(
            lifetime_cfg.cyclic_handover_point_ids,
            ("handover@9:9", "handover@11:9"),
        )
        self.assertEqual(len(certificate.points), 4)
        self.assertEqual(len(certificate.relations), 6)
        self.assertEqual(
            {item.relation for item in certificate.relations},
            {"ordered_path"},
        )
        self.assertEqual(
            {
                (item.first_point_id, item.second_point_id)
                for item in certificate.relations
            },
            {
                ("call@8:9", "call@10:9"),
                ("call@8:9", "handover@9:9"),
                ("call@8:9", "handover@11:9"),
                ("handover@9:9", "call@10:9"),
                ("handover@9:9", "handover@11:9"),
                ("call@10:9", "handover@11:9"),
            },
        )

    def test_same_kind_calls_on_opposite_branch_arms_remain_path_disjoint(self):
        module, bridge, lifetime = _branch_calls()
        call_cfg = region_call_cfg.certify_region_call_cfg(bridge, module)
        lifetime_cfg = region_cfg.certify_region_lifetime_cfg(lifetime, module)
        certificate = region_iteration_order.certify_region_iteration_order(
            call_cfg,
            lifetime_cfg,
            module,
        )

        self.assertEqual(len(call_cfg.relations), 1)
        relation = call_cfg.relations[0]
        self.assertEqual(relation.relation, "path_disjoint")
        self.assertEqual(len(certificate.points), 2)
        self.assertEqual(len(certificate.relations), 1)
        self.assertEqual(certificate.relations[0].relation, "path_disjoint")


if __name__ == "__main__":
    unittest.main()
