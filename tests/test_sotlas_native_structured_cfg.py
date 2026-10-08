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
        for typ in ("[f64; 4]", "[u8; 257]"):
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

    def test_lazy_boolean_values_skip_calls_and_unsafe_loads(self):
        self.assert_native_result("lazy_values", """
fn touch(counter: *mut u32) -> bool {
    unsafe { *counter = *counter + 1; }
    return true;
}
fn read_or(flag: bool, pointer: *const u8) -> bool {
    return flag || unsafe { *pointer } == 7;
}
fn accept(flag: bool) -> u32 { if flag { return 42; } return 1; }
pub fn main_entry() -> u32 {
    let mut count: u32 = 0;
    let pointer: *mut u32 = unsafe { (&count) as *mut u32 };
    let skipped: bool = false && touch(pointer);
    let mut selected: bool = true || touch(pointer);
    selected = !skipped && touch(pointer);
    let safe: bool = read_or(true, null);
    if count == 1 && safe { return accept(selected || touch(pointer)); }
    return 2;
}
""", 42)

    def test_single_loop_compares_two_byte_bindings_and_returns_early(self):
        self.assert_native_result("byte_search", """
fn equal(left: *const u8, right: *const u8, count: usize) -> bool {
    let mut index: usize = 0;
    while index < count {
        let lhs: u8 = unsafe { *(left + index) };
        let rhs: u8 = unsafe { *(right + index) };
        if lhs != rhs { return false; }
        index = index + 1;
    }
    return true;
}
pub fn main_entry() -> u32 {
    let mut left: u8 = 7;
    let mut right: u8 = 9;
    let a: *const u8 = unsafe { (&left) as *const u8 };
    let b: *const u8 = unsafe { (&right) as *const u8 };
    if equal(a, a, 1) && !equal(a, b, 1) && equal(null, null, 0) { return 42; }
    return 1;
}
""", 42)

    def test_nested_field_replacement_and_local_aggregate_assignment(self):
        self.assert_native_result("aggregate_assignment", """
pub struct Inner { pub value: u32; }
pub struct Outer { pub inner: Inner; pub tail: u64; }
pub fn main_entry() -> u32 {
    let original: Outer = Outer { inner: Inner { value: 40 }, tail: 7 };
    let mut changed: Outer = Outer { inner: Inner { value: 1 }, tail: 9 };
    let mut i: u32 = 0;
    while i < 1 {
        changed = original;
        changed.inner = Inner { value: 2 };
        changed.inner.value = changed.inner.value + 1;
        i = i + 1;
    }
    return original.inner.value + changed.inner.value - 1;
}
""", 42)

    def test_void_method_call_and_narrow_method_comparison(self):
        self.assert_native_result("void_method", """
pub struct Cell { pub value: u8; pub count: u32; }
impl Cell {
    pub fn update(mut self: &mut Self, value: u8) { self.value = value; self.count = self.count + 1; }
    pub fn read(self: &Self) -> u8 { return self.value; }
}
pub fn main_entry() -> u32 {
    let mut cell: Cell = Cell { value: 1, count: 0 };
    cell.update(42);
    if cell.read() == 42 && cell.count == 1 { return 42; }
    return 1;
}
""", 42)

    def test_negative_i64_literals_preserve_extreme_value(self):
        self.assert_native_result("negative_literals", """
fn minimum() -> i64 { return -9223372036854775808; }
fn invalid_digit() -> i64 { return -1; }
pub fn main_entry() -> u32 {
    if minimum() == -9223372036854775808 && invalid_digit() == -1 { return 42; }
    return 1;
}
""", 42)

    def test_negative_literal_rejects_unsigned_and_i64_overflow(self):
        for typ, literal in (("u64", "-1"), ("i64", "-9223372036854775809")):
            with self.subTest(typ=typ):
                result, output = self.compile("negative_bad", f"fn value() -> {typ} {{ return {literal}; }}")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_real_lexer_module_emits_native_object(self):
        source = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "lexer.sotlas"
        output = self.directory / "real_lexer.o"
        result = subprocess.run([str(self.stage), "--compile-obj", str(source), str(output)],
                                capture_output=True, text=True, timeout=30, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes()[:4], b"\x7fELF")

    def test_real_lexer_next_token_executes_natively(self):
        self.assert_native_result("real_lexer_token", """
import sotlas::compiler::lexer::*;
pub fn main_entry() -> u32 {
    let mut byte: u8 = 42;
    let pointer: *const u8 = unsafe { (&byte) as *const u8 };
    let mut lexer: Lexer = Lexer::new(pointer, 1);
    let token: Token = lexer.next_token();
    let eof: Token = lexer.next_token();
    if token.kind == TokenKind::Star && token.span.length == 1 && token.span.offset == 0
        && eof.kind == TokenKind::Eof && lexer.is_at_end() { return 42; }
    return 1;
}
""", 42)

    def test_real_sema_name_comparison_executes_natively(self):
        source = (ROOT / "bootstrap" / "sotlas" / "native_compiler" / "sema.sotlas").read_text(encoding="utf-8")
        # Keep the production declarations and method bodies through the first
        # comparison loop; the remaining module is a separate native milestone.
        prefix = source.split("    pub fn reject_node(", 1)[0] + "}\n"
        self.assert_native_result("real_sema_names", prefix + """
pub fn main_entry() -> u32 {
    let mut byte: u8 = 42;
    let pointer: *const u8 = unsafe { (&byte) as *const u8 };
    let sema: Sema = Sema::new();
    let span: Span = Span { line: 0, col: 0, offset: 0, length: 1 };
    let mut left: AstNode = AstNode::new(AstKind::Block, span);
    left.str_len = 1;
    let mut right: AstNode = left;
    right.str_len = 0;
    if sema.same_declaration_name(pointer, 1, left, left)
        && !sema.same_declaration_name(pointer, 1, left, right) { return 42; }
    return 1;
}
""", 42)

    def test_local_address_cast_rejects_mismatched_pointee(self):
        result, output = self.compile("address_pointee_bad", """
pub fn main_entry() -> u32 {
    let mut byte: u8 = 42;
    let pointer: *const u32 = unsafe { (&byte) as *const u32 };
    while false { return 1; }
    return 42;
}
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_signed_i64_ordering_uses_overflow_aware_conditions(self):
        self.assert_native_result("signed_ordering", """
fn ordered(low: i64, high: i64) -> bool {
    return low < high && low <= high && high > low && high >= low
        && low <= low && high >= high && !(low > high) && !(high < low);
}
pub fn main_entry() -> u32 {
    if ordered(-9223372036854775808, 9223372036854775807)
        && ordered(-1, 0) && ordered(-2, -1) && ordered(0, 1) { return 42; }
    return 1;
}
""", 42)

    def test_unsigned_ordering_keeps_unsigned_conditions(self):
        self.assert_native_result("unsigned_ordering", """
fn ordered(low: u64, high: u64) -> bool {
    return low < high && low <= high && high > low && high >= low;
}
pub fn main_entry() -> u32 {
    if ordered(0, 18446744073709551615) && ordered(9223372036854775807, 9223372036854775808) { return 42; }
    return 1;
}
""", 42)

    def test_ordered_comparison_rejects_mixed_sign_and_pointers(self):
        for name, args in (("mixed", "left: i64, right: u64"),
                           ("pointer", "left: *const u8, right: *const u8")):
            with self.subTest(name=name):
                result, output = self.compile(name, f"fn less({args}) -> bool {{ return left < right; }}")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_aggregate_pointer_load_store_and_field_binding_copy(self):
        self.assert_native_result("aggregate_pointer_copy", """
pub struct Inner { pub value: i64; }
pub struct Record { pub tag: u32; pub inner: Inner; }
fn read(pointer: *const Record) -> Record { unsafe { return *pointer; } }
fn write(pointer: *mut Record, value: Record) { unsafe { *pointer = value; } }
pub fn main_entry() -> u32 {
    let mut original: Record = Record { tag: 1, inner: Inner { value: 3 } };
    let pointer: *mut Record = unsafe { (&original) as *mut Record };
    let replacement: Record = Record { tag: 42, inner: Inner { value: -1 } };
    write(pointer, replacement);
    let saved: Record = read(pointer);
    let inner: Inner = saved.inner;
    original.inner.value = 7;
    if saved.tag == 42 && inner.value < 0 && read(pointer).inner.value > 0 { return 42; }
    return 1;
}
""", 42)

    def test_discarded_aggregate_call_preserves_side_effect(self):
        self.assert_native_result("discarded_aggregate", """
pub struct Item { pub value: u32; }
fn advance(pointer: *mut Item) -> Item {
    let mut value: Item = unsafe { *pointer };
    value.value = value.value + 1;
    unsafe { *pointer = value; }
    return value;
}
pub fn main_entry() -> u32 {
    let mut value: Item = Item { value: 41 };
    let pointer: *mut Item = unsafe { (&value) as *mut Item };
    advance(pointer);
    return value.value;
}
""", 42)

    def test_aggregate_global_array_cast_requires_exact_struct(self):
        result, output = self.compile("wrong_struct_array", """
pub struct First { pub value: u32; }
pub struct Second { pub value: u32; }
static mut data: [First; 4] = 0;
pub fn main_entry() -> u32 {
    let pointer: *mut Second = unsafe { data as *mut Second };
    return 0;
}
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_real_sema_and_parser_modules_emit_native_objects(self):
        for module, symbol in (("sema", b"Sema_check_top_level_declarations\0"),
                               ("parser", b"Parser_parse_module\0")):
            with self.subTest(module=module):
                source = ROOT / "bootstrap" / "sotlas" / "native_compiler" / f"{module}.sotlas"
                output = self.directory / f"real_{module}.o"
                result = subprocess.run([str(self.stage), "--compile-obj", str(source), str(output)],
                                        capture_output=True, text=True, timeout=30, cwd=ROOT)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = output.read_bytes()
                self.assertEqual(data[:4], b"\x7fELF")
                self.assertIn(symbol, data)

    def test_aggregate_global_array_rejects_overflow_and_nonzero_initializer(self):
        for count, initializer in (("18446744073709551615", "0"),
                                   ("18446744073709551619", "0"), ("4", "1")):
            with self.subTest(count=count, initializer=initializer):
                result, output = self.compile("aggregate_array_invalid", f"""
pub struct Record {{ pub value: u64; }}
static mut data: [Record; {count}] = {initializer};
pub fn main_entry() -> u32 {{ return 0; }}
""")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_real_frontend_pipeline_compiles_and_links(self):
        example = ROOT / "bootstrap" / "sotlas" / "native_examples" / "frontend_native.sotlas"
        output = self.directory / "frontend_native.o"
        result = subprocess.run([str(self.stage), "--compile-obj", str(example), str(output)],
                                capture_output=True, text=True, timeout=30, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        binary = output.with_suffix(".elf")
        linked = subprocess.run([str(self.stage), "--link-exe", str(output), str(binary), "main_entry"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(linked.returncode, 0, linked.stderr)
        self.assertEqual(binary.read_bytes()[:4], b"\x7fELF")
        if sys.platform.startswith("linux"):
            self.assertEqual(subprocess.run([str(binary)], timeout=30).returncode, 0)

    def test_native_frontend_pipeline_rejects_invalid_return(self):
        example = ROOT / "bootstrap" / "sotlas" / "native_examples" / "frontend_native.sotlas"
        source = example.read_text(encoding="utf-8")
        valid = "module demo; fn answer() -> u32 { return 42; }"
        invalid = "module demo; fn answer() -> u32 { return 4294967296; }"
        source = source.replace(valid, invalid).replace("source_length: usize = 46", f"source_length: usize = {len(invalid)}")
        result, output = self.compile("frontend_invalid", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        binary = output.with_suffix(".elf")
        linked = subprocess.run([str(self.stage), "--link-exe", str(output), str(binary), "main_entry"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(linked.returncode, 0, linked.stderr)
        if sys.platform.startswith("linux"):
            self.assertEqual(subprocess.run([str(binary)], timeout=30).returncode, 4)

    def test_inline_integer_arrays_preserve_width_stride_and_value_copy(self):
        self.assert_native_result("integer_array_fields", """
pub struct Table { pub bytes: [u8; 4]; pub short: [u16; 4]; pub words: [u32; 4]; pub wide: [u64; 4]; pub tail: u32; }
fn make() -> Table { return Table { bytes: [0; 4], short: [0; 4], words: [0; 4], wide: [0; 4], tail: 7 }; }
pub fn main_entry() -> u32 {
    let mut table: Table = make();
    table.bytes[0] = 255;
    table.short[1] = 65535;
    table.words[2] = 4000000000;
    table.wide[3] = 9007199254740993;
    let saved: Table = table;
    table.words[2] = 0;
    if saved.bytes[0] == 255 && saved.short[1] == 65535 && saved.words[2] == 4000000000
        && saved.wide[3] == 9007199254740993 && saved.tail == 7 { return 42; }
    return 1;
}
""", 42)

    def test_inline_integer_array_nested_method_updates(self):
        self.assert_native_result("nested_array_method", """
pub struct Table { pub values: [usize; 4]; }
pub struct Wrapper { pub table: Table; pub sentinel: u64; }
impl Wrapper {
    pub fn update(mut self: &mut Self, index: usize, value: usize) { self.table.values[index] = value; }
}
pub fn main_entry() -> u32 {
    let mut value: Wrapper = Wrapper { table: Table { values: [0; 4] }, sentinel: 99 };
    value.update(3, 42);
    if value.table.values[3] == 42 && value.sentinel == 99 { return 42; }
    return 1;
}
""", 42)

    def test_unsafe_boolean_wrapper_keeps_short_circuit(self):
        self.assert_native_result("unsafe_condition_wrapper", """
fn safe(flag: bool, pointer: *const u8) -> bool { return unsafe { flag || *pointer == 7 }; }
fn same(left: *const u8, right: *const u8) -> bool {
    if unsafe { *left != *right } { return false; }
    return true;
}
pub fn main_entry() -> u32 {
    let mut byte: u8 = 7;
    let pointer: *const u8 = unsafe { (&byte) as *const u8 };
    if safe(true, null) && safe(false, pointer) && same(pointer, pointer) { return 42; }
    return 1;
}
""", 42)

    def test_inline_array_out_of_bounds_traps_before_read_or_write(self):
        for index in (4, 4294967296):
            for operation in ("table.values[index] = 42;", "let read: u32 = table.values[index];"):
                with self.subTest(index=index, operation=operation):
                    result, output = self.compile("field_array_bounds", f"""
pub struct Table {{ pub values: [u32; 4]; }}
pub fn main_entry() -> u32 {{
    let mut table: Table = Table {{ values: [0; 4] }};
    let index: usize = {index};
    {operation}
    return 1;
}}
""")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if sys.platform == "win32":
                        executed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--execute", str(output)],
                                                  capture_output=True, text=True, timeout=15)
                        self.assertEqual(executed.returncode, 0xC000001D, executed.stderr)
                    elif sys.platform.startswith("linux"):
                        binary = output.with_suffix(".elf")
                        linked = subprocess.run([str(self.stage), "--link-exe", str(output), str(binary), "main_entry"],
                                                capture_output=True, text=True)
                        self.assertEqual(linked.returncode, 0, linked.stderr)
                        self.assertEqual(subprocess.run([str(binary)], timeout=15).returncode, -4)

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

    def test_same_pointee_pointer_cast_preserves_scalar_storage(self):
        self.assert_native_result("pointer_qualifiers", """
fn write(source: *const u32) -> u32 {
    let writable: *mut u32 = source as *mut u32;
    unsafe { *writable = 42; }
    let readonly: *const u32 = writable as *const u32;
    return unsafe { *readonly };
}
pub fn main_entry() -> u32 {
    let mut value: u32 = 7;
    let address: *const u32 = unsafe { (&value) as *const u32 };
    let result: u32 = write(address);
    if result == 42 && value == 42 { return 0; }
    return 1;
}
""", 0)

    def test_same_pointee_pointer_cast_preserves_struct_identity(self):
        self.assert_native_result("struct_pointer_qualifiers", """
struct Pair { first: u32; second: u32; }
fn update(source: *const Pair) -> u32 {
    let writable: *mut Pair = source as *mut Pair;
    unsafe { *writable = Pair { first: 40, second: 2 }; }
    let readonly: *const Pair = writable as *const Pair;
    let result: Pair = unsafe { *readonly };
    return result.first + result.second;
}
pub fn main_entry() -> u32 {
    let mut pair: Pair = Pair { first: 1, second: 2 };
    let address: *const Pair = unsafe { (&pair) as *const Pair };
    return update(address);
}
""", 42)

    def test_scalar_reference_load_store_and_guard(self):
        self.assert_native_result("scalar_reference", """
fn increment(counter: &mut usize, capacity: usize) -> bool {
    if *counter >= capacity { return false; }
    *counter = *counter + 1;
    return true;
}
pub fn main_entry() -> u32 {
    let mut counter: usize = 40;
    let pointer: &mut usize = &counter;
    if !increment(pointer, 42) || !increment(pointer, 42) { return 1; }
    if increment(pointer, 42) || counter != 42 { return 2; }
    return 0;
}
""", 0)

    def test_pointer_casts_reject_reinterpretation(self):
        for name, body in (
            ("scalar", "fn invalid(p: *const u32) -> *mut u8 { return p as *mut u8; }"),
            ("struct", "struct A { value: u32; } struct B { value: u32; } "
             "fn invalid(p: *const A) -> *mut B { return p as *mut B; }"),
            ("integer", "fn invalid(p: u64) -> *mut u8 { return p as *mut u8; }"),
            ("nested", "fn invalid(p: *const *const u32) -> *mut *const u8 { return p as *mut *const u8; }"),
        ):
            with self.subTest(name=name):
                result, output = self.compile("invalid_pointer_" + name, body)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_real_object_writer_helpers_compile_and_execute(self):
        writer = (ROOT / "bootstrap/sotlas/native_compiler/backend/x86_64_scalar.sotlas").read_text(encoding="utf-8")
        prefix = writer.split("fn append_object_sysv_parameter_store(", 1)[0]
        self.assertIn("fn append_object_load_mem64", prefix)
        # These byte/storage helpers do not use Target IR types. Keep this
        # execution fixture independent of the validator's large stack frames.
        prefix = prefix.replace("import sotlas::compiler::backend::target_ir::*;", "")
        self.assert_native_result("real_writer_helpers", prefix + """
pub fn main_entry() -> u32 {
    let mut byte: u8 = 0;
    let buffer: *mut u8 = unsafe { (&byte) as *mut u8 };
    let mut cursor: usize = 0;
    let length: &mut usize = &cursor;
    if !append_object_byte(buffer, 1, length, 42) { return 1; }
    if byte != 42 || cursor != 1 { return 2; }
    if append_object_byte(buffer, 1, length, 7) { return 3; }
    if byte != 42 || cursor != 1 { return 4; }
    if put_u16(buffer, 0, 0, 65535) || get_u16(buffer as *const u8, 1, 0) != 0 { return 5; }
    if byte != 42 || align_to(17, 8) != 24 { return 6; }
    return 0;
}
""", 0)

    def test_narrow_constant_shifts_normalize_both_widths(self):
        self.assert_native_result("narrow_shifts", """
fn byte_left(value: u8) -> u8 { return value << 7; }
fn byte_right(value: u8) -> u8 { return value >> 7; }
fn word_left(value: u16) -> u16 { return value << 15; }
fn word_right(value: u16) -> u16 { return value >> 15; }
fn identity(value: u8) -> u8 { return value >> 0; }
pub fn main_entry() -> u32 {
    if byte_left(255) != 128 || byte_right(255) != 1 { return 1; }
    if word_left(65535) != 32768 || word_right(65535) != 1 { return 2; }
    if byte_left(2) != 0 || word_left(2) != 0 || identity(255) != 255 { return 3; }
    return 0;
}
""", 0)

    def test_narrow_shifts_reject_dynamic_and_out_of_range_counts(self):
        for width, count in (("u8", "8"), ("u16", "16"), ("u8", "count"), ("u16", "count")):
            with self.subTest(width=width, count=count):
                result, output = self.compile("invalid_shift_" + width + "_" + count,
                    f"fn invalid(value: {width}, count: {width}) -> {width} {{ return value >> {count}; }}")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

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
