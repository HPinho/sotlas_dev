"""Path-sensitive REGION lifetime certification against the real Phase-1 CFG."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
COMPILER_DIR = ROOT / "compiler"


def _load_package():
    name = "sotlas_region_lifetime_cfg_package"
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
sir = importlib.import_module("sotlas.sir")
frontend = importlib.import_module(f"{package.__name__}.region_frontend")
region_cfg = importlib.import_module(f"{package.__name__}.region_cfg")


SEQUENTIAL = """module app::region_cfg_sequential;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn consume(token: region Token) -> void { return; }
fn run(source: region Token, destination: region Token) -> void {
    inspect(&source);
    consume(move destination);
    handover source to destination;
    return;
}
"""

BRANCHED = """module app::region_cfg_branches;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn consume(token: region Token) -> void { return; }
fn route(flag: bool, source: region Token, destination: region Token) -> void {
    if flag {
        inspect(&source);
        return;
    } else {
        consume(move destination);
        handover source to destination;
        return;
    }
}
"""

LOOP_BORROW = """module app::region_cfg_loop_borrow;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn run(flag: bool, token: region Token) -> void {
    while flag {
        inspect(&token);
    }
    return;
}
"""


class SotlasRegionLifetimeCFGTests(unittest.TestCase):
    def test_real_sequential_borrow_before_handover_is_certified(self):
        checked = package.analyze_source_phase1(
            SEQUENTIAL,
            filename="<region-cfg-sequential>",
        )
        certificate = region_cfg.certify_checked_region_lifetime_cfg(
            checked,
            function="run",
        )
        self.assertEqual(certificate.function, "run")
        self.assertEqual(
            {item.kind for item in certificate.locations},
            {"direct", "handover"},
        )
        direct = next(item for item in certificate.locations if item.kind == "direct")
        handover = next(
            item for item in certificate.locations if item.kind == "handover"
        )
        self.assertEqual(direct.source, "source")
        self.assertEqual(handover.source, "source")
        if direct.block == handover.block:
            self.assertLess(direct.instruction_index, handover.instruction_index)

    def test_alternative_branch_borrow_and_handover_are_not_linearized(self):
        checked = package.analyze_source_phase1(
            BRANCHED,
            filename="<region-cfg-branches>",
        )
        certificate = region_cfg.certify_checked_region_lifetime_cfg(
            checked,
            function="route",
        )
        direct = next(item for item in certificate.locations if item.kind == "direct")
        handover = next(
            item for item in certificate.locations if item.kind == "handover"
        )
        self.assertNotEqual(direct.block, handover.block)

    def test_call_scoped_region_borrow_inside_loop_is_certified(self):
        checked = package.analyze_source_phase1(
            LOOP_BORROW,
            filename="<region-cfg-loop-borrow>",
        )
        certificate = region_cfg.certify_checked_region_lifetime_cfg(
            checked,
            function="run",
        )
        direct = next(item for item in certificate.locations if item.kind == "direct")
        self.assertEqual(direct.source, "token")
        self.assertFalse(certificate.acyclic_points)
        self.assertEqual(
            certificate.cyclic_borrow_point_ids,
            (direct.point_id,),
        )

    def test_tampered_cfg_borrow_after_handover_is_rejected(self):
        checked = package.analyze_source_phase1(
            SEQUENTIAL,
            filename="<region-cfg-tampered>",
        )
        lifetime = frontend.plan_checked_region_lifetime(
            checked,
            function="run",
        )
        checked_sir = sir.generate_checked_ownership_sir(checked)
        function = next(
            item for item in checked_sir.module.functions if item.name == "run"
        )
        direct_point = next(
            item.point_id for item in lifetime.borrows if item.mode == "direct"
        )
        handover_point = next(
            item.point_id
            for item in lifetime.transfers
            if item.via == "handover"
        )
        direct_location = None
        handover_location = None
        for block in function.blocks:
            for index, instruction in enumerate(block.instructions):
                if getattr(instruction, "point_id", None) == direct_point:
                    direct_location = (block, index)
                if getattr(instruction, "point_id", None) == handover_point:
                    handover_location = (block, index)
        self.assertIsNotNone(direct_location)
        self.assertIsNotNone(handover_location)
        direct_block, direct_index = direct_location
        handover_block, handover_index = handover_location
        self.assertIs(direct_block, handover_block)
        direct_block.instructions[direct_index], direct_block.instructions[handover_index] = (
            direct_block.instructions[handover_index],
            direct_block.instructions[direct_index],
        )

        with self.assertRaisesRegex(
            region_cfg.RegionLifetimeCFGError,
            r"borrow point .* reachable after handover",
        ):
            region_cfg.certify_region_lifetime_cfg(
                lifetime,
                checked_sir.module,
            )

    def test_tampered_duplicate_lifetime_point_is_rejected_before_cfg_scan(self):
        checked = package.analyze_source_phase1(
            SEQUENTIAL,
            filename="<region-cfg-duplicate-point>",
        )
        lifetime = frontend.plan_checked_region_lifetime(
            checked,
            function="run",
        )
        handover_point = next(
            item.point_id
            for item in lifetime.transfers
            if item.via == "handover"
        )
        borrow = lifetime.borrows[0]
        tampered = replace(
            lifetime,
            borrows=(replace(borrow, point_id=handover_point),),
        )
        checked_sir = sir.generate_checked_ownership_sir(checked)

        with self.assertRaisesRegex(
            region_cfg.RegionLifetimeCFGError,
            r"duplicate REGION lifetime point identity",
        ):
            region_cfg.certify_region_lifetime_cfg(
                tampered,
                checked_sir.module,
            )


if __name__ == "__main__":
    unittest.main()
