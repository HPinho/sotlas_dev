"""Regression guards for the bounded Sotlas-native self-hosting contract.

The production compiler is still Python-backed, but the checked-in ``sotlas_lite``
bootstrap path has a narrower sovereignty claim: once Stage 0 has produced the
first native compiler, Stage 1/2 compilation must flow through the compiled
``sotlas_compile`` entrypoint and the fixed-point test must compare generated
compiler sources exactly. These guards prevent that bounded claim from silently
regressing into a Python trampoline or a weaker smoke test.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas.bootstrap_pipeline import NATIVE_DRIVER_C


class SotlasSelfHostSovereigntyContractTests(unittest.TestCase):
    def test_native_driver_routes_selfhost_through_compiled_sotlas_entrypoint(self):
        self.assertIn(
            "size_t sotlas_compile(const uint8_t *source, uint8_t *out_buf, size_t max_len);",
            NATIVE_DRIVER_C,
        )
        self.assertIn("static int run_selfhost_command", NATIVE_DRIVER_C)
        self.assertIn(
            "size_t out_len = sotlas_compile(src, out, MAX_OUTPUT_SIZE);",
            NATIVE_DRIVER_C,
        )
        self.assertIn(
            'if (strcmp(argv[1], "selfhost") == 0 || strcmp(argv[1], "bootstrap") == 0)',
            NATIVE_DRIVER_C,
        )

    def test_native_driver_has_no_python_process_escape_hatch(self):
        lowered = NATIVE_DRIVER_C.lower()
        forbidden = (
            "python3",
            "python.exe",
            "py.exe",
            "sys.executable",
            "subprocess.",
            "-m sotlas",
            "-m sotlas_compile",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, lowered)

    def test_fixed_point_gate_requires_exact_stage2_stage3_source_identity(self):
        gate = (ROOT / "tests" / "test_sotlas_self_hosting.py").read_text(
            encoding="utf-8"
        )
        required = (
            "def test_native_compiler_stage2_self_compilation_fixed_point(self):",
            "stage2_c = self.tmp_path / \"stage2_compiler.c\"",
            "[str(self.native_compiler), str(BOOTSTRAP_ENTRY), \"-o\", str(stage2_c)]",
            "stage3_c = self.tmp_path / \"stage3_compiler.c\"",
            "[str(stage2_exe), str(BOOTSTRAP_ENTRY), \"-o\", str(stage3_c)]",
            "content_st2 = stage2_c.read_text(encoding=\"utf-8\")",
            "content_st3 = stage3_c.read_text(encoding=\"utf-8\")",
            "self.assertEqual(content_st2, content_st3",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, gate)


if __name__ == "__main__":
    unittest.main()
