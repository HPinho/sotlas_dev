"""Phase 4: backend-neutral typestate semantics over State Spaces."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_module(name: str):
    package = "sotlas_typestate_package"
    if package not in sys.modules:
        package_spec = importlib.util.spec_from_file_location(
            package,
            PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(PACKAGE_DIR)],
        )
        assert package_spec is not None and package_spec.loader is not None
        package_module = importlib.util.module_from_spec(package_spec)
        sys.modules[package] = package_module
        package_spec.loader.exec_module(package_module)
    module_name = f"{package}.{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name,
        PACKAGE_DIR / f"{name}.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


state_space = _load_module("state_space")
typestate = _load_module("state_typestate")
state_sir = _load_module("state_sir")
canonical_sir = _load_module("canonical_sir")


class TypestateTests(unittest.TestCase):
    def _device_space(self):
        return state_space.certify_state_space(
            "DeviceLifecycle",
            (
                state_space.StateSpaceState("Discovered"),
                state_space.StateSpaceState("Configured"),
                state_space.StateSpaceState("Running"),
            ),
            (
                state_space.StateSpaceTransition("Discovered", "Configured"),
                state_space.StateSpaceTransition("Configured", "Running"),
            ),
        )

    def test_typestate_can_bind_nominal_type_to_certified_state(self):
        space = self._device_space()
        discovered = typestate.certify_typestate(space, "Device", "Discovered")
        self.assertEqual(discovered.display(), "Device<Discovered>")
        self.assertEqual(discovered.space_name, "DeviceLifecycle")

    def test_typestate_boundary_requires_exact_state(self):
        space = self._device_space()
        configured = typestate.certify_typestate(space, "Device", "Configured")
        discovered = typestate.certify_typestate(space, "Device", "Discovered")
        self.assertIs(
            typestate.require_typestate(configured, configured),
            configured,
        )
        with self.assertRaisesRegex(
            typestate.TypestateError,
            r"requires Device<Configured>, received Device<Discovered>",
        ):
            typestate.require_typestate(configured, discovered)

    def test_transition_follows_only_declared_state_space_edge(self):
        space = self._device_space()
        discovered = typestate.certify_typestate(space, "Device", "Discovered")
        configured_fact = typestate.transition_typestate(
            space,
            discovered,
            "Configured",
        )
        self.assertEqual(configured_fact.source, discovered)
        self.assertEqual(configured_fact.target.display(), "Device<Configured>")
        running_fact = typestate.transition_typestate(
            space,
            configured_fact.target,
            "Running",
        )
        self.assertEqual(running_fact.target.display(), "Device<Running>")

    def test_certified_transition_lowers_to_source_stable_sir(self):
        space = self._device_space()
        discovered = typestate.certify_typestate(space, "Device", "Discovered")
        fact = typestate.transition_typestate(
            space,
            discovered,
            "Configured",
            point_id="state_transition@12:9",
        )
        sir = canonical_sir.load_canonical_sir()
        instruction = state_sir.lower_typestate_transition(
            space,
            fact,
            sir.SIRValue("device", "Device<Discovered>"),
            "configured_device",
        )
        self.assertIsInstance(instruction, sir.StateTransitionInst)
        self.assertEqual(instruction.result.type_name, "Device<Configured>")
        self.assertEqual(instruction.point_id, "state_transition@12:9")
        self.assertIn("Discovered->Configured", str(instruction))

        forged = typestate.TypestateTransitionFact(
            source=fact.source,
            target=fact.target,
            transition=state_space.StateSpaceTransition(
                "Configured", "Running"
            ),
            point_id=fact.point_id,
        )
        with self.assertRaisesRegex(
            state_sir.StateTransitionSIRError,
            "edge diverges from the certified State Space",
        ):
            state_sir.lower_typestate_transition(
                space,
                forged,
                sir.SIRValue("device", "Device<Discovered>"),
                "configured_device",
            )

    def test_transition_sir_rejects_missing_or_wrong_source_identity(self):
        space = self._device_space()
        discovered = typestate.certify_typestate(space, "Device", "Discovered")
        missing_identity = typestate.transition_typestate(
            space, discovered, "Configured"
        )
        sir = canonical_sir.load_canonical_sir()
        with self.assertRaisesRegex(
            state_sir.StateTransitionSIRError,
            "requires source-stable identity",
        ):
            state_sir.lower_typestate_transition(
                space,
                missing_identity,
                sir.SIRValue("device", "Device<Discovered>"),
                "configured_device",
            )

        sourced = typestate.transition_typestate(
            space,
            discovered,
            "Configured",
            point_id="state_transition@12:9",
        )
        with self.assertRaisesRegex(
            state_sir.StateTransitionSIRError,
            "source must have type Device<Discovered>",
        ):
            state_sir.lower_typestate_transition(
                space,
                sourced,
                sir.SIRValue("device", "Device<Running>"),
                "configured_device",
            )

    def test_transition_cannot_skip_required_state(self):
        space = self._device_space()
        discovered = typestate.certify_typestate(space, "Device", "Discovered")
        with self.assertRaisesRegex(
            typestate.TypestateError,
            r"invalid typestate transition for Device: Discovered -> Running",
        ):
            typestate.transition_typestate(space, discovered, "Running")

    def test_transition_does_not_invent_implicit_self_edge(self):
        space = self._device_space()
        configured = typestate.certify_typestate(space, "Device", "Configured")
        with self.assertRaisesRegex(
            typestate.TypestateError,
            r"Configured -> Configured",
        ):
            typestate.transition_typestate(space, configured, "Configured")

    def test_typestate_rejects_unknown_state(self):
        space = self._device_space()
        with self.assertRaisesRegex(
            typestate.TypestateError,
            r"Device<Closed> references unknown state",
        ):
            typestate.certify_typestate(space, "Device", "Closed")

    def test_typestate_cannot_cross_state_spaces(self):
        device_space = self._device_space()
        job_space = state_space.certify_state_space(
            "JobLifecycle",
            (
                state_space.StateSpaceState("Configured"),
                state_space.StateSpaceState("Running"),
            ),
            (state_space.StateSpaceTransition("Configured", "Running"),),
        )
        configured_device = typestate.certify_typestate(
            device_space,
            "Device",
            "Configured",
        )
        with self.assertRaisesRegex(
            typestate.TypestateError,
            r"belongs to state space 'DeviceLifecycle', not 'JobLifecycle'",
        ):
            typestate.transition_typestate(
                job_space,
                configured_device,
                "Running",
            )

    def test_nominal_base_type_mismatch_is_rejected(self):
        space = self._device_space()
        expected = typestate.certify_typestate(space, "Device", "Configured")
        actual = typestate.certify_typestate(space, "Socket", "Configured")
        with self.assertRaisesRegex(
            typestate.TypestateError,
            r"requires Device<Configured>, received Socket<Configured>",
        ):
            typestate.require_typestate(expected, actual)


if __name__ == "__main__":
    unittest.main()
