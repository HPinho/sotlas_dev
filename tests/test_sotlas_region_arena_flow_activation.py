"""REGION arena flow preserves callee activation alternatives explicitly."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_arena_flow_activation_package"
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
closed = importlib.import_module(f"{package.__name__}.region_closed_interprocedural")


SOURCE = """module app::region_arena_activation;
sole struct Token { value: u32; }

fn consume(token: region Token) -> void { return; }

fn relay(token: region Token) -> void {
    consume(move token);
    return;
}

fn run(first: region Token, second: region Token) -> void {
    relay(move first);
    relay(move second);
    return;
}
"""


class SotlasRegionArenaFlowActivationTests(unittest.TestCase):
    def test_callee_pre_preserves_all_call_entry_activations(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-arena-activation>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        flow = plan.require_complete_arena_flow()
        graph = plan.arena_lifetime

        relay_pre = next(
            item
            for item in graph.epochs_for("relay", "token")
            if item.phase == "pre"
        )
        call_entries = tuple(
            item
            for item in graph.epochs_for("relay", "token")
            if item.phase == "call_entry"
        )
        self.assertEqual(len(call_entries), 2)
        self.assertEqual(len({item.activation_id for item in call_entries}), 2)

        activation = flow.activation_for(relay_pre.epoch_id)
        self.assertEqual(
            set(activation.input_epoch_ids),
            {item.epoch_id for item in call_entries},
        )
        self.assertEqual(activation.function, "relay")
        self.assertEqual(activation.binding, "token")
        self.assertTrue(flow.complete)

    def test_generic_parameter_origin_is_not_used_for_activation_sensitive_pre(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-arena-activation-origin>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        flow = plan.require_complete_arena_flow()
        graph = plan.arena_lifetime
        relay_pre = next(
            item for item in graph.epochs_for("relay", "token") if item.phase == "pre"
        )
        origin = next(
            item for item in graph.epochs_for("relay", "token") if item.phase == "origin"
        )
        activation = flow.activation_for(relay_pre.epoch_id)
        self.assertNotIn(origin.epoch_id, activation.input_epoch_ids)
        with self.assertRaisesRegex(Exception, "exactly one resolution"):
            flow.resolution_for(relay_pre.epoch_id)


if __name__ == "__main__":
    unittest.main()
