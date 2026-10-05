"""Sovereignty Milestone SV9 Gate: Native Compiler/Backend Default Installed Path.

Validates that:
1. The command-line parser defaults to --backend native.
2. Default compilation produces native ELF64 relocatable objects and static executables
   via Stage 1 compiler without invoking C compilers or external linkers.
3. Explicit --backend native works identically and deterministically.
4. The legacy --backend c11 path remains fully operational as an optional reference/legacy
   tooling path when explicitly selected.
5. Freestanding kernel compilation operates out-of-the-box with the default native backend.
6. Fail-closed contract guards validate arguments, rejection of invalid backends, and error handling.
"""
from __future__ import annotations

import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas import cli
from sotlas.bootstrap_pipeline import (
    build_stage1_native_compiler,
    NATIVE_COMPILER_DIR,
)

REAL_APP_SOURCE = """module app::calculator;

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
"""

FREESTANDING_KERNEL_SOURCE = """module kernel::minimal;

fn early_setup(magic: u32) -> u32 {
    return magic + 1;
}

@system
pub fn _start() -> u32 {
    let status: u32 = early_setup(41);
    return status;
}
"""


class TestSotlasSovereigntySV9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="sotlas-sv9-")
        cls.root = Path(cls.tmp_dir.name)
        exe_suffix = ".exe" if os.name == "nt" else ""
        cls.stage1_exe = ROOT / "build" / f"sotlas_stage1{exe_suffix}"
        if not cls.stage1_exe.is_file():
            build_stage1_native_compiler(cls.stage1_exe, verbose=False)

        cls.app_src = cls.root / "app_calculator.sotlas"
        cls.app_src.write_text(REAL_APP_SOURCE, encoding="utf-8")

        cls.kernel_src = cls.root / "kernel_min.sotlas"
        cls.kernel_src.write_text(FREESTANDING_KERNEL_SOURCE, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_sv9_cli_parser_defaults_to_native_backend(self):
        """SV9.1: The command-line parser defaults to --backend native."""
        parser = cli.build_parser()
        args = parser.parse_args(["compile", str(self.app_src)])
        self.assertEqual(args.backend, "native")
        self.assertIn("native", ["native", "llvm", "c11", "sotlas-x86_64"])

    def test_sv9_cli_compile_object_default_native(self):
        """SV9.2: Default `sotlas compile` emits ELF64 object using native compiler."""
        out_obj = self.root / "app_default.o"
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(sys, "argv", ["sotlas", "compile", str(self.app_src), "-o", str(out_obj)]):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                ret = cli.main()

        self.assertEqual(ret, 0, f"CLI exited with {ret}: {stderr_buf.getvalue()}")
        self.assertTrue(out_obj.is_file())
        self.assertGreater(out_obj.stat().st_size, 100)
        self.assertIn("objeto ELF64 nativo emitido", stdout_buf.getvalue())

        # Validate ELF64 relocatable object header
        data = out_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertEqual(data[4], 2)   # 64-bit
        self.assertEqual(data[5], 1)   # Little-endian
        e_type = struct.unpack_from("<H", data, 16)[0]
        self.assertEqual(e_type, 1)    # ET_REL
        e_machine = struct.unpack_from("<H", data, 18)[0]
        self.assertEqual(e_machine, 62)  # EM_X86_64

    def test_sv9_cli_compile_executable_default_native(self):
        """SV9.3: Default `sotlas compile` links native static executable without external linkers."""
        out_exe = self.root / "app_default.bin"
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(sys, "argv", ["sotlas", "compile", str(self.app_src), "-o", str(out_exe)]):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                ret = cli.main()

        self.assertEqual(ret, 0, f"CLI exited with {ret}: {stderr_buf.getvalue()}")
        self.assertTrue(out_exe.is_file())
        self.assertGreater(out_exe.stat().st_size, 100)
        self.assertIn("executável nativo gerado com sucesso", stdout_buf.getvalue())

        # Validate ELF64 static executable header
        data = out_exe.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertEqual(data[4], 2)   # 64-bit
        self.assertEqual(data[5], 1)   # Little-endian
        e_type = struct.unpack_from("<H", data, 16)[0]
        self.assertEqual(e_type, 2)    # ET_EXEC
        e_machine = struct.unpack_from("<H", data, 18)[0]
        self.assertEqual(e_machine, 62)  # EM_X86_64

    def test_sv9_cli_explicit_native_parity_with_default(self):
        """SV9.4: Explicit --backend native produces bit-for-bit identical object and executable."""
        out_obj_explicit = self.root / "app_explicit.o"
        out_exe_explicit = self.root / "app_explicit.bin"

        # Explicit compile object
        with patch.object(
            sys, "argv",
            ["sotlas", "compile", str(self.app_src), "--backend", "native", "-o", str(out_obj_explicit)]
        ):
            self.assertEqual(cli.main(), 0)

        # Explicit compile executable
        with patch.object(
            sys, "argv",
            ["sotlas", "compile", str(self.app_src), "--backend", "native", "-o", str(out_exe_explicit)]
        ):
            self.assertEqual(cli.main(), 0)

        # Ensure default outputs exist
        out_obj_default = self.root / "app_default.o"
        out_exe_default = self.root / "app_default.bin"
        if not out_obj_default.is_file():
            self.test_sv9_cli_compile_object_default_native()
        if not out_exe_default.is_file():
            self.test_sv9_cli_compile_executable_default_native()

        self.assertEqual(out_obj_explicit.read_bytes(), out_obj_default.read_bytes())
        self.assertEqual(out_exe_explicit.read_bytes(), out_exe_default.read_bytes())

    def test_sv9_cli_c11_reference_backend_remains_available(self):
        """SV9.5: Legacy --backend c11 remains available as optional reference tooling."""
        out_c = self.root / "app_legacy.c"
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(
            sys, "argv",
            ["sotlas", "compile", str(self.app_src), "--backend", "c11", "--emit-c", "-o", str(out_c)]
        ):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                ret = cli.main()

        self.assertEqual(ret, 0, f"CLI exited with {ret}: {stderr_buf.getvalue()}")
        self.assertTrue(out_c.is_file())
        c_content = out_c.read_text(encoding="utf-8")
        self.assertIn("multiply_offset", c_content)
        self.assertIn("compute_metric", c_content)
        self.assertIn("main_entry", c_content)

    def test_sv9_cli_freestanding_kernel_compilation_default_native(self):
        """SV9.6: Freestanding kernel compiles to standalone binary with default native backend."""
        out_kernel_bin = self.root / "kernel_default.bin"
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(
            sys, "argv",
            ["sotlas", "compile", str(self.kernel_src), "--target", "x86_64-freestanding", "-o", str(out_kernel_bin)]
        ):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                ret = cli.main()

        self.assertEqual(ret, 0, f"CLI exited with {ret}: {stderr_buf.getvalue()}")
        self.assertTrue(out_kernel_bin.is_file())
        self.assertGreater(out_kernel_bin.stat().st_size, 100)

        # Validate ELF header
        data = out_kernel_bin.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        e_type = struct.unpack_from("<H", data, 16)[0]
        self.assertEqual(e_type, 2)  # ET_EXEC

    def test_sv9_cli_fail_closed_contract_guards(self):
        """SV9.7: CLI fails closed on non-existent files or invalid backend choices."""
        # Non-existent file
        stderr_buf = io.StringIO()
        with patch.object(sys, "argv", ["sotlas", "compile", str(self.root / "does_not_exist.sotlas")]):
            with redirect_stderr(stderr_buf):
                ret = cli.main()
        self.assertNotEqual(ret, 0)

        # Invalid backend choice rejected by argparse
        with patch.object(sys, "argv", ["sotlas", "compile", str(self.app_src), "--backend", "unknown_backend"]):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli.main()
                self.assertEqual(cm.exception.code, 2)

    def test_sv9_native_compile_failure_never_falls_back(self):
        """A rejected native input must not proceed through LLVM or C11."""
        stage1 = self.root / "stage1.exe"
        stage1.write_bytes(b"test executable placeholder")
        output = self.root / "rejected.o"
        failure = subprocess.CompletedProcess([], 1, stdout="", stderr="unsupported native form")

        with patch("sotlas.bootstrap_pipeline.build_stage1_native_compiler", return_value=stage1), \
             patch("sotlas.cli.subprocess.run", return_value=failure) as run, \
             patch.object(cli, "compile_source") as compile_source, \
             patch("sotlas.llvm_toolchain.LLVMToolchain.compile_c11_source") as compile_c11:
            stderr_buf = io.StringIO()
            with patch.object(
                sys, "argv",
                ["sotlas", "compile", str(self.app_src), "--emit-obj", "-o", str(output)],
            ), redirect_stderr(stderr_buf):
                ret = cli.main()

        self.assertEqual(ret, 1)
        self.assertFalse(output.exists())
        self.assertIn("unsupported native form", stderr_buf.getvalue())
        self.assertIn("nenhum fallback implicito", stderr_buf.getvalue())
        run.assert_called_once()
        compile_source.assert_not_called()
        compile_c11.assert_not_called()

    def test_sv9_native_stage1_build_failure_never_falls_back(self):
        """A failed Stage 1 bootstrap must stop before reference backends run."""
        with patch(
            "sotlas.bootstrap_pipeline.build_stage1_native_compiler",
            side_effect=RuntimeError("bootstrap unavailable"),
        ), patch.object(cli, "compile_source") as compile_source, \
             patch("sotlas.llvm_toolchain.LLVMToolchain.compile_c11_source") as compile_c11:
            stderr_buf = io.StringIO()
            with patch.object(
                sys, "argv", ["sotlas", "compile", str(self.app_src), "--emit-obj"]
            ), redirect_stderr(stderr_buf):
                ret = cli.main()

        self.assertEqual(ret, 1)
        self.assertIn("bootstrap unavailable", stderr_buf.getvalue())
        self.assertIn("nenhum fallback implicito", stderr_buf.getvalue())
        compile_source.assert_not_called()
        compile_c11.assert_not_called()


if __name__ == "__main__":
    unittest.main()
