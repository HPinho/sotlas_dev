"""Tests for the preview installation/toolchain doctor."""
from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PACKAGE = "_sotlas_doctor_canonical"
package = ModuleType(CANONICAL_PACKAGE)
package.__path__ = [str(ROOT / "compiler" / "sotlas")]
package.SOTLAS_VERSION = "1.0.0rc1"
package.SOTLAS_LANG_VERSION = "1.0.0"
sys.modules[CANONICAL_PACKAGE] = package
doctor = importlib.import_module(f"{CANONICAL_PACKAGE}.doctor")


class SotlasDoctorTests(unittest.TestCase):
    def _frontend(self):
        return SimpleNamespace(
            parse=lambda *args, **kwargs: None,
            check=lambda *args, **kwargs: None,
            emit_c=lambda *args, **kwargs: "",
        )

    def test_collect_report_marks_native_capabilities_when_tools_exist(self):
        toolchain = Mock()
        toolchain.find_tool.return_value = Path("/opt/llvm/bin/clang")
        toolchain.get_version.return_value = "clang version 18.1.0"
        with (
            patch.object(doctor, "canonical_llvm_frontend", return_value=self._frontend()),
            patch.object(doctor, "LLVMToolchain", return_value=toolchain),
            patch.object(doctor, "_first_path", return_value=Path("/usr/bin/clang")),
            patch.object(doctor.importlib.util, "find_spec", return_value=object()),
        ):
            report = doctor.collect_report()

        self.assertTrue(report["core_ready"])
        self.assertTrue(report["native_ready"])
        self.assertTrue(report["capabilities"]["check"])
        self.assertTrue(report["capabilities"]["emit_c11"])
        self.assertTrue(report["capabilities"]["native_c11"])
        self.assertTrue(report["capabilities"]["llvm_native"])
        self.assertTrue(report["capabilities"]["lsp"])
        self.assertEqual(report["checks"]["llvm"]["version"], "clang version 18.1.0")

    def test_collect_report_keeps_core_ready_without_optional_native_tools(self):
        toolchain = Mock()
        toolchain.find_tool.return_value = None
        with (
            patch.object(doctor, "canonical_llvm_frontend", return_value=self._frontend()),
            patch.object(doctor, "LLVMToolchain", return_value=toolchain),
            patch.object(doctor, "_first_path", return_value=None),
            patch.object(doctor.importlib.util, "find_spec", return_value=object()),
        ):
            report = doctor.collect_report()

        self.assertTrue(report["core_ready"])
        self.assertFalse(report["native_ready"])
        self.assertTrue(report["capabilities"]["check"])
        self.assertTrue(report["capabilities"]["emit_c11"])
        self.assertFalse(report["capabilities"]["native_c11"])
        self.assertFalse(report["capabilities"]["llvm_native"])

    def test_frontend_failure_blocks_core_capabilities(self):
        toolchain = Mock()
        toolchain.find_tool.return_value = None
        with (
            patch.object(doctor, "canonical_llvm_frontend", side_effect=RuntimeError("boom")),
            patch.object(doctor, "LLVMToolchain", return_value=toolchain),
            patch.object(doctor, "_first_path", return_value=None),
            patch.object(doctor.importlib.util, "find_spec", return_value=object()),
        ):
            report = doctor.collect_report()

        self.assertFalse(report["core_ready"])
        self.assertEqual(report["status"], "blocked")
        self.assertIn("RuntimeError", report["checks"]["canonical_frontend"]["detail"])
        self.assertFalse(any(report["capabilities"][name] for name in ("check", "emit_c11", "native_c11", "llvm_native")))

    def test_main_json_and_requirements_have_stable_exit_codes(self):
        report = {
            "sotlas_version": "1.0.0rc1",
            "language_version": "1.0.0",
            "host": {"platform": "test", "machine": "test"},
            "status": "ready",
            "core_ready": True,
            "native_ready": False,
            "checks": {},
            "capabilities": {
                "check": True,
                "emit_c11": True,
                "native_c11": False,
                "llvm_native": False,
                "lsp": True,
            },
        }
        with patch.object(doctor, "collect_report", return_value=report):
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                self.assertEqual(doctor.main(["--json"]), 0)
            decoded = json.loads(stdout.getvalue())
            self.assertEqual(decoded["sotlas_version"], "1.0.0rc1")
            self.assertTrue(decoded["core_ready"])
            with patch("sys.stdout", io.StringIO()):
                self.assertEqual(doctor.main(["--json", "--require-native"]), 2)
                self.assertEqual(doctor.main(["--json", "--require-llvm"]), 3)

    def test_pyproject_exposes_doctor_console_script(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('sotlas-doctor = "sotlas.doctor:main"', pyproject)


if __name__ == "__main__":
    unittest.main()
