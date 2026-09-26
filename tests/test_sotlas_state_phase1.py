"""Phase 4: State Spaces composed into the public Phase-1 semantic pipeline."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_state_phase1_public_package"
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


sotlas_compile = _load_canonical_package()
state_frontend = importlib.import_module(
    f"{sotlas_compile.__name__}.state_frontend"
)


class SotlasStatePhase1Tests(unittest.TestCase):
    def _source(self) -> str:
        return """
        module test::state_phase1;

        pub space Device {
            state Discovered
            state Configured
            Discovered -> Configured
        }

        pub fn inspect(dev: Device<Discovered>) -> Device<Discovered> {
            return dev;
        }
        """

    def test_checked_module_carries_canonical_typed_state_snapshot(self):
        checked = sotlas_compile.analyze_source_phase1(
            self._source(), filename="<state-phase1>"
        )
        self.assertIsNotNone(checked.state_spaces)
        snapshot = checked.state_spaces
        space = snapshot.space("Device")
        self.assertTrue(space.public)
        self.assertEqual(
            tuple(state.name for state in space.states),
            ("Discovered", "Configured"),
        )
        self.assertEqual(
            tuple((edge.source, edge.target) for edge in space.transitions),
            (("Discovered", "Configured"),),
        )
        self.assertEqual(
            snapshot.site("fn:inspect:param:0:dev").qualified.display(),
            "Device<Discovered>",
        )
        self.assertEqual(
            snapshot.site("fn:inspect:return").qualified.display(),
            "Device<Discovered>",
        )
        self.assertIsNotNone(checked.semantic)
        self.assertIsNotNone(checked.ownership_sir)
        self.assertIsNotNone(checked.authority)

    def test_opt_in_analysis_does_not_mutate_or_open_production_release_gate(self):
        module = sotlas_compile.bootstrap.parse(
            self._source(), filename="<state-phase1-immutability>"
        )
        original_spaces = module.state_spaces
        checked = sotlas_compile.analyze_module_phase1(module)
        self.assertIsNotNone(checked.state_spaces)
        self.assertIs(module.state_spaces, original_spaces)
        self.assertEqual(module.state_spaces, original_spaces)

        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"State Spaces estão em PREVIEW.*fail-closed",
        ):
            sotlas_compile.bootstrap.check(module)

    def test_existing_state_edge_does_not_invent_source_transition(self):
        source = """
        module test::state_phase1_no_magic_transition;
        space Device {
            state Discovered
            state Configured
            Discovered -> Configured
        }
        pub fn configure(dev: Device<Discovered>) -> Device<Configured> {
            return dev;
        }
        """
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<state-phase1-no-magic>"
            )

    def test_unknown_state_fails_before_checked_snapshot_is_created(self):
        source = """
        module test::state_phase1_unknown;
        space Device { state Ready }
        pub fn inspect(dev: Device<Missing>) -> void { return; }
        """
        with self.assertRaisesRegex(
            state_frontend.StateSpaceFrontendError,
            r"Device<Missing> references unknown state",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<state-phase1-unknown>"
            )

    def test_ordinary_module_keeps_state_snapshot_absent(self):
        checked = sotlas_compile.analyze_source_phase1(
            "module test::ordinary_phase1; pub fn value() -> u32 { return 7; }",
            filename="<ordinary-phase1>",
        )
        self.assertIsNone(checked.state_spaces)


if __name__ == "__main__":
    unittest.main()
