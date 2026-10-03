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
    @staticmethod
    def _build_fake_provider(directory: Path, compiler: str) -> Path:
        provider_name = "OpenCL.dll" if os.name == "nt" else "libOpenCL.so.1"
        provider = directory / provider_name
        command = [
            str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-shared",
        ]
        if os.name != "nt":
            command.append("-fPIC")
        command.extend([
            str(ROOT / "tests" / "native" / "fake_opencl_fault.c"),
            "-o", str(provider),
        ])
        provider_build = subprocess.run(
            command, capture_output=True, text=True, check=False,
        )
        if provider_build.returncode != 0:
            raise AssertionError(provider_build.stderr or provider_build.stdout)
        return provider

    @staticmethod
    def _fake_provider_environment(directory: Path, fail_at: str | None = None) -> dict[str, str]:
        environment = os.environ.copy()
        if os.name == "nt":
            environment["PATH"] = str(directory) + os.pathsep + environment.get("PATH", "")
        else:
            environment["LD_LIBRARY_PATH"] = str(directory) + os.pathsep + environment.get(
                "LD_LIBRARY_PATH", ""
            )
        if fail_at is None:
            environment.pop("SOTLAS_FAKE_OPENCL_FAIL_AT", None)
        else:
            environment["SOTLAS_FAKE_OPENCL_FAIL_AT"] = fail_at
        return environment

    def test_fake_opencl_device_matches_cpu_vector_add(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for OpenCL equivalence testing")

        with tempfile.TemporaryDirectory(prefix="sotlas-opencl-equivalence-") as temp:
            directory = Path(temp)
            self._build_fake_provider(directory, compiler)
            executable = directory / (
                "opencl_equivalence_test.exe" if os.name == "nt" else "opencl_equivalence_test"
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "runtime"),
                str(ROOT / "runtime" / "opencl_vector.c"),
                str(ROOT / "tests" / "native" / "test_opencl_vector_equivalence_native.c"),
            ]
            if os.name != "nt":
                command.append("-ldl")
            command.extend(["-o", str(executable)])
            runtime_build = subprocess.run(
                command,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(runtime_build.returncode, 0,
                             runtime_build.stderr or runtime_build.stdout)
            environment = self._fake_provider_environment(directory)
            executed = subprocess.run(
                [str(executable)], env=environment,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(executed.returncode, 0,
                             executed.stderr or executed.stdout)

    def test_missing_gpu_falls_back_to_cpu_and_required_mode_preserves_output(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for OpenCL fallback testing")

        with tempfile.TemporaryDirectory(prefix="sotlas-opencl-fallback-") as temp:
            directory = Path(temp)
            self._build_fake_provider(directory, compiler)
            executable = directory / (
                "opencl_fallback_test.exe" if os.name == "nt" else "opencl_fallback_test"
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "runtime"),
                str(ROOT / "runtime" / "opencl_vector.c"),
                str(ROOT / "tests" / "native" / "test_opencl_fallback_native.c"),
            ]
            if os.name != "nt":
                command.append("-ldl")
            command.extend(["-o", str(executable)])
            compiled = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr or compiled.stdout)

            for unavailable in ("no_gpu", "no_platform"):
                with self.subTest(unavailable=unavailable):
                    executed = subprocess.run(
                        [str(executable)],
                        env=self._fake_provider_environment(directory, unavailable),
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(
                        executed.returncode, 0, executed.stderr or executed.stdout
                    )

    def test_opencl_failure_paths_release_every_created_resource_without_a_gpu(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for the OpenCL cleanup check")

        with tempfile.TemporaryDirectory(prefix="sotlas-opencl-fault-") as temp:
            directory = Path(temp)
            self._build_fake_provider(directory, compiler)
            executable = directory / (
                "opencl_fault_test.exe" if os.name == "nt" else "opencl_fault_test"
            )
            command = [
                str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "runtime"),
                str(ROOT / "runtime" / "opencl_vector.c"),
                str(ROOT / "tests" / "native" / "test_opencl_fault_native.c"),
            ]
            if os.name != "nt":
                command.append("-ldl")
            command.extend(["-o", str(executable)])
            runtime_build = subprocess.run(
                command,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(runtime_build.returncode, 0,
                             runtime_build.stderr or runtime_build.stdout)

            # Exercise failures from partial initialization through readback and
            # verify handle and buffer counters explicitly after runtime cleanup.
            for fail_at in ("context", "queue", "program", "build", "kernel",
                            "buffer", "write", "arg", "kernel_enqueue",
                            "finish", "read", "profile"):
                with self.subTest(fail_at=fail_at):
                    environment = self._fake_provider_environment(directory, fail_at)
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
