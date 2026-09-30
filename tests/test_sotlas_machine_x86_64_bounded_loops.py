"""Bounded-loop execution gates for the Sotlas-owned x86-64 backend."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_machine_bounded_loop_compile"


def _load_backend():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            COMPILER_PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(COMPILER_PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    backend = importlib.import_module(f"{_CANONICAL_PACKAGE}.machine_x86_64")
    if Path(backend.__file__).resolve().parent != COMPILER_PACKAGE_DIR.resolve():
        raise RuntimeError("machine backend did not load from compiler/sotlas_compile")
    return backend


_BACKEND = _load_backend()
MachineBackendError = _BACKEND.MachineBackendError
compile_source_to_x86_64_sysv_assembly = (
    _BACKEND.compile_source_to_x86_64_sysv_assembly
)


class SotlasX8664BoundedLoopTests(unittest.TestCase):
    def test_runtime_bound_unit_step_loop_reaches_machine_backend(self):
        source = """
module test::machine_bounded_loop;
fn sum_to(limit: u32) -> u32 {
    let mut index: u32 = 0u32;
    let mut total: u32 = 0u32;
    while index < limit {
        total = total + index;
        index = index + 1u32;
    }
    return total;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_bounded_loop.sotlas"
        )
        self.assertIn(".globl sum_to", assembly)
        self.assertIn("setb al", assembly)
        self.assertGreaterEqual(assembly.count("jmp .Lsum_to_bb"), 2)

    def test_runtime_bound_inclusive_loop_stays_fail_closed_on_wrap_risk(self):
        source = """
module test::machine_unproven_loop;
fn sum_inclusive(limit: u8) -> u8 {
    let mut index: u8 = 0u8;
    let mut total: u8 = 0u8;
    while index <= limit {
        total = total + index;
        index = index + 1u8;
    }
    return total;
}
"""
        with self.assertRaisesRegex(
            MachineBackendError,
            "loop is not proven bounded without unsigned counter wrap",
        ):
            compile_source_to_x86_64_sysv_assembly(
                source, "machine_unproven_loop.sotlas"
            )

    def test_runtime_bound_multi_step_loop_stays_fail_closed_on_wrap_risk(self):
        source = """
module test::machine_unproven_step;
fn stepped(limit: u32) -> u32 {
    let mut index: u32 = 0u32;
    let mut total: u32 = 0u32;
    while index < limit {
        total = total + 1u32;
        index = index + 2u32;
    }
    return total;
}
"""
        with self.assertRaisesRegex(
            MachineBackendError,
            "loop is not proven bounded without unsigned counter wrap",
        ):
            compile_source_to_x86_64_sysv_assembly(
                source, "machine_unproven_step.sotlas"
            )

    def test_constant_inclusive_bound_is_accepted_when_next_step_cannot_wrap(self):
        source = """
module test::machine_constant_bounded_loop;
fn sum_fixed() -> u8 {
    let mut index: u8 = 0u8;
    let mut total: u8 = 0u8;
    while index <= 3u8 {
        total = total + index;
        index = index + 1u8;
    }
    return total;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_constant_bounded_loop.sotlas"
        )
        self.assertIn(".globl sum_fixed", assembly)
        self.assertIn("setbe al", assembly)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_runtime_bounded_loop(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for x86-64 loop execution gate")

        source = """
module test::machine_bounded_loop_e2e;
fn sum_to(limit: u32) -> u32 {
    let mut index: u32 = 0u32;
    let mut total: u32 = 0u32;
    while index < limit {
        total = total + index;
        index = index + 1u32;
    }
    return total;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_bounded_loop_e2e.sotlas"
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_loop_x86_64_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine_loop.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_loop_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t sum_to(uint32_t limit);
int main(void) {
    if (sum_to(0u) != 0u) return 1;
    if (sum_to(1u) != 0u) return 2;
    if (sum_to(4u) != 6u) return 3;
    if (sum_to(10u) != 45u) return 4;
    return 0;
}
""",
                encoding="utf-8",
            )
            build = subprocess.run(
                [compiler, str(caller_path), str(asm_path), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
