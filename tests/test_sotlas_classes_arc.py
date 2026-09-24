"""Integration tests for classes/ARC with portable process-exit assertions.

The recovered historical suite lives in ``sotlas_classes_arc_impl.py``.  This
wrapper keeps that complete suite discoverable while overriding the one runtime
probe that previously encoded a value larger than the POSIX 8-bit process exit
status.  The replacement preserves the semantic assertion: both deferred
borrows must run before the shared owner is destroyed, and destruction must
occur exactly once.
"""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
_IMPL_PATH = ROOT / "tests" / "sotlas_classes_arc_impl.py"
_IMPL_NAME = "_sotlas_classes_arc_recovered_impl"
_IMPL_SPEC = importlib.util.spec_from_file_location(_IMPL_NAME, _IMPL_PATH)
assert _IMPL_SPEC is not None and _IMPL_SPEC.loader is not None
legacy = importlib.util.module_from_spec(_IMPL_SPEC)
sys.modules[_IMPL_NAME] = legacy
_IMPL_SPEC.loader.exec_module(legacy)


class SotlasClassesAndArcTests(legacy.SotlasClassesAndArcTests):
    def test_shared_deferred_direct_free_call_runs_before_arc_destroy(self):
        source = (
            legacy.ROOT
            / "bootstrap"
            / "sotlas"
            / "test_shared_defer_direct_temp.sotlas"
        )
        executable = legacy.ROOT / "build" / "test_shared_defer_direct.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_defer_direct;
import core::arc::*;
static mut observed_sum: u32 = 0;
static mut destroyed: u32 = 0;
sole struct Token { value: u32; }
fn inspect(token: direct Token, snapshot: whisper Token, bias: u32) -> void {
    unsafe { observed_sum = observed_sum + token.value + snapshot.value + bias; }
}
fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroyed = destroyed + 1u32; self.value = 0; }
}
fn run(token: Token) -> void {
    let peer = share token;
    for index in 0u32..2u32 {
        defer inspect(&peer, &peer, index);
        if index == 0u32 { continue; }
        break;
    }
    return;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 7;
    run(move token);
    if observed_sum == 29u32 && destroyed == 1u32 { return 0; }
    return 1;
}
""", encoding="utf-8")
        legacy.bootstrap.emit_c_project(source, self.output_c)
        compiler = legacy._host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
