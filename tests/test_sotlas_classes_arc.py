"""Testes unitários e de integração para Classes, Métodos e ARC (Fase E)."""
import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Load production compiler under a unique package name so legacy tests that
# import tools/sotlas_compile cannot hijack this integration test's backend.
_PROD_PACKAGE = "_sotlas_compile_production_arc_test"
_PROD_DIR = ROOT / "compiler" / "sotlas_compile"
_PROD_SPEC = importlib.util.spec_from_file_location(
    _PROD_PACKAGE,
    _PROD_DIR / "__init__.py",
    submodule_search_locations=[str(_PROD_DIR)],
)
assert _PROD_SPEC is not None and _PROD_SPEC.loader is not None
_PROD_MODULE = importlib.util.module_from_spec(_PROD_SPEC)
sys.modules[_PROD_PACKAGE] = _PROD_MODULE
_PROD_SPEC.loader.exec_module(_PROD_MODULE)
bootstrap = _PROD_MODULE.bootstrap


def _host_c_compiler() -> Path:
    resolved = shutil.which("gcc") or shutil.which("clang") or shutil.which("cl")
    if resolved is None:
        for candidate in (
            Path(r"C:\Program Files\LLVM\bin\clang.exe"),
            Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\14.16.27023\bin\HostX64\x64\cl.exe"),
        ):
            if candidate.is_file():
                resolved = str(candidate)
                break
    if resolved is None:
        raise unittest.SkipTest("host C compiler not available")
    return Path(resolved)


