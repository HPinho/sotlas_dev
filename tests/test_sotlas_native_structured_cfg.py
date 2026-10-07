"""Native execution gates for structured loops, mutable state and CFG scope."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))
from sotlas.bootstrap_pipeline import build_stage1_native_compiler


def execute_windows_text(path: Path) -> int:
    """Run a zero-argument, relocation-free SysV entry in a child process.

    The wrapper preserves Windows' additional nonvolatile registers and aligns
    the stack. Fixtures have no foreign calls or data-section references.
    """
    data = path.read_bytes()
    section_headers = struct.unpack_from("<Q", data, 40)[0]
    section_size, section_count = struct.unpack_from("<HH", data, 58)
    text = None
    for index in range(section_count):
        header = section_headers + index * section_size
        flags = struct.unpack_from("<Q", data, header + 8)[0]
        if flags & 4:
            offset, length = struct.unpack_from("<QQ", data, header + 24)
            text = data[offset:offset + length]
            break
    if not text:
        raise RuntimeError("object has no executable text")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    kernel.VirtualAlloc.restype = ctypes.c_void_p
    kernel.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    kernel.VirtualProtect.restype = ctypes.c_int
    kernel.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
    size = len(text) + 25
    address = kernel.VirtualAlloc(None, size, 0x3000, 0x04)
    if not address:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        wrapper = b"\x57\x56\x48\x83\xec\x28\x48\xb8" + struct.pack("<Q", address + 25)
        wrapper += b"\xff\xd0\x48\x83\xc4\x28\x5e\x5f\xc3"
        ctypes.memmove(address, wrapper + text, size)
        old = ctypes.c_uint32()
        if not kernel.VirtualProtect(address, size, 0x20, ctypes.byref(old)):
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.WINFUNCTYPE(ctypes.c_uint32)(address)()
    finally:
        kernel.VirtualFree(address, 0, 0x8000)


class NativeStructuredCFGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-structured-cfg-")
        cls.directory = Path(cls.temp.name)
        cls.stage = cls.directory / ("stage1.exe" if os.name == "nt" else "stage1")
        build_stage1_native_compiler(cls.stage, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compile(self, name: str, body: str):
        source = self.directory / f"{name}.sotlas"
        source.write_text("module gate::structured;\n" + body, encoding="utf-8")
        output = self.directory / f"{name}.o"
        result = subprocess.run([str(self.stage), "--compile-obj", str(source), str(output)],
                                capture_output=True, text=True, timeout=30)
        return result, output

    def assert_native_result(self, name: str, body: str, expected: int):
        result, output = self.compile(name, body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[:4], b"\x7fELF")
        if sys.platform == "win32":
            execution = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                        "--execute", str(output)], capture_output=True, text=True, timeout=15)
            self.assertEqual(execution.returncode, 0, execution.stderr)
            self.assertEqual(int(execution.stdout.strip()), expected)
        elif sys.platform.startswith("linux"):
            binary = self.directory / name
            link = subprocess.run([str(self.stage), "--link-exe", str(output), str(binary), "main_entry"],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(link.returncode, 0, link.stderr)
            self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, expected)

    def test_nested_loop_accumulator_and_counter_reset(self):
        self.assert_native_result("nested", """
pub fn main_entry() -> u32 {
    let mut total: u32 = 0;
    let mut row: u32 = 0;
    while row < 3 {
        let mut column: u32 = 0;
        while column < 2 {
            total = total + row + column;
            column = column + 1;
        }
        row = row + 1;
    }
    return total;
}
""", 9)

    def test_break_continue_and_branch_join_preserve_outer_state(self):
        self.assert_native_result("jumps", """
pub fn main_entry() -> u32 {
    let mut row: u32 = 0;
    let mut total: u32 = 0;
    while row < 4 {
        row = row + 1;
        if row == 2 { continue; }
        let mut column: u32 = 0;
        while column < 5 {
            column = column + 1;
            if column == 2 { continue; }
            if column == 4 { break; }
            if row == 3 { total = total + 3; }
            else { total = total + 1; }
        }
    }
    return total;
}
""", 10)

    def test_short_circuit_does_not_execute_trapping_rhs(self):
        self.assert_native_result("short_circuit", """
