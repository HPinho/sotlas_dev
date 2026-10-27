"""Caller-backed UTF-8 edits, alias rules and failure atomicity in native code."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT=Path(__file__).resolve().parents[1]


class NativeUtf8BufferTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body,capacity=32,helpers=''):
        sources=[]
        for module in ('results','text','unicode','utf8_buffer'):
            source=(ROOT/('runtime/native/'+module+'.sotlas')).read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines() if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'\n'+helpers+'''
pub fn main_entry()->u32{let mut bytes:[u8;CAPACITY]=[77;CAPACITY];
let data:*mut u8=unsafe{bytes as *mut u8};let mut buffer:NativeUtf8Buffer=native_utf8_buffer_open(data,CAPACITY);
let b:*mut NativeUtf8Buffer=unsafe{(&mut buffer) as *mut NativeUtf8Buffer};
'''.replace('CAPACITY',str(capacity))+body+'}'))

    def test_append_exceeds_inline_text_capacity(self):
        self.program('buffer_large','''let mut i:u32=0;while i<600{
if native_utf8_buffer_append(b,"x",1).status!=0{return 1;}i=i+1;}
if buffer.length!=600 || native_utf8_buffer_check(b).value!=600 || bytes[599]!=120
|| bytes[600]!=77 || native_utf8_buffer_view(b).length!=600{return 2;}return 42;''',1024)

    def test_numeric_and_scalar_append(self):
        self.program('buffer_numeric','''if native_utf8_buffer_append_u32(b,4294967295).status!=0
|| native_utf8_buffer_append_scalar(b,8364).value!=13 || native_utf8_buffer_check(b).value!=11
|| bytes[10]!=226 || bytes[12]!=172 || bytes[13]!=77{return 1;}return 42;''')

    def test_capacity_failure_preserves_all_bytes_and_length(self):
        self.program('buffer_capacity','''native_utf8_buffer_append(b,"42",2);
if native_utf8_buffer_append_u32(b,999999).status!=7 || buffer.length!=2
|| bytes[0]!=52 || bytes[1]!=50 || bytes[2]!=77 || bytes[3]!=77{return 1;}return 42;''',4)

    def test_malformed_append_is_transactional(self):
        self.program('buffer_bad_utf8','''native_utf8_buffer_append(b,"ok",2);let bad:[u8;3]=[65,226,130];
let r:NativeU32Result=native_utf8_buffer_append(b,unsafe{bad as *const u8},3);
if r.status!=8 || r.error.offset!=1 || buffer.length!=2 || bytes[2]!=77{return 1;}return 42;''')

    def test_self_append_and_overlapping_source_use_memmove(self):
        self.program('buffer_overlap','''native_utf8_buffer_append(b,"abcd",4);
if native_utf8_buffer_append(b,data,4).status!=0 || !native_text_equal(native_utf8_buffer_view(b),native_text_open("abcdabcd",8)){return 1;}
native_utf8_buffer_reset(b,false);let seed:[u8;6]=[97,98,99,100,101,102];
let mut i:u32=0;while i<6{bytes[i]=seed[i];i=i+1;}buffer.length=2;
if native_utf8_buffer_append(b,data,6).status!=0 || !native_text_equal(native_utf8_buffer_view(b),native_text_open("ababcdef",8)){return 2;}return 42;''')

    def test_replace_growth_shrink_and_delete(self):
        self.program('buffer_edits','''native_utf8_buffer_append(b,"a=1;z",5);
if native_utf8_buffer_replace(b,2,3,"42",2).status!=0 || !native_text_equal(native_utf8_buffer_view(b),native_text_open("a=42;z",6)){return 1;}
if native_utf8_buffer_replace(b,0,2,null,0).status!=0 || !native_text_equal(native_utf8_buffer_view(b),native_text_open("42;z",4)){return 2;}
if native_utf8_buffer_replace(b,2,4,"!",1).status!=0 || !native_text_equal(native_utf8_buffer_view(b),native_text_open("42!",3)){return 3;}return 42;''')

    def test_replace_capacity_and_alias_rejections_preserve_state(self):
        self.program('buffer_edit_failure','''native_utf8_buffer_append(b,"abcdef",6);
if native_utf8_buffer_replace(b,1,2,"1234567",7).status!=7
|| native_utf8_buffer_replace(b,1,2,data,2).status!=7
|| buffer.length!=6 || !native_text_equal(native_utf8_buffer_view(b),native_text_open("abcdef",6))
|| bytes[6]!=77{return 1;}return 42;''',8)

    def test_scalar_boundaries_for_replace_and_truncate(self):
        self.program('buffer_boundaries','''native_utf8_buffer_append_scalar(b,8364);native_utf8_buffer_append(b,"42",2);
if native_utf8_buffer_truncate(b,1).status!=8 || native_utf8_buffer_replace(b,1,3,"x",1).status!=8
|| native_utf8_buffer_replace(b,0,2,"x",1).status!=8 || buffer.length!=5{return 1;}
if native_utf8_buffer_truncate(b,3).status!=0 || buffer.length!=3 || bytes[3]!=52
|| native_utf8_buffer_truncate(b,4).status!=7{return 2;}return 42;''')

    def test_malformed_replacement_does_not_shift_suffix(self):
        self.program('buffer_bad_replace','''native_utf8_buffer_append(b,"abc",3);let bad:[u8;1]=[255];
if native_utf8_buffer_replace(b,1,2,unsafe{bad as *const u8},1).status!=8
|| buffer.length!=3 || bytes[1]!=98 || bytes[2]!=99{return 1;}return 42;''')

    def test_null_and_wrapping_storage_rejected(self):
        self.program('buffer_ranges','''if native_utf8_buffer_open(null,1).valid || native_utf8_buffer_open(data,4294967296).valid
|| native_utf8_buffer_append(null,"a",1).status!=7 || native_utf8_buffer_append(b,null,1).status!=1{return 1;}
let address:u64=18446744073709551615;let invalid:*mut u8=unsafe{address as *mut u8};
if native_utf8_buffer_open(invalid,1).valid || native_utf8_buffer_append(b,invalid,1).status!=7
|| native_utf8_buffer_replace(b,0,0,invalid,1).status!=7{return 2;}
let mut empty:NativeUtf8Buffer=native_utf8_buffer_open(null,0);let e:*mut NativeUtf8Buffer=unsafe{(&mut empty) as *mut NativeUtf8Buffer};
if native_utf8_buffer_append(e,null,0).status!=0 || !native_utf8_buffer_view(e).valid{return 3;}return 42;''')

    def test_forged_descriptor_and_invalid_content_fail_before_edits(self):
        self.program('buffer_forged','''buffer.length=33;
if native_utf8_buffer_check(b).status!=7 || native_utf8_buffer_reset(b,true).status!=7 || bytes[0]!=77{return 1;}
buffer.length=1;bytes[0]=255;
if native_utf8_buffer_check(b).status!=8 || native_utf8_buffer_view(b).valid
|| native_utf8_buffer_append(b,"x",1).status!=8 || native_utf8_buffer_replace(b,0,1,"x",1).status!=8{return 2;}
if native_utf8_buffer_reset(b,true).status!=0 || bytes[0]!=0 || buffer.length!=0 || bytes[1]!=77{return 3;}return 42;''')

    def test_slice_append_and_wipe(self):
        self.program('buffer_slice','''let borrowed:NativeByteSlice=native_text_open("42",2);
if native_utf8_buffer_append_slice(b,borrowed).status!=0 || native_utf8_buffer_append_slice(b,native_text_invalid()).status!=7{return 1;}
native_utf8_buffer_reset(b,false);if bytes[0]!=52 || buffer.length!=0{return 2;}
native_utf8_buffer_append(b,"ab",2);native_utf8_buffer_reset(b,true);
if bytes[0]!=0 || bytes[1]!=0 || bytes[2]!=77 || buffer.length!=0{return 3;}return 42;''')

    def test_invalid_scalar_does_not_publish(self):
        self.program('buffer_scalar_invalid','''if native_utf8_buffer_append_scalar(b,55296).status!=8
|| native_utf8_buffer_append_scalar(b,1114112).status!=8 || buffer.length!=0 || bytes[0]!=77{return 1;}return 42;''')

    def test_result_propagation_and_lifo_cleanup(self):
        self.program('buffer_result','''let good:NativeU32Result=work(b,false);let bad:NativeU32Result=work(b,true);
if good.status!=0 || good.value!=2 || bad.status!=7 || buffer.length!=4 || unsafe{trace}!=2121{return 1;}return 42;''',32,
'''static mut trace:u32=0;
fn work(b:*mut NativeUtf8Buffer,fail:bool)->NativeU32Result{
defer{unsafe{trace=trace*10+1;}}defer{unsafe{trace=trace*10+2;}}
native_utf8_buffer_append_u32(b,42)?;
if fail{native_utf8_buffer_replace(b,100,101,null,0)?;}
return native_utf8_buffer_check(b);}''')

    def test_deferred_wipe_preserves_return_and_clears_success_and_error(self):
        self.program('buffer_deferred_wipe','''let good:NativeU32Result=clean(b,false);
if good.status!=0 || good.value!=2 || buffer.length!=0 || bytes[0]!=0 || bytes[1]!=0 || bytes[2]!=77{return 1;}
let bad:NativeU32Result=clean(b,true);
if bad.status!=7 || buffer.length!=0 || bytes[0]!=0 || bytes[1]!=0 || bytes[2]!=77{return 2;}return 42;''',32,
'''fn clean(b:*mut NativeUtf8Buffer,fail:bool)->NativeU32Result{
defer native_utf8_buffer_reset(b,true);native_utf8_buffer_append_u32(b,42)?;
if fail{native_utf8_buffer_replace(b,100,101,null,0)?;}return native_utf8_buffer_check(b);}''')


if __name__=='__main__':unittest.main()
