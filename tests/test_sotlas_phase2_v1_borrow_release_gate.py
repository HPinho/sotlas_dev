"""Sotlas 1.0 release gate for call-scoped non-owning borrows.

The 1.0 contract intentionally freezes only the already-supported forms:
``direct`` provides zero-bookkeeping call-scoped access and ``whisper`` provides
non-owning const access/forwarding. Stored weak references, general FFI borrow
ABIs and broader lifetime invalidation are not release blockers when rejected
fail-closed.
"""
from __future__ import annotations

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
    name = "sotlas_phase2_v1_borrow_gate_package"
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
bootstrap = package.bootstrap


DIRECT_SOURCE = """module app::phase2_v1_direct_gate;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 { return token.value; }
fn call(token: Token) -> u32 { return inspect(&token); }
fn main() -> i32 {
    let token: Token = Token { value: 41u32 };
    if call(move token) == 41u32 { return 0; }
    return 1;
}
"""


WHISPER_SOURCE = """module app::phase2_v1_whisper_gate;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return token.value; }
fn forward(token: whisper Token) -> u32 { return inspect(token); }
fn call(token: Token) -> u32 { return forward(&token); }
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 37;
    if call(move token) == 37u32 { return 0; }
    return 1;
}
"""


def _host_c_compiler() -> Path:
    resolved = shutil.which("gcc") or shutil.which("clang")
    if resolved is None:
        raise unittest.SkipTest("host GCC/Clang not available")
    return Path(resolved)


class SotlasPhase2V1BorrowReleaseGateTests(unittest.TestCase):
    def _compile_and_run(self, source_text: str, stem: str) -> str:
        source = ROOT / "bootstrap" / "sotlas" / f"{stem}_temp.sotlas"
        output_c = ROOT / "build" / f"{stem}.c"
        executable = ROOT / "build" / (f"{stem}.exe" if os.name == "nt" else stem)
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(output_c.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text(source_text, encoding="utf-8")

        bootstrap.emit_c_project(source, output_c)
        generated = output_c.read_text(encoding="utf-8")

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
        return generated

    def test_direct_v1_subset_runs_as_call_scoped_zero_bookkeeping_access(self):
        generated = self._compile_and_run(
            DIRECT_SOURCE,
            "test_phase2_v1_direct_gate",
        )
        self.assertIn("inspect", generated)

    def test_whisper_v1_subset_runs_as_const_non_owning_access(self):
        generated = self._compile_and_run(
            WHISPER_SOURCE,
            "test_phase2_v1_whisper_gate",
        )
        self.assertIn("const Token * token", generated)
        self.assertIn("token->value", generated)


if __name__ == "__main__":
    unittest.main()
