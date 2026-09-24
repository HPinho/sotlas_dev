"""Checked REGION lifetime topology must remain identical in ownership SIR."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
COMPILER_DIR = ROOT / "compiler"


def _load_package():
    name = "sotlas_region_lifetime_sir_package"
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
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))
importlib.import_module("sotlas.sir")
frontend = importlib.import_module(f"{package.__name__}.region_frontend")
region_sir = importlib.import_module(f"{package.__name__}.region_sir")


SOURCE = """module app::region_lifetime_sir;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn observe(token: whisper Token) -> void { return; }
fn consume(token: region Token) -> void { return; }
fn run() -> u32 {
    let source: region Token = Token { value: 41u32 };
    let destination: region Token = Token { value: 9u32 };
    inspect(&source);
    observe(&source);
    consume(move destination);
    handover source to destination;
    return destination.value;
}
"""


class SotlasRegionLifetimeSIRTests(unittest.TestCase):
    def _checked_and_lifetime(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<region-lifetime-sir>",
        )
        lifetime = frontend.plan_checked_region_lifetime(
            checked,
            function="run",
        )
        return checked, lifetime

    def test_real_source_lifetime_matches_existing_ownership_sir(self):
        checked, lifetime = self._checked_and_lifetime()
        bridge = region_sir.validate_region_lifetime_sir(
            lifetime,
            checked.ownership_sir,
        )

        self.assertEqual(bridge.function, "run")
        self.assertEqual(len(bridge.handover_point_ids), 1)
        self.assertEqual(len(bridge.whisper_point_ids), 1)
        self.assertEqual(len(bridge.direct_point_ids), 1)
        self.assertTrue(bridge.handover_point_ids[0].startswith("handover@"))
        self.assertTrue(bridge.whisper_point_ids[0].startswith("whisper@"))
        self.assertTrue(bridge.direct_point_ids[0].startswith("direct@"))
        self.assertEqual(len(set(bridge.point_ids)), 3)

    def test_tampered_lifetime_borrow_identity_is_rejected(self):
        checked, lifetime = self._checked_and_lifetime()
        whisper_index = next(
            index for index, item in enumerate(lifetime.borrows)
            if item.mode == "whisper"
        )
        borrows = list(lifetime.borrows)
        borrows[whisper_index] = replace(
            borrows[whisper_index],
            point_id="whisper@999:1",
        )
        tampered = replace(lifetime, borrows=tuple(borrows))

        with self.assertRaisesRegex(
            region_sir.RegionLifetimeSIRError,
            "whisper lifetime edges diverged",
        ):
            region_sir.validate_region_lifetime_sir(
                tampered,
                checked.ownership_sir,
            )

    def test_tampered_lifetime_handover_destination_is_rejected(self):
        checked, lifetime = self._checked_and_lifetime()
        handover_index = next(
            index for index, item in enumerate(lifetime.transfers)
            if item.via == "handover"
        )
        transfers = list(lifetime.transfers)
        transfers[handover_index] = replace(
            transfers[handover_index],
            destination="source",
        )
        tampered = replace(lifetime, transfers=tuple(transfers))

        with self.assertRaisesRegex(
            region_sir.RegionLifetimeSIRError,
            "handovers diverged",
        ):
            region_sir.validate_region_lifetime_sir(
                tampered,
                checked.ownership_sir,
            )

    def test_missing_matching_sir_function_is_rejected(self):
        _, lifetime = self._checked_and_lifetime()
        fake = SimpleNamespace(functions=())
        with self.assertRaisesRegex(
            region_sir.RegionLifetimeSIRError,
            "exactly one matching function plan",
        ):
            region_sir.validate_region_lifetime_sir(lifetime, fake)

    def test_non_lifetime_plan_is_rejected(self):
        checked, _ = self._checked_and_lifetime()
        with self.assertRaisesRegex(
            region_sir.RegionLifetimeSIRError,
            "RegionLifetimePlan",
        ):
            region_sir.validate_region_lifetime_sir(
                object(),
                checked.ownership_sir,
            )


if __name__ == "__main__":
    unittest.main()
