"""REGION calls can re-consume one source-stable binding after a valid re-arm."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_call_rearm_package"
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
region_call = importlib.import_module(f"{package.__name__}.region_call")
closed = importlib.import_module(
    f"{package.__name__}.region_closed_interprocedural"
)


SOURCE = """module app::region_call_rearm;
sole struct Token { value: u32; }

fn consume(token: region Token) -> void { return; }

fn run(source: region Token, destination: region Token) -> void {
    consume(move destination);
    handover source to destination;
    consume(move destination);
    return;
}
"""


class SotlasRegionCallRearmTests(unittest.TestCase):
    def test_rearmed_binding_maps_to_two_distinct_call_contracts(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-call-rearm>",
        )
        plan = region_call.plan_checked_region_calls(checked)
        repeated = tuple(
            item
            for item in plan.transfers
            if item.function == "run" and item.binding == "destination"
        )
        self.assertEqual(len(repeated), 2)
        self.assertEqual(tuple(item.callee for item in repeated), ("consume", "consume"))
        self.assertEqual(tuple(item.parameter for item in repeated), ("token", "token"))
        self.assertEqual(len({item.point_id for item in repeated}), 2)

    def test_rearmed_binding_closes_through_arena_flow(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-call-rearm-closed>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        flow = plan.require_complete_arena_flow()
        destination_epochs = plan.arena_lifetime.epochs_for("run", "destination")
        pre_epochs = tuple(item for item in destination_epochs if item.phase == "pre")
        self.assertEqual(len(pre_epochs), 2)
        producers = tuple(
            plan.arena_lifetime.epoch(flow.resolution_for(item.epoch_id).producer_epoch_id)
            for item in pre_epochs
        )
        self.assertEqual(
            {item.phase for item in producers},
            {"origin", "post"},
        )


if __name__ == "__main__":
    unittest.main()
