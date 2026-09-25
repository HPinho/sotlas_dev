"""Checked closed REGION plans carry and gate arena-flow certification."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_closed_arena_flow_package"
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
arena_flow = importlib.import_module(f"{package.__name__}.region_arena_flow")


SOURCE = """module app::region_closed_arena_flow;
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


class SotlasRegionClosedArenaFlowTests(unittest.TestCase):
    def test_checked_closed_plan_carries_complete_arena_flow(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-closed-arena-flow>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        self.assertIsNotNone(plan.arena_flow)
        certificate = plan.require_complete_arena_flow()
        self.assertTrue(certificate.complete)
        self.assertGreaterEqual(len(certificate.resolutions), 4)

    def test_incomplete_arena_flow_is_fail_closed_when_required(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-closed-arena-flow-gate>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        assert plan.arena_flow is not None
        pre_epoch_id = plan.arena_flow.resolutions[0].pre_epoch_id
        forged_flow = arena_flow.RegionArenaFlowCertificate(
            resolutions=(),
            unresolved=(
                arena_flow.RegionArenaFlowUnresolved(
                    function="run",
                    binding="destination",
                    pre_epoch_id=pre_epoch_id,
                    reason="ambiguous_merge",
                ),
            ),
        )
        forged = replace(plan, arena_flow=forged_flow)
        with self.assertRaisesRegex(
            closed.RegionClosedInterproceduralError,
            "arena flow is incomplete: ambiguous_merge",
        ):
            forged.require_complete_arena_flow()

    def test_manual_builder_does_not_fake_checked_arena_flow(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-closed-arena-flow-builder>",
        )
        checked_plan = closed.plan_checked_region_closed_interprocedural(checked)
        manual = closed.build_region_closed_interprocedural_plan(
            checked_plan.lifetime,
            checked_plan.boundaries,
            checked_plan.return_links,
        )
        self.assertIsNone(manual.arena_flow)
        with self.assertRaisesRegex(
            closed.RegionClosedInterproceduralError,
            "lacks checked arena-flow certification",
        ):
            manual.require_complete_arena_flow()


if __name__ == "__main__":
    unittest.main()
