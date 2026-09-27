from contextlib import redirect_stderr
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sotlas import cli, llvm_toolchain


class SotlasCliRunTests(unittest.TestCase):
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
