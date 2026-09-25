"""REGION call/handover ordering must be proven within one loop iteration."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_iteration_order_package"
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


def _lifetime(point_id="handover@9:9"):
    return region_lifetime.RegionLifetimePlan(
        function="run",
        owners=(),
        transfers=(
            region_lifetime.RegionLifetimeTransfer(
                source="source",
                destination="destination",
                via="handover",
                point_id=point_id,
                terminal=False,
            ),
        ),
        borrows=(),
    )


def _bridge(*, block, instruction_index, point_id="call@8:9"):
    return region_call_sir.RegionCallSIRBridge(
        (
            region_call_sir.RegionCallSIRSite(
                function="run",
                binding="token",
                callee="consume",
                parameter="value",
                argument_index=0,
                point_id=point_id,
                block=block,
                instruction_index=instruction_index,
            ),
        )
    )


def _handover(sir, point_id="handover@9:9"):
    return sir.OwnershipDomainTransferInst(
        operation="handover",
        source=sir.SIRValue("source", "Token"),
        source_domain="region",
        target_domain="region",
        destination=sir.SIRValue("destination", "Token"),
        point_id=point_id,
    )


def _linear_loop(*, handover_first=False):
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("synthetic_region_iteration_order")
    function = sir.SIRFunction("run", [], "void")
    module.add_function(function)
    entry = function.add_block("entry")
    loop = function.add_block("loop")
    entry.add(sir.BranchInst("loop"))

    if handover_first:
        loop.add(_handover(sir))
        loop.add(sir.CallInst("consume", [sir.SIRValue("token", "Token")]))
        call_index = 1
    else:
        loop.add(sir.CallInst("consume", [sir.SIRValue("token", "Token")]))
        loop.add(_handover(sir))
        call_index = 0

    loop.add(
        sir.BranchInst(
            "loop",
            point_id="while_backedge@7:5",
            control_kind="backedge",
        )
    )
    return sir, module, _bridge(block="loop", instruction_index=call_index), _lifetime()


def _branch_loop():
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("synthetic_region_iteration_branch")
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
    left.add(sir.CallInst("consume", [sir.SIRValue("token", "Token")]))
    left.add(sir.BranchInst("latch"))
    right.add(_handover(sir))
    right.add(sir.BranchInst("latch"))
    latch.add(
        sir.BranchInst(
            "header",
            point_id="while_backedge@20:5",
            control_kind="backedge",
        )
    )
    return sir, module, _bridge(block="left", instruction_index=0), _lifetime()


def _certificates(module, bridge, lifetime):
    call_cfg = region_call_cfg.certify_region_call_cfg(bridge, module)
    lifetime_cfg = region_cfg.certify_region_lifetime_cfg(lifetime, module)
    return call_cfg, lifetime_cfg


class SotlasRegionIterationOrderTests(unittest.TestCase):
    def test_call_before_handover_uses_cfg_order_not_cycle_reachability(self):
        _, module, bridge, lifetime = _linear_loop(handover_first=False)
        call_cfg, lifetime_cfg = _certificates(module, bridge, lifetime)
        certificate = region_iteration_order.certify_region_iteration_order(
            call_cfg,
            lifetime_cfg,
            module,
        )

        self.assertEqual(len(certificate.points), 2)
        self.assertEqual(len(certificate.relations), 1)
        relation = certificate.relations[0]
        self.assertEqual(relation.iteration_id, "while_backedge@7:5")
        self.assertEqual(relation.relation, "ordered_path")
        self.assertEqual(
            (relation.first_point_id, relation.second_point_id),
            ("call@8:9", "handover@9:9"),
        )

    def test_handover_before_call_is_oriented_from_sir_instruction_order(self):
        _, module, bridge, lifetime = _linear_loop(handover_first=True)
        call_cfg, lifetime_cfg = _certificates(module, bridge, lifetime)
        certificate = region_iteration_order.certify_region_iteration_order(
            call_cfg,
            lifetime_cfg,
            module,
        )

        relation = certificate.relations[0]
        self.assertEqual(relation.relation, "ordered_path")
        self.assertEqual(
            (relation.first_point_id, relation.second_point_id),
            ("handover@9:9", "call@8:9"),
        )

    def test_opposite_branch_arms_are_path_disjoint_after_backedge_cut(self):
        _, module, bridge, lifetime = _branch_loop()
        call_cfg, lifetime_cfg = _certificates(module, bridge, lifetime)
        certificate = region_iteration_order.certify_region_iteration_order(
            call_cfg,
            lifetime_cfg,
            module,
        )

        relation = certificate.relations[0]
        self.assertEqual(relation.iteration_id, "while_backedge@20:5")
        self.assertEqual(relation.relation, "path_disjoint")
        self.assertEqual(
            {relation.first_point_id, relation.second_point_id},
            {"call@8:9", "handover@9:9"},
        )

    def test_tampered_iteration_identity_is_rejected(self):
        _, module, bridge, lifetime = _linear_loop(handover_first=False)
        call_cfg, lifetime_cfg = _certificates(module, bridge, lifetime)
        call_point = call_cfg.points[0]
        tampered = replace(
            call_cfg,
            points=(replace(call_point, iteration_id="while_backedge@999:1"),),
        )

        with self.assertRaisesRegex(
            region_iteration_order.RegionIterationOrderError,
            "matching iteration identities",
        ):
            region_iteration_order.certify_region_iteration_order(
                tampered,
                lifetime_cfg,
                module,
            )


if __name__ == "__main__":
    unittest.main()
