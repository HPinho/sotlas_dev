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

MULTI_ARGUMENT_SOURCE = """module app::region_call_multi_sir;
sole struct Token { value: u32; }
fn consume(left: region Token, right: region Token) -> void { return; }
fn run(left: region Token, right: region Token) -> void {
    consume(move left, move right);
    return;
}
"""


class SotlasRegionCallOnlySIRTests(unittest.TestCase):
    def _plans(self, source: str):
        checked = package.analyze_source_phase1(
            source, filename="<region-call-only-sir>"
        )
        calls = region_call.plan_checked_region_calls(checked)
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        return calls, checked_sir

    def test_pure_region_move_calls_survive_sir_and_keep_semantic_identities(self):
        calls, checked_sir = self._plans(SOURCE)
        bridge = region_call_sir.validate_region_call_sir(calls, checked_sir)

        self.assertEqual(tuple(item.binding for item in bridge.sites), ("first", "second"))
        self.assertEqual(tuple(item.callee for item in bridge.sites), ("consume", "consume"))
        self.assertEqual(len({item.point_id for item in bridge.sites}), 2)
        self.assertEqual(len({item.instruction_index for item in bridge.sites}), 2)
        self.assertLess(bridge.sites[0].instruction_index, bridge.sites[1].instruction_index)
        self.assertTrue(all(not item.source_identity_embedded for item in bridge.sites))

    def test_multiple_region_arguments_share_one_canonical_sir_call(self):
        calls, checked_sir = self._plans(MULTI_ARGUMENT_SOURCE)
        bridge = region_call_sir.validate_region_call_sir(calls, checked_sir)

        self.assertEqual(len(bridge.sites), 2)
        self.assertEqual(len({item.point_id for item in bridge.sites}), 1)
        self.assertEqual(len({item.block for item in bridge.sites}), 1)
        self.assertEqual(len({item.instruction_index for item in bridge.sites}), 1)
        self.assertEqual(tuple(item.argument_index for item in bridge.sites), (0, 1))
        self.assertEqual(tuple(item.parameter for item in bridge.sites), ("left", "right"))

    def test_reordered_same_block_calls_are_rejected(self):
        calls, checked_sir = self._plans(SOURCE)
        sir = canonical_sir.load_canonical_sir()
        run = next(item for item in checked_sir.module.functions if item.name == "run")
        block = run.blocks[0]
        call_indexes = [
            index
            for index, instruction in enumerate(block.instructions)
            if isinstance(instruction, sir.CallInst) and instruction.callee == "consume"
        ]
        self.assertEqual(len(call_indexes), 2)
        first_index, second_index = call_indexes
        block.instructions[first_index], block.instructions[second_index] = (
            block.instructions[second_index],
            block.instructions[first_index],
        )

        with self.assertRaisesRegex(
            region_call_sir.RegionCallSIRError,
            "source order diverges from SIR order",
        ):
            region_call_sir.validate_region_call_sir(calls, checked_sir)


if __name__ == "__main__":
    unittest.main()
