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
sys.path.insert(0, str(ROOT / "compiler"))
from sotlas.llvm_toolchain import default_toolchain  # noqa: E402

BOOTSTRAP_PATH = ROOT / "compiler" / "sotlas_compile" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location("sotlas_stdlib_runtime_bootstrap", BOOTSTRAP_PATH)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)


class SotlasStdlibRuntimeTests(unittest.TestCase):
    def test_data_structures_example_compiles_and_runs_with_foundation_hashmap(self):
        if not default_toolchain.is_available() and not (shutil.which("gcc") or shutil.which("clang")):
            self.skipTest("GCC or Clang is required for native example execution")

        with tempfile.TemporaryDirectory(prefix="sotlas-data-structures-example-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            (project / "foundation").mkdir()
            shutil.copy2(ROOT / "stdlib" / "core" / "iter.sotlas", project / "core" / "iter.sotlas")
            shutil.copy2(
                ROOT / "stdlib" / "foundation" / "hashmap.sotlas",
                project / "foundation" / "hashmap.sotlas",
            )
            source_file = project / "main.sotlas"
            shutil.copy2(ROOT / "examples" / "08_data_structures" / "main.sotlas", source_file)
            executable = project / ("data_structures.exe" if os.name == "nt" else "data_structures")
            default_toolchain.compile_source_to_native(
                source_file.read_text(encoding="utf-8"),
                str(source_file),
                executable,
                emit_type="exe",
                backend="c11",
            )
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_foundation_hashmap_preserves_u64_values_and_collision_probe_after_remove(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        source = """module test::hashmap_u64_runtime;
import foundation::hashmap::*;

static mut entries: [HashEntry; 8] = 0;

pub fn main() -> i32 {
    let mut map: HashMapU64 = hashmap_new(entries as *mut HashEntry, 8);
    unsafe {
    let unavailable: HashMapU64 = hashmap_new(null, 4);
    if hashmap_cap((&unavailable) as *const HashMapU64) != 0 { return 20; }
    if hashmap_insert((&unavailable) as *mut HashMapU64, 1, 2) { return 21; }
    if hashmap_get((&unavailable) as *const HashMapU64, 1).has_value { return 22; }
    let mutable_map: *mut HashMapU64 = (&mut map) as *mut HashMapU64;
    let readonly_map: *const HashMapU64 = (&map) as *const HashMapU64;
    if !hashmap_insert(mutable_map, 0, 1311768467463790320) { return 1; }
    if !hashmap_insert(mutable_map, 8, 18446744073709551614) { return 2; }
    if hashmap_len(readonly_map) != 2 { return 3; }
    if !hashmap_insert(mutable_map, 0, 18364758544493064720) { return 4; }
    if hashmap_len(readonly_map) != 2 { return 5; }
    let first: OptionU64 = hashmap_get(readonly_map, 0);
    if !first.has_value || first.value != 18364758544493064720 { return 6; }
    if !hashmap_remove(mutable_map, 0) { return 7; }
    let collided: OptionU64 = hashmap_get(readonly_map, 8);
    if !collided.has_value || collided.value != 18446744073709551614 { return 8; }
    if hashmap_len(readonly_map) != 1 { return 9; }
    hashmap_clear(mutable_map);
    let mut full: HashMapU64 = hashmap_new(entries as *mut HashEntry, 2);
    let full_map: *mut HashMapU64 = (&mut full) as *mut HashMapU64;
    let full_readonly: *const HashMapU64 = (&full) as *const HashMapU64;
    if !hashmap_insert(full_map, 11, 101) || !hashmap_insert(full_map, 22, 202) { return 10; }
    if hashmap_len(full_readonly) != 2 { return 11; }
    if !hashmap_insert(full_map, 11, 303) { return 12; }
    let updated: OptionU64 = hashmap_get(full_readonly, 11);
    if !updated.has_value || updated.value != 303 { return 13; }
    if hashmap_len(full_readonly) != 2 { return 14; }
    if hashmap_insert(full_map, 33, 404) { return 15; }
    if hashmap_len(full_readonly) != 2 { return 16; }
    let mut malformed: HashMapU64 = hashmap_new(entries as *mut HashEntry, 0);
    malformed.count = 1;
    let malformed_map: *mut HashMapU64 = (&mut malformed) as *mut HashMapU64;
    let malformed_readonly: *const HashMapU64 = (&malformed) as *const HashMapU64;
    let missing: OptionU64 = hashmap_get(malformed_readonly, 11);
    if missing.has_value { return 17; }
    if hashmap_remove(malformed_map, 11) { return 18; }
    if hashmap_len(malformed_readonly) != 0 { return 19; }
    let mut overfull: HashMapU64 = hashmap_new(entries as *mut HashEntry, 2);
    overfull.count = 3;
    entries[0].is_occupied = true;
    entries[0].key = 11;
    entries[0].value = 101;
    let overfull_map: *mut HashMapU64 = (&mut overfull) as *mut HashMapU64;
    let overfull_readonly: *const HashMapU64 = (&overfull) as *const HashMapU64;
    if hashmap_insert(overfull_map, 11, 999) { return 23; }
    let rejected: OptionU64 = hashmap_get(overfull_readonly, 11);
    if rejected.has_value { return 24; }
    if hashmap_remove(overfull_map, 11) { return 25; }
    if hashmap_len(overfull_readonly) != 0 || overfull.count != 3 ||
        entries[0].value != 101 {
        return 26;
    }
    return 0;
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-hashmap-u64-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            destination = project / "foundation" / "hashmap.sotlas"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "stdlib" / "foundation" / "hashmap.sotlas", destination)
            source_file = project / "main.sotlas"
            source_file.write_text(source, encoding="utf-8")
            generated = project / "hashmap_u64.c"
            executable = project / ("hashmap_u64.exe" if os.name == "nt" else "hashmap_u64")
            bootstrap.emit_c_project(source_file, generated)
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", str(generated), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_bounded_vector_and_result_error_contract_run_natively(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        source = """module app::stdlib_vector_result_native;
import foundation::vec::*;
import core::result::*;

static mut storage: [u32; 2] = [0; 2];

pub fn main() -> i32 {
    unsafe {
    let unavailable: VecU32 = vec_new(null, 4);
    if vec_capacity((&unavailable) as *const VecU32) != 0 { return 28; }
    if vec_push((&unavailable) as *mut VecU32, 1u32) { return 29; }
    let unavailable_value: OptionU32 = vec_get(
        (&unavailable) as *const VecU32, 0
    );
    if unavailable_value.has_value { return 30; }
    if vec_len(null) != 0 || vec_capacity(null) != 0 || !vec_is_empty(null) {
        return 31;
    }
    if vec_push(null, 7u32) { return 32; }
    let null_value: OptionU32 = vec_get(null, 0);
    let null_pop: OptionU32 = vec_pop(null);
    if null_value.has_value || null_pop.has_value { return 33; }
    vec_clear(null);
    let mut values: VecU32 = vec_new(storage as *mut u32, 2);
    if !vec_is_empty((&values) as *const VecU32) { return 1; }
    if !vec_push((&mut values) as *mut VecU32, 17u32) { return 2; }
    if !vec_push((&mut values) as *mut VecU32, 29u32) { return 3; }
    if vec_push((&mut values) as *mut VecU32, 41u32) { return 4; }
    if vec_len((&values) as *const VecU32) != 2 { return 5; }
    let first: OptionU32 = vec_get((&values) as *const VecU32, 0);
    if !first.has_value || first.value != 17u32 { return 6; }
    let outside: OptionU32 = vec_get((&values) as *const VecU32, 2);
    if outside.has_value { return 7; }
    values.length = 3;
    if vec_len((&values) as *const VecU32) != 0 ||
        !vec_is_empty((&values) as *const VecU32) || values.length != 3 {
        return 37;
    }
    let malformed_value: OptionU32 = vec_get((&values) as *const VecU32, 0);
    if malformed_value.has_value { return 20; }
    let malformed_pop: OptionU32 = vec_pop((&mut values) as *mut VecU32);
    if malformed_pop.has_value || values.length != 3 { return 21; }
    values.length = 2;
    let last: OptionU32 = vec_pop((&mut values) as *mut VecU32);
    if !last.has_value || last.value != 29u32 || vec_len((&values) as *const VecU32) != 1 {
        return 34;
    }
    vec_clear((&mut values) as *mut VecU32);
    if vec_len((&values) as *const VecU32) != 0 ||
        vec_capacity((&values) as *const VecU32) != 2 || storage[0] != 17u32 {
        return 35;
    }
    let empty_pop: OptionU32 = vec_pop((&mut values) as *mut VecU32);
    let empty_value: OptionU32 = vec_get((&values) as *const VecU32, 0);
    if empty_pop.has_value || empty_value.has_value { return 36; }

    let success: ResultU32 = ResultU32::ok(53u32);
    if success.status != ResultCode::Ok || success.value != 53u32 { return 8; }
    let failure: ResultU32 = ResultU32::err(ResultCode::InvalidParam);
    if failure.status != ResultCode::InvalidParam || failure.value != 0u32 { return 9; }
    let zero_success: ResultU32 = ResultU32::ok(0u32);
    let mut extracted_u32: u32 = 99u32;
    if !zero_success.try_unwrap((&mut extracted_u32) as *mut u32) || extracted_u32 != 0u32 { return 13; }
    if zero_success.try_unwrap(null) { return 18; }
    extracted_u32 = 77u32;
    if failure.try_unwrap((&mut extracted_u32) as *mut u32) || extracted_u32 != 77u32 { return 14; }
    let false_success: ResultBool = ResultBool::ok(false);
    if !false_success.is_ok() || false_success.is_err() || false_success.unwrap_or(true) { return 22; }
    let mut extracted_bool: bool = true;
    if !false_success.try_unwrap((&mut extracted_bool) as *mut bool) || extracted_bool { return 23; }
    let bool_failure: ResultBool = ResultBool::err(ResultCode::TimedOut);
    if !bool_failure.is_err() || bool_failure.unwrap_err() != ResultCode::TimedOut { return 24; }
    if !bool_failure.unwrap_or(true) { return 25; }
    extracted_bool = true;
    if bool_failure.try_unwrap((&mut extracted_bool) as *mut bool) || !extracted_bool { return 26; }
    if false_success.try_unwrap(null) { return 27; }
    let negative_success: ResultI32 = ResultI32::ok(-17i32);
    let mut extracted_i32: i32 = 0i32;
    if !negative_success.try_unwrap((&mut extracted_i32) as *mut i32) || extracted_i32 != -17i32 { return 15; }
    let wide_success: ResultU64 = ResultU64::ok(18446744073709551615u64);
    if !wide_success.is_ok() || wide_success.unwrap() != 18446744073709551615u64 { return 10; }
    let mut extracted_u64: u64 = 0u64;
    if !wide_success.try_unwrap((&mut extracted_u64) as *mut u64) || extracted_u64 != 18446744073709551615u64 { return 16; }
    let wide_failure: ResultU64 = ResultU64::err(ResultCode::NotFound);
    if !wide_failure.is_err() || wide_failure.unwrap_err() != ResultCode::NotFound { return 11; }
    if wide_failure.unwrap_or(77u64) != 77u64 { return 12; }
    extracted_u64 = 81u64;
    if wide_failure.try_unwrap((&mut extracted_u64) as *mut u64) || extracted_u64 != 81u64 { return 17; }
    return 0;
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-vector-result-") as temporary:
            project = Path(temporary)
            for relative in (
                Path("foundation") / "vec.sotlas",
                Path("core") / "result.sotlas",
            ):
                destination = project / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / "stdlib" / relative, destination)
            source_file = project / "main.sotlas"
            source_file.write_text(source, encoding="utf-8")
            generated = project / "stdlib_vector_result.c"
            executable = project / (
                "stdlib_vector_result.exe" if os.name == "nt" else "stdlib_vector_result"
            )
            bootstrap.emit_c_project(source_file, generated)
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(generated), "-o", str(executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_string_vector_and_result_compose_in_a_native_preview_program(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-preview-stdlib-integration-") as temporary:
            project = Path(temporary)
            modules = (
                (Path("core") / "alloc.sotlas", ROOT / "stdlib" / "core" / "alloc.sotlas"),
                (Path("core") / "string.sotlas", ROOT / "stdlib" / "core" / "string.sotlas"),
                (Path("core") / "result.sotlas", ROOT / "stdlib" / "core" / "result.sotlas"),
                (Path("foundation") / "vec.sotlas", ROOT / "stdlib" / "foundation" / "vec.sotlas"),
            )
            for relative, source in modules:
                destination = project / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            source_file = project / "main.sotlas"
            shutil.copy2(
                ROOT / "tests" / "native" / "test_preview_stdlib_integration.sotlas",
                source_file,
            )
            generated = project / "preview_stdlib_integration.c"
            executable = project / (
                "preview_stdlib_integration.exe"
                if os.name == "nt" else "preview_stdlib_integration"
            )
            bootstrap.emit_c_project(source_file, generated)
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(generated), "-o", str(executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_core_arc_local_helpers_reject_underflow_and_overflow(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        source = """module app::arc_local_bounds;
import core::arc::*;

pub fn main() -> i32 {
    unsafe {
    let mut live: ArcHeader = 0;
    live.ref_count = 1u64;
    let live_ptr: *mut ArcHeader = (&mut live) as *mut ArcHeader;
    if arc_retain_local(live_ptr) == null { return 1; }
    if arc_count(live_ptr as *const ArcHeader) != 2u64 { return 2; }
    if arc_release_local(live_ptr) { return 3; }
    if !arc_release_local(live_ptr) { return 4; }
    if arc_release_local(live_ptr) { return 5; }
    if arc_retain_local(live_ptr) != null { return 6; }
    if arc_count(live_ptr as *const ArcHeader) != 0u64 { return 7; }

    let mut saturated: ArcHeader = 0;
    saturated.ref_count = 18446744073709551615u64;
    let saturated_ptr: *mut ArcHeader = (&mut saturated) as *mut ArcHeader;
    if arc_retain_local(saturated_ptr) != null { return 8; }
    if arc_count(saturated_ptr as *const ArcHeader)
        != 18446744073709551615u64 { return 9; }

    let mut shared: SharedCounter = SharedCounter::new(7u64);
    if !shared.retain() { return 10; }
    if arc_count((&shared.header) as *const ArcHeader) != 2u64 { return 11; }
    if shared.release() { return 12; }
    if !shared.release() { return 13; }
    if shared.retain() { return 14; }
    return 0;
    }
}
"""
        implementations = (
            ROOT / "stdlib",
            ROOT / "bootstrap" / "sotlas",
        )
        for implementation in implementations:
            with self.subTest(implementation=implementation.name):
                with tempfile.TemporaryDirectory(prefix="sotlas-arc-local-") as temporary:
                    project = Path(temporary)
                    for module in ("arc", "mem"):
                        destination = project / "core" / f"{module}.sotlas"
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(implementation / "core" / f"{module}.sotlas", destination)
                    source_file = project / "main.sotlas"
                    source_file.write_text(source, encoding="utf-8")
                    generated = project / "arc_local.c"
                    executable = project / ("arc_local.exe" if os.name == "nt" else "arc_local")
                    bootstrap.emit_c_project(source_file, generated)
                    compiled = subprocess.run(
                        [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                         str(generated), "-o", str(executable)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(compiled.returncode, 0, compiled.stderr or compiled.stdout)
                    executed = subprocess.run(
                        [str(executable)], capture_output=True, text=True, check=False
                    )
                    self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_arena_allocation_rejects_exhaustion_and_address_overflow(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-arena-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            library = (ROOT / "stdlib" / "foundation" / "alloc.sotlas").read_text(encoding="utf-8")
            native_checks = (ROOT / "tests" / "native" / "test_arena_overflow_native.sotlas").read_text(encoding="utf-8")
            (project / "main.sotlas").write_text(
                library + "\n" + native_checks, encoding="utf-8"
            )

            generated = project / "arena_test.c"
            executable = project / ("arena_test.exe" if os.name == "nt" else "arena_test")
            bootstrap.emit_c_project(project / "main.sotlas", generated)
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", str(generated), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)

            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_string_native_contract_executes(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-string-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            shutil.copy2(ROOT / "stdlib" / "core" / "alloc.sotlas", project / "core" / "alloc.sotlas")
            shutil.copy2(ROOT / "stdlib" / "core" / "string.sotlas", project / "core" / "string.sotlas")
            shutil.copy2(ROOT / "stdlib" / "core" / "result.sotlas", project / "core" / "result.sotlas")
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

    def test_bootstrap_string_utf8_validator_executes(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native string check")

        source = """module test::bootstrap_string_utf8;
import core::string::*;
pub fn main() -> i32 {
    let empty: StringSlice = string_from_raw(null, 0);
    if !string_is_valid_utf8(empty) { return 1; }
    let mut valid: [u8; 4] = 0;
    unsafe {
        valid[0] = 0xF0u8;
        valid[1] = 0x9Fu8;
        valid[2] = 0x92u8;
        valid[3] = 0xA9u8;
    }
    if !string_is_valid_utf8(string_from_raw(valid as *const u8, 4)) {
        return 2;
    }
    unsafe {
        valid[0] = 0xEDu8;
        valid[1] = 0xA0u8;
        valid[2] = 0x80u8;
    }
    if string_is_valid_utf8(string_from_raw(valid as *const u8, 3)) {
        return 3;
    }
    if string_is_valid_utf8(string_from_raw(null, 1)) { return 4; }
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas-bootstrap-utf8-") as temporary:
            project = Path(temporary)
            core = project / "core"
            core.mkdir()
            shutil.copy2(
                ROOT / "bootstrap" / "sotlas" / "core" / "string.sotlas",
                core / "string.sotlas",
            )
            source_file = project / "main.sotlas"
            source_file.write_text(source, encoding="utf-8")
            generated = project / "bootstrap_string_utf8.c"
            executable = project / (
                "bootstrap_string_utf8.exe"
                if os.name == "nt" else "bootstrap_string_utf8"
            )
            bootstrap.emit_c_project(source_file, generated)
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(generated), "-o", str(executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_bootstrap_result_bool_executes(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native Result check")

        source = """module test::bootstrap_result_bool;
import core::result::*;
pub fn main() -> i32 {
    let success: ResultBool = ResultBool::ok(false);
    if !success.is_ok() || success.is_err() || success.unwrap_or(true) {
        return 1;
    }
    let mut value: bool = true;
    unsafe {
        if !success.try_unwrap((&mut value) as *mut bool) || value { return 2; }
    }
    let failure: ResultBool = ResultBool::err(ResultCode::TimedOut);
    if !failure.is_err() || failure.unwrap_err() != ResultCode::TimedOut {
        return 3;
    }
    value = true;
    unsafe {
        if failure.try_unwrap((&mut value) as *mut bool) || !value { return 4; }
    }
    if success.try_unwrap(null) { return 5; }
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas-bootstrap-result-bool-") as temporary:
            project = Path(temporary)
            core = project / "core"
            core.mkdir()
            shutil.copy2(
                ROOT / "bootstrap" / "sotlas" / "core" / "result.sotlas",
                core / "result.sotlas",
            )
            source_file = project / "main.sotlas"
            source_file.write_text(source, encoding="utf-8")
            generated = project / "bootstrap_result_bool.c"
            executable = project / (
                "bootstrap_result_bool.exe"
                if os.name == "nt" else "bootstrap_result_bool"
            )
            bootstrap.emit_c_project(source_file, generated)
            compiled = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(generated), "-o", str(executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_core_arena_and_bump_allocators_reject_usize_overflow(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-core-alloc-overflow-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            shutil.copy2(ROOT / "stdlib" / "core" / "alloc.sotlas", project / "core" / "alloc.sotlas")
            shutil.copy2(
                ROOT / "tests" / "native" / "test_core_alloc_overflow_native.sotlas",
                project / "main.sotlas",
            )

            generated = project / "alloc_overflow.c"
            executable = project / ("alloc_overflow.exe" if os.name == "nt" else "alloc_overflow")
            bootstrap.emit_c_project(project / "main.sotlas", generated)
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", str(generated), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)

            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_owned_string_growth_rejects_usize_overflow(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-string-overflow-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            for module in ("alloc", "string", "result"):
                shutil.copy2(ROOT / "stdlib" / "core" / f"{module}.sotlas", project / "core" / f"{module}.sotlas")
            shutil.copy2(
                ROOT / "tests" / "native" / "test_core_string_overflow_native.sotlas",
                project / "main.sotlas",
            )

            generated = project / "string_overflow.c"
            executable = project / ("string_overflow.exe" if os.name == "nt" else "string_overflow")
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

    def test_ring_buffer_native_contract_rejects_invalid_state(self):
        compiler = default_toolchain.find_tool("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("GCC or Clang is required for the native standard-library check")

        with tempfile.TemporaryDirectory(prefix="sotlas-stdlib-ring-buffer-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            library = (ROOT / "stdlib" / "core" / "ring_buffer.sotlas").read_text(encoding="utf-8")
            native_checks = (ROOT / "tests" / "native" / "test_ring_buffer_native.sotlas").read_text(encoding="utf-8")
            native_checks = native_checks.replace(
                "module test_ring_buffer_native;\nimport core::ring_buffer::*;", ""
            )
            (project / "main.sotlas").write_text(library + "\n" + native_checks, encoding="utf-8")

            executable = project / ("ring_buffer_test.exe" if os.name == "nt" else "ring_buffer_test")
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "compiler"), str(ROOT / "tools")))
            compiled = subprocess.run(
                [
                    sys.executable, "-m", "sotlas.cli", "compile",
                    str(project / "main.sotlas"), "--backend", "c11", "-o", str(executable),
                    "--cc", compiler,
                ],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run([str(executable)], cwd=project, capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stderr)


if __name__ == "__main__":
    unittest.main()