class SotlasClassesAndArcTests(unittest.TestCase):
    def setUp(self):
        self.output_c = ROOT / "build" / "test_classes_arc.c"
        self.output_o = ROOT / "build" / "test_classes_arc.o"

    def tearDown(self):
        self.output_c.unlink(missing_ok=True)
        self.output_o.unlink(missing_ok=True)

    def test_loop_local_shared_allocation_cleans_continue_and_break(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_loop_control_temp.sotlas"
        executable = ROOT / "build" / "test_shared_loop_control.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_loop_control;
import core::arc::*;
static mut dropped_sum: u32 = 0;
sole struct Token { value: u32; }
fn Token_deinit(self: *mut Token) -> void {
    unsafe { dropped_sum = dropped_sum + self.value; }
}
fn main() -> i32 {
    for index in 0u32..3u32 {
        let token: Token = Token { value: index + 1u32 };
        let peer = share token;
        if peer.value == 0u32 { break; }
        if index == 0u32 { continue; }
        if index == 1u32 { break; }
    }
    return dropped_sum as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 3, executed.stderr)

    def test_loop_local_shared_allocation_cleans_before_early_return(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_loop_return_temp.sotlas"
        executable = ROOT / "build" / "test_shared_loop_return.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_loop_return;
import core::arc::*;
static mut dropped_sum: u32 = 0;
sole struct Token { value: u32; }
fn Token_deinit(self: *mut Token) -> void {
    unsafe { dropped_sum = dropped_sum + self.value; }
}
fn run() -> u32 {
    for index in 0u32..3u32 {
        let token: Token = Token { value: index + 1u32 };
        let peer = share token;
        if index == 0u32 { return peer.value; }
    }
    return 0u32;
}
fn main() -> i32 {
    return (run() as i32 * 10) + dropped_sum as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 11, executed.stderr)

    def test_whisper_parameter_is_lowered_as_const_non_owning_pointer(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_whisper_param_temp.sotlas"
        executable = ROOT / "build" / "test_whisper_param.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::whisper_param;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return token.value; }
fn forward(token: whisper Token) -> u32 { return inspect(token); }
fn call(token: Token) -> u32 { return forward(&token); }
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 37;
    return call(move token) as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("const Token * token", generated)
        self.assertIn("token->value", generated)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 37, executed.stderr)

    def test_direct_parameter_forwarding_runs_without_ownership_bookkeeping(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_direct_forward_temp.sotlas"
        executable = ROOT / "build" / "test_direct_forward.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::direct_forward;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 { return token.value; }
fn forward(token: direct Token) -> u32 { return inspect(token); }
fn call(token: Token) -> u32 { return forward(&token); }
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 31;
    return call(move token) as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("inspect(token)", generated)
        self.assertIn("forward((&token))", generated)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 31, executed.stderr)

    def test_direct_borrow_forwards_to_verified_whisper_call_in_c11(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_direct_whisper_forward_temp.sotlas"
        executable = ROOT / "build" / "test_direct_whisper_forward.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::direct_whisper_forward;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return token.value; }
fn forward(token: direct Token) -> u32 { return inspect(token); }
fn call(token: Token) -> u32 { return forward(&token); }
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 43;
    return call(move token) as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 43, executed.stderr)

    def test_whisper_method_receiver_is_lowered_as_const_borrow(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_whisper_receiver_temp.sotlas"
        executable = ROOT / "build" / "test_whisper_receiver.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::whisper_receiver;
sole struct Token {
    value: u32;
    fn read(self: whisper Token) -> u32 { return self.value; }
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 29;
    return token.read() as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("const Token * self", generated)
        self.assertIn("Token_read(&(token))", generated)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 29, executed.stderr)

    def test_loop_local_shared_allocation_releases_on_each_fallthrough(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_loop_fallthrough_temp.sotlas"
        executable = ROOT / "build" / "test_shared_loop_fallthrough.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_loop_fallthrough;
import core::arc::*;
static mut dropped_sum: u32 = 0;
sole struct Token { value: u32; }
fn Token_deinit(self: *mut Token) -> void {
    unsafe { dropped_sum = dropped_sum + self.value; }
}
fn main() -> i32 {
    let mut total: u32 = 0;
    for index in 0u32..3u32 {
        let token: Token = Token { value: index + 1u32 };
        let peer = share token;
        let observer = share peer;
        total = total + observer.value;
    }
    return (total as i32 * 10) + dropped_sum as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 66, executed.stderr)

    def test_while_local_shared_allocation_releases_on_each_backedge(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_while_fallthrough_temp.sotlas"
        executable = ROOT / "build" / "test_shared_while_fallthrough.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_while_fallthrough;
import core::arc::*;
static mut dropped_sum: u32 = 0;
sole struct Token { value: u32; }
fn Token_deinit(self: *mut Token) -> void {
    unsafe { dropped_sum = dropped_sum + self.value; }
}
fn main() -> i32 {
    let mut index: u32 = 0;
    let mut total: u32 = 0;
    while index < 3u32 {
        let token: Token = Token { value: index + 1u32 };
        let peer = share token;
        total = total + peer.value;
        index = index + 1u32;
    }
    return (total as i32 * 10) + dropped_sum as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 66, executed.stderr)

    def test_loop_local_shared_allocation_releases_before_break(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_loop_break_temp.sotlas"
        executable = ROOT / "build" / "test_shared_loop_break.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_loop_break;
import core::arc::*;
static mut dropped_sum: u32 = 0;
sole struct Token { value: u32; }
fn Token_deinit(self: *mut Token) -> void {
    unsafe { dropped_sum = dropped_sum + self.value; }
}
fn main() -> i32 {
    let mut index: u32 = 0;
    let mut total: u32 = 0;
    loop {
        let token: Token = Token { value: index + 1u32 };
        let peer = share token;
        total = total + peer.value;
        index = index + 1u32;
        if index == 3u32 { break; }
    }
    return (total as i32 * 10) + dropped_sum as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 66, executed.stderr)

    def test_class_declaration_and_method_calls(self):
        source = """
        module test::geometry;

        pub class Point {
            x: i32;
            y: i32;

            pub fn new(px: i32, py: i32) -> Point {
                let mut pt: Point = 0;
                pt.x = px;
                pt.y = py;
                return pt;
            }

            pub fn get_x(self: *const Point) -> i32 {
                unsafe {
                    return self.x;
                }
            }

            pub fn translate(self: *mut Point, dx: i32, dy: i32) {
                unsafe {
                    self.x = self.x + dx;
                    self.y = self.y + dy;
                }
            }
        }

        pub fn run_test() -> i32 {
            let mut p: Point = Point::new(10, 20);
            p.translate(5, -5);
            return p.get_x();
        }
        """
        mod = bootstrap.parse(source)
        bootstrap.check(mod)
        emitted = bootstrap.emit_c(mod)
        self.assertIn("typedef struct Point", emitted)
        self.assertIn("Point_new(10, 20)", emitted)
        self.assertIn("Point_translate(&(p), 5, (-5))", emitted)
        self.assertIn("Point_get_x(&(p))", emitted)

    def test_direct_parameter_runs_as_zero_bookkeeping_c11_access(self):
        source = """module test::direct_access;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 { return token.value; }
fn call(token: Token) -> u32 { return inspect(&token); }
"""
        parsed = bootstrap.parse(source, filename="<direct-access-c11>")
        bootstrap.check(parsed)
        emitted = bootstrap.emit_c(parsed, mangle=False)
        self.output_c.write_text(
            emitted
            + "\nint main(void) { Token value = {37u}; "
              "return call(value) == 37u ? 0 : 1; }\n",
            encoding="utf-8",
        )
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(executable.unlink, missing_ok=True)
        compiler = _host_c_compiler()
        result = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        execution = subprocess.run(
            [str(executable)], capture_output=True, text=True
        )
        self.assertEqual(execution.returncode, 0, execution.stderr)

    def test_shared_owner_can_be_read_through_direct_call_in_c11(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_direct_temp.sotlas"
        executable = ROOT / "build" / "test_shared_direct.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_direct;
import core::arc::*;
static mut destroy_count: u32 = 0;
sole struct Token { value: u32; }
fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroy_count = destroy_count + 1; }
}
fn inspect(left: direct Token, right: direct Token) -> u32 {
    return left.value + right.value;
}
fn read_shared(token: Token) -> u32 {
    let peer = share token;
    return inspect(&peer, &peer);
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 41;
    let value = read_shared(move token);
    if value == 82u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_shared_alias_cannot_be_passed_to_owning_callee_without_handover(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_owning_call_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_owning_call;
import core::arc::*;
sole struct Token { value: u32; }
fn consume(token: Token) -> u32 { return token.value; }
fn read_shared(token: Token) -> u32 {
    let peer = share token;
    return consume(peer);
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "shared owner 'peer' cannot be consumed by sole parameter of 'consume'",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_owner_can_be_read_by_direct_method_receiver_in_c11(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_direct_method_temp.sotlas"
        executable = ROOT / "build" / "test_shared_direct_method.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_direct_method;
import core::arc::*;
static mut destroy_count: u32 = 0;
sole struct Token {
    value: u32;
    fn inspect(self: direct Token) -> u32 { return self.value; }
}
fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroy_count = destroy_count + 1; }
}
fn read_shared(token: Token) -> u32 {
    let peer = share token;
    return peer.inspect();
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 37;
    let value = read_shared(move token);
    if value == 37u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_core_arc_compiles_and_links_cleanly(self):
        entry = ROOT / "bootstrap" / "sotlas" / "core" / "arc.sotlas"
        bootstrap.emit_c_project(entry, self.output_c)
        self.assertTrue(self.output_c.exists())

        gcc = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
        cmd = [str(gcc), "-std=c11", "-Wall", "-Wextra", "-Werror", "-c", str(self.output_c), "-o", str(self.output_o)]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, f"Erro GCC core::arc: {res.stderr}")

    def test_arc_runtime_emits_atomic_reference_count_operations(self):
        entry = ROOT / "bootstrap" / "sotlas" / "core" / "arc.sotlas"
        preamble_before = bootstrap.PREAMBLE
        try:
            # Earlier tests may install architecture-specific wrappers into
            # this process-global preamble. Isolate this project-emission gate.
            bootstrap.PREAMBLE = "/* clean test preamble */"
            bootstrap.emit_c_project(entry, self.output_c)
        finally:
            bootstrap.PREAMBLE = preamble_before
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("__atomic_cmpxchg_u64", generated)
        self.assertIn("__atomic_compare_exchange_n", generated)
        self.assertIn("SOTLAS_ATOMIC_INTRINSICS", generated)
        self.assertNotIn("SOTLAS_X86_64_PRIVILEGED_INTRINSICS", generated)
        self.assertEqual(
            preamble_before,
            bootstrap.PREAMBLE,
            "emitting an ARC project must not mutate the global backend preamble",
        )

    def test_shared_sole_project_emits_arc_box_after_runtime(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_sole_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_sole;
import core::arc::*;
sole struct Token { value: u32; }
pub fn read_shared(token: Token) -> u32 {
    let peer = share token;
    return peer.value;
}
fn unrelated(token: u32) -> u32 {
    return token;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertLess(generated.index("typedef struct ArcHeader"), generated.index("__sotlas_shared_box_Token"))
        self.assertEqual(generated.count("#include <stdlib.h>"), 1)
        self.assertIn("arc_retain(&_st_shared_box_peer->header)", generated)
        self.assertIn("if (arc_retain(&_st_shared_box_peer->header) == NULL) abort();", generated)
        self.assertIn("if (box == NULL) abort();", generated)
        self.assertEqual(generated.count("__sotlas_shared_release_Token(_st_shared_box_peer);"), 2)

    def test_exclusive_handover_reacquisition_destroys_each_owner_once(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_handover_runtime_temp.sotlas"
        executable = ROOT / "build" / "test_handover_runtime.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::handover_runtime;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn discard(token: Token) -> void { return; }
fn reacquire(source: Token, destination: Token) -> Token {
    discard(move destination);
    handover source to destination;
    return destination;
}
fn main() -> i32 {
    let mut source: Token = 0;
    source.value = 37;
    let mut destination: Token = 0;
    destination.value = 0;
    let result = reacquire(move source, move destination);
    let value = result.value;
    discard(move result);
    return (destroy_count as i32 * 10) + value as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("destination = source;", generated)
        self.assertNotIn("Token_deinit(&source)", generated)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 57, executed.stderr)

    def test_shared_alias_chain_runs_with_native_arc_runtime(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_alias_chain_temp.sotlas"
        executable = ROOT / "build" / "test_shared_alias_chain.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_alias_chain;
import core::arc::*;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn read_shared(token: Token) -> u32 {
    let peer = share token;
    let peer2 = share peer;
    return peer2.value;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 41;
    let value: u32 = read_shared(move token);
    return (destroy_count as i32 * 10) + value as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertEqual(generated.count("if (arc_retain(&"), 2)
        self.assertIn("Token_deinit(value);", generated)
        self.assertGreaterEqual(
            generated.count("__sotlas_shared_release_Token("), 4
        )
        gcc = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
        compile_result = subprocess.run(
            [str(gcc), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(
            compile_result.returncode, 0,
            f"shared alias chain did not compile: {compile_result.stderr}",
        )
        run_result = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(
            run_result.returncode, 51,
            f"shared alias chain returned unexpected result: {run_result.stderr}",
        )

    def test_shared_deferred_readonly_method_runs_before_arc_destroy(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_defer_temp.sotlas"
        executable = ROOT / "build" / "test_shared_defer.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_defer;
import core::arc::*;
static mut deferred_count: u32 = 0;
static mut destroy_count: u32 = 0;
sole struct Token {
    value: u32;
    @system fn inspect(&self) -> void {
        unsafe { deferred_count = deferred_count + self.value; }
    }
}
fn Token_deinit(self: *mut Token) -> void {
    unsafe {
        destroy_count = destroy_count + 1;
        self.value = 0;
    }
}
fn run(token: Token, flag: bool) -> void {
    let peer = share token;
    defer peer.inspect();
    defer { peer.inspect(); }
    if flag { return; }
    return;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 3;
    run(move token, true);
    let mut second: Token = 0;
    second.value = 3;
    run(move second, false);
    return (deferred_count as i32 * 10) + destroy_count as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        run_body = generated[generated.rfind("void run("):].split("\n}", 1)[0]
        self.assertEqual(run_body.count("Token_inspect"), 4)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 122, executed.stderr)

    def test_shared_deferred_external_method_remains_fail_closed(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_defer_external_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_defer_external;
import core::arc::*;
sole struct Token {
    value: u32;
    @extern(C) fn inspect(&self) -> void { return; }
}
fn run(token: Token) -> void {
    let peer = share token;
    defer peer.inspect();
    return;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "shared aliases cannot escape or be captured outside their scope",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_direct_call_argument_is_lowered_in_defer(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_direct_defer_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_direct_defer;
import core::arc::*;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn run(token: Token) -> void {
    let peer = share token;
    defer inspect(&peer);
    return;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("inspect((&(", generated)
        self.assertIn("__sotlas_shared_release_Token", generated)

    def test_shared_direct_method_receiver_remains_fail_closed_in_defer(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_direct_method_defer_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_direct_method_defer;
import core::arc::*;
sole struct Token {
    value: u32;
    fn inspect(self: direct Token) -> void { return; }
}
fn run(token: Token) -> void {
    let peer = share token;
    defer peer.inspect();
    return;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "shared aliases cannot escape or be captured outside their scope",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_deferred_whisper_argument_cannot_escape(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_defer_whisper_escape_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_defer_whisper_escape;
import core::arc::*;
sole struct Token { value: u32; }
static mut saved: *const Token = null;
fn inspect(token: direct Token, snapshot: whisper Token) -> void {
    unsafe { saved = snapshot; }
}
fn run(token: Token) -> void {
    let peer = share token;
    defer inspect(&peer, &peer);
    return;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "whisper.*(escape|store|global)",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_deferred_readonly_method_runs_on_loop_control_exits(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_defer_loop_temp.sotlas"
        executable = ROOT / "build" / "test_shared_defer_loop.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_defer_loop;
import core::arc::*;
static mut deferred_count: u32 = 0;
static mut destroy_count: u32 = 0;
sole struct Token {
    value: u32;
    @system fn inspect(&self, bias: u32) -> void {
        unsafe { deferred_count = deferred_count + self.value + bias; }
    }
}
fn Token_deinit(self: *mut Token) -> void {
    unsafe {
        destroy_count = destroy_count + 1;
        self.value = 0;
    }
}
fn run(token: Token) -> void {
    let peer = share token;
    for index in 0u32..2u32 {
        defer peer.inspect(index);
        if index == 0u32 { continue; }
        break;
    }
    return;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 3;
    run(move token);
    return (deferred_count as i32 * 10) + destroy_count as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 71, executed.stderr)

    def test_shared_deferred_method_rejects_arguments_that_reborrow_alias(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_defer_method_alias_arg_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_defer_method_alias_arg;
import core::arc::*;
sole struct Token {
    value: u32;
    fn inspect(&self, value: u32) -> void { return; }
}
fn run(token: Token) -> void {
    let peer = share token;
    defer peer.inspect(peer.value);
    return;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "C11 shared aliases cannot escape or be captured outside their scope",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_owner_cleanup_runs_across_if_return_and_loop_exits(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_cfg_cleanup_temp.sotlas"
        executable = ROOT / "build" / "test_shared_cfg_cleanup.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_cfg_cleanup;
import core::arc::*;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn branch_value(flag: bool, token: Token) -> u32 {
    let peer = share token;
    if flag && peer.value > 0u32 { return peer.value; }
    return peer.value + 1u32;
}
fn branch_both_return(flag: bool, token: Token) -> u32 {
    let peer = share token;
    if flag { return peer.value; }
    else { return peer.value + 1u32; }
}
fn loop_value(token: Token) -> u32 {
    let peer = share token;
    let mut index: u32 = 0;
    while index < 4u32 && peer.value > 0u32 {
        index = index + 1u32;
        if index == 2u32 { continue; }
        if index == 3u32 { break; }
    }
    return peer.value + index;
}
fn main() -> i32 {
    let mut first: Token = 0;
    first.value = 7;
    let first_value = branch_value(true, move first);
    let mut second: Token = 0;
    second.value = 8;
    let second_value = branch_value(false, move second);
    let mut third: Token = 0;
    third.value = 40;
    let third_value = loop_value(move third);
    let mut fourth: Token = 0;
    fourth.value = 10;
    let fourth_value = branch_both_return(false, move fourth);
    return (destroy_count as i32 * 10) + first_value as i32 + second_value as i32 + third_value as i32 + fourth_value as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("if (flag)", generated)
        self.assertIn("while (", generated)
        self.assertGreaterEqual(generated.count("__sotlas_shared_release_Token"), 4)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 110, executed.stderr)

    def test_shared_allocation_inside_conditional_cleans_up_per_branch(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_nested_allocation_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_nested_allocation;
import core::arc::*;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn branch(flag: bool, token: Token) -> u32 {
    if flag {
        let peer = share token;
        return peer.value;
    }
    return token.value;
}
fn main() -> i32 {
    let shared_result = branch(true, Token { value: 41u32 });
    let exclusive_result = branch(false, Token { value: 69u32 });
    if shared_result == 41u32 && exclusive_result == 69u32 && destroy_count == 2u32 {
        return 0;
    }
    return 1;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_shared_deferred_direct_free_call_runs_before_arc_destroy(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_defer_direct_temp.sotlas"
        executable = ROOT / "build" / "test_shared_defer_direct.exe"
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
    return (observed_sum as i32 * 10) + destroyed as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 291, executed.stderr)

    def test_shared_direct_defer_early_return_releases_arc_exactly_once(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_direct_defer_return_temp.sotlas"
        executable = ROOT / "build" / "test_shared_direct_defer_return.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_direct_defer_return;
import core::arc::*;
static mut observed: u32 = 0;
static mut destroyed: u32 = 0;
sole struct Token { value: u32; }
fn inspect(token: direct Token, snapshot: whisper Token, delta: u32) -> void {
    unsafe { observed = token.value + snapshot.value + delta; }
}
fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroyed = destroyed + 1u32; self.value = 0; }
}
fn run(token: Token) -> void {
    let peer = share token;
    defer inspect(&peer, &peer, 5u32);
    return;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.value = 7;
    run(move token);
    return (observed as i32 * 10) + destroyed as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        run_body = generated.split(
            "void run(Token token) {", 1
        )[1].split("\n}", 1)[0]
        self.assertEqual(
            run_body.count("__sotlas_shared_release_Token(_st_shared_box_peer);"),
            2,
            run_body,
        )
        compiler = _host_c_compiler()
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
        self.assertEqual(executed.returncode, 191, executed.stderr)

    def test_shared_nested_block_with_fallthrough_remains_fail_closed(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_nested_fallthrough_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_nested_fallthrough;
import core::arc::*;
sole struct Token { value: u32; }
fn branch(flag: bool, token: Token) -> u32 {
    if flag {
        let peer = share token;
        peer.value;
    }
    return token.value;
}
""", encoding="utf-8")
        with self.assertRaises(bootstrap.SotlasBootstrapError):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_parameter_owner_is_released_on_function_fallthrough(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_param_fallthrough_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_param_fallthrough;
import core::arc::*;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
static mut observed: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn observe(token: direct Token) -> void {
    unsafe { observed = token.value; }
}
fn run(token: Token) -> void {
    let peer = share token;
    defer observe(&peer);
}
fn main() -> i32 {
    let token = Token { value: 73u32 };
    run(move token);
    if destroy_count == 1u32 && observed == 73u32 { return 0; }
    return 1;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
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

    def test_shared_local_owner_cleans_up_on_nested_block_fallthrough(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_nested_local_fallthrough_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_nested_local_fallthrough;
import core::arc::*;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn run(flag: bool) -> u32 {
    if flag {
        let token = Token { value: 37u32 };
        let peer = share token;
        if peer.value == 37u32 { }
    }
    return destroy_count;
}
fn main() -> i32 {
    let skipped = run(false);
    let count = run(true);
    if skipped == 0u32 && count == 1u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_shared_box_supports_nested_non_owning_pod_payload(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_pod_temp.sotlas"
        executable = ROOT / "build" / "test_shared_pod.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_pod;
import core::arc::*;
struct Metadata { code: u32; }
struct Identity { metadata: Metadata; }
sole struct Token { identity: Identity; value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn read_shared(token: Token) -> u32 {
    let peer = share token;
    return peer.identity.metadata.code + peer.value;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.identity.metadata.code = 17;
    token.value = 25;
    let value = read_shared(move token);
    return (destroy_count as i32 * 10) + value as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("Identity identity;", generated)
        self.assertIn("Metadata metadata;", generated)
        self.assertIn("Token_deinit(value);", generated)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 52, executed.stderr)

    def test_shared_box_recursively_destroys_nested_sole_payload(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_nested_sole_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_nested_sole;
import core::arc::*;
sole struct Leaf { code: u32; }
sole struct Metadata { leaves: [[Leaf; 2]; 2]; }
struct Wrapper { metadata: Metadata; }
sole struct Token { wrapper: Wrapper; }
static mut destroy_count: u32 = 0;
static mut destroy_order: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe {
        destroy_count = destroy_count + 1;
        destroy_order = destroy_order * 10u32 + 9u32;
    }
}
fn Leaf_deinit(self: *mut Leaf) {
    unsafe {
        destroy_count = destroy_count + 1;
        destroy_order = destroy_order * 10u32 + self.code;
    }
}
fn read_shared(token: Token) -> u32 {
    let peer = share token;
    return peer.wrapper.metadata.leaves[0][0].code + peer.wrapper.metadata.leaves[0][1].code + peer.wrapper.metadata.leaves[1][0].code + peer.wrapper.metadata.leaves[1][1].code;
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.wrapper.metadata.leaves[0][0].code = 1u32;
    token.wrapper.metadata.leaves[1][0].code = 2u32;
    token.wrapper.metadata.leaves[0][1].code = 3u32;
    token.wrapper.metadata.leaves[1][1].code = 4u32;
    let value = read_shared(move token);
    if value != 10u32 { return 10; }
    if destroy_count != 5u32 { return 20; }
    if destroy_order != 94231u32 { return 30; }
    return 0;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn(
            "Leaf_deinit(value);", generated
        )
        self.assertIn(
            "&value->leaves[__sotlas_drop_index_Metadata_leaves_0 - 1]"
            "[__sotlas_drop_index_Metadata_leaves_1 - 1]",
            generated,
        )
        self.assertIn(
            "__sotlas_shared_drop_Metadata(&value->metadata)", generated
        )
        self.assertIn(
            "__sotlas_shared_drop_Wrapper(&value->wrapper)", generated
        )
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_shared_nonsole_wrapper_deinit_runs_before_owned_children(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_nested_wrapper_deinit_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::shared_nested_wrapper_deinit;
import core::arc::*;
sole struct Child { value: u32; }
struct Wrapper { child: Child; }
sole struct Parent { wrapper: Wrapper; }
static mut destroy_count: u32 = 0;
static mut destroy_order: u32 = 0;
fn Wrapper_deinit(self: *mut Wrapper) {
    unsafe {
        destroy_count = destroy_count + 1u32;
        destroy_order = destroy_order * 10u32 + 8u32;
    }
}
fn Child_deinit(self: *mut Child) {
    unsafe {
        destroy_count = destroy_count + 1u32;
        destroy_order = destroy_order * 10u32 + self.value;
    }
}
fn read_shared(parent: Parent) -> u32 {
    let peer = share parent;
    return peer.wrapper.child.value;
}
fn main() -> i32 {
    let mut parent: Parent = 0;
    parent.wrapper.child.value = 1u32;
    let value = read_shared(move parent);
    if value == 1u32 && destroy_count == 2u32 && destroy_order == 81u32 { return 0; }
    return 1;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_shared_wrapper_deinit_that_accesses_owned_fields_fails_closed(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_nested_deinit_gate_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_nested_deinit_gate;
import core::arc::*;
sole struct Child { value: u32; }
struct Wrapper { child: Child; }
sole struct Parent { wrapper: Wrapper; }
fn Wrapper_deinit(self: *mut Wrapper) {
    unsafe { self.child.value = 2u32; }
}
fn read_shared(parent: Parent) -> u32 {
    let peer = share parent;
    return peer.wrapper.child.value;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "C11 shared allocation has an unsupported payload field in Parent",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_owner_deinit_that_accesses_owned_fields_fails_closed(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_owner_deinit_gate_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_owner_deinit_gate;
import core::arc::*;
sole struct Child { value: u32; }
sole struct Parent { child: Child; }
fn Parent_deinit(self: *mut Parent) {
    unsafe { self.child.value = 2u32; }
}
fn read_shared(parent: Parent) -> u32 {
    let peer = share parent;
    return peer.child.value;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "C11 shared allocation has an unsupported payload field in Parent",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_shared_multidimensional_pointer_payload_remains_fail_closed(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_shared_pointer_array_gate_temp.sotlas"
        self.addCleanup(source.unlink, missing_ok=True)
        source.write_text("""module app::shared_pointer_array_gate;
import core::arc::*;
sole struct Parent { pointers: [[*mut u32; 2]; 2]; }
fn read_shared(parent: Parent) -> u32 {
    let peer = share parent;
    return 0u32;
}
""", encoding="utf-8")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "C11 shared allocation has an unsupported payload field in Parent",
        ):
            bootstrap.emit_c_project(source, self.output_c)

    def test_deferred_by_value_method_receiver_suppresses_caller_cleanup(self):
        source = """module app::deferred_method_move;
sole struct Token {
    value: u32;
    fn consume(self: Token) -> void { return; }
    fn deinit(self: *mut Token) -> void { return; }
}
fn caller(token: Token) -> void {
    defer token.consume();
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<deferred-method-move>")
        bootstrap.check(parsed)
        generated = bootstrap.emit_c(parsed)
        caller_body = generated.split(
            "void caller(Token token) {", 1
        )[1].split("\n}", 1)[0]
        self.assertIn("Token_consume(token);", caller_body)
        self.assertNotIn("Token_deinit(&token);", caller_body)

    def test_deferred_by_value_method_receiver_destroys_owner_once(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_deferred_method_move_temp.sotlas"
        executable = ROOT / "build" / "test_deferred_method_move.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::deferred_method_move_runtime;
sole struct Token {
    value: u32;
    fn consume(self: Token) -> void { return; }
    fn deinit(self: *mut Token) -> void {
        unsafe {
            if self.value == 7u32 {
                destroy_count = destroy_count + 1;
            } else {
                destroy_count = destroy_count + 1;
            }
        }
    }
}
static mut destroy_count: u32 = 0;
fn caller(token: Token) -> void {
    defer token.consume();
    return;
}
fn main() -> i32 {
    let token: Token = Token { value: 7u32 };
    caller(move token);
    return destroy_count as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        result = subprocess.run(
            [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                str(self.output_c), "-o", str(executable),
            ],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 1, executed.stderr)

    def test_core_option_and_result_compile_cleanly(self):
        for subpath in ["option.sotlas", "result.sotlas"]:
            entry = ROOT / "bootstrap" / "sotlas" / "core" / subpath
            bootstrap.emit_c_project(entry, self.output_c)
            gcc = _host_c_compiler()
            env = dict(os.environ)
            env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
            cmd = [str(gcc), "-std=c11", "-Wall", "-Wextra", "-Werror", "-c", str(self.output_c), "-o", str(self.output_o)]
            res = subprocess.run(cmd, capture_output=True, text=True, env=env)
            self.assertEqual(res.returncode, 0, f"Erro GCC core::{subpath}: {res.stderr}")

    def test_runtime_class_and_arc_execution(self):
        test_source = ROOT / "bootstrap" / "sotlas" / "test_arc_runtime_temp.sotlas"
        driver_c = ROOT / "build" / "test_driver_main.c"
        driver_exe = ROOT / "build" / "test_driver_main.exe"
        self.addCleanup(test_source.unlink, missing_ok=True)
        self.addCleanup(driver_c.unlink, missing_ok=True)
        self.addCleanup(driver_exe.unlink, missing_ok=True)
        test_source.write_text("""
        module app::test;
        import core::mem::*;
        import core::arc::*;
        import core::option::*;
        import core::result::*;

        @export
        @system
        pub fn main_test() -> u32 {
            let mut counter: SharedCounter = SharedCounter::new(100);
            counter.increment();
            counter.retain();

            unsafe {
                if arc_count((&counter.header) as *const ArcHeader) != 2 {
                    return 0;
                }
                if arc_release((&counter.header) as *mut ArcHeader) {
                    return 0;
                }
                if !arc_release((&counter.header) as *mut ArcHeader) {
                    return 0;
                }
                if arc_retain((&counter.header) as *mut ArcHeader) != null {
                    return 0;
                }
                if arc_release((&counter.header) as *mut ArcHeader) {
                    return 0;
                }
                if arc_count((&counter.header) as *const ArcHeader) != 0 {
                    return 0;
                }

                let mut saturated: ArcHeader = 0;
                saturated.ref_count = 18446744073709551615u64;
                if arc_retain((&saturated) as *mut ArcHeader) != null {
                    return 0;
                }
                if arc_count((&saturated) as *const ArcHeader)
                    != 18446744073709551615u64 {
                    return 0;
                }
                if arc_release((&saturated) as *mut ArcHeader) {
                    return 0;
                }
                if arc_count((&saturated) as *const ArcHeader)
                    != 18446744073709551614u64 {
                    return 0;
                }
            }

            let opt: OptionU32 = OptionU32::some(42);
            let opt_val: u32 = opt.unwrap_or(0);

            let res: ResultU32 = ResultU32::ok(opt_val);
            if res.is_ok() {
                return (counter.get_value() as u32) + res.unwrap_or(0);
            }
            return 0;
        }
        """, encoding="utf-8")

        bootstrap.emit_c_project(test_source, self.output_c)
        driver_c.write_text("""
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

uint32_t main_test(void);

int main(void) {
    uint32_t val = main_test();
    if (val != (101 + 42)) {
        printf("ERROR: unexpected val=%u (expected 143)\\n", val);
        return 1;
    }
    printf("SUCCESS: class and ARC runtime val=%u\\n", val);
    return 0;
}
""", encoding="utf-8")

        gcc = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")
        cmd = [str(gcc), "-std=c11", str(self.output_c), str(driver_c), "-o", str(driver_exe)]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, f"Falha na compilação: {res.stderr}")

        run_res = subprocess.run([str(driver_exe)], capture_output=True, text=True, env=env)
        self.assertEqual(run_res.returncode, 0, f"Falha na execução: {run_res.stderr}")
        self.assertIn("SUCCESS: class and ARC runtime val=143", run_res.stdout)

        test_source.unlink(missing_ok=True)
        driver_c.unlink(missing_ok=True)
        driver_exe.unlink(missing_ok=True)

    def test_island_quarantine_handover_runs_through_c11(self):
        source = """module app::island_runtime;
sole struct Token { value: u32; }
fn discard(token: Token) -> void { return; }
pub fn quarantine_value(token: Token) -> island Token {
    quarantine token;
    return token;
}
pub fn reacquire(source: island Token, destination: Token) -> Token {
    discard(destination);
    handover source to destination;
    return destination;
}
"""
        driver_c = ROOT / "build" / "test_island_runtime_main.c"
        driver_exe = ROOT / "build" / "test_island_runtime.exe"
        self.addCleanup(driver_c.unlink, missing_ok=True)
        self.addCleanup(driver_exe.unlink, missing_ok=True)
        parsed = bootstrap.parse(source, filename="<island-runtime>")
        bootstrap.check(parsed)
        generated = bootstrap.emit_c(parsed)
        self.assertIn("Token quarantine_value(Token token)", generated)
        self.assertIn("destination = source;", generated)
        self.output_c.write_text(generated, encoding="utf-8")
        driver_c.write_text("""
#include <stdint.h>
typedef struct Token { uint32_t value; } Token;
Token quarantine_value(Token token);
Token reacquire(Token source, Token destination);
int main(void) {
    Token original = {37};
    Token empty = {0};
    Token isolated = quarantine_value(original);
    Token restored = reacquire(isolated, empty);
    return restored.value == 37 ? 0 : 1;
}
""", encoding="utf-8")

        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        result = subprocess.run(
            [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                str(self.output_c), str(driver_c), "-o", str(driver_exe),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        executed = subprocess.run(
            [str(driver_exe)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_quarantine_disjoint_branches_compile_and_run_through_c11(self):
        source = """module app::quarantine_disjoint_runtime;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn isolate(token: Token, isolate_owner: bool) -> u32 {
    let alias = &token;
    if isolate_owner {
        quarantine token;
        return 0u32;
    } else {
        unsafe { return alias.value; }
    }
}
fn run(isolate_owner: bool) -> u32 {
    let token = Token { value: 73u32 };
    return isolate(move token, isolate_owner);
}
fn main() -> i32 {
    let quarantined = run(true);
    let borrowed = run(false);
    if quarantined == 0u32 && borrowed == 73u32 && destroy_count == 2u32 {
        return 0;
    }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_quarantine_branch_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
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

    def test_region_handover_compiles_and_destroys_exactly_once_in_c11(self):
        source = """module app::region_handover_runtime;
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
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_handover_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_region_return_moves_owner_to_caller_and_drops_once(self):
        source = """module app::region_return_runtime;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn produce() -> region Token {
    let token: region Token = Token { value: 88u32 };
    return move token;
}
fn main() -> i32 {
    let token: region Token = produce();
    if token.value == 88u32 && destroy_count == 0u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_return_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_region_sole_field_transfers_and_drops_recursively_in_c11(self):
        source = """module app::region_nested_runtime;
sole struct Token { value: u32; }
sole struct Bundle { token: region Token; }
static mut destroy_sum: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_sum = destroy_sum + self.value; }
}
fn consume(bundle: region Bundle) -> void { return; }
fn main() -> i32 {
    let token: region Token = Token { value: 37u32 };
    let bundle: region Bundle = Bundle { token: move token };
    consume(move bundle);
    if destroy_sum == 37u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_nested_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_region_nested_owner_deinit_that_captures_self_fails_closed(self):
        source = """module app::region_nested_deinit_gate;
sole struct Token { value: u32; }
sole struct Bundle { token: region Token; }
fn Bundle_deinit(self: *mut Bundle) { unsafe { self.token.value; } }
fn consume(bundle: region Bundle) -> void { return; }
fn main() -> i32 {
    let token: region Token = Token { value: 37u32 };
    let bundle: region Bundle = Bundle { token: move token };
    consume(move bundle);
    return 0;
}
"""
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "C11 region recursive cleanup requires a detached owner deinit",
        ):
            bootstrap.compile_source(source, filename="<region-nested-deinit>")

    def test_region_array_fields_drop_in_reverse_order_in_c11(self):
        source = """module app::region_array_runtime;
sole struct Token { value: u32; }
sole struct Bundle { tokens: [region Token; 2]; }
static mut destroy_order: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_order = destroy_order * 10u32 + self.value; }
}
fn consume(bundle: region Bundle) -> void { return; }
fn main() -> i32 {
    let bundle: region Bundle = Bundle { tokens: [
        Token { value: 1u32 }, Token { value: 2u32 }
    ] };
    consume(move bundle);
    if destroy_order == 21u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_array_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_region_cleanup_runs_defer_before_drop_on_return_and_fallthrough(self):
        source = """module app::region_cleanup_paths;
sole struct Token { value: u32; }
static mut cleanup_order: u32 = 0;
fn record_defer() -> void {
    unsafe { cleanup_order = cleanup_order * 10u32 + 1u32; }
}
fn Token_deinit(self: *mut Token) {
    unsafe { cleanup_order = cleanup_order * 10u32 + 2u32; }
}
fn consume(token: region Token, early: bool) -> void {
    defer record_defer();
    if early { return; }
    return;
}
fn main() -> i32 {
    let first: region Token = Token { value: 1u32 };
    let second: region Token = Token { value: 2u32 };
    consume(move first, true);
    consume(move second, false);
    if cleanup_order == 1212u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_cleanup_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_region_owner_can_be_borrowed_by_direct_and_whisper_calls(self):
        source = """module app::region_borrow_runtime;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_count = destroy_count + 1; }
}
fn inspect_whisper(token: whisper Token) -> u32 { return token.value; }
fn inspect_direct(token: direct Token) -> u32 { return token.value; }
fn read(token: region Token) -> u32 {
    return inspect_whisper(&token) + inspect_direct(&token);
}
fn main() -> i32 {
    let token: region Token = Token { value: 31u32 };
    let value = read(move token);
    if value == 62u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_borrows_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_region_drop_walks_through_plain_wrappers(self):
        source = """module app::region_wrapper_runtime;
sole struct Token { value: u32; }
sole struct Metadata { token: region Token; }
sole struct Bundle { metadata: Metadata; }
static mut destroy_sum: u32 = 0;
fn Token_deinit(self: *mut Token) {
    unsafe { destroy_sum = destroy_sum + self.value; }
}
fn consume(bundle: region Bundle) -> void { return; }
fn make_wrapper() -> void {
    let leftover_token: region Token = Token { value: 44u32 };
    let leftover = Metadata { token: move leftover_token };
    return;
}
fn main() -> i32 {
    let token: region Token = Token { value: 43u32 };
    let metadata = Metadata { token: move token };
    let bundle: region Bundle = Bundle { metadata: metadata };
    consume(move bundle);
    make_wrapper();
    if destroy_sum == 87u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_region_wrapper_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_whisper_borrows_island_owner_for_internal_call_in_c11(self):
        source = """module app::whisper_island_runtime;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return token.value; }
fn read_island(token: island Token) -> u32 { return inspect(&token); }
fn main() -> i32 {
    let token = Token { value: 64u32 };
    quarantine token;
    let value = read_island(move token);
    if value == 64u32 { return 0; }
    return 1;
}
"""
        source_file = ROOT / "bootstrap" / "sotlas" / "test_whisper_island_temp.sotlas"
        executable = self.output_c.with_suffix(".exe")
        self.addCleanup(source_file.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source_file.write_text(source, encoding="utf-8")
        bootstrap.emit_c_project(source_file, self.output_c)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        compiled = subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_island_field_in_sole_container_runs_through_c11(self):
        source = ROOT / "bootstrap" / "sotlas" / "test_island_field_temp.sotlas"
        executable = ROOT / "build" / "test_island_field.exe"
        self.addCleanup(source.unlink, missing_ok=True)
        self.addCleanup(executable.unlink, missing_ok=True)
        source.write_text("""module app::island_field;
struct Metadata { code: u32; }
sole struct Token { metadata: Metadata; value: u32; }
sole struct Container { payload: island Token; }
fn wrap(token: Token) -> Container {
    return Container { payload: move token };
}
fn main() -> i32 {
    let mut token: Token = 0;
    token.metadata.code = 17;
    token.value = 25;
    let container = wrap(move token);
    return (container.payload.metadata.code + container.payload.value) as i32;
}
""", encoding="utf-8")
        bootstrap.emit_c_project(source, self.output_c)
        generated = self.output_c.read_text(encoding="utf-8")
        self.assertIn("Token payload;", generated)
        compiler = _host_c_compiler()
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(self.output_c), "-o", str(executable)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        executed = subprocess.run(
            [str(executable)], capture_output=True, text=True, env=env
        )
        self.assertEqual(executed.returncode, 42, executed.stderr)

    def test_island_field_rejects_nonsole_container_and_implicit_cleanup(self):
        cases = (
            ("nonsole", "struct Container { payload: island Token; }"),
            (
                "pointer_payload",
                "struct Payload { pointer: *u8; }\n"
                "sole struct Token { data: Payload; }\n"
                "sole struct Container { payload: island Token; }",
            ),
            (
                "cleanup",
                "sole struct Container { payload: island Token; }\n"
                "fn Token_deinit(self: *mut Token) { return; }",
            ),
        )
        for label, declarations in cases:
            with self.subTest(label=label):
                source = ROOT / "bootstrap" / "sotlas" / f"test_island_field_{label}_temp.sotlas"
                self.addCleanup(source.unlink, missing_ok=True)
                source.write_text(f"""module app::island_field_{label};
sole struct Token {{ value: u32; }}
{declarations}
fn passthrough(container: Container) -> Container {{ return container; }}
""", encoding="utf-8")
                with self.assertRaisesRegex(
                    bootstrap.SotlasBootstrapError,
                    "C11 island lowering currently supports only direct by-value",
                ):
                    bootstrap.emit_c_project(source, self.output_c)


if __name__ == "__main__":
    unittest.main()
