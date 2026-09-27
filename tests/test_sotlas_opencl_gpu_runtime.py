"""Build and execute the optional OpenCL GPU vector-add runtime contract."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))
from sotlas.llvm_toolchain import default_toolchain  # noqa: E402


class SotlasOpenCLGpuRuntimeTests(unittest.TestCase):
    def test_opencl_failure_paths_release_every_created_resource_without_a_gpu(self):
        if sys.platform != "linux":
            self.skipTest("The fault provider overrides Linux libOpenCL dynamic loading")
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for the OpenCL cleanup check")

        with tempfile.TemporaryDirectory(prefix="sotlas-opencl-fault-") as temp:
            directory = Path(temp)
            provider = directory / "libOpenCL.so.1"
            executable = directory / "opencl_fault_test"
            provider_build = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-shared", "-fPIC",
                 str(ROOT / "tests" / "native" / "fake_opencl_fault.c"),
                 "-o", str(provider)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(provider_build.returncode, 0,
                             provider_build.stderr or provider_build.stdout)
            runtime_build = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", str(ROOT / "runtime"),
                 str(ROOT / "runtime" / "opencl_vector.c"),
                 str(ROOT / "tests" / "native" / "test_opencl_fault_native.c"),
                 "-ldl", "-o", str(executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(runtime_build.returncode, 0,
                             runtime_build.stderr or runtime_build.stdout)

            # Exercise failures from partial initialization through readback. The
            # provider aborts during dlclose if any acquired OpenCL handle leaked.
            for fail_at in ("context", "queue", "program", "build", "kernel",
                            "buffer", "write", "arg", "kernel_enqueue",
                            "finish", "read", "profile"):
                with self.subTest(fail_at=fail_at):
                    environment = os.environ.copy()
                    environment["LD_LIBRARY_PATH"] = str(directory) + os.pathsep + environment.get(
                        "LD_LIBRARY_PATH", ""
                    )
                    environment["SOTLAS_FAKE_OPENCL_FAIL_AT"] = fail_at
                    executed = subprocess.run(
                        [str(executable)], env=environment,
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(executed.returncode, 0,
                                     executed.stderr or executed.stdout)

    def test_compute_policy_reports_cpu_and_validates_device_fallback(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for the compute policy check")

        with tempfile.TemporaryDirectory(prefix="sotlas-compute-policy-") as temp:
            executable = Path(temp) / (
                "compute_policy_test.exe" if os.name == "nt" else "compute_policy_test"
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "runtime"),
                str(ROOT / "runtime" / "opencl_vector.c"),
                str(ROOT / "tests" / "native" / "test_compute_policy_native.c"),
                "-o", str(executable),
            ]
            if os.name != "nt":
                command.append("-ldl")
            compiled = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr or compiled.stdout)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_f32_vector_add_runs_on_opencl_gpu_and_checks_failure_inputs(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for the OpenCL runtime check")

        with tempfile.TemporaryDirectory(prefix="sotlas-opencl-vector-") as temp:
            directory = Path(temp)
            executable = directory / (
                "opencl_vector_test.exe" if os.name == "nt" else "opencl_vector_test"
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "runtime"),
                str(ROOT / "runtime" / "opencl_vector.c"),
                str(ROOT / "tests" / "native" / "test_opencl_vector_native.c"),
                "-o", str(executable),
            ]
            if os.name != "nt":
                command.append("-ldl")
            compiled = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr or compiled.stdout)

            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            if executed.returncode == 77:
                self.skipTest("No OpenCL runtime or GPU is available on this host")
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_canonical_sotlas_c11_program_selects_gpu_or_cpu_fallback(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for the Sotlas/OpenCL integration")

        with tempfile.TemporaryDirectory(prefix="sotlas-opencl-e2e-") as temp:
            directory = Path(temp)
            object_file = directory / "sotlas_gpu_call.o"
            caller = directory / "gpu_caller.c"
            executable = directory / (
                "sotlas_gpu_call.exe" if os.name == "nt" else "sotlas_gpu_call"
            )
            default_toolchain.compile_source_to_native(
                (ROOT / "examples" / "13_opencl_vector_add" / "main.sotlas").read_text(encoding="utf-8"),
                "examples::opencl_vector_add",
                object_file,
                emit_type="obj",
                backend="c11",
            )
            caller.write_text(
                (ROOT / "examples" / "13_opencl_vector_add" / "host.c").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "runtime"), str(caller),
                str(ROOT / "runtime" / "opencl_vector.c"),
                str(object_file), "-o", str(executable),
            ]
            if os.name != "nt":
                command.append("-ldl")
            compiled = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr or compiled.stdout)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)


if __name__ == "__main__":
    unittest.main()
