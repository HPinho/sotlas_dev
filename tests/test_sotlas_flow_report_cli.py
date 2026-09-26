from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SotlasFlowReportCliTests(unittest.TestCase):
    def test_flow_report_is_deterministic_and_includes_reconciled_provenance(self):
        source = """module test::flow_report;
fn load() -> u32 { return 4u32; }
fn transform(value: u32) -> u32 { return value; }
flow Calculate {
    stage input = load;
    stage output = transform after input;
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas_flow_report_") as temp:
            source_path = Path(temp) / "flow.sotlas"
            source_path.write_text(source, encoding="utf-8")
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                (str(ROOT / "compiler"), str(ROOT / "tools"),
                 environment.get("PYTHONPATH", ""))
            )
            command = [
                sys.executable,
                str(ROOT / "compiler" / "sotlas" / "cli.py"),
                "flow-report",
                str(source_path),
            ]
            first = subprocess.run(
                command, capture_output=True, text=True, env=environment, check=False
            )
            second = subprocess.run(
                command, capture_output=True, text=True, env=environment, check=False
            )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema"], "sotlas.flow-report.v1")
        self.assertEqual(report["module"], "test::flow_report")
        self.assertEqual(report["flows"][0]["schedule"], [["input"], ["output"]])
        self.assertEqual(
            report["flows"][0]["stages"][1]["arguments"],
            [{
                "parameter_index": 0,
                "parameter": "value",
                "type": "u32",
                "producer_stage": "input",
                "producer_function": "load",
            }],
        )

    def test_flow_report_rejects_invalid_checked_source_without_json(self):
        source = """module test::flow_report_invalid;
fn load() -> u32 { return 4u32; }
flow Calculate { stage input = missing; }
"""
        with tempfile.TemporaryDirectory(prefix="sotlas_flow_report_bad_") as temp:
            source_path = Path(temp) / "invalid.sotlas"
            source_path.write_text(source, encoding="utf-8")
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                (str(ROOT / "compiler"), str(ROOT / "tools"),
                 environment.get("PYTHONPATH", ""))
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "compiler" / "sotlas" / "cli.py"),
                    "flow-report",
                    str(source_path),
                ],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("flow report", result.stderr)


if __name__ == "__main__":
    unittest.main()
