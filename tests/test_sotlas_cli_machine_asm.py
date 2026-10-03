"""CLI contract for Sotlas-owned x86-64 assembly emission."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas import driver


class SotlasCliMachineAssemblyTests(unittest.TestCase):
    def _run(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["sotlas", *args]),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = driver.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_emit_asm_uses_sotlas_owned_backend_without_llvm_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-machine-cli-") as temp:
            root = Path(temp)
            source = root / "compare.sotlas"
            output = root / "nested" / "compare.s"
            source.write_text(
                "module test::cli_machine_compare;\n"
                "pub fn less_than(left: i32, right: i32) -> bool {\n"
                "    return left < right;\n"
                "}\n",
                encoding="utf-8",
            )

            with patch(
                "sotlas.llvm_toolchain.default_toolchain.compile_source_to_native",
                side_effect=AssertionError("LLVM dispatch must not run"),
            ):
                status, stdout, stderr = self._run([
                    "compile", str(source),
                    "--backend", "sotlas-x86_64",
                    "--target", "x86_64-unknown-linux-gnu",
                    "--emit-asm", "-o", str(output),
                ])

            self.assertEqual(status, 0, stderr)
            self.assertIn("Sotlas-owned x86-64 assembly emitted", stdout)
            assembly = output.read_text(encoding="utf-8")
            self.assertIn("cmp eax, ecx", assembly)
            self.assertIn("setl al", assembly)
            self.assertNotIn("LLVM", assembly)

            from sotlas.llvm_toolchain import default_toolchain

            clang = default_toolchain.find_tool("clang")
            if clang is not None:
                obj = root / "compare.o"
                assembled = subprocess.run(
                    [
                        str(clang), "-c", "-target", "x86_64-unknown-linux-gnu",
                        str(output), "-o", str(obj),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(assembled.returncode, 0, assembled.stderr)
                self.assertTrue(obj.is_file())

    def test_machine_backend_requires_sysv_target(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-machine-target-") as temp:
            source = Path(temp) / "main.sotlas"
            output = Path(temp) / "main.s"
            source.write_text(
                "module test::cli_machine_target;\n"
                "fn value() -> u32 { return 7u32; }\n",
                encoding="utf-8",
            )
            status, _, stderr = self._run([
                "compile", str(source),
                "--backend", "sotlas-x86_64",
                "--target", "x86_64-pc-windows-msvc",
                "--emit-asm", "-o", str(output),
            ])

        self.assertEqual(status, 2)
        self.assertIn("requires an x86-64 SysV target", stderr)
        self.assertFalse(output.exists())

    def test_machine_backend_must_be_selected_for_assembly_output(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-machine-artifact-") as temp:
            source = Path(temp) / "main.sotlas"
            source.write_text(
                "module test::cli_machine_artifact;\n"
                "fn value() -> u32 { return 7u32; }\n",
                encoding="utf-8",
            )
            status, _, stderr = self._run([
                "compile", str(source), "--backend", "sotlas-x86_64",
            ])

        self.assertEqual(status, 2)
        self.assertIn("requires --emit-asm", stderr)

    def test_out_of_subset_program_is_rejected_without_writing_assembly(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-machine-subset-") as temp:
            source = Path(temp) / "main.sotlas"
            output = Path(temp) / "main.s"
            source.write_text(
                "module test::cli_machine_subset;\n"
                "fn add(left: i32, right: i32) -> i32 { return left + right; }\n",
                encoding="utf-8",
            )
            status, _, stderr = self._run([
                "compile", str(source),
                "--backend", "sotlas-x86_64",
                "--target", "x86_64-unknown-linux-gnu",
                "--emit-asm", "-o", str(output),
            ])

        self.assertEqual(status, 1)
        self.assertIn("signed integer lowering waits for Sotlas overflow-mode semantics", stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
