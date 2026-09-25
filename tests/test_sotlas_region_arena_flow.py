"""REGION symbolic arenas resolve unambiguous reaching epochs through CFG order."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_arena_flow_package"
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
closed = importlib.import_module(
    f"{package.__name__}.region_closed_interprocedural"
)
arena_flow = importlib.import_module(f"{package.__name__}.region_arena_flow")


CALL_RETURN_SOURCE = """module app::region_arena_flow_call;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn run(token: region Token) -> void {
    let out: region Token = pass(move token);
    return;
}
"""


REARM_SOURCE = """module app::region_arena_flow_rearm;
sole struct Token { value: u32; }

fn consume(token: region Token) -> void { return; }

fn run(source: region Token, destination: region Token, final: region Token) -> void {
    consume(move destination);
    handover source to destination;
    consume(move final);
    handover destination to final;
    return;
}
"""


def _certificate(source: str, filename: str):
    checked = package.analyze_source_phase1(source, filename=filename)
    plan = closed.plan_checked_region_closed_interprocedural(checked)
    checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
    flow = arena_flow.certify_region_arena_flow(
        plan.lifetime,
        plan.arena_lifetime,
        checked_sir,
    )
    return plan, flow


class SotlasRegionArenaFlowTests(unittest.TestCase):
    def test_call_source_pre_epoch_resolves_to_parameter_origin(self):
        plan, flow = _certificate(
            CALL_RETURN_SOURCE,
            "<region-arena-flow-call>",
        )
        graph = plan.arena_lifetime
        pre = next(
            item
            for item in graph.epochs_for("run", "token")
            if item.phase == "pre"
        )
        resolution = flow.resolution_for(pre.epoch_id)
        producer = graph.epoch(resolution.producer_epoch_id)
        self.assertEqual(
            (producer.function, producer.binding, producer.phase),
            ("run", "token", "origin"),
        )
        self.assertTrue(flow.complete)

    def test_rearmed_destination_uses_origin_then_previous_post(self):
        plan, flow = _certificate(
            REARM_SOURCE,
            "<region-arena-flow-rearm>",
        )
        graph = plan.arena_lifetime
        destination_epochs = graph.epochs_for("run", "destination")
        pre_epochs = tuple(item for item in destination_epochs if item.phase == "pre")
        self.assertEqual(len(pre_epochs), 2)
        post = next(item for item in destination_epochs if item.phase == "post")
        origin = next(item for item in destination_epochs if item.phase == "origin")

        resolutions = tuple(flow.resolution_for(item.epoch_id) for item in pre_epochs)
        producer_ids = tuple(item.producer_epoch_id for item in resolutions)
        self.assertEqual(set(producer_ids), {origin.epoch_id, post.epoch_id})
        self.assertTrue(flow.complete)

    def test_unknown_resolution_fails_closed(self):
        _, flow = _certificate(
            CALL_RETURN_SOURCE,
            "<region-arena-flow-query>",
        )
        with self.assertRaisesRegex(
            arena_flow.RegionArenaFlowError,
            "exactly one resolution",
        ):
            flow.resolution_for("pre@missing")


if __name__ == "__main__":
    unittest.main()
