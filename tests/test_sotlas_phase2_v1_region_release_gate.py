"""Sotlas 1.0 release gate for the minimum executable REGION contract.

This is intentionally narrower than the complete REGION roadmap. The 1.0 gate
requires the supported subset to keep its backend-neutral arena proof *and* to
execute through the C11 reference backend with deterministic ownership cleanup.
Those are two independent contracts: the isolated Phase-1 pipeline does not
pretend to support every C11-only bootstrap construct used by native probes.
Broader arena/CFG/runtime generalizations remain eligible for 1.0.x.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_phase2_v1_region_gate_package"
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


package = _load_package()
bootstrap = importlib.import_module(f"{package.__name__}.bootstrap")
closed = importlib.import_module(
    f"{package.__name__}.region_closed_interprocedural"
)


REGION_SEMANTIC_SOURCE = """module app::region_v1_semantic_gate;
sole struct Token { value: u32; }

fn consume(token: region Token) -> void { return; }

fn run(source: region Token, destination: region Token, final: region Token) -> void {
    consume(move destination);
    handover source to destination;
    consume(move final);
    handover destination to final;
    return;
}
"""


REGION_NATIVE_SOURCE = """module app::region_v1_native_gate;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;

fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}

fn consume(token: region Token) -> void { return; }

fn main() -> i32 {
    let source: region Token = Token { value: 41u32 };
    let destination: region Token = Token { value: 9u32 };
    consume(move destination);
    handover source to destination;
    if destination.value == 41u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
"""


def _host_c_compiler() -> Path:
    resolved = shutil.which("gcc") or shutil.which("clang")
    if resolved is None:
        raise unittest.SkipTest("host GCC/Clang not available")
    return Path(resolved)


class SotlasPhase2V1RegionReleaseGateTests(unittest.TestCase):
    def test_region_supported_subset_has_complete_backend_neutral_arena_proof(self):
        checked = package.analyze_source_phase1(
            REGION_SEMANTIC_SOURCE,
            filename="<phase2-v1-region-semantic-gate>",
        )
        plan = closed.plan_checked_region_closed_interprocedural(checked)
        flow = plan.require_complete_arena_flow()
        self.assertTrue(flow.complete)
        self.assertEqual(flow.unresolved, ())

    def test_region_supported_subset_runs_natively_with_deterministic_cleanup(self):
        # emit_c_project resolves the bootstrap project root by walking from the
        # source path until it finds core/. Keep the probe inside bootstrap/sotlas
        # exactly like the established native backend tests do.
        source_file = ROOT / "bootstrap" / "sotlas" / "test_phase2_v1_region_gate_temp.sotlas"
        output_c = ROOT / "build" / "test_phase2_v1_region_gate.c"
        executable = ROOT / "build" / (
            "test_phase2_v1_region_gate.exe"
            if os.name == "nt"
            else "test_phase2_v1_region_gate"
        )
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(output_c.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(REGION_NATIVE_SOURCE, encoding="utf-8")

        bootstrap.emit_c_project(source_file, output_c)
        self.assertTrue(output_c.exists())

        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [
                str(compiler),
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(output_c),
                "-o",
                str(executable),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)

        executed = subprocess.run(
            [str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)


if __name__ == "__main__":
    unittest.main()
