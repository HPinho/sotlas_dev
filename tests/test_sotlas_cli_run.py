from contextlib import redirect_stderr
import io
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sotlas import cli, llvm_toolchain


class SotlasCliRunTests(unittest.TestCase):
    def test_checkout_sotlas_toml_does_not_turn_standalone_example_into_project(self):
        source = Path(__file__).resolve().parents[1] / "examples" / "01_hello_systems" / "main.sotlas"
        source_text = source.read_text(encoding="utf-8")
        generated = llvm_toolchain.default_toolchain.compile_c11_source(
            source_text, str(source)
        )
        self.assertIn("main(void)", generated)

    def test_project_imports_are_resolved_consistently_by_check_compile_and_run(self):
        toolchain = llvm_toolchain.default_toolchain
        if not toolchain.is_available() and not (shutil.which("gcc") or shutil.which("clang")):
            self.skipTest("GCC or Clang is required for native CLI execution")

        with tempfile.TemporaryDirectory(prefix="sotlas-cli-project-parity-") as tmpdir:
            root = Path(tmpdir)
            project = root / "project" / "core"
            project.mkdir(parents=True)
            (project / "answer.sotlas").write_text(
                "module core::answer;\n"
                "pub fn value() -> i32 { return 42; }\n",
                encoding="utf-8",
            )
            source = project / "main.sotlas"
            source.write_text(
                "module app::main;\nimport core::answer::*;\n"
                "pub fn main() -> i32 { return value() - 42; }\n",
                encoding="utf-8",
            )
            generated = root / "main.c"

            for command in (
                ["check", str(source)],
                ["compile", str(source), "--backend", "c11", "--emit-c", "-o", str(generated)],
            ):
                stderr = io.StringIO()
                with patch.object(sys, "argv", ["sotlas", *command]), redirect_stderr(stderr):
                    self.assertEqual(cli.main(), 0, stderr.getvalue())

            generated_c = generated.read_text(encoding="utf-8")
            self.assertIn("int32_t main(void)", generated_c)
            self.assertIn("int32_t value(void)", generated_c)
            stderr = io.StringIO()
            with patch.object(sys, "argv", ["sotlas", "run", str(source)]), redirect_stderr(stderr):
                self.assertEqual(cli.main(), 0, stderr.getvalue())

    def test_check_compile_and_run_accept_the_same_structured_c11_program(self):
        toolchain = llvm_toolchain.default_toolchain
        if not toolchain.is_available() and not (shutil.which("gcc") or shutil.which("clang")):
            self.skipTest("GCC or Clang is required for native CLI execution")
        source_text = """module test::cli_structured_profile;
pub fn main() -> i32 {
    let mut index: u32 = 0u32;
    let mut total: u32 = 0u32;
    while index < 6u32 {
        index += 1u32;
        if index == 2u32 { continue; }
        if index == 5u32 { break; }
        total += index;
    }
    if total == 8u32 { return 0; }
    return 1;
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas-cli-structured-") as tmpdir:
            root = Path(tmpdir)
            source = root / "main.sotlas"
            output = root / "main.c"
            source.write_text(source_text, encoding="utf-8")

            for command in (
                ["check", str(source)],
                ["compile", str(source), "--backend", "c11", "--emit-c", "-o", str(output)],
            ):
                stderr = io.StringIO()
                with patch.object(sys, "argv", ["sotlas", *command]), redirect_stderr(stderr):
                    self.assertEqual(cli.main(), 0, stderr.getvalue())

            self.assertTrue(output.is_file())
            stderr = io.StringIO()
            with patch.object(sys, "argv", ["sotlas", "run", str(source)]), redirect_stderr(stderr):
                self.assertEqual(cli.main(), 0, stderr.getvalue())

    def test_check_compile_and_run_share_canonical_rejection(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-cli-parity-") as tmpdir:
            root = Path(tmpdir)
            source = root / "invalid.sotlas"
            source.write_text(
                "module test::cli_parity;\npub fn broken( -> u32 { return 1u32; }\n",
                encoding="utf-8",
            )
            output = root / "invalid.c"
            diagnostics = []
            toolchain = llvm_toolchain.default_toolchain

            for command in (
                ["check", str(source)],
                ["compile", str(source), "--backend", "c11", "--emit-c", "-o", str(output)],
                ["run", str(source)],
            ):
                stderr = io.StringIO()
                with (
                    patch.object(toolchain, "is_available", return_value=False),
                    patch.object(sys, "argv", ["sotlas", *command]),
                    redirect_stderr(stderr),
                ):
                    self.assertEqual(cli.main(), 1, command[0])
                diagnostics.append(stderr.getvalue())

            self.assertEqual(diagnostics[0], diagnostics[1])
            self.assertEqual(diagnostics[1], diagnostics[2])
            self.assertIn(str(source), diagnostics[0])
            self.assertRegex(diagnostics[0], r"invalid\.sotlas:2:\d+:")
            self.assertIn("pode estar faltando um parâmetro", diagnostics[0])
            self.assertIn("^", diagnostics[0])
            self.assertFalse(output.exists())

    def test_region_escape_diagnostic_points_to_the_return_site(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-region-diagnostic-") as tmpdir:
            source = Path(tmpdir) / "region_escape.sotlas"
            source.write_text(
                "module test::region_escape_diagnostic;\n"
                "sole struct Token { value: u32; }\n"
                "sole struct Bundle { token: Token; }\n"
                "fn leak(token: region Token) -> Bundle {\n"
                "    return Bundle { token: move token };\n"
                "}\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with (
                patch.object(sys, "argv", ["sotlas", "check", str(source)]),
                redirect_stderr(stderr),
            ):
                self.assertEqual(cli.main(), 1)

        diagnostic = stderr.getvalue()
        self.assertIn(str(source), diagnostic)
        self.assertRegex(diagnostic, r"region_escape\.sotlas:5:\d+:")
        self.assertIn("cannot escape through return or aggregate storage", diagnostic)
        self.assertIn("^", diagnostic)

    def test_run_uses_isolated_temporary_executable(self):
        source = Path(__file__).resolve().parents[1] / "examples/07_cli_tool/main.sotlas"

        class FakeToolchain:
            def is_available(self):
                return True

            def compile_source_to_native(self, text, source_path, output_path, **kwargs):
                Path(output_path).write_bytes(b"native test executable")
                self.output_path = Path(output_path)
                self.kwargs = kwargs

        toolchain = FakeToolchain()
        args = SimpleNamespace(source=str(source), cc="cc")
        with (
            patch("sotlas.llvm_toolchain.default_toolchain", toolchain),
            patch("sotlas.cli.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            result = cli._run_exec(args)

        self.assertEqual(result, 0)
        self.assertEqual(toolchain.kwargs, {"emit_type": "exe", "backend": "c11"})
        self.assertFalse(toolchain.output_path.parent.exists())
        self.assertEqual(run.call_args.args[0], [str(toolchain.output_path)])
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
