"""Repository example-manifest coverage, including nested source examples."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sotlas_example_manifest_validator",
    ROOT / "scripts" / "validate_example_manifest.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load example-manifest validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class SotlasExampleManifestTests(unittest.TestCase):
    def test_checked_in_manifest_covers_all_example_directories(self):
        self.assertEqual(VALIDATOR.validate_manifest(ROOT / "examples"), [])

    def test_nested_entry_is_covered_by_its_numbered_parent(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_manifest_") as temp:
            root = Path(temp) / "examples"
            (root / "12_sotlas_by_example").mkdir(parents=True)
            (root / "12_sotlas_by_example" / "05_native_control_flow.sotlas").write_text(
                "fn main() {}\n", encoding="utf-8"
            )
            (root / "manifest.json").write_text(
                '{"examples":[{"id":"12_sotlas_by_example_native_control_flow",'
                '"entry":"examples/12_sotlas_by_example/05_native_control_flow.sotlas",'
                '"status":"EXPERIMENTAL","backend_contract":true}]}',
                encoding="utf-8",
            )

            self.assertEqual(VALIDATOR.validate_manifest(root), [])

    def test_unlisted_numbered_directory_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_manifest_") as temp:
            root = Path(temp) / "examples"
            (root / "01_hello").mkdir(parents=True)
            (root / "02_orphan").mkdir()
            (root / "01_hello" / "main.sotlas").write_text(
                "fn main() {}\n", encoding="utf-8"
            )
            (root / "manifest.json").write_text(
                '{"examples":[{"id":"01_hello","entry":"examples/01_hello/main.sotlas",'
                '"status":"EXPERIMENTAL"}]}',
                encoding="utf-8",
            )

            errors = VALIDATOR.validate_manifest(root)
            self.assertTrue(
                any("manifest example-directory coverage mismatch" in error for error in errors),
                errors,
            )


if __name__ == "__main__":
    unittest.main()
