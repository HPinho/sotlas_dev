from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SotlasContractReportCliTests(unittest.TestCase):
    def test_contract_report_separates_static_proofs_from_runtime_guards(self):
        source = """
module test::contract_report;
fn nonzero(value: i32) -> i32
    requires value != 0
{
    return value;
}
fn positive(value: i32) -> i32
    ensures result > 0
{
    return nonzero(value);
}
fn entry() -> i32 { return nonzero(2); }
"""
        with tempfile.TemporaryDirectory(prefix="sotlas_contract_report_") as temp:
            source_path = Path(temp) / "report.sotlas"
            source_path.write_text(source, encoding="utf-8")
            environment = os.environ.copy()
            compiler_path = str(ROOT / "compiler")
            tools_path = str(ROOT / "tools")
            environment["PYTHONPATH"] = os.pathsep.join(
                (compiler_path, tools_path, environment.get("PYTHONPATH", ""))
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "compiler" / "sotlas" / "cli.py"),
                    "contract-report",
                    str(source_path),
                ],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "sotlas.contract-report.v1")
        self.assertEqual(report["module"], "test::contract_report")
        self.assertEqual(len(report["proofs"]), 1)
        self.assertEqual(report["proofs"][0]["status"], "proven")
        self.assertEqual(report["proofs"][0]["function"], "nonzero")
        self.assertEqual(
            report["runtime_preconditions"],
            [{"function": "nonzero", "predicate": "(value != 0)"}],
        )
        self.assertEqual(
            report["runtime_postconditions"],
            [{"function": "positive", "predicate": "(result > 0)"}],
        )


if __name__ == "__main__":
    unittest.main()
