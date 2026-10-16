"""SV8.61: borrowed text values used by native Sotlas programs."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv860 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeTextSV861Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV860Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV860Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV860Tests.compile
    execute=previous.NativeMigrationSV860Tests.execute
    link_image=previous.NativeMigrationSV860Tests.link_image

    def text(self,name,body):
        source=(ROOT/'runtime/native/text.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,source+'pub fn main_entry()->u32{'+body+'}'))

    def test_text_slices_preserve_embedded_zero_bytes(self):
        self.text('text_open','let s:NativeByteSlice=native_text_open("a\\0b",3);if !s.valid || s.length!=3{return 1;}let empty:NativeByteSlice=native_text_open(null,0);if !empty.valid{return 2;}return 42;')

    def test_text_substrings_are_length_delimited_borrowed_values(self):
        self.text('text_sub','let s:NativeByteSlice=native_text_open("before:42:after",15);let part:NativeByteSlice=native_text_sub(s,7,2);if !native_text_equal(part,native_text_open("42",2)) || native_text_sub(s,15,1).valid{return 1;}return 42;')

    def test_text_byte_access_preserves_output_when_out_of_bounds(self):
        self.text('text_at','let s:NativeByteSlice=native_text_open("*",1);let mut value:u8=0;let out:*mut u8=unsafe{(&mut value) as *mut u8};if !native_text_at(s,0,out) || value!=42 || native_text_at(s,1,out) || value!=42{return 1;}return 42;')

    def test_text_lexical_comparison_uses_unsigned_bytes_and_lengths(self):
        self.text('text_compare','let mut value:i32=0;let out:*mut i32=unsafe{(&mut value) as *mut i32};if !native_text_compare(native_text_open("a",1),native_text_open("ab",2),out) || value!=-1{return 1;}return 42;')

    def test_text_equality_compares_complete_values_past_zero_bytes(self):
        self.text('text_equal','if !native_text_equal(native_text_open("a\\0b",3),native_text_open("a\\0b",3)) || native_text_equal(native_text_open("a\\0b",3),native_text_open("a\\0c",3)){return 1;}return 42;')

    def test_text_prefix_checks_accept_an_empty_prefix(self):
        self.text('text_prefix','let s:NativeByteSlice=native_text_open("sotlas",6);if !native_text_starts_with(s,native_text_open("sot",3)) || !native_text_starts_with(s,native_text_open(null,0)) || native_text_starts_with(s,native_text_open("atlas",5)){return 1;}return 42;')

    def test_text_suffix_checks_use_the_slice_end(self):
        self.text('text_suffix','let s:NativeByteSlice=native_text_open("main.sotlas",11);if !native_text_ends_with(s,native_text_open(".sotlas",7)) || native_text_ends_with(s,native_text_open("main",4)){return 1;}return 42;')

    def test_text_search_finds_substrings_and_preserves_missing_output(self):
        self.text('text_find','let s:NativeByteSlice=native_text_open("abc42def",8);let mut offset:usize=99;let out:*mut usize=unsafe{(&mut offset) as *mut usize};if !native_text_find(s,native_text_open("42",2),out) || offset!=3 || native_text_find(s,native_text_open("99",2),out) || offset!=3{return 1;}return 42;')

    def test_text_split_once_returns_borrowed_key_and_value(self):
        self.text('text_split_once','let split:NativeTextSplit=native_text_split_once(native_text_open("answer=42",9),native_text_open("=",1));if !split.found || !native_text_equal(split.before,native_text_open("answer",6)) || !native_text_equal(split.after,native_text_open("42",2)){return 1;}return 42;')
        self.text('text_records_program','''let mut cursor:NativeTextCursor=native_text_cursor(native_text_open("answer=40\\nbonus=2\\n",18));
let p:*mut NativeTextCursor=unsafe{(&mut cursor) as *mut NativeTextCursor};let mut total:u64=0;
loop{let line:NativeByteSlice=native_text_line_next(p);if !line.valid{break;}
let fields:NativeTextSplit=native_text_split_once(line,native_text_open("=",1));
let mut number:u64=0;let out:*mut u64=unsafe{(&mut number) as *mut u64};
if !fields.found || !native_text_parse_u64(fields.after,out){return 1;}total+=number;}
return total as u32;''')

    def test_text_ascii_trimming_retains_interior_whitespace(self):
        self.text('text_trim','let value:NativeByteSlice=native_text_trim_ascii(native_text_open(" \\t4 2\\r\\n",7));if !native_text_equal(value,native_text_open("4 2",3)){return 1;}return 42;')

    def test_text_decimal_parsing_handles_u64_limits_without_partial_output(self):
        self.text('text_parse','let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};if !native_text_parse_u64(native_text_open("18446744073709551615",20),out) || value!=18446744073709551615{return 1;}if native_text_parse_u64(native_text_open("18446744073709551616",20),out) || value!=18446744073709551615{return 2;}return 42;')

    def test_text_copy_materializes_a_slice_with_overlap_safe_movement(self):
        self.text('text_copy','let mut bytes:[u8;6]=[1,2,3,4,5,6];let p:*mut u8=unsafe{bytes as *mut u8};let s:NativeByteSlice=native_text_open(p,4);if !native_text_copy(s,unsafe{p+1},5) || bytes[1]!=1 || bytes[4]!=4 || bytes[5]!=6{return 1;}return 42;')

    def test_text_split_cursor_preserves_empty_and_trailing_fields(self):
        self.text('text_split_next','let mut cursor:NativeTextCursor=native_text_cursor(native_text_open("a,,b,",5));let p:*mut NativeTextCursor=unsafe{(&mut cursor) as *mut NativeTextCursor};let a:NativeByteSlice=native_text_split_next(p,44);let empty:NativeByteSlice=native_text_split_next(p,44);let b:NativeByteSlice=native_text_split_next(p,44);let tail:NativeByteSlice=native_text_split_next(p,44);let end:NativeByteSlice=native_text_split_next(p,44);if !native_text_equal(a,native_text_open("a",1)) || !empty.valid || empty.length!=0 || !native_text_equal(b,native_text_open("b",1)) || !tail.valid || tail.length!=0 || end.valid{return 1;}return 42;')

    def test_text_line_cursor_reads_crlf_lf_and_final_unterminated_lines(self):
        self.text('text_lines','let mut cursor:NativeTextCursor=native_text_cursor(native_text_open("a\\r\\nb\\nc",6));let p:*mut NativeTextCursor=unsafe{(&mut cursor) as *mut NativeTextCursor};let a:NativeByteSlice=native_text_line_next(p);let b:NativeByteSlice=native_text_line_next(p);let c:NativeByteSlice=native_text_line_next(p);let end:NativeByteSlice=native_text_line_next(p);if !native_text_equal(a,native_text_open("a",1)) || !native_text_equal(b,native_text_open("b",1)) || !native_text_equal(c,native_text_open("c",1)) || end.valid{return 1;}return 42;')

if __name__=='__main__':unittest.main()
