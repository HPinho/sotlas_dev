"""Source profile to concrete execution-target contract."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas.execution_target import ExecutionTargetError
from sotlas.source_target import resolve_source_execution_target


class SotlasSourceExecutionTargetTests(unittest.TestCase):
    def test_barecore_infers_canonical_x86_64_freestanding_target(self):
        plan = resolve_source_execution_target("barecore")
        self.assertTrue(plan.inferred_target)
        self.assertEqual(plan.selected_target, "x86_64-freestanding")
        self.assertEqual(
            plan.execution_target.triple,
            "x86_64-unknown-none-elf",
        )
        self.assertTrue(plan.is_freestanding)

    def test_barecore_accepts_explicit_aarch64_freestanding_target(self):
        plan = resolve_source_execution_target(
            "barecore",
            source_profile_explicit=True,
            requested_target="aarch64-freestanding",
            cpu_features=("sve2",),
        )
        self.assertFalse(plan.inferred_target)
        self.assertEqual(
            plan.execution_target.triple,
            "aarch64-unknown-none-elf",
        )
        self.assertEqual(plan.execution_target.cpu_features, ("sve", "sve2"))
        self.assertTrue(plan.is_freestanding)

    def test_barecore_rejects_hosted_target(self):
        with self.assertRaisesRegex(
            ExecutionTargetError,
            "barecore source profile requires a freestanding execution target",
        ):
            resolve_source_execution_target(
                "barecore",
                source_profile_explicit=True,
                requested_target="x86_64-unknown-linux-gnu",
            )

    def test_explicit_native_rejects_freestanding_target(self):
        with self.assertRaisesRegex(
            ExecutionTargetError,
            "explicit native source profile cannot use a freestanding execution target",
        ):
            resolve_source_execution_target(
                "native",
                source_profile_explicit=True,
                requested_target="x86_64-freestanding",
            )

    def test_implicit_native_keeps_legacy_explicit_freestanding_override(self):
        plan = resolve_source_execution_target(
            "native",
            source_profile_explicit=False,
            requested_target="x86_64-freestanding",
        )
        self.assertEqual(
            plan.execution_target.triple,
            "x86_64-unknown-none-elf",
        )
        self.assertTrue(plan.is_freestanding)

    def test_native_without_requested_target_remains_hosted(self):
        plan = resolve_source_execution_target("native")
        self.assertTrue(plan.inferred_target)
        self.assertEqual(plan.selected_target, "host")
        self.assertEqual(plan.execution_target.triple, "x86_64-pc-none")
        self.assertFalse(plan.is_freestanding)

    def test_web_remains_fail_closed_for_native_machine_targets(self):
        with self.assertRaisesRegex(
            ExecutionTargetError,
            "web source profile is not supported by native execution targets",
        ):
            resolve_source_execution_target("web")

    def test_unknown_source_profile_is_rejected(self):
        with self.assertRaisesRegex(
            ExecutionTargetError,
            "unsupported source target profile",
        ):
            resolve_source_execution_target("firmware")

    def test_compiler_and_tools_source_target_contracts_remain_identical(self):
        compiler_contract = (
            ROOT / "compiler" / "sotlas" / "source_target.py"
        ).read_text(encoding="utf-8")
        tools_contract = (
            ROOT / "tools" / "sotlas" / "source_target.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(compiler_contract, tools_contract)


if __name__ == "__main__":
    unittest.main()
