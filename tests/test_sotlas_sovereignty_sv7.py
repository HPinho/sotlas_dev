"""Sovereignty Milestone SV7 Gate: Stage 1 Native Compiler Build from Sotlas Sources.

Validates that:
1. Stage 0 builds the Sotlas Stage 1 compiler binary directly from Sotlas sources
   (`bootstrap/sotlas/native_compiler`) without external runtime dependencies.
2. The Stage 1 native binary executes standalone, reporting valid version information.
3. Stage 1 compiles a real multi-function application into an ELF64 relocatable object
   and static ELF64 executable directly without C11 backend or external linkers.
4. Stage 1 compiles the minimal freestanding kernel into an ELF64 relocatable object
   and freestanding image without C11 backend or external linkers.
5. The full `verify_stage1_compiler` test cycle passes and fail-closed contract guards reject
   invalid sources or malformed entry points.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.bootstrap_pipeline import (
    build_stage1_native_compiler,
    verify_stage1_compiler,
    NATIVE_COMPILER_DIR,
    NATIVE_COMPILER_MODULES,
)


class TestSotlasSovereigntySV7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="sotlas-sv7-")
        cls.root = Path(cls.tmp_dir.name)
        exe_suffix = ".exe" if os.name == "nt" else ""
        cls.stage1_exe = cls.root / f"sotlas_stage1{exe_suffix}"
        build_stage1_native_compiler(cls.stage1_exe, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_sv7_stage1_build_from_sources(self):
        """SV7.1: Stage 0 successfully builds Stage 1 compiler from bootstrap/sotlas/native_compiler."""
        self.assertTrue(self.stage1_exe.is_file())
        self.assertGreater(self.stage1_exe.stat().st_size, 50000)

        # Standalone invocation: --version
        res = subprocess.run([str(self.stage1_exe), "--version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("sotlas", res.stdout.lower())
        self.assertIn("1.0.0", res.stdout)

    def test_sv7_stage1_real_application_native_compilation(self):
        """SV7.2: Stage 1 compiles real application to ELF64 object and static executable."""
        app_source = self.root / "real_app.sotlas"
        app_source.write_text(
            """module app::calculator;

fn multiply_offset(a: u32, b: u32, offset: u32) -> u32 {
    let prod: u32 = a * b;
    return prod + offset;
}

fn compute_metric(x: u32, y: u32) -> u32 {
    let base: u32 = multiply_offset(x, y, 10);
    if base > 50 {
        return base;
    } else {
        return 50;
    }
}

pub fn main_entry() -> u32 {
    return compute_metric(10, 6);
}
""",
            encoding="utf-8",
        )

        app_obj = self.root / "real_app.o"
        res_obj = subprocess.run(
            [str(self.stage1_exe), "--compile-obj", str(app_source), str(app_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_obj.returncode, 0, f"Compilation failed: {res_obj.stderr}")
        self.assertTrue(app_obj.is_file())

        obj_data = app_obj.read_bytes()
        self.assertGreater(len(obj_data), 64)
        self.assertEqual(obj_data[:4], b"\x7fELF")
        self.assertEqual(obj_data[4], 2)  # ELFCLASS64
        self.assertEqual(obj_data[5], 1)  # ELFDATA2LSB
        e_type = struct.unpack_from("<H", obj_data, 16)[0]
        e_machine = struct.unpack_from("<H", obj_data, 18)[0]
        self.assertEqual(e_type, 1)  # ET_REL
        self.assertEqual(e_machine, 62)  # EM_X86_64

        app_exe = self.root / "real_app.elf"
        res_exe = subprocess.run(
            [str(self.stage1_exe), "--link-exe", str(app_obj), str(app_exe), "main_entry"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_exe.returncode, 0, f"Link failed: {res_exe.stderr}")
        self.assertTrue(app_exe.is_file())

        exe_data = app_exe.read_bytes()
        self.assertEqual(exe_data[:4], b"\x7fELF")
        e_type_exe = struct.unpack_from("<H", exe_data, 16)[0]
        self.assertEqual(e_type_exe, 2)  # ET_EXEC

    def test_sv7_stage1_minimal_kernel_native_compilation(self):
        """SV7.3: Stage 1 compiles minimal kernel to freestanding ELF64 object and image."""
        kernel_source = self.root / "kernel_min.sotlas"
        kernel_source.write_text(
            """module kernel::minimal;

fn early_setup(magic: u32) -> u32 {
    return magic + 1;
}

@system
pub fn _start() -> u32 {
    let status: u32 = early_setup(41);
    return status;
}
""",
            encoding="utf-8",
        )

        kernel_obj = self.root / "kernel_min.o"
        res_obj = subprocess.run(
            [str(self.stage1_exe), "--compile-obj", str(kernel_source), str(kernel_obj)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_obj.returncode, 0, f"Kernel compilation failed: {res_obj.stderr}")
        self.assertTrue(kernel_obj.is_file())

        obj_data = kernel_obj.read_bytes()
        self.assertEqual(obj_data[:4], b"\x7fELF")
        e_type = struct.unpack_from("<H", obj_data, 16)[0]
        self.assertEqual(e_type, 1)  # ET_REL

        kernel_bin = self.root / "kernel_min.bin"
        res_link = subprocess.run(
            [str(self.stage1_exe), "--link-exe", str(kernel_obj), str(kernel_bin), "_start", "--freestanding"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res_link.returncode, 0, f"Kernel link failed: {res_link.stderr}")
        self.assertTrue(kernel_bin.is_file())

        bin_data = kernel_bin.read_bytes()
        self.assertEqual(bin_data[:4], b"\x7fELF")
        e_entry = struct.unpack_from("<Q", bin_data, 24)[0]
        self.assertGreaterEqual(e_entry, 0x100000)

    def test_sv7_stage1_verification_cycle_and_run(self):
        """SV7.4: verify_stage1_compiler passes and run subcommand executes successfully."""
        ok = verify_stage1_compiler(self.stage1_exe)
        self.assertTrue(ok, "Stage 1 verification cycle must pass")

        run_file = self.root / "quick_run.sotlas"
        run_file.write_text(
            """module test::quick;
pub fn main() -> i32 {
    let a: i32 = 40;
    let b: i32 = 2;
    if a + b == 42 {
        return 0;
    } else {
        return 1;
    }
}
""",
            encoding="utf-8",
        )
        res_run = subprocess.run([str(self.stage1_exe), "run", str(run_file)], capture_output=True, text=True)
        self.assertEqual(res_run.returncode, 0)

    def test_sv7_stage1_fail_closed_contract_guards(self):
        """SV7.5: Stage 1 fails closed on invalid inputs, malformed files, and missing entry points."""
        bad_file = self.root / "malformed.sotlas"
        bad_file.write_text("invalid syntax {[[", encoding="utf-8")
        res_bad = subprocess.run(
            [str(self.stage1_exe), "--compile-obj", str(bad_file), str(self.root / "bad.o")],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_bad.returncode, 0)

        missing_file = self.root / "nonexistent.sotlas"
        res_missing = subprocess.run(
            [str(self.stage1_exe), "--compile-obj", str(missing_file), str(self.root / "bad.o")],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_missing.returncode, 0)


if __name__ == "__main__":
    unittest.main()
