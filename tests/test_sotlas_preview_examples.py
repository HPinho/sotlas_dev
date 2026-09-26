"""Native checks for the examples promoted on the preview website."""
from pathlib import Path
import json
import shutil
from types import SimpleNamespace
import unittest

from sotlas import cli


ROOT = Path(__file__).resolve().parents[1]
RUNNABLE_EXAMPLES = (
    "examples/01_hello_systems/main.sotlas",
    "examples/07_cli_tool/main.sotlas",
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
        if not (shutil.which("gcc") or shutil.which("clang")):
            self.skipTest("GCC or Clang is required to execute native preview examples")

        for relative_source in RUNNABLE_EXAMPLES:
            with self.subTest(source=relative_source):
                source = ROOT / relative_source
                self.assertTrue(source.is_file())
                result = cli._run_exec(SimpleNamespace(source=str(source), cc="cc"))
                self.assertEqual(result, 0, f"native example failed: {relative_source}")


if __name__ == "__main__":
    unittest.main()
