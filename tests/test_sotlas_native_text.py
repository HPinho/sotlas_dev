"""Execute bounded UTF-8 value text through the Sotlas-written native compiler."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT=Path(__file__).resolve().parents[1]


class NativeUtf8TextTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body,helpers=''):
        numeric=(ROOT/'runtime/native/results.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        legacy=(ROOT/'runtime/native/text.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        text=(ROOT/'runtime/native/utf8.sotlas').read_text(encoding='utf-8').split('import sotlas::runtime::text::*;',1)[1]
        self.execute(self.compile(name,numeric+'\n'+legacy+'\n'+text+'\n'+helpers+'\npub fn main_entry()->u32{'+body+'}'))

    def test_existing_byte_slice_api_and_owned_utf8_values_coexist(self):
        self.program('text_borrowed_bridge','''let mut bytes:[u8;2]=[52,50];
let slice:NativeByteSlice=native_text_open(unsafe{bytes as *const u8},2);
let copied:NativeUtf8TextResult=native_utf8_from_slice(slice);bytes[0]=57;
if copied.status!=0 || native_utf8_parse_u32(copied.value).value!=42
|| !native_text_equal(slice,native_text_open("92",2))
|| native_utf8_from_slice(native_text_invalid()).status!=7
|| native_utf8_from_slice(native_text_open(null,0)).status!=0{return 1;}return 42;''')

    def test_empty_and_ascii_values(self):
        self.program('text_ascii','''let empty:NativeUtf8TextResult=native_utf8_from_bytes(null,0);
let text:NativeUtf8TextResult=native_utf8_from_bytes("Sotlas",6);
if empty.status!=0 || empty.value.length!=0 || text.status!=0 || text.value.length!=6
|| native_utf8_validate(text.value).value!=6 || text.value.bytes[0]!=83{return 1;}return 42;''')

    def test_multibyte_scalar_encoding_and_count(self):
        self.program('text_scalars','''let text:NativeUtf8TextResult=build();
if text.status!=0 || text.value.length!=10 || native_utf8_validate(text.value).value!=4
|| text.value.bytes[0]!=65 || text.value.bytes[1]!=194 || text.value.bytes[3]!=226
|| text.value.bytes[6]!=240 || text.value.bytes[9]!=128{return 1;}return 42;''',
'''fn build()->NativeUtf8TextResult{let a:NativeUtf8Text=native_utf8_push_scalar(native_utf8_empty(),65)?;
let b:NativeUtf8Text=native_utf8_push_scalar(a,162)?;let c:NativeUtf8Text=native_utf8_push_scalar(b,8364)?;
return native_utf8_push_scalar(c,128512);}''')

    def test_utf8_boundary_scalars(self):
        self.program('text_boundaries','''let values:[u32;9]=[0,127,128,2047,2048,55295,57344,65535,1114111];
let mut i:u32=0;while i<9{let r:NativeUtf8TextResult=native_utf8_push_scalar(native_utf8_empty(),values[i]);
if r.status!=0 || native_utf8_validate(r.value).value!=1{return 1;}i=i+1;}return 42;''')

    def test_invalid_scalars_and_capacity(self):
        self.program('text_scalar_fail','''if native_utf8_push_scalar(native_utf8_empty(),55296).status!=8
|| native_utf8_push_scalar(native_utf8_empty(),57343).status!=8
|| native_utf8_push_scalar(native_utf8_empty(),1114112).status!=8{return 1;}
let full:NativeUtf8Text=NativeUtf8Text{bytes:[65;256],length:256};let r:NativeUtf8TextResult=native_utf8_push_scalar(full,66);
if r.status!=7 || full.bytes[255]!=65{return 2;}return 42;''')

    def test_invalid_utf8_reports_leading_byte(self):
        for i,values in enumerate(((128,), (192,128), (193,191), (224,159,191), (237,160,128),
                                   (240,143,191,191), (244,144,128,128), (245,128,128,128),
                                   (194,), (226,130), (240,159,152), (226,65,172), (226,130,65))):
            with self.subTest(bytes=values):
                arr=','.join(map(str,(65,)+values))
                self.program('text_invalid_'+str(i),'let bytes:[u8;'+str(len(values)+1)+']=['+arr+'];'
                             'let r:NativeUtf8TextResult=native_utf8_from_bytes(unsafe{bytes as *const u8},'+str(len(values)+1)+');'
                             'if r.status!=8 || r.error.offset!=1{return 1;}return 42;')

    def test_input_range_validation(self):
        self.program('text_ranges','''if native_utf8_from_bytes(null,1).status!=1
|| native_utf8_from_bytes(null,257).status!=7{return 1;}
let address:u64=18446744073709551615;let p:*const u8=unsafe{address as *const u8};
if native_utf8_from_bytes(p,1).status!=7{return 2;}return 42;''')

    def test_exact_capacity_and_independent_value_copy(self):
        self.program('text_value_copy','''let bytes:[u8;256]=[65;256];
let result:NativeUtf8TextResult=native_utf8_from_bytes(unsafe{bytes as *const u8},256);
let mut changed:NativeUtf8Text=result.value;changed.bytes[0]=66;
if result.status!=0 || result.value.length!=256 || result.value.bytes[0]!=65
|| changed.bytes[0]!=66 || changed.bytes[255]!=65{return 1;}return 42;''')

    def test_concat_and_capacity_errors_preserve_inputs(self):
        self.program('text_concat','''let a:NativeUtf8Text=native_utf8_from_bytes("Sot",3).value;
let b:NativeUtf8Text=native_utf8_from_bytes("las",3).value;let r:NativeUtf8TextResult=native_utf8_concat(a,b);
let full:NativeUtf8Text=NativeUtf8Text{bytes:[65;256],length:256};
if r.status!=0 || !native_utf8_equal(r.value,native_utf8_from_bytes("Sotlas",6).value)
|| native_utf8_concat(full,a).status!=7 || full.bytes[255]!=65 || a.length!=3{return 1;}return 42;''')

    def test_slice_enforces_scalar_boundaries(self):
        self.program('text_slice','''let a:NativeUtf8Text=native_utf8_push_scalar(native_utf8_empty(),8364).value;
let r:NativeUtf8Text=native_utf8_concat(a,native_utf8_from_bytes("42",2).value).value;
let good:NativeUtf8TextResult=native_utf8_slice(r,3,5);
if !native_utf8_equal(good.value,native_utf8_from_bytes("42",2).value)
|| native_utf8_slice(r,1,3).status!=8 || native_utf8_slice(r,0,2).status!=8
|| native_utf8_slice(r,4,3).status!=7 || native_utf8_slice(r,0,6).status!=7
|| native_utf8_slice(r,5,5).value.length!=0{return 1;}return 42;''')

    def test_trim_removes_ascii_space_only(self):
        self.program('text_trim','''let a:NativeUtf8Text=native_utf8_from_bytes("  42  ",6).value;
let b:NativeUtf8Text=native_utf8_trim(a).value;
let nbsp:NativeUtf8Text=native_utf8_push_scalar(native_utf8_empty(),160).value;
if native_utf8_parse_u32(b).value!=42 || native_utf8_trim(native_utf8_empty()).status!=0
|| native_utf8_trim(native_utf8_from_bytes("   ",3).value).value.length!=0
|| native_utf8_trim(nbsp).value.length!=2{return 1;}return 42;''')

    def test_ascii_case_preserves_non_ascii(self):
        self.program('text_case','''let text:NativeUtf8Text=native_utf8_concat(native_utf8_from_bytes("AbZ!",4).value,
native_utf8_push_scalar(native_utf8_empty(),8364).value).value;
let low:NativeUtf8Text=native_utf8_ascii_case(text,1).value;let up:NativeUtf8Text=native_utf8_ascii_case(text,2).value;
if low.bytes[0]!=97 || low.bytes[2]!=122 || up.bytes[1]!=66 || low.bytes[4]!=226
|| !native_utf8_equal(native_utf8_ascii_case(text,0).value,text)
|| native_utf8_ascii_case(text,3).status!=7 || text.bytes[0]!=65{return 1;}return 42;''')

    def test_find_empty_absent_unicode_and_last_position(self):
        self.program('text_find','''let text:NativeUtf8Text=native_utf8_from_bytes("ababa",5).value;
if native_utf8_find(text,native_utf8_from_bytes("ba",2).value).value!=1
|| native_utf8_find(text,native_utf8_empty()).value!=0
|| native_utf8_find(text,native_utf8_from_bytes("x",1).value).status!=9
|| native_utf8_find(text,native_utf8_from_bytes("ababab",6).value).status!=9{return 1;}
let euro:NativeUtf8Text=native_utf8_push_scalar(native_utf8_empty(),8364).value;
if native_utf8_find(native_utf8_concat(text,euro).value,euro).value!=5{return 2;}return 42;''')

    def test_before_after_and_empty_separator(self):
        self.program('text_split','''let text:NativeUtf8Text=native_utf8_from_bytes("key=42=1",8).value;
let separator:NativeUtf8Text=native_utf8_from_bytes("=",1).value;
if !native_utf8_equal(native_utf8_before(text,separator).value,native_utf8_from_bytes("key",3).value)
|| !native_utf8_equal(native_utf8_after(text,separator).value,native_utf8_from_bytes("42=1",4).value)
|| native_utf8_before(text,native_utf8_empty()).value.length!=0
|| !native_utf8_equal(native_utf8_after(text,native_utf8_empty()).value,text)
|| native_utf8_after(text,native_utf8_from_bytes("?",1).value).status!=9{return 1;}return 42;''')

    def test_repeat_guards_overflow_and_exact_capacity(self):
        self.program('text_repeat','''let a:NativeUtf8Text=native_utf8_from_bytes("ab",2).value;
let r:NativeUtf8TextResult=native_utf8_repeat(a,128);
if r.status!=0 || r.value.length!=256 || r.value.bytes[255]!=98
|| native_utf8_repeat(a,129).status!=7 || native_utf8_repeat(a,4294967295).status!=7
|| native_utf8_repeat(a,0).value.length!=0
|| native_utf8_repeat(native_utf8_empty(),4294967295).status!=0{return 1;}return 42;''')

    def test_compare_prefix_and_utf8_order(self):
        self.program('text_order','''let a:NativeUtf8Text=native_utf8_from_bytes("a",1).value;
let ab:NativeUtf8Text=native_utf8_from_bytes("ab",2).value;
let unicode:NativeUtf8Text=native_utf8_push_scalar(native_utf8_empty(),8364).value;
if native_utf8_compare(a,a).value!=0 || native_utf8_compare(a,ab).value!=1
|| native_utf8_compare(ab,a).value!=2 || native_utf8_compare(a,unicode).value!=1
|| native_utf8_compare(unicode,a).value!=2
|| native_utf8_compare(native_utf8_empty(),a).value!=1{return 1;}return 42;''')

    def test_replace_growth_shrink_deletion_and_nonoverlap(self):
        self.program('text_replace','''let text:NativeUtf8Text=native_utf8_from_bytes("aaaaa",5).value;
let needle:NativeUtf8Text=native_utf8_from_bytes("aa",2).value;
let grown:NativeUtf8TextResult=native_utf8_replace(text,needle,native_utf8_from_bytes("XYZ",3).value);
let erased:NativeUtf8TextResult=native_utf8_replace(text,needle,native_utf8_empty());
if !native_utf8_equal(grown.value,native_utf8_from_bytes("XYZXYZa",7).value)
|| !native_utf8_equal(erased.value,native_utf8_from_bytes("a",1).value)
|| !native_utf8_equal(native_utf8_replace(text,native_utf8_from_bytes("z",1).value,needle).value,text)
|| native_utf8_replace(text,native_utf8_empty(),needle).status!=7{return 1;}return 42;''')

    def test_replace_capacity_is_transactional(self):
        self.program('text_replace_full','''let full:NativeUtf8Text=NativeUtf8Text{bytes:[65;256],length:256};
let a:NativeUtf8Text=native_utf8_from_bytes("A",1).value;let aa:NativeUtf8Text=native_utf8_from_bytes("AA",2).value;
let r:NativeUtf8TextResult=native_utf8_replace(full,a,aa);
if r.status!=7 || r.value.length!=0 || full.length!=256 || full.bytes[255]!=65{return 1;}return 42;''')

    def test_decimal_conversion_roundtrips(self):
        self.program('text_numbers','''let numbers:[u32;4]=[0,42,1000000,4294967295];let mut i:u32=0;
while i<4{let text:NativeUtf8TextResult=native_utf8_from_u32(numbers[i]);let n:NativeU32Result=native_utf8_parse_u32(text.value);
if text.status!=0 || n.status!=0 || n.value!=numbers[i]{return 1;}i=i+1;}
if native_utf8_parse_u32(native_utf8_empty()).status!=2
|| native_utf8_parse_u32(native_utf8_from_bytes("4x",2).value).error.offset!=1{return 2;}return 42;''')

    def test_write_checks_before_publishing_and_has_no_terminator(self):
        self.program('text_write','''let text:NativeUtf8Text=native_utf8_from_bytes("42",2).value;
let mut bytes:[u8;4]=[77;4];let p:*mut u8=unsafe{bytes as *mut u8};
if native_utf8_write(text,p,1).status!=7 || bytes[0]!=77
|| native_utf8_write(text,null,2).status!=1 || native_utf8_write(native_utf8_empty(),null,0).status!=0{return 1;}
let r:NativeU32Result=native_utf8_write(text,p,4);
if r.status!=0 || r.value!=2 || bytes[0]!=52 || bytes[1]!=50 || bytes[2]!=77{return 2;}return 42;''')

    def test_forged_length_is_rejected_before_indexing(self):
        self.program('text_forged','''let bad:NativeUtf8Text=NativeUtf8Text{bytes:[65;256],length:4294967295};
let empty:NativeUtf8Text=native_utf8_empty();
if native_utf8_ok(bad).status!=7 || native_utf8_error(0,9).status!=7
|| native_utf8_validate(bad).status!=7 || native_utf8_slice(bad,0,1).status!=7
|| native_utf8_concat(bad,empty).status!=7 || native_utf8_trim(bad).status!=7
|| native_utf8_ascii_case(bad,0).status!=7 || native_utf8_find(bad,empty).status!=7
|| native_utf8_replace(bad,empty,empty).status!=7 || native_utf8_push_scalar(bad,65).status!=7
|| native_utf8_write(bad,null,0).status!=7 || native_utf8_parse_u32(bad).status!=7
|| native_utf8_equal(bad,bad){return 1;}return 42;''')

    def test_propagation_captures_text_before_cleanup(self):
        self.program('text_propagation','''let good:NativeUtf8TextResult=work(true);let bad:NativeUtf8TextResult=work(false);
if native_utf8_parse_u32(good.value).value!=42 || bad.status!=7 || unsafe{trace}!=2121{return 1;}return 42;''',
'''static mut trace:u32=0;
fn work(ok:bool)->NativeUtf8TextResult{defer{unsafe{trace=trace*10+1;}}defer{unsafe{trace=trace*10+2;}}
let value:NativeUtf8Text=native_utf8_from_u32(42)?;let end:u32=if ok{2}else{3};
let selected:NativeUtf8Text=native_utf8_slice(value,0,end)?;return native_utf8_ok(selected);}''')


if __name__=='__main__':unittest.main()
