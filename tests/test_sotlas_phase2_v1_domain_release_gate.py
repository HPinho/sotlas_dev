"""Canonical native gates for the bounded ISLAND and HANDOVER subset."""
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


ISLAND_HANDOVER_SOURCE = """module app::phase2_v1_island_handover;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;

fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroy_count = destroy_count + 1u32; }
}

fn consume(token: Token) -> void { return; }

fn main() -> i32 {
    let source: Token = Token { value: 41u32 };
    let destination: Token = Token { value: 9u32 };
    consume(move destination);
    quarantine source;
    handover source to destination;
    if destination.value == 41u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
"""

EXTERNAL_WRAPPER_SOURCE = """module app::phase2_v1_external_wrapper;
@repr(C) sole struct Token { value: u32; }
@repr(C) sole struct Bundle { token: external Token; tag: u32; }
@extern(C) fn consume_bundle(bundle: external Bundle) -> void;
@system @export fn dispose(bundle: external Bundle) -> void {
    consume_bundle(move bundle);
    return;
}
"""


class SotlasPhase2V1DomainReleaseGateTests(unittest.TestCase):
    def test_island_handover_executes_through_canonical_c11_with_one_drop_per_owner(self):
        compiler_available = default_toolchain.is_available() or shutil.which("gcc")
        if not compiler_available:
            self.skipTest("Clang or GCC is required for canonical ownership execution")

        with tempfile.TemporaryDirectory(prefix="sotlas-island-handover-") as temp:
            executable = Path(temp) / (
                "island_handover.exe" if os.name == "nt" else "island_handover"
            )
            default_toolchain.compile_source_to_native(
                ISLAND_HANDOVER_SOURCE,
                "app::phase2_v1_island_handover",
                executable,
                emit_type="exe",
                backend="c11",
            )
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_external_repr_c_wrapper_executes_through_canonical_c11_and_c_caller(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("Clang or GCC is required for canonical FFI execution")

        with tempfile.TemporaryDirectory(prefix="sotlas-external-ffi-") as temp:
            directory = Path(temp)
            object_file = directory / "external_wrapper.o"
            caller = directory / "ffi_caller.c"
            executable = directory / (
                "external_wrapper.exe" if os.name == "nt" else "external_wrapper"
            )
            default_toolchain.compile_source_to_native(
                EXTERNAL_WRAPPER_SOURCE,
                "app::phase2_v1_external_wrapper",
                object_file,
                emit_type="obj",
                backend="c11",
            )
            caller.write_text(
                "#include <stdint.h>\n"
                "typedef struct { uint32_t value; } Token;\n"
                "typedef struct { Token token; uint32_t tag; } Bundle;\n"
                "extern void dispose(Bundle bundle);\n"
                "static uint32_t observed_value;\n"
                "static uint32_t observed_tag;\n"
                "void consume_bundle(Bundle bundle) {\n"
                "  observed_value = bundle.token.value;\n"
                "  observed_tag = bundle.tag;\n"
                "}\n"
                "int main(void) {\n"
                "  Bundle bundle = {{37u}, 9u};\n"
                "  dispose(bundle);\n"
                "  return observed_value == 37u && observed_tag == 9u ? 0 : 1;\n"
                "}\n",
                encoding="utf-8",
            )
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(caller), str(object_file), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)


if __name__ == "__main__":
    unittest.main()
