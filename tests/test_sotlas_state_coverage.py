"""Phase 4: backend-neutral exhaustive State Space coverage semantics."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_module(name: str):
    package = "sotlas_state_coverage_package"
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
coverage = _load_module("state_coverage")


class StateCoverageTests(unittest.TestCase):
    def _download_space(self):
        return state_space.certify_state_space(
            "Download",
            (
                state_space.StateSpaceState("idle"),
                state_space.StateSpaceState(
                    "downloading",
                    (
                        state_space.StateSpacePayload(
                            "Percent",
                            name="progress",
                        ),
                    ),
                ),
                state_space.StateSpaceState(
                    "paused",
                    (
                        state_space.StateSpacePayload(
                            "Percent",
                            name="progress",
                        ),
                    ),
                ),
                state_space.StateSpaceState(
                    "completed",
                    (state_space.StateSpacePayload("File"),),
                ),
                state_space.StateSpaceState(
                    "failed",
                    (state_space.StateSpacePayload("Error"),),
                ),
            ),
            (
                state_space.StateSpaceTransition("idle", "downloading"),
                state_space.StateSpaceTransition("downloading", "paused"),
                state_space.StateSpaceTransition("paused", "downloading"),
                state_space.StateSpaceTransition("downloading", "completed"),
                state_space.StateSpaceTransition("downloading", "failed"),
            ),
        )

    def test_complete_coverage_is_certified(self):
        space = self._download_space()
        plan = coverage.require_exhaustive_state_coverage(
            space,
            ("downloading", "idle", "paused", "failed", "completed"),
        )
        self.assertTrue(plan.complete)
        self.assertEqual(plan.coverage_text(), "5/5")
        self.assertEqual(
            plan.arms,
            ("downloading", "idle", "paused", "failed", "completed"),
        )
        self.assertEqual(plan.missing_states, ())

    def test_missing_states_follow_space_declaration_order(self):
        space = self._download_space()
        plan = coverage.analyze_state_coverage(
            space,
            ("downloading", "idle", "completed"),
        )
        self.assertFalse(plan.complete)
        self.assertEqual(plan.coverage_text(), "3/5")
        self.assertEqual(plan.missing_states, ("paused", "failed"))

    def test_exhaustive_gate_rejects_missing_state(self):
        space = self._download_space()
        with self.assertRaisesRegex(
            coverage.StateCoverageError,
            r"incomplete: 4/5; missing: failed",
        ):
            coverage.require_exhaustive_state_coverage(
                space,
                ("idle", "downloading", "paused", "completed"),
            )

    def test_duplicate_state_arm_is_rejected(self):
        space = self._download_space()
        with self.assertRaisesRegex(
            coverage.StateCoverageError,
            r"repeats state 'idle'",
        ):
            coverage.analyze_state_coverage(space, ("idle", "idle"))

    def test_unknown_state_arm_is_rejected(self):
        space = self._download_space()
        with self.assertRaisesRegex(
            coverage.StateCoverageError,
            r"references unknown state 'verifying'",
        ):
            coverage.analyze_state_coverage(space, ("idle", "verifying"))

    def test_payload_states_still_count_as_one_state_each(self):
        space = self._download_space()
        plan = coverage.analyze_state_coverage(
            space,
            ("idle", "downloading", "paused"),
        )
        self.assertEqual(plan.covered_count, 3)
        self.assertEqual(plan.total_count, 5)
        self.assertEqual(plan.missing_states, ("completed", "failed"))

    def test_non_tuple_arms_fail_closed(self):
        space = self._download_space()
        with self.assertRaisesRegex(
            coverage.StateCoverageError,
            r"source-ordered tuple",
        ):
            coverage.analyze_state_coverage(space, ["idle"])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
