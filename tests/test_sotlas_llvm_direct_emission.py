"""Testes de emissão direta de código objeto (.obj / .o) e executáveis nativos via LLVM / LLD."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.llvm_toolchain import (
    LLVMToolchain,
    LLVMToolchainError,
    default_toolchain,
    require_llvm_ownership_supported,
)


class TestSotlasLLVMDirectEmission(unittest.TestCase):
    def setUp(self):
        self.toolchain = default_toolchain
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_llvm_toolchain_detected(self):
        self.assertTrue(self.toolchain.is_available(), "LLVM Clang deve ser detectado no ambiente")
        version = self.toolchain.get_version()
        self.assertIn("clang version", version)
        clang_path = self.toolchain.find_tool("clang")
        self.assertIsNotNone(clang_path)
        self.assertTrue(clang_path.exists())

    def test_compile_llvm_ir_to_native_obj(self):
        ir_code = """
target triple = "x86_64-pc-windows-msvc"

define i32 @add_numbers(i32 %a, i32 %b) {
entry:
    %res = add i32 %a, %b
    ret i32 %res
}
"""
        obj_file = self.tmp_path / "math.obj"
        res_obj = self.toolchain.compile_llvm_ir_to_obj(ir_code, obj_file, opt_level=2)
        self.assertTrue(res_obj.is_file())
        self.assertGreater(res_obj.stat().st_size, 0)

    def test_link_native_executable_and_execute(self):
        ir_code = """
target triple = "x86_64-pc-windows-msvc"

define i32 @main() {
entry:
    ret i32 55
}
"""
        obj_file = self.tmp_path / "main.obj"
        exe_file = self.tmp_path / "main.exe"

        self.toolchain.compile_llvm_ir_to_obj(ir_code, obj_file)
        self.toolchain.link_native_binary([obj_file], exe_file)

        self.assertTrue(exe_file.is_file())
        run_res = subprocess.run([str(exe_file)])
        self.assertEqual(run_res.returncode, 55)

    def test_compile_sotlas_source_to_native_obj(self):
        source = """module test::obj_demo;
pub fn compute(x: u32) -> u32 {
    let factor: u32 = 4;
    return x * factor;
}
"""
        obj_file = self.tmp_path / "compute.obj"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::obj_demo",
            obj_file,
            emit_type="obj",
            backend="c11"
        )
        self.assertTrue(res.is_file())
        self.assertGreater(res.stat().st_size, 100)

    def test_compile_sotlas_source_to_native_exe_and_run(self):
        source = """module test::exe_demo;
pub fn main() -> i32 {
    let mut a: i32 = 20;
    let b: i32 = 22;
    return a + b;
}
"""
        exe_file = self.tmp_path / "test_app.exe"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::exe_demo",
            exe_file,
            emit_type="exe",
            backend="c11"
        )
        self.assertTrue(res.is_file())
        run_res = subprocess.run([str(res)])
        self.assertEqual(run_res.returncode, 42)

    def test_compile_sotlas_source_to_llvm_ir(self):
        source = """module test::ir_demo;
pub fn answer() -> i32 {
    return 42;
}
"""
        ll_file = self.tmp_path / "answer.ll"
        res = self.toolchain.compile_source_to_native(
            source,
            "test::ir_demo",
            ll_file,
            emit_type="llvm",
            backend="llvm"
        )
        self.assertTrue(res.is_file())
        content = res.read_text(encoding="utf-8")
        self.assertIn("ModuleID", content)
        self.assertIn("@answer", content)

    def test_llvm_source_backend_lowers_trivial_call_scoped_direct_domain(self):
        source = """module test::llvm_direct;
sole struct Token { value: u32; }
fn inspect(left: direct Token, right: direct Token) -> void { return; }
fn main(left: Token, right: Token) -> void {
    inspect(&left, &right);
    return;
}
"""
        ll_file = self.tmp_path / "direct.ll"
        obj_file = self.tmp_path / "direct.obj"

        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )

        ir = ll_file.read_text(encoding="utf-8")
        self.assertEqual(ir.count("direct access"), 2)
        self.assertIn("call void @inspect(ptr %slot_left2, ptr %slot_right3)", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_lowers_verified_call_scoped_whisper_domain(self):
        source = """module test::llvm_whisper;
