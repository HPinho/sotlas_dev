"""Phase 4: backend-neutral State Space graph semantics."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_state_space():
    package = "sotlas_state_space_package"
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
    module_name = f"{package}.state_space"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name,
        PACKAGE_DIR / "state_space.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


state_space = _load_state_space()


def _download_plan():
    payload = state_space.StateSpacePayload
    state = state_space.StateSpaceState
    edge = state_space.StateSpaceTransition
    return state_space.certify_state_space(
        "Download",
        (
            state("idle"),
            state("downloading", (payload("Percent", "progress"),)),
            state("paused", (payload("Percent", "progress"),)),
            state("completed", (payload("File"),)),
            state("failed", (payload("Error"),)),
        ),
        (
            edge("idle", "downloading"),
            edge("downloading", "paused"),
            edge("paused", "downloading"),
            edge("downloading", "completed"),
            edge("downloading", "failed"),
        ),
    )


class SotlasStateSpaceTests(unittest.TestCase):
    def test_master_roadmap_download_graph_is_certified_exactly(self):
        plan = _download_plan()
        self.assertEqual(plan.name, "Download")
        self.assertEqual(
            tuple(item.name for item in plan.states),
            ("idle", "downloading", "paused", "completed", "failed"),
        )
        self.assertTrue(plan.allows("idle", "downloading"))
        self.assertTrue(plan.allows("downloading", "paused"))
        self.assertTrue(plan.allows("paused", "downloading"))
        self.assertTrue(plan.allows("downloading", "completed"))
        self.assertTrue(plan.allows("downloading", "failed"))
        self.assertFalse(plan.allows("paused", "completed"))

    def test_payload_contract_preserves_named_and_positional_forms(self):
        plan = _download_plan()
        downloading = plan.state("downloading")
        completed = plan.state("completed")
        self.assertEqual(downloading.payload[0].name, "progress")
        self.assertEqual(downloading.payload[0].type_name, "Percent")
        self.assertIsNone(completed.payload[0].name)
        self.assertEqual(completed.payload[0].type_name, "File")

    def test_successors_and_predecessors_preserve_declared_edge_order(self):
        plan = _download_plan()
        self.assertEqual(
            tuple(item.name for item in plan.successors("downloading")),
            ("paused", "completed", "failed"),
        )
        self.assertEqual(
            tuple(item.name for item in plan.predecessors("downloading")),
            ("idle", "paused"),
        )

    def test_nonexistent_transition_is_compile_time_semantic_error(self):
        plan = _download_plan()
        with self.assertRaisesRegex(
            state_space.StateSpaceError,
            "forbids transition paused -> completed",
        ):
            plan.require_transition("paused", "completed")

    def test_duplicate_state_is_rejected(self):
        state = state_space.StateSpaceState
        with self.assertRaisesRegex(
            state_space.StateSpaceError,
            "repeats state 'idle'",
        ):
            state_space.certify_state_space(
                "Download",
                (state("idle"), state("idle")),
                (),
            )

    def test_transition_to_unknown_state_is_rejected(self):
        state = state_space.StateSpaceState
        edge = state_space.StateSpaceTransition
        with self.assertRaisesRegex(
            state_space.StateSpaceError,
            "unknown target 'missing'",
        ):
            state_space.certify_state_space(
                "Download",
                (state("idle"),),
                (edge("idle", "missing"),),
            )

    def test_duplicate_transition_is_rejected(self):
        state = state_space.StateSpaceState
        edge = state_space.StateSpaceTransition
        with self.assertRaisesRegex(
            state_space.StateSpaceError,
            "repeats transition idle -> downloading",
        ):
            state_space.certify_state_space(
                "Download",
                (state("idle"), state("downloading")),
                (
                    edge("idle", "downloading"),
                    edge("idle", "downloading"),
                ),
            )

    def test_duplicate_named_payload_is_rejected(self):
        payload = state_space.StateSpacePayload
        state = state_space.StateSpaceState
        with self.assertRaisesRegex(
            state_space.StateSpaceError,
            "repeats payload 'progress'",
        ):
            state_space.certify_state_space(
                "Download",
                (
                    state(
                        "downloading",
                        (
                            payload("Percent", "progress"),
                            payload("Percent", "progress"),
                        ),
                    ),
                ),
                (),
            )


if __name__ == "__main__":
    unittest.main()
