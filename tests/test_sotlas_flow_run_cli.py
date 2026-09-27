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

    def test_runs_flow_through_compiled_c11_backend(self):
        result = self._run(
            """module test::flow_run_native;
fn load() -> u32 { return 7u32; }
fn twice(value: u32) -> u32 { return value * 2u32; }
fn ready(value: u32) -> bool { return value == 7u32; }
pub fn main() -> i32 { return 0i32; }
flow Compute {
    stage seed = load;
    stage doubled = twice after seed;
    stage is_ready = ready after seed;
}
""",
            "--flow",
            "Compute",
            "--backend",
            "c11",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "sotlas.flow-result.v1")
        self.assertEqual(report["backend"], "c11")
        self.assertEqual(
            report["outputs"],
            {"seed": 7, "doubled": 14, "is_ready": True},
        )

    def test_c11_flow_runner_reports_f32_and_f64_outputs(self):
        result = self._run(
            """module test::flow_run_native_float;
fn first64() -> f64 { return 1.25f64; }
fn add64(value: f64) -> f64 { return value + 2.25f64; }
fn first32() -> f32 { return 1.5f32; }
fn add32(value: f32) -> f32 { return value + 2.25f32; }
flow DoublePrecision {
    stage seed = first64;
    stage result = add64 after seed;
}
flow SinglePrecision {
    stage seed = first32;
    stage result = add32 after seed;
}
""",
            "--flow",
            "DoublePrecision",
            "--backend",
            "c11",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["backend"], "c11")
        self.assertEqual(report["outputs"], {"seed": 1.25, "result": 3.5})

        single = self._run(
            """module test::flow_run_native_float32;
fn first() -> f32 { return 1.5f32; }
fn add(value: f32) -> f32 { return value + 2.25f32; }
flow SinglePrecision { stage seed = first; stage result = add after seed; }
""",
            "--flow",
            "SinglePrecision",
            "--backend",
            "c11",
        )
        self.assertEqual(single.returncode, 0, single.stderr)
        self.assertEqual(
            json.loads(single.stdout)["outputs"],
            {"seed": 1.5, "result": 3.75},
        )

    def test_published_cpu_example_matches_reference_and_c11(self):
        source_path = ROOT / "examples" / "12_sotlas_by_example" / "04_flow_cpu.sotlas"
        source = source_path.read_text(encoding="utf-8")
        reference = self._run(source, "--flow", "Compute")
        native = self._run(
            source, "--flow", "Compute", "--backend", "c11"
        )

        self.assertEqual(reference.returncode, 0, reference.stderr)
        self.assertEqual(native.returncode, 0, native.stderr)
        self.assertEqual(
            json.loads(reference.stdout)["outputs"],
            json.loads(native.stdout)["outputs"],
        )

    def test_c11_flow_runner_executes_structured_stage_branches(self):
        result = self._run(
            """module test::flow_run_branches;
fn choose(value: u32) -> u32 {
    if value > 4u32 { return value * 2u32; }
    else { return value + 1u32; }
}
fn high() -> u32 { return choose(5u32); }
fn low() -> u32 { return choose(2u32); }
flow Compute {
    stage high = high;
    stage low = low;
}
""",
            "--flow",
            "Compute",
            "--backend",
            "c11",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["backend"], "c11")
        self.assertEqual(report["outputs"], {"high": 10, "low": 3})

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

    def test_rejects_workers_for_serial_c11_backend(self):
        result = self._run(
            """module test::flow_run_native_workers;
fn load() -> u32 { return 4u32; }
flow Compute { stage seed = load; }
""",
            "--flow",
            "Compute",
            "--workers",
            "2",
            "--backend",
            "c11",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("C11 Flow runs in deterministic serial order", result.stderr)


if __name__ == "__main__":
    unittest.main()
