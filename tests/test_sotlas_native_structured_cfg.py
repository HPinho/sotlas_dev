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


def execute_windows_text(path: Path, aggregate_size: int = 0) -> int | bytes:
    """Run a zero-argument, relocation-free SysV entry in a child process.

    The wrapper preserves Windows' additional nonvolatile registers and aligns
    the stack. Fixtures have no foreign calls or data-section references.
    """
    data = path.read_bytes()
    section_headers = struct.unpack_from("<Q", data, 40)[0]
    section_size, section_count = struct.unpack_from("<HH", data, 58)
    text = None
    text_index = None
    for index in range(section_count):
        header = section_headers + index * section_size
        flags = struct.unpack_from("<Q", data, header + 8)[0]
        if flags & 4:
            offset, length = struct.unpack_from("<QQ", data, header + 24)
            text = data[offset:offset + length]
            text_index = index
            break
    if not text:
        raise RuntimeError("object has no executable text")
    entry_offset = None
    for index in range(section_count):
        header = section_headers + index * section_size
        if struct.unpack_from("<I", data, header + 4)[0] != 2:
            continue
        symbols_offset, symbols_length = struct.unpack_from("<QQ", data, header + 24)
        strings_index = struct.unpack_from("<I", data, header + 40)[0]
        strings_header = section_headers + strings_index * section_size
        strings_offset = struct.unpack_from("<Q", data, strings_header + 24)[0]
        for symbol in range(symbols_offset, symbols_offset + symbols_length, 24):
            name = strings_offset + struct.unpack_from("<I", data, symbol)[0]
            if data[name:data.index(b"\0", name)] == b"main_entry":
                if struct.unpack_from("<H", data, symbol + 6)[0] != text_index:
                    raise RuntimeError("entry is not defined in executable text")
                entry_offset = struct.unpack_from("<Q", data, symbol + 8)[0]
    if entry_offset is None or entry_offset >= len(text):
        raise RuntimeError("object has no valid main_entry symbol")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    kernel.VirtualAlloc.restype = ctypes.c_void_p
    kernel.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    kernel.VirtualProtect.restype = ctypes.c_int
    kernel.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
    wrapper_length = 25 + (10 if aggregate_size else 0)
    size = len(text) + wrapper_length
    address = kernel.VirtualAlloc(None, size, 0x3000, 0x04)
    if not address:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        destination = ctypes.create_string_buffer(bytes([165]) * (aggregate_size + 16)) if aggregate_size else None
        wrapper = b"\x57\x56\x48\x83\xec\x28"
        if destination is not None:
            wrapper += b"\x48\xbf" + struct.pack("<Q", ctypes.addressof(destination) + 8)
        wrapper += b"\x48\xb8" + struct.pack("<Q", address + wrapper_length + entry_offset)
        wrapper += b"\xff\xd0\x48\x83\xc4\x28\x5e\x5f\xc3"
        ctypes.memmove(address, wrapper + text, size)
        old = ctypes.c_uint32()
        if not kernel.VirtualProtect(address, size, 0x20, ctypes.byref(old)):
            raise ctypes.WinError(ctypes.get_last_error())
        result = ctypes.WINFUNCTYPE(ctypes.c_uint32)(address)()
        if destination is not None:
            return destination.raw[:aggregate_size + 16]
        return result
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

    def test_aggregate_return_owns_caller_storage_across_calls(self):
        self.assert_native_result("aggregate_calls", """
pub struct Pair { pub left: u32; pub right: u64; }
fn make(value: u32) -> Pair { return Pair { left: value, right: 100 }; }
fn forward(value: u32) -> Pair { return make(value); }
pub fn main_entry() -> u32 {
    let mut first: Pair = forward(40);
    let second: Pair = make(2);
    first.left = first.left + second.left;
    return first.left;
}
""", 42)

    def test_aggregate_branch_returns_and_nested_fields(self):
        self.assert_native_result("aggregate_branches", """
pub struct Inner { pub value: u32; }
pub struct Outer { pub inner: Inner; pub tail: u64; }
fn choose(flag: bool) -> Outer {
    if flag { return Outer { inner: Inner { value: 40 }, tail: 7 }; }
    return Outer { inner: Inner { value: 2 }, tail: 9 };
}
pub fn main_entry() -> u32 {
    let first: Outer = choose(true);
    let second: Outer = choose(false);
    return first.inner.value + second.inner.value;
}
""", 42)

    def test_aggregate_value_parameter_does_not_alias_caller(self):
        self.assert_native_result("aggregate_value_parameter", """
pub struct Pair { pub left: u32; pub right: u32; }
fn alter(mut value: Pair) -> Pair { value.left = 2; return value; }
pub fn main_entry() -> u32 {
    let original: Pair = Pair { left: 40, right: 1 };
    let changed: Pair = alter(original);
    return original.left + changed.left;
}
""", 42)

    def test_aggregate_hidden_destination_uses_stack_argument(self):
        self.assert_native_result("aggregate_stack_destination", """
pub struct Pair { pub left: u32; pub right: u32; }
fn make(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32) -> Pair {
    return Pair { left: a + b + c + d + e + f, right: 0 };
}
pub fn main_entry() -> u32 {
    let value: Pair = make(1, 2, 3, 4, 5, 27);
    return value.left;
}
""", 42)

    def test_aggregate_local_binding_copies_value(self):
        self.assert_native_result("aggregate_binding_copy", """
pub struct Pair { pub left: u32; pub right: u32; }
fn make() -> Pair { return Pair { left: 40, right: 1 }; }
pub fn main_entry() -> u32 {
    let original: Pair = make();
    let mut copy: Pair = original;
    copy.left = 2;
    return original.left + copy.left;
}
""", 42)

    def test_aggregate_layout_rejects_unsupported_array_fields(self):
        for typ in ("[u32; 4]", "[u8; 257]"):
            with self.subTest(typ=typ):
                result, output = self.compile("aggregate_layout_bad", f"""
pub struct Unsupported {{ pub data: {typ}; }}
pub fn main_entry() -> u32 {{ return 42; }}
""")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_real_token_and_ast_modules_emit_native_objects(self):
        for module in ("token", "ast"):
            with self.subTest(module=module):
                source = ROOT / "bootstrap" / "sotlas" / "native_compiler" / f"{module}.sotlas"
                output = self.directory / f"real_{module}.o"
                result = subprocess.run([str(self.stage), "--compile-obj", str(source), str(output)],
                                        capture_output=True, text=True, timeout=30, cwd=ROOT)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_bytes()[:4], b"\x7fELF")

    def test_real_token_and_ast_constructors_execute_natively(self):
        self.assert_native_result("real_constructors", """
import sotlas::compiler::ast::*;
pub fn main_entry() -> u32 {
    let span: Span = Span { line: 40, col: 1, offset: 0, length: 3 };
    let node: AstNode = AstNode::new(AstKind::Block, span);
    let token: Token = Token::new(TokenKind::Ident, 7, 2);
    return node.span.line + token.span.col;
}
""", 42)

    def test_aggregate_byte_array_layout_and_copy(self):
        result, output = self.compile("aggregate_bytes", """
pub struct Bytes { pub head: u32; pub bytes: [u8; 128]; pub tail: u32; }
fn make() -> Bytes { return Bytes { head: 40, bytes: [0; 128], tail: 2 }; }
pub fn main_entry() -> Bytes { return make(); }
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = bytes([165]) * 8 + struct.pack("<I", 40) + bytes(128) + struct.pack("<I", 2) + bytes([165]) * 8
        if sys.platform == "win32":
            execution = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                        "--execute-aggregate", str(output), "136"], capture_output=True, text=True, timeout=15)
            self.assertEqual(execution.returncode, 0, execution.stderr)
            self.assertEqual(bytes.fromhex(execution.stdout.strip()), expected)
        elif sys.platform.startswith("linux"):
            caller = self.directory / "aggregate_caller.c"
            caller.write_text("""#include <stdint.h>
#include <string.h>
extern void main_entry(uint8_t *destination);
int main(void) {
    uint8_t result[152]; memset(result, 165, sizeof result);
    main_entry(result + 8);
    for (unsigned i = 0; i < 152; ++i) {
        uint8_t expected = (i < 8 || i >= 144) ? 165 : 0;
        if (i == 8) expected = 40;
        if (i == 140) expected = 2;
        if (result[i] != expected) return 1;
    }
    return 0;
}
""", encoding="utf-8")
            binary = self.directory / "aggregate_caller"
            linked = subprocess.run(["clang", str(caller), str(output), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(linked.returncode, 0, linked.stderr)
            self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, 0)

    def test_aggregate_return_rejects_foreign_abi(self):
        result, output = self.compile("aggregate_ffi", """
pub struct Pair { pub left: u32; pub right: u32; }
@extern(C)
fn foreign_pair() -> Pair;
pub fn main_entry() -> u32 { return 42; }
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_aggregate_repeat_count_must_match_field(self):
        result, output = self.compile("aggregate_repeat_bad", """
pub struct Bytes { pub bytes: [u8; 128]; }
fn make() -> Bytes { return Bytes { bytes: [0; 127] }; }
pub fn main_entry() -> u32 { return 42; }
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

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

    def test_sysv_stack_arguments_preserve_order_and_alignment(self):
        result, output = self.compile("sysv_stack_arguments", """
fn identity(value: u32) -> u32 { return value; }
fn weighted(a: u32, b: u32, c: u32, d: u32, e: u32,
            f: u32, g: u32, h: u32, i: u32) -> u32 {
    return a + b * 2 + c * 3 + d * 4 + e * 5
        + f * 6 + g * 7 + h * 8 + i * 9;
}
pub fn main_entry() -> u32 {
    return weighted(1, 2, 3, 4, 5, 6, identity(7), 8, 9);
}
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        blob = output.read_bytes()
        self.assertEqual(blob[:4], b"\x7fELF")
        # Three outgoing stack slots need 32 bytes to preserve 16-byte alignment.
        self.assertIn(b"\x48\x81\xec\x20\x00\x00\x00", blob)
        self.assertIn(b"\x48\x81\xc4\x20\x00\x00\x00", blob)
        if sys.platform.startswith("linux"):
            binary = self.directory / "sysv_stack_arguments"
            link = subprocess.run([str(self.stage), "--link-exe", str(output),
                                   str(binary), "main_entry"],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(link.returncode, 0, link.stderr)
            self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, 285 & 255)

    def test_native_call_rejects_more_than_sixteen_arguments(self):
        parameters = ", ".join(f"p{index}: u32" for index in range(17))
        arguments = ", ".join(str(index) for index in range(17))
        result, output = self.compile("too_many_arguments", f"""
fn overloaded({parameters}) -> u32 {{ return p16; }}
pub fn main_entry() -> u32 {{ return overloaded({arguments}); }}
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_narrow_bitwise_values_execute_with_full_width_storage(self):
        self.assert_native_result("narrow_bitwise", """
pub fn main_entry() -> u32 {
    let first: u8 = 170;
    let second: u8 = 204;
    let and_byte: u8 = first & second;
    let or_byte: u8 = first | second;
    let xor_byte: u8 = first ^ second;
    let wide_first: u16 = 4660;
    let wide_second: u16 = 255;
    let and_word: u16 = wide_first & wide_second;
    if and_byte == 136 && or_byte == 238 && xor_byte == 102
        && and_word == 52 { return 73; }
    return 1;
}
""", 73)

    def test_narrow_arithmetic_remains_outside_native_bitwise_contract(self):
        result, output = self.compile("narrow_arithmetic_reject", """
pub fn main_entry() -> u8 {
    let first: u8 = 2;
    let second: u8 = 3;
    return first + second;
}
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_global_array_cast_emits_bss_address(self):
        result, output = self.compile("global_array_cast", """
pub static mut g_bytes: [u8; 16] = 0;
pub fn buffer() -> *const u8 {
    return unsafe { g_bytes as *const u8 };
}
pub fn main_entry() -> u32 {
    let data: *const u8 = buffer();
    if data == null { return 1; }
    return 0;
}
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        blob = output.read_bytes()
        self.assertEqual(blob[:4], b"\x7fELF")
        self.assertIn(b"g_bytes\x00", blob)
        if sys.platform.startswith("linux"):
            binary = self.directory / "global_array_cast"
            link = subprocess.run([str(self.stage), "--link-exe", str(output),
                                   str(binary), "main_entry"],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(link.returncode, 0, link.stderr)
            self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, 0)

    def test_global_array_cast_rejects_mismatched_pointee(self):
        result, output = self.compile("global_array_cast_mismatch", """
pub static mut g_bytes: [u8; 16] = 0;
pub fn bad() -> *const u16 {
    return unsafe { g_bytes as *const u16 };
}
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_no_loop_short_circuit_skips_unsafe_read(self):
        result, output = self.compile("no_loop_short_circuit", """
pub fn guard(data: *const u8, skip: u32) -> bool {
    if skip == 0 || unsafe { *data } == 0 { return true; }
    return false;
}
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[:4], b"\x7fELF")
        if sys.platform.startswith("linux"):
            caller = self.directory / "no_loop_short_circuit_caller.c"
            caller.write_text(
                "#include <stdbool.h>\n#include <stdint.h>\n"
                "extern bool guard(const uint8_t *, uint32_t);\n"
                "int main(void) { uint8_t value = 1; "
                "return guard((const uint8_t *)0, 0) && !guard(&value, 1) ? 0 : 1; }\n",
                encoding="utf-8",
            )
            binary = self.directory / "no_loop_short_circuit"
            linked = subprocess.run(["clang", str(caller), str(output), "-o", str(binary)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(linked.returncode, 0, linked.stderr)
            self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, 0)

    def test_field_assignment_inside_branch_uses_structured_cfg(self):
        result, output = self.compile("branch_field_store", """
struct Counter { val: u32; }
impl Counter {
    pub fn add_if(mut self: &mut Self, delta: u32, enabled: bool) -> u32 {
        if enabled { self.val = self.val + delta; }
        return self.val;
    }
}
pub fn main_entry() -> u32 {
    let mut counter: Counter = Counter { val: 5 };
    return counter.add_if(9, true);
}
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[:4], b"\x7fELF")
        if sys.platform.startswith("linux"):
            binary = self.directory / "branch_field_store"
            linked = subprocess.run([str(self.stage), "--link-exe", str(output),
                                     str(binary), "main_entry"],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(linked.returncode, 0, linked.stderr)
            self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, 14)

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

    def test_short_circuit_preserves_narrow_raw_load_types(self):
        """A single while loop must short-circuit unsafe u8/u16 reads natively."""
        result, output = self.compile("narrow_guard_loads", """
pub fn byte_guard(data: *const u8, offset: usize, skip: u32) -> bool {
    let mut round: u32 = 0;
    while round < 1 {
        if skip == 0 || unsafe { *(data + offset) } == 0 {
            return true;
        }
        round = round + 1;
    }
    return false;
}
pub fn word_guard(data: *const u16, offset: usize, skip: u32) -> bool {
    let mut round: u32 = 0;
    while round < 1 {
        if skip != 0 && unsafe { *(data + offset) } == 13 {
            return true;
        }
        round = round + 1;
    }
    return false;
}
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[:4], b"\x7fELF")
        self.assertIn(b"byte_guard\x00", output.read_bytes())
        self.assertIn(b"word_guard\x00", output.read_bytes())
        if sys.platform.startswith("linux"):
            caller = self.directory / "narrow_guard_loads_caller.c"
            caller.write_text(
                "#include <stdbool.h>\n#include <stdint.h>\n#include <stddef.h>\n"
                "extern bool byte_guard(const uint8_t *, size_t, uint32_t);\n"
                "extern bool word_guard(const uint16_t *, size_t, uint32_t);\n"
                "int main(void) { uint8_t bytes[2] = {0, 9}; "
                "uint16_t words[2] = {3, 13}; "
                "return byte_guard((const uint8_t *)0, 0, 0) "
                "&& byte_guard(bytes, 0, 1) "
                "&& !byte_guard(bytes, 1, 1) "
                "&& !word_guard((const uint16_t *)0, 0, 0) "
                "&& word_guard(words, 1, 1) ? 0 : 1; }\n",
                encoding="utf-8",
            )
            binary = self.directory / "narrow_guard_loads"
            linked = subprocess.run(
                ["clang", str(caller), str(output), "-o", str(binary)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(linked.returncode, 0, linked.stderr)
            executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            self.assertEqual(executed.returncode, 0, executed.stderr)

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
    elif len(sys.argv) == 4 and sys.argv[1] == "--execute-aggregate":
        print(execute_windows_text(Path(sys.argv[2]), int(sys.argv[3])).hex())
    else:
        unittest.main()
