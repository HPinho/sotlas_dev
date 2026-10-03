"""Native checks for the examples promoted on the preview website."""
from pathlib import Path
import json
import io
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from sotlas import cli
from sotlas.llvm_toolchain import default_toolchain


ROOT = Path(__file__).resolve().parents[1]
RUNNABLE_EXAMPLES = (
    "examples/01_hello_systems/main.sotlas",
    "examples/07_cli_tool/main.sotlas",
    "examples/12_sotlas_by_example/05_native_control_flow.sotlas",
)


def has_native_compiler() -> bool:
    return bool(
        default_toolchain.find_tool("clang")
        or shutil.which("gcc")
        or shutil.which("clang")
    )


class SotlasPreviewExampleTests(unittest.TestCase):
    def test_website_examples_are_declared_as_native_run_contracts(self):
        manifest = json.loads((ROOT / "examples" / "manifest.json").read_text(encoding="utf-8"))
        declared = {
            item["entry"]
            for item in manifest["examples"]
            if item.get("native_run") is True and item.get("backend_contract") is True
        }
        self.assertTrue(set(RUNNABLE_EXAMPLES).issubset(declared))

    def test_manifest_examples_compile_and_run(self):
        if not has_native_compiler():
            self.skipTest("GCC or Clang is required to execute native preview examples")

        for relative_source in RUNNABLE_EXAMPLES:
            with self.subTest(source=relative_source):
                source = ROOT / relative_source
                self.assertTrue(source.is_file())
                result = cli._run_exec(SimpleNamespace(source=str(source), cc="cc"))
                self.assertEqual(result, 0, f"native example failed: {relative_source}")

    def test_native_control_flow_example_passes_check_compile_and_run(self):
        source = ROOT / "examples/12_sotlas_by_example/05_native_control_flow.sotlas"
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["sotlas", "check", str(source)]), redirect_stderr(stderr):
            self.assertEqual(cli.main(), 0, stderr.getvalue())

        if not has_native_compiler():
            self.skipTest("Clang or GCC is required for native compile/run of the control-flow example")

        with tempfile.TemporaryDirectory(prefix="sotlas-native-profile-") as temp:
            output = Path(temp) / "native_control_flow.c"
            commands = (
                ("compile", str(source), "--backend", "c11", "--emit-c", "-o", str(output)),
                ("run", str(source)),
            )
            for args in commands:
                with self.subTest(command=args[0]):
                    stderr = io.StringIO()
                    with patch.object(sys, "argv", ["sotlas", *args]), redirect_stderr(stderr):
                        result = cli.main()
                    self.assertEqual(result, 0, stderr.getvalue())
            generated_c = output.read_text(encoding="utf-8")
            self.assertIn("while", generated_c)
            self.assertIn("?", generated_c)


if __name__ == "__main__":
    unittest.main()
