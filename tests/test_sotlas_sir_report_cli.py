from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SotlasSIRReportCliTests(unittest.TestCase):
    def _run_report(self, source: str, command: str = "sir-report"):
        temp = tempfile.TemporaryDirectory(prefix="sotlas_sir_report_")
        self.addCleanup(temp.cleanup)
        source_path = Path(temp.name) / "report.sotlas"
        source_path.write_text(source, encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            (str(ROOT / "compiler"), str(ROOT / "tools"),
             environment.get("PYTHONPATH", ""))
        )
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "compiler" / "sotlas" / "cli.py"),
                command,
                str(source_path),
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

    def test_sir_report_is_deterministic_and_summarizes_checked_module(self):
        source = """module test::sir_report;
fn load() -> u32 { return 4u32; }
fn identity(value: u32) -> u32 { return value; }
flow Calculate {
    stage input = load;
    stage output = identity after input;
}
"""
        first = self._run_report(source)
        second = self._run_report(source)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema"], "sotlas.sir-report.v1")
        self.assertEqual(report["representation"], "canonical_checked_subset")
        self.assertEqual(report["module"], "test::sir_report")
        self.assertEqual([item["name"] for item in report["functions"]], ["load", "identity"])
        self.assertEqual(report["flows"], ["Calculate"])
        self.assertEqual(report["summary"]["function_count"], 2)
        self.assertGreater(report["summary"]["block_count"], 0)
        self.assertGreater(report["summary"]["instruction_count"], 0)

    def test_sir_report_rejects_invalid_source_without_partial_json(self):
        result = self._run_report(
            "module test::sir_report_bad; fn broken() -> i32 { return missing; }"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("sir report", result.stderr)

    def test_target_ir_report_is_deterministic_and_preserves_typed_operations(self):
        source = """module test::target_ir;
pub fn sum(left: u32, right: u32) -> u32 { return left + right; }
"""
        first = self._run_report(source, "target-ir-report")
        second = self._run_report(source, "target-ir-report")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema"], "sotlas.target-ir.v1")
        self.assertEqual(report["stage"], "pre_selection")
        function = report["functions"][0]
        self.assertEqual(function["name"], "sum")
        operations = [
            instruction["op"]
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        self.assertIn("add", operations)
        self.assertIn("return", operations)
        self.assertTrue(report["limitations"])

    def test_target_ir_report_fails_closed_for_unlowered_sir_operations(self):
        result = self._run_report(
            """module test::target_ir_bad;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn caller(token: Token) -> void { inspect(&token); return; }
""",
            "target-ir-report",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Target IR v1 does not lower", result.stderr)


if __name__ == "__main__":
    unittest.main()
