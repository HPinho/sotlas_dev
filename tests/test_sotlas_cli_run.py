import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sotlas import cli


class SotlasCliRunTests(unittest.TestCase):
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
