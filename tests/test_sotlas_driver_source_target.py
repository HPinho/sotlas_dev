"""Public driver coverage for source-profile target and artifact inference."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas import driver
from sotlas.execution_target import ExecutionTargetError


class SotlasPublicDriverTargetTests(unittest.TestCase):
    def _source(self, directory: str, text: str) -> Path:
        path = Path(directory) / "main.sotlas"
        path.write_text(text, encoding="utf-8")
        return path

    def test_barecore_compile_infers_freestanding_target_and_object(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::driver;\nfn entry() -> u8 { return 0; }\n",
            )
            with patch.object(
                driver.default_toolchain, "is_available", return_value=True
            ):
                prepared = driver.prepare_argv(
                    ["sotlas", "compile", str(source)]
                )
        self.assertIn("--target", prepared)
        target_at = prepared.index("--target")
        self.assertEqual(prepared[target_at + 1], "x86_64-freestanding")
        self.assertIn("--emit-obj", prepared)

    def test_explicit_aarch64_freestanding_target_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "target barecore;\nmodule kernel::arm;\nfn entry() -> u8 { return 0; }\n",
            )
            argv = [
                "sotlas", "compile", "--target", "aarch64-freestanding",
                "--cpu-feature", "sve2", "--emit-c", str(source),
            ]
            prepared = driver.prepare_argv(argv)
        self.assertEqual(prepared, argv)

    def test_barecore_rejects_explicit_hosted_target_before_cli(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "target barecore;\nmodule kernel::bad;\nfn entry() -> u8 { return 0; }\n",
            )
            original = [
                "sotlas", "compile", str(source),
                "--target", "x86_64-unknown-linux-gnu",
            ]
            stderr = StringIO()
            with patch.object(driver.sys, "argv", original), \
                 patch.object(driver.cli, "main") as delegated, \
                 patch.object(driver.sys, "stderr", stderr):
                result = driver.main()
        self.assertEqual(result, 2)
        delegated.assert_not_called()
        self.assertIn("requires a freestanding execution target", stderr.getvalue())

    def test_explicit_native_rejects_freestanding_override(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "target native;\nmodule app::native;\nfn main() -> u8 { return 0; }\n",
            )
            with self.assertRaisesRegex(
                ExecutionTargetError,
                "explicit native source profile cannot use a freestanding execution target",
            ):
                driver.prepare_argv([
                    "sotlas", "compile", str(source),
                    "--target", "x86_64-freestanding",
                ])

    def test_implicit_native_source_keeps_cli_host_default(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "module app::legacy;\nfn main() -> u8 { return 0; }\n",
            )
            argv = ["sotlas", "compile", str(source)]
            self.assertEqual(driver.prepare_argv(argv), argv)

    def test_options_before_source_do_not_confuse_source_detection(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::ordered;\nfn entry() -> u8 { return 0; }\n",
            )
            prepared = driver.prepare_argv([
                "sotlas", "compile", "--backend", "c11", "--emit-c", str(source),
            ])
        self.assertIn("--target", prepared)
        self.assertNotIn("--emit-obj", prepared)

    def test_invalid_source_is_left_to_canonical_cli_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(temp, "target barecore;\nthis is not a module\n")
            argv = ["sotlas", "compile", str(source)]
            self.assertEqual(driver.prepare_argv(argv), argv)

    def test_barecore_object_default_fails_closed_without_llvm(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::no_llvm;\nfn entry() -> u8 { return 0; }\n",
            )
            with patch.object(
                driver.default_toolchain, "is_available", return_value=False
            ), self.assertRaisesRegex(
                ExecutionTargetError,
                "barecore object emission requires Clang/LLVM",
            ):
                driver.prepare_argv(["sotlas", "compile", str(source)])

    def test_barecore_emit_c_does_not_require_llvm(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::portable;\nfn entry() -> u8 { return 0; }\n",
            )
            with patch.object(
                driver.default_toolchain, "is_available", return_value=False
            ):
                prepared = driver.prepare_argv([
                    "sotlas", "compile", "--emit-c", str(source)
                ])
        self.assertIn("--target", prepared)
        self.assertIn("--emit-c", prepared)
        self.assertNotIn("--emit-obj", prepared)

    def test_barecore_executable_requires_internal_linker(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::elf;\nfn entry() -> u8 { return 0; }\n",
            )
            with self.assertRaisesRegex(
                ExecutionTargetError,
                "barecore executable linking requires --linker internal",
            ):
                driver.prepare_argv([
                    "sotlas", "compile", str(source), "-o", "kernel.elf"
                ])

    def test_barecore_internal_linker_is_explicitly_allowed(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::linked;\nfn _start() -> u8 { return 0; }\n",
            )
            prepared = driver.prepare_argv([
                "sotlas", "compile", str(source), "--linker", "internal"
            ])
        self.assertIn("--target", prepared)
        self.assertNotIn("--emit-obj", prepared)

    def test_barecore_run_is_rejected_before_host_execution(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::run;\nfn entry() -> u8 { return 0; }\n",
            )
            original = ["sotlas", "run", str(source)]
            stderr = StringIO()
            with patch.object(driver.sys, "argv", original), \
                 patch.object(driver.cli, "main") as delegated, \
                 patch.object(driver.sys, "stderr", stderr):
                result = driver.main()
        self.assertEqual(result, 2)
        delegated.assert_not_called()
        self.assertIn("cannot be executed as a hosted process", stderr.getvalue())

    def test_main_delegates_with_inferred_target_object_and_restores_argv(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_driver_") as temp:
            source = self._source(
                temp,
                "barecore;\nmodule kernel::delegate;\nfn entry() -> u8 { return 0; }\n",
            )
            original = ["sotlas", "compile", str(source)]
            observed: list[list[str]] = []

            def delegated_main() -> int:
                observed.append(list(driver.sys.argv))
                return 0

            with patch.object(driver.sys, "argv", original), \
                 patch.object(driver.default_toolchain, "is_available", return_value=True), \
                 patch.object(driver.cli, "main", side_effect=delegated_main):
                self.assertEqual(driver.main(), 0)
                self.assertIs(driver.sys.argv, original)

        self.assertIn("--target", observed[0])
        self.assertIn("--emit-obj", observed[0])

    def test_compiler_and_tools_drivers_remain_identical(self):
        compiler_driver = (
            ROOT / "compiler" / "sotlas" / "driver.py"
        ).read_text(encoding="utf-8")
        tools_driver = (
            ROOT / "tools" / "sotlas" / "driver.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(compiler_driver, tools_driver)

    def test_console_scripts_route_through_public_driver(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('sotlas = "sotlas.driver:main"', pyproject)
        self.assertIn('sotlasc = "sotlas.driver:main"', pyproject)

        setup_source = (ROOT / "setup.py").read_text(encoding="utf-8")
        self.assertIn('"sotlas=sotlas.driver:main"', setup_source)
        self.assertIn('"sotlasc=sotlas.driver:main"', setup_source)


if __name__ == "__main__":
    unittest.main()
