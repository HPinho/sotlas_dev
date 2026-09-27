from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SotlasFlowRunCliTests(unittest.TestCase):
    def _run(self, source: str, *arguments: str):
        temporary = tempfile.TemporaryDirectory(prefix="sotlas-flow-run-")
        self.addCleanup(temporary.cleanup)
        source_path = Path(temporary.name) / "flow.sotlas"
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
                "flow-run",
                str(source_path),
                *arguments,
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

    def test_runs_canonical_parallel_scalar_flow_and_prints_stage_outputs(self):
        result = self._run(
            """module test::flow_run;
fn load() -> u32 { return 4u32; }
fn double(value: u32) -> u32 { return value * 2u32; }
fn increment(value: u32) -> u32 { return value + 1u32; }
fn sum(left: u32, right: u32) -> u32 { return left + right; }
flow Compute {
    stage seed = load;
    stage left = double after seed;
    stage right = increment after seed;
    stage final = sum after left, right;
}
""",
            "--flow",
            "Compute",
            "--workers",
            "2",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "sotlas.flow-result.v1")
        self.assertEqual(report["module"], "test::flow_run")
        self.assertEqual(report["flow"], "Compute")
        self.assertEqual(
            report["outputs"],
            {"seed": 4, "left": 8, "right": 5, "final": 13},
        )

    def test_reports_unknown_plan_without_success_json(self):
        result = self._run(
            """module test::flow_run_missing;
fn load() -> u32 { return 4u32; }
flow Compute { stage seed = load; }
""",
            "--flow",
            "Missing",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Flow execution failed", result.stderr)

    def test_rejects_invalid_worker_count(self):
        result = self._run(
            """module test::flow_run_workers;
fn load() -> u32 { return 4u32; }
flow Compute { stage seed = load; }
""",
            "--flow",
            "Compute",
            "--workers",
            "0",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("max_workers must be a positive integer", result.stderr)


if __name__ == "__main__":
    unittest.main()
