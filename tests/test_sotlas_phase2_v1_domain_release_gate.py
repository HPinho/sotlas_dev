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
from sotlas.llvm_toolchain import (  # noqa: E402
    LLVMToolchain,
    canonical_llvm_frontend,
    default_toolchain,
)


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

QUARANTINE_ALIAS_REBIND_SOURCE = """module app::phase2_v1_quarantine_alias_rebind;
sole struct Token { value: u32; }

fn read_other(token: Token, other: Token) -> u32 {
    let mut alias = &token;
    quarantine token;
    alias = &other;
    unsafe { return alias.value; }
}

fn main() -> i32 {
    let token: Token = Token { value: 5u32 };
    let other: Token = Token { value: 37u32 };
    if read_other(move token, move other) == 37u32 { return 0; }
    return 1;
}
"""

QUARANTINE_STALE_ALIAS_SOURCE = """module app::phase2_v1_quarantine_stale_alias;
sole struct Token { value: u32; }

fn read_after_quarantine(token: Token) -> u32 {
    let alias = &token;
    quarantine token;
    unsafe { return alias.value; }
}

fn main() -> i32 { return 0; }
"""

SHARED_ARC_SOURCE = """module app::phase2_v1_shared_arc;
import core::arc::*;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;

fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroy_count = destroy_count + 1u32; }
}

fn exercise() -> u32 {
    let token: Token = Token { value: 41u32 };
    let first = share token;
    let second = share first;
    if first.value != 41u32 || second.value != 41u32 { return 1; }
    if destroy_count != 0u32 { return 2; }
    return 0;
}

fn main() -> i32 {
    let status: u32 = exercise();
    if status != 0u32 { return status as i32; }
    if destroy_count != 1u32 { return 3; }
    return 0;
}
"""

SHARED_DEFER_EARLY_RETURN_SOURCE = """module app::phase2_v1_shared_defer_early_return;
import core::arc::*;
sole struct Token { value: u32; }
static mut observed: u32 = 0;
static mut destroy_count: u32 = 0;

fn inspect(owner: direct Token, snapshot: whisper Token) -> void {
    unsafe { observed = observed + owner.value + snapshot.value; }
}

fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroy_count = destroy_count + 1u32; }
}

fn early(token: Token, return_early: bool) -> void {
    let alias = share token;
    defer inspect(&alias, &alias);
    if return_early { return; }
    return;
}

fn main() -> i32 {
    let first: Token = Token { value: 41u32 };
    let second: Token = Token { value: 41u32 };
    early(move first, true);
    early(move second, false);
    if observed != 164u32 { return 1; }
    if destroy_count != 2u32 { return 2; }
    return 0;
}
"""


class SotlasPhase2V1DomainReleaseGateTests(unittest.TestCase):
    def test_quarantine_alias_can_be_rebound_and_run_natively(self):
        if not default_toolchain.is_available() and not shutil.which("gcc"):
            self.skipTest("Clang or GCC is required for canonical ownership execution")
        with tempfile.TemporaryDirectory(prefix="sotlas-quarantine-rebind-") as temp:
            executable = Path(temp) / (
                "quarantine_rebind.exe" if os.name == "nt" else "quarantine_rebind"
            )
            default_toolchain.compile_source_to_native(
                QUARANTINE_ALIAS_REBIND_SOURCE,
                "app::phase2_v1_quarantine_alias_rebind",
                executable,
                emit_type="exe",
                backend="c11",
            )
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_quarantine_stale_alias_fails_closed_in_canonical_frontend(self):
        with self.assertRaisesRegex(
            canonical_llvm_frontend().SotlasBootstrapError,
            "reference alias 'alias' to quarantined owner 'token' is used after quarantine",
        ):
            LLVMToolchain.compile_c11_source(
                QUARANTINE_STALE_ALIAS_SOURCE,
                "<phase2-v1-quarantine-stale-alias>",
            )

    def test_shared_defer_runs_before_single_arc_drop_on_early_return(self):
        if not default_toolchain.is_available() and not shutil.which("gcc"):
            self.skipTest("Clang or GCC is required for canonical shared ARC execution")
        with tempfile.TemporaryDirectory(prefix="sotlas-shared-defer-return-") as temp:
            project = Path(temp)
            core = project / "core"
            core.mkdir()
            for module in ("arc", "mem"):
                shutil.copy2(
                    ROOT / "stdlib" / "core" / f"{module}.sotlas",
                    core / f"{module}.sotlas",
                )
            source_file = project / "main.sotlas"
            source_file.write_text(SHARED_DEFER_EARLY_RETURN_SOURCE, encoding="utf-8")
            executable = project / ("shared_defer_return.exe" if os.name == "nt" else "shared_defer_return")
            default_toolchain.compile_source_to_native(
                SHARED_DEFER_EARLY_RETURN_SOURCE,
                source_file,
                executable,
                emit_type="exe",
                backend="c11",
            )
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_shared_alias_chain_executes_through_canonical_c11_with_one_drop(self):
        if not default_toolchain.is_available() and not shutil.which("gcc"):
            self.skipTest("Clang or GCC is required for canonical shared ARC execution")
        with tempfile.TemporaryDirectory(prefix="sotlas-shared-canonical-") as temp:
            project = Path(temp)
            core = project / "core"
            core.mkdir()
            for module in ("arc", "mem"):
                shutil.copy2(
                    ROOT / "stdlib" / "core" / f"{module}.sotlas",
                    core / f"{module}.sotlas",
                )
            source_file = project / "main.sotlas"
            source_file.write_text(SHARED_ARC_SOURCE, encoding="utf-8")
            executable = project / (
                "shared_arc.exe" if os.name == "nt" else "shared_arc"
            )
            default_toolchain.compile_source_to_native(
                SHARED_ARC_SOURCE,
                source_file,
                executable,
                emit_type="exe",
                backend="c11",
            )
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

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
