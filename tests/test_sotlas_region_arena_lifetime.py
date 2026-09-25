"""Symbolic REGION arena/lifetime epochs across local and call boundaries."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_arena_lifetime_package"
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


CALL_RETURN_SOURCE = """module app::region_arena_call_return;
sole struct Token { value: u32; }

fn pass(token: region Token) -> region Token {
    return token;
}

fn run(token: region Token) -> void {
    let out: region Token = pass(move token);
    return;
}
"""


HANDOVER_SOURCE = """module app::region_arena_handover;
sole struct Token { value: u32; }

fn consume(token: region Token) -> void { return; }

fn run(source: region Token, destination: region Token) -> void {
    consume(move destination);
    handover source to destination;
    return;
}
"""


class SotlasRegionArenaLifetimeTests(unittest.TestCase):
    def test_call_and_return_create_activation_scoped_identity_constraints(self):
        checked = package.analyze_source_phase1(
            CALL_RETURN_SOURCE,
            filename="<region-arena-call-return>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        graph = plan.arena_lifetime

        self.assertEqual(
            {(item.function, item.binding) for item in graph.slots},
            {("pass", "token"), ("run", "token"), ("run", "out")},
        )
        self.assertEqual(
            {item.via for item in graph.constraints},
            {"call", "return"},
        )
        self.assertEqual(len(graph.constraints), 2)
        self.assertEqual(
            {(item.function, item.binding) for item in graph.origin_epochs()},
            {("pass", "token"), ("run", "token")},
        )
        self.assertFalse(
            any(
                item.function == "run"
                and item.binding == "out"
                and item.phase == "origin"
                for item in graph.epochs
            )
        )

        link = plan.return_links.links[0]
        constraints = graph.constraints_at(link.point_id)
        self.assertEqual(len(constraints), 2)

        call = next(item for item in constraints if item.via == "call")
        call_source = graph.epoch(call.source_epoch_id)
        call_target = graph.epoch(call.target_epoch_id)
        self.assertEqual(
            (call_source.function, call_source.binding, call_source.phase),
            ("run", "token", "pre"),
        )
        self.assertEqual(
            (call_target.function, call_target.binding, call_target.phase),
            ("pass", "token", "call_entry"),
        )
        self.assertIsNotNone(call_target.activation_id)
        self.assertTrue(call.preserves_identity)

        returned = next(item for item in constraints if item.via == "return")
        return_source = graph.epoch(returned.source_epoch_id)
        return_target = graph.epoch(returned.target_epoch_id)
        self.assertEqual(
            (return_source.function, return_source.binding, return_source.phase),
            ("pass", "token", "call_return"),
        )
        self.assertEqual(
            (return_target.function, return_target.binding, return_target.phase),
            ("run", "out", "post"),
        )
        self.assertIsNotNone(return_source.activation_id)
        self.assertTrue(returned.preserves_identity)

    def test_reused_handover_destination_gets_origin_pre_and_post_epochs(self):
        checked = package.analyze_source_phase1(
            HANDOVER_SOURCE,
            filename="<region-arena-handover>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        graph = plan.arena_lifetime

        handovers = tuple(
            item for item in graph.constraints if item.via == "local:handover"
        )
        self.assertEqual(len(handovers), 1)
        handover = handovers[0]
        source = graph.epoch(handover.source_epoch_id)
        destination = graph.epoch(handover.target_epoch_id)
        self.assertEqual(
            (source.function, source.binding, source.phase),
            ("run", "source", "pre"),
        )
        self.assertEqual(
            (destination.function, destination.binding, destination.phase),
            ("run", "destination", "post"),
        )
        self.assertNotEqual(source.epoch_id, destination.epoch_id)
        self.assertTrue(handover.preserves_identity)

        destination_epochs = graph.epochs_for("run", "destination")
        self.assertEqual(
            {item.phase for item in destination_epochs},
            {"origin", "pre", "post"},
        )
        origin_epoch = next(
            item for item in destination_epochs if item.phase == "origin"
        )
        pre_epoch = next(item for item in destination_epochs if item.phase == "pre")
        post_epoch = next(item for item in destination_epochs if item.phase == "post")
        self.assertEqual(origin_epoch.point_id, "param_origin@run::destination")
        self.assertNotEqual(origin_epoch.epoch_id, pre_epoch.epoch_id)
        self.assertNotEqual(pre_epoch.epoch_id, post_epoch.epoch_id)
        self.assertEqual(pre_epoch.point_id, plan.boundaries.links[0].point_id)
        self.assertEqual(post_epoch.point_id, handover.point_id)


if __name__ == "__main__":
    unittest.main()
