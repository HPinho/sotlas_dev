"""Pure REGION move calls should survive canonical SIR generation."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_call_only_sir_package"
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


SOURCE = """module app::region_call_only_sir;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionCallOnlySIRTests(unittest.TestCase):
    def test_pure_region_move_calls_survive_sir_and_keep_semantic_identities(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-call-only-sir>"
        )
        calls = region_call.plan_checked_region_calls(checked)
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        bridge = region_call_sir.validate_region_call_sir(calls, checked_sir)

        self.assertEqual(tuple(item.binding for item in bridge.sites), ("first", "second"))
        self.assertEqual(tuple(item.callee for item in bridge.sites), ("consume", "consume"))
        self.assertEqual(len({item.point_id for item in bridge.sites}), 2)
        self.assertEqual(len({item.instruction_index for item in bridge.sites}), 2)
        self.assertTrue(all(not item.source_identity_embedded for item in bridge.sites))


if __name__ == "__main__":
    unittest.main()
