"""REGION source-stable call contracts must map to explicit canonical SIR facts."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_call_sir_package"
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


SOURCE = """module app::region_call_sir;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(source: region Token, destination: region Token) -> void {
    consume(move destination);
    handover source to destination;
    return;
}
"""

MULTI_SOURCE = """module app::region_call_sir_multi;
sole struct Token { value: u32; }
fn consume(left: region Token, right: region Token) -> void { return; }
fn run(left: region Token, right: region Token) -> void {
    consume(move left, move right);
    return;
}
"""


class SotlasRegionCallSIRTests(unittest.TestCase):
    def _plans(self, source=SOURCE):
        checked = package.analyze_source_phase1(
            source, filename="<region-call-sir>"
        )
        calls = region_call.plan_checked_region_calls(checked)
        sir_module, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        return calls, sir_module

    def test_real_region_call_embeds_source_identity_in_sir(self):
        calls, sir_module = self._plans()
        bridge = region_call_sir.validate_region_call_sir(calls, sir_module)
        self.assertEqual(len(bridge.sites), 1)
        site = bridge.sites[0]
        self.assertEqual((site.function, site.binding), ("run", "destination"))
        self.assertEqual((site.callee, site.parameter), ("consume", "token"))
        self.assertEqual(site.argument_index, 0)
        self.assertTrue(site.point_id.startswith("call@"))
        self.assertTrue(site.source_identity_embedded)
        self.assertEqual(site.block, "0")
        self.assertLess(site.instruction_index, site.call_instruction_index)

    def test_multiple_region_arguments_share_call_point_but_keep_parameter_identity(self):
        calls, sir_module = self._plans(MULTI_SOURCE)
        bridge = region_call_sir.validate_region_call_sir(calls, sir_module)
        self.assertEqual(len(bridge.sites), 2)
        self.assertEqual(
            tuple((site.parameter, site.argument_index) for site in bridge.sites),
            (("left", 0), ("right", 1)),
        )
        self.assertEqual(bridge.sites[0].point_id, bridge.sites[1].point_id)
        self.assertEqual(
            bridge.sites[0].call_instruction_index,
            bridge.sites[1].call_instruction_index,
        )
        self.assertNotEqual(
            bridge.sites[0].instruction_index,
            bridge.sites[1].instruction_index,
        )

    def test_tampered_binding_is_rejected_against_sir_fact(self):
        calls, sir_module = self._plans()
        tampered = replace(
            calls,
            transfers=(replace(calls.transfers[0], binding="source"),),
        )
        with self.assertRaisesRegex(
            region_call_sir.RegionCallSIRError,
            "exactly one RegionCallTransferInst",
        ):
            region_call_sir.validate_region_call_sir(tampered, sir_module)

    def test_tampered_source_point_is_rejected_against_embedded_sir_identity(self):
        calls, sir_module = self._plans()
        tampered = replace(
            calls,
            transfers=(replace(calls.transfers[0], point_id="call@999:1"),),
        )
        with self.assertRaisesRegex(
            region_call_sir.RegionCallSIRError,
            "exactly one RegionCallTransferInst",
        ):
            region_call_sir.validate_region_call_sir(tampered, sir_module)

    def test_non_call_plan_is_rejected(self):
        _, sir_module = self._plans()
        with self.assertRaisesRegex(
            region_call_sir.RegionCallSIRError,
            "RegionCallLifetimePlan",
        ):
            region_call_sir.validate_region_call_sir(object(), sir_module)


if __name__ == "__main__":
    unittest.main()