sole struct Token { value: u32; }
fn inspect(primary: direct Token, observer: whisper Token) -> void { return; }
fn caller(token: Token) -> void { inspect(&token, &token); return; }
"""
        ll_file = self.tmp_path / "whisper.ll"
        obj_file = self.tmp_path / "whisper.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_whisper",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertIn("direct access %token -> @inspect.primary", ir)
        self.assertIn("whisper borrow %token -> @inspect.observer", ir)
        self.assertIn("call void @inspect(ptr %slot_token", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)


    def test_llvm_source_backend_preserves_forwarded_direct_access(self):
        source = """module test::llvm_direct_forward;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn forward(token: direct Token) -> void { inspect(token); return; }
fn caller(token: Token) -> void { forward(&token); return; }
"""
        ll_file = self.tmp_path / "direct_forward.ll"
        obj_file = self.tmp_path / "direct_forward.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct_forward",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        self.assertIn("direct access %token -> @inspect.token", ir)
        self.assertRegex(ir, r"call void @inspect\(ptr %direct_token\d+\)")
        self.assertIn("call void @forward(ptr %slot_token", ir)
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_places_deferred_direct_call_before_return(self):
        source = """module test::llvm_direct_defer;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn deferred(token: direct Token) -> void {
    defer inspect(token);
    return;
}
fn caller(token: Token) -> void { deferred(&token); return; }
"""
        ll_file = self.tmp_path / "direct_defer.ll"
        obj_file = self.tmp_path / "direct_defer.obj"
        self.toolchain.compile_source_to_native(
            source,
            "test::llvm_direct_defer",
            ll_file,
            emit_type="llvm",
            backend="llvm",
        )
        ir = ll_file.read_text(encoding="utf-8")
        deferred_body = ir.split("define void @deferred(", 1)[1].split(
            "define void @caller(", 1
        )[0]
        self.assertLess(deferred_body.index("direct access"), deferred_body.index("call void @inspect"))
        self.assertLess(deferred_body.index("call void @inspect"), deferred_body.index("ret void"))
        self.toolchain.compile_llvm_ir_to_obj(ir, obj_file)
        self.assertGreater(obj_file.stat().st_size, 0)

    def test_llvm_source_backend_fails_closed_for_unverified_direct_domain(self):
        module = SimpleNamespace(
            structs=(),
            functions=(SimpleNamespace(
                params=(("token", SimpleNamespace(
                    name="Token", ownership_domain="direct",
                    pointer=True, is_reference=True,
                )),),
                result=SimpleNamespace(name="u32"),
            ),),
            classes=(),
            globals=(),
            enums=(),
        )
        frontend = SimpleNamespace(check=lambda parsed: None)
        with self.assertRaisesRegex(
            LLVMToolchainError,
            "LLVM backend does not lower canonical Ownership Domains yet",
        ):
            require_llvm_ownership_supported(module, frontend)

    def test_llvm_direct_backend_rejects_unlowered_control_flow(self):
        source = """module test::llvm_direct_cfg;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn main(token: Token) -> void {
    if true { inspect(&token); }
    return;
}
"""

        with self.assertRaisesRegex(
            LLVMToolchainError,
            "LLVM backend does not lower canonical Ownership Domains yet",
        ):
            self.toolchain.compile_source_to_native(
                source,
                "test::llvm_direct_cfg",
                self.tmp_path / "direct_cfg.ll",
                emit_type="llvm",
                backend="llvm",
            )

    def test_llvm_backend_fails_closed_for_unlowered_region_device_external(self):
        for domain in ("region", "device", "external"):
            with self.subTest(domain=domain):
                source = (
                    "module test::llvm_domain_gate; "
                    "sole struct Resource { value: u32; } "
                    f"fn use(resource: {domain} Resource) -> void {{ return; }}"
                )
                with self.assertRaisesRegex(
                    LLVMToolchainError,
                    "LLVM backend does not lower canonical Ownership Domains yet",
                ):
                    self.toolchain.compile_source_to_native(
                        source,
                        f"test::llvm_{domain}_gate",
                        self.tmp_path / f"{domain}.ll",
                        emit_type="llvm",
                        backend="llvm",
                    )


if __name__ == "__main__":
    unittest.main()