pub fn main_entry() -> u32 {
    let mut row: u32 = 0;
    let mut total: u32 = 0;
    while row < 2 {
        let mut column: u32 = 0;
        while column < 2 {
            let zero: u32 = 0;
            if row == row || 12 / zero > 1 { total = total + 1; }
            if row != row && 12 / zero > 1 { return 99; }
            column = column + 1;
        }
        row = row + 1;
    }
    return total;
}
""", 4)

    def test_early_return_exits_both_loops(self):
        self.assert_native_result("early_return", """
pub fn main_entry() -> u32 {
    let mut row: u32 = 0;
    while row < 3 {
        let mut column: u32 = 0;
        while column < 3 {
            if row == 1 && column == 2 { return 42; }
            column = column + 1;
        }
        row = row + 1;
    }
    return 7;
}
""", 42)

    def test_inner_loop_binding_cannot_escape(self):
        result, output = self.compile("scope_error", """
pub fn main_entry() -> u32 {
    let mut row: u32 = 0;
    while row < 2 {
        let mut column: u32 = 0;
        while column < 2 { column = column + 1; }
        row = row + 1;
    }
    return column;
}
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_aligned_nested_fields_and_wide_mutable_state(self):
        self.assert_native_result("nested_fields", """
struct Slice { prefix: u8; length: u64; }
struct Holder { flag: u8; slice: Slice; tail: u32; }
pub fn main_entry() -> u32 {
    let holder: Holder = Holder { flag: 7, slice: Slice { prefix: 3, length: 40 }, tail: 2 };
    let mut total: u64 = 0;
    let mut row: u32 = 0;
    while row < 2 {
        let mut column: u32 = 0;
        while column < 2 {
            total = total + holder.slice.length;
            column = column + 1;
        }
        row = row + 1;
    }
    return total as u32 + holder.tail + holder.flag as u32 + holder.slice.prefix as u32;
}
""", 172)

    def test_structured_nesting_limit_fails_without_output(self):
        statement = "row = row + 1;"
        for _ in range(65):
            statement = "if row < 2 { " + statement + " }"
        body = """pub fn main_entry() -> u32 {
    let mut row: u32 = 0;
    while row < 2 {
        let mut column: u32 = 0;
        while column < 2 { column = column + 1; }
""" + statement + "\n} return row; }"
        result, output = self.compile("depth_limit", body)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_explicit_void_return_and_implicit_void_fallthrough(self):
        self.assert_native_result("void_helpers", """
pub fn main_entry() -> u32 {
    let mut row: u32 = 0;
    let mut total: u32 = 0;
    while row < 2 {
        explicit_return();
        let mut column: u32 = 0;
        while column < 2 {
            implicit_return();
            total = total + 1;
            column = column + 1;
        }
        row = row + 1;
    }
    return total;
}
fn explicit_return() -> void { return; }
fn implicit_return() -> void { }
""", 4)

    def test_void_function_cannot_return_a_value(self):
        result, output = self.compile("void_value_error", """
pub fn main_entry() -> u32 { return 1; }
fn invalid() -> void { return 1; }
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_bool_store_does_not_overwrite_adjacent_narrow_fields(self):
        self.assert_native_result("bool_layout", """
struct State { active: bool; marker: u8; limit: u16; wide: u64; }
pub fn main_entry() -> u32 {
    let state: State = State { marker: 7, limit: 9, wide: 40, active: true };
    let mut total: u32 = 0;
    let mut row: u32 = 0;
    while row < 1 {
        let mut column: u32 = 0;
        while column < 1 {
            if state.active {
                total = total + state.marker as u32 + state.limit as u32;
            }
            column = column + 1;
        }
        row = row + 1;
    }
    return total + state.wide as u32;
}
""", 56)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--execute":
        print(execute_windows_text(Path(sys.argv[2])))
    else:
        unittest.main()
