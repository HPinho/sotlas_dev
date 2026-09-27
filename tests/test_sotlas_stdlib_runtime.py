"""Native behavior checks for the standard library preview subset."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sotlas.llvm_toolchain import default_toolchain  # noqa: E402

BOOTSTRAP_PATH = ROOT / "compiler" / "sotlas_compile" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("sotlas_stdlib_runtime_bootstrap", BOOTSTRAP_PATH)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)


class SotlasStdlibRuntimeTests(unittest.TestCase):
    def test_string_native_contract_executes(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-string-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            shutil.copy2(ROOT / "stdlib" / "core" / "alloc.sotlas", project / "core" / "alloc.sotlas")
            shutil.copy2(ROOT / "stdlib" / "core" / "string.sotlas", project / "core" / "string.sotlas")
            shutil.copy2(ROOT / "tests" / "native" / "test_string_native.sotlas", project / "main.sotlas")

            generated = project / "string_test.c"
            executable = project / ("string_test.exe" if os.name == "nt" else "string_test")
            bootstrap.emit_c_project(project / "main.sotlas", generated)
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", str(generated), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)

            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_string_buf_zero_and_minimum_capacity_are_memory_safe(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-string-buf-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            library = (ROOT / "stdlib" / "foundation" / "string_buf.sotlas").read_text(encoding="utf-8")
            native_checks = (ROOT / "tests" / "native" / "test_string_buf_native.sotlas").read_text(encoding="utf-8")
            (project / "main.sotlas").write_text(
                library + "\n" + native_checks, encoding="utf-8"
            )

            generated = project / "string_buf_test.c"
            executable = project / ("string_buf_test.exe" if os.name == "nt" else "string_buf_test")
            bootstrap.emit_c_project(project / "main.sotlas", generated)
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", str(generated), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)

            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)


if __name__ == "__main__":
    unittest.main()
