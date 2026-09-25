"""REGION arena flow certifies intra-iteration producers and loop recurrence."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_arena_flow_cycle_package"
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
arena = importlib.import_module(f"{package.__name__}.region_arena")
arena_flow = importlib.import_module(f"{package.__name__}.region_arena_flow")
call_cfg_mod = importlib.import_module(f"{package.__name__}.region_call_cfg")
call_sir = importlib.import_module(f"{package.__name__}.region_call_sir")
region_cfg = importlib.import_module(f"{package.__name__}.region_cfg")
interprocedural = importlib.import_module(f"{package.__name__}.region_interprocedural")
iteration_order = importlib.import_module(f"{package.__name__}.region_iteration_order")
region_lifetime = importlib.import_module(f"{package.__name__}.region_lifetime")
region_return = importlib.import_module(f"{package.__name__}.region_return")
ownership_origin = importlib.import_module(f"{package.__name__}.ownership_origin")


def _fixture(*, post_before_pre: bool):
    sir = canonical_sir.load_canonical_sir()
    module = sir.SIRModule("synthetic_region_arena_cycle")
    function = sir.SIRFunction("run", [], "void")
    module.add_function(function)
    entry = function.add_block("entry")
    loop = function.add_block("loop")
    entry.add(sir.BranchInst("loop"))

    handover = sir.OwnershipDomainTransferInst(
        operation="handover",
        source=sir.SIRValue("source", "Token"),
        source_domain="region",
        target_domain="region",
        destination=sir.SIRValue("destination", "Token"),
        point_id="handover@9:9",
    )
    call = sir.CallInst("consume", [sir.SIRValue("destination", "Token")])
    if post_before_pre:
        loop.add(handover)
        loop.add(call)
        handover_index, call_index = 0, 1
    else:
        loop.add(call)
        loop.add(handover)
        call_index, handover_index = 0, 1
    loop.add(
        sir.BranchInst(
            "loop",
            point_id="while_backedge@7:5",
            control_kind="backedge",
        )
    )

    bridge = call_sir.RegionCallSIRBridge(
        (
            call_sir.RegionCallSIRSite(
                function="run",
                binding="destination",
                callee="consume",
                parameter="token",
                argument_index=0,
                point_id="call@10:9",
                block="loop",
                instruction_index=call_index,
            ),
        )
    )
    local = region_lifetime.RegionLifetimePlan(
        function="run",
        owners=(),
        transfers=(
            region_lifetime.RegionLifetimeTransfer(
                source="source",
                destination="destination",
                via="handover",
                point_id="handover@9:9",
                terminal=False,
            ),
        ),
        borrows=(),
    )
    call_cfg = call_cfg_mod.certify_region_call_cfg(bridge, module)
    lifetime_cfg = region_cfg.certify_region_lifetime_cfg(local, module)
    order = iteration_order.certify_region_iteration_order(
        call_cfg,
        lifetime_cfg,
        module,
    )
    function_plan = interprocedural.RegionInterproceduralFunctionPlan(
        function="run",
        local=local,
        calls=(),
        lifetime_cfg=lifetime_cfg,
        iteration_order=order,
        origins=ownership_origin.OwnershipOriginPlan(function="run", origins=()),
    )
    lifetime = interprocedural.RegionInterproceduralLifetimePlan(
        functions=(function_plan,),
        returns=region_return.RegionReturnLifetimePlan(contracts=(), transfers=()),
        call_cfg=call_cfg,
    )

    graph = arena.RegionArenaLifetimeGraph(
        slots=(arena.RegionArenaSlot("run", "destination", "Token"),),
        epochs=(
            arena.RegionArenaEpoch(
                epoch_id="origin@run::param_origin@run::destination::destination",
                function="run",
                binding="destination",
                phase="origin",
                point_id="param_origin@run::destination",
                type="Token",
            ),
            arena.RegionArenaEpoch(
                epoch_id="post@run::handover@9:9::destination",
                function="run",
                binding="destination",
                phase="post",
                point_id="handover@9:9",
                type="Token",
            ),
            arena.RegionArenaEpoch(
                epoch_id="pre@run::call@10:9::destination",
                function="run",
                binding="destination",
                phase="pre",
                point_id="call@10:9",
                type="Token",
            ),
        ),
        constraints=(),
    )
    return module, lifetime, graph


class SotlasRegionArenaFlowCycleTests(unittest.TestCase):
    def test_previous_post_in_same_iteration_feeds_cyclic_pre(self):
        module, lifetime, graph = _fixture(post_before_pre=True)
        certificate = arena_flow.certify_region_arena_flow(
            lifetime,
            graph,
            module,
        )
        pre = next(item for item in graph.epochs if item.phase == "pre")
        post = next(item for item in graph.epochs if item.phase == "post")
        resolution = certificate.resolution_for(pre.epoch_id)
        self.assertEqual(resolution.producer_epoch_id, post.epoch_id)
        self.assertEqual(certificate.recurrences, ())
        self.assertTrue(certificate.complete)

    def test_post_after_pre_becomes_certified_loop_recurrence(self):
        module, lifetime, graph = _fixture(post_before_pre=False)
        certificate = arena_flow.certify_region_arena_flow(
            lifetime,
            graph,
            module,
        )
        pre = next(item for item in graph.epochs if item.phase == "pre")
        post = next(item for item in graph.epochs if item.phase == "post")
        origin = next(item for item in graph.epochs if item.phase == "origin")
        recurrence = certificate.recurrence_for(pre.epoch_id)
        self.assertEqual(recurrence.initial_epoch_id, origin.epoch_id)
        self.assertEqual(recurrence.carried_epoch_id, post.epoch_id)
        self.assertEqual(recurrence.iteration_id, "while_backedge@7:5")
        self.assertEqual(certificate.resolutions, ())
        self.assertEqual(certificate.unresolved, ())
        self.assertTrue(certificate.complete)

    def test_unknown_recurrence_query_fails_closed(self):
        module, lifetime, graph = _fixture(post_before_pre=True)
        certificate = arena_flow.certify_region_arena_flow(
            lifetime,
            graph,
            module,
        )
        with self.assertRaisesRegex(
            arena_flow.RegionArenaFlowError,
            "exactly one recurrence",
        ):
            certificate.recurrence_for("pre@missing")


if __name__ == "__main__":
    unittest.main()
