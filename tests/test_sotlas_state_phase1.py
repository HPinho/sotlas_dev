"""Phase 4: State Spaces composed into the public Phase-1 semantic pipeline."""
from __future__ import annotations

import importlib
import importlib.util
from dataclasses import replace
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

        sole struct Device {
            id: u32;
        }

        pub space Device {
            state Discovered
            state Configured
            Discovered -> Configured
        }

        pub fn inspect(dev: Device<Discovered>) -> Device<Discovered> {
            return move(dev);
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

    def test_typed_state_snapshot_preserves_explicit_initial_state(self):
        source = self._source().replace(
            "state Discovered", "initial state Discovered"
        )
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<state-phase1-initial>"
        )
        self.assertEqual(
            checked.state_spaces.space("Device").initial_state,
            "Discovered",
        )

    def test_production_checker_accepts_backend_representable_state_types(self):
        module = sotlas_compile.bootstrap.parse(
            self._source(), filename="<state-phase1-immutability>"
        )
        original_spaces = module.state_spaces
        checked = sotlas_compile.analyze_module_phase1(module)
        self.assertIsNotNone(checked.state_spaces)
        self.assertIs(module.state_spaces, original_spaces)
        self.assertEqual(module.state_spaces, original_spaces)

        sotlas_compile.bootstrap.check(module)
        self.assertIsNotNone(module.state_space_typed_snapshot)

    def test_source_transition_compiles_to_the_same_c_representation(self):
        source = """
        module test::state_transition_release;

        sole struct Device {
            id: u32;
        }

        space Device {
            state Discovered
            state Configured
            Discovered -> Configured
        }

        pub fn configure(device: Device<Discovered>) -> Device<Configured> {
            unsafe {
                return transition(move(device), Configured);
            }
        }
        """
        module = sotlas_compile.bootstrap.parse(
            source, filename="<state-transition-release>"
        )
        sotlas_compile.bootstrap.check(module)
        checked_module = sotlas_compile.analyze_module_phase1(module)
        self.assertEqual(len(module.state_transition_facts), 1)
        function_name, point_id, binding, fact = module.state_transition_facts[0]
        self.assertEqual(function_name, "configure")
        self.assertEqual(binding, "device")
        self.assertRegex(point_id, r"^state_transition@\d+:\d+$")
        self.assertEqual(fact.source.display(), "Device<Discovered>")
        self.assertEqual(fact.target.display(), "Device<Configured>")

        self.assertIsNotNone(checked_module.state_spaces)
        generated = sotlas_compile.bootstrap.emit_c(module)
        self.assertIn("Device configure", generated)

    def test_checked_source_transition_lowers_into_verified_canonical_sir(self):
        source = """
        module test::state_transition_sir;
        sole struct Device { id: u32; }
        space Device {
            state Discovered
            state Configured
            Discovered -> Configured
        }
        pub fn configure(device: Device<Discovered>) -> Device<Configured> {
            unsafe { return transition(move(device), Configured); }
        }
        """
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<state-transition-sir>"
        )
        canonical_bridge = importlib.import_module(
            f"{sotlas_compile.__name__}.canonical_sir"
        )
        canonical_sir = canonical_bridge.load_canonical_sir()
        checked_sir, _ = canonical_bridge.build_canonical_checked_ownership_sir(
            checked
        )
        function = checked_sir.module.functions[0]
        instructions = function.blocks[0].instructions
        transition = next(
            instruction for instruction in instructions
            if isinstance(instruction, canonical_sir.StateTransitionInst)
        )
        self.assertEqual(transition.source.type_name, "Device<Discovered>")
        self.assertEqual(transition.result.type_name, "Device<Configured>")
        self.assertRegex(transition.point_id, r"^state_transition@\d+:\d+$")

        bad_module = sotlas_compile.bootstrap.parse(
            source, filename="<state-transition-sir-mismatch>"
        )
        importlib.import_module(
            f"{sotlas_compile.__name__}.state_typed_ast"
        ).check_state_space_preview_semantics(
            bad_module, sotlas_compile.bootstrap
        )
        bad_module.functions[0].result = replace(
            bad_module.functions[0].result,
            state_name="Discovered",
        )
        with self.assertRaisesRegex(
            ValueError,
            "target state diverges from function result",
        ):
            generator_type = importlib.import_module(
                f"{sotlas_compile.__name__}.region_return_cfg_generator"
            ).make_region_return_cfg_generator(canonical_sir)
            generator_type(
                module_name=bad_module.name
            ).generate_from_ast(bad_module)

    def test_source_transition_rejects_missing_edge_and_safe_context(self):
        prefix = """
        module test::state_transition_reject;
        sole struct Device { id: u32; }
        space Device {
            state Discovered
            state Configured
            Discovered -> Configured
        }
        """
        missing_edge = prefix.replace(
            "Discovered -> Configured\n", ""
        ) + """
        fn configure(device: Device<Discovered>) -> Device<Configured> {
            unsafe { return transition(move(device), Configured); }
        }
        """
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"invalid typestate transition for Device: Discovered -> Configured",
        ):
            sotlas_compile.analyze_module_phase1(
                sotlas_compile.bootstrap.parse(missing_edge)
            )

        safe_context = prefix + """
        fn configure(device: Device<Discovered>) -> Device<Configured> {
            return transition(move(device), Configured);
        }
        """
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "requires an unsafe block",
        ):
            sotlas_compile.analyze_module_phase1(
                sotlas_compile.bootstrap.parse(safe_context)
            )

    def test_existing_state_edge_does_not_invent_source_transition(self):
        source = """
        module test::state_phase1_no_magic_transition;
        sole struct Device { id: u32; }
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
            importlib.import_module(
                f"{sotlas_compile.__name__}.typed_ast"
            ).Phase1SemanticError,
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
