"""Native JSON construction, grammar state and per-operation failure atomicity."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as harness

ROOT = Path(__file__).resolve().parents[1]


class NativeJsonWriterTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute

    def program(self, name, body, capacity=256):
        runtime = '\n'.join(line for module in ('text', 'unicode', 'results', 'utf8_buffer', 'json', 'json_writer')
                            for line in (ROOT / f'runtime/native/{module}.sotlas').read_text(encoding='utf-8').splitlines()
                            if not line.startswith(('module ', 'import ')))
        setup = f'''let mut bytes:[u8;{max(1, capacity)}]=[77;{max(1, capacity)}];
let data:*mut u8=unsafe{{bytes as *mut u8}};
let mut writer:NativeJsonWriter=native_json_writer_open(data,{capacity});
let w:*mut NativeJsonWriter=unsafe{{(&mut writer) as *mut NativeJsonWriter}};
'''
        self.execute(self.compile(name, runtime + '\npub fn main_entry()->u32{\n' + setup + body + '}'))

    def test_nested_objects_arrays_and_readback(self):
        self.program('json_writer_nested', '''
if native_json_writer_object(w)!=0 || native_json_writer_key(w,native_text_open("values",6))!=0
|| native_json_writer_array(w)!=0 || native_json_writer_u32(w,20)!=0 || native_json_writer_u32(w,22)!=0
|| native_json_writer_bool(w,true)!=0 || native_json_writer_null(w)!=0 || native_json_writer_end_array(w)!=0
|| native_json_writer_key(w,native_text_open("ready",5))!=0 || native_json_writer_bool(w,false)!=0
|| native_json_writer_end_object(w)!=0{return 1;}
let view:NativeByteSlice=native_json_writer_view(w);let parsed:NativeJsonResult=native_json_parse(view);
if !view.valid || parsed.status!=0{return 2;}
let values:NativeJsonResult=native_json_object_get(parsed.value,native_text_open("values",6));
if native_json_u32(native_json_array_at(values.value,0).value).value!=20
|| native_json_u32(native_json_array_at(values.value,1).value).value!=22
|| native_json_array_at(values.value,2).value.kind!=5 || native_json_array_at(values.value,3).value.kind!=7
|| native_json_object_get(parsed.value,native_text_open("ready",5)).value.kind!=6{return 3;}return 42;''')

    def test_string_escaping_preserves_unicode_controls_and_nul(self):
        self.program('json_writer_escapes', '''let input:[u8;11]=[34,92,0,10,9,195,169,240,159,153,130];
let text:NativeByteSlice=native_text_open(unsafe{input as *const u8},11);
if native_json_writer_string(w,text)!=0{return 1;}
let root:NativeJsonResult=native_json_parse(native_json_writer_view(w));
let mut decoded:[u8;12]=[77;12];
let copied:NativeJsonStringResult=native_json_string_copy(root.value,unsafe{decoded as *mut u8},12);
if copied.status!=0 || copied.length!=11 || decoded[11]!=77{return 2;}
let mut i:usize=0;while i<11{if decoded[i]!=input[i]{return 3;}i+=1;}return 42;''')

    def test_exact_capacity_empty_keys_strings_and_numbers(self):
        # {"":4294967295} occupies exactly 15 bytes, without a terminator.
        self.program('json_writer_exact', '''
if native_json_writer_object(w)!=0 || native_json_writer_key(w,native_text_open(null,0))!=0
|| native_json_writer_u32(w,4294967295)!=0 || native_json_writer_end_object(w)!=0{return 1;}
let view:NativeByteSlice=native_json_writer_view(w);
if !view.valid || view.length!=15 || bytes[14]!=125{return 2;}
if native_json_writer_reset(w)!=0 || native_json_writer_string(w,native_text_open(null,0))!=0
|| native_json_writer_view(w).length!=2{return 3;}
if native_json_writer_reset(w)!=0 || native_json_writer_number(w,native_text_open("-1.25e+3",8))!=0{return 4;}
let number:NativeByteSlice=native_json_writer_view(w);
if !number.valid || number.length!=8 || bytes[0]!=45 || bytes[7]!=51{return 5;}return 42;''', capacity=15)

    def test_state_errors_do_not_publish_or_consume_pending_values(self):
        self.program('json_writer_state', '''
if native_json_writer_view(w).valid || native_json_writer_key(w,native_text_open("x",1))!=8
|| native_json_writer_end_array(w)!=8 || writer.buffer.length!=0 || bytes[0]!=77{return 1;}
if native_json_writer_object(w)!=0 || native_json_writer_u32(w,9)!=8 || writer.buffer.length!=1{return 2;}
if native_json_writer_key(w,native_text_open("x",1))!=0{return 3;}
let before:usize=writer.buffer.length;
if native_json_writer_end_object(w)!=8 || native_json_writer_key(w,native_text_open("y",1))!=8
|| native_json_writer_view(w).valid || writer.buffer.length!=before{return 4;}
if native_json_writer_array(w)!=0 || native_json_writer_end_object(w)!=8
|| native_json_writer_key(w,native_text_open("x",1))!=8 || native_json_writer_end_array(w)!=0
|| native_json_writer_end_object(w)!=0 || !native_json_writer_view(w).valid{return 5;}
let complete:usize=writer.buffer.length;
if native_json_writer_null(w)!=8 || native_json_writer_array(w)!=8
|| writer.buffer.length!=complete || !native_json_writer_view(w).valid{return 6;}return 42;''')

    def test_capacity_failure_includes_comma_and_preserves_bytes_and_state(self):
        self.program('json_writer_capacity', '''
if native_json_writer_array(w)!=0 || native_json_writer_u32(w,1)!=0{return 1;}
if native_json_writer_u32(w,22)!=6 || writer.buffer.length!=2 || bytes[0]!=91
|| bytes[1]!=49 || bytes[2]!=77 || bytes[3]!=77{return 2;}
if native_json_writer_end_array(w)!=0 || !native_json_writer_view(w).valid{return 3;}
if native_json_writer_reset(w)!=0 || native_json_writer_string(w,native_text_open("abcd",4))!=6
|| writer.root || writer.buffer.length!=0{return 4;}
if native_json_writer_object(w)!=0 || native_json_writer_key(w,native_text_open("x",1))!=6
|| writer.buffer.length!=1 || writer.frames[0]!=3{return 5;}
if native_json_writer_end_object(w)!=0 || !native_json_writer_view(w).valid{return 6;}return 42;''', capacity=4)

    def test_invalid_utf8_number_and_source_alias_do_not_write(self):
        self.program('json_writer_invalid', '''let invalid:[u8;2]=[192,128];
let bad:NativeByteSlice=native_text_open(unsafe{invalid as *const u8},2);
if native_json_writer_string(w,bad)!=3 || native_json_writer_number(w,native_text_open("NaN",3))!=2
|| native_json_writer_number(w,native_text_open("true",4))!=4
|| native_json_writer_number(w,native_text_open(" 1",2))!=2
|| native_json_writer_string(w,native_text_open(null,1))!=1 || writer.root
|| writer.buffer.length!=0 || bytes[0]!=77{return 1;}
if native_json_writer_array(w)!=0{return 2;}
let alias:NativeByteSlice=native_text_open(unsafe{data as *const u8},1);
if native_json_writer_string(w,alias)!=7 || writer.buffer.length!=1 || bytes[1]!=77{return 3;}
if native_json_writer_string(w,native_text_open("ok",2))!=0 || native_json_writer_end_array(w)!=0{return 4;}return 42;''')

    def test_depth_limit_is_recoverable_and_reader_accepts_boundary(self):
        self.program('json_writer_depth', '''let mut i:usize=0;
while i<64{if native_json_writer_array(w)!=0{return 1;}i+=1;}
if native_json_writer_array(w)!=5 || writer.buffer.length!=64 || writer.depth!=64{return 2;}
if native_json_writer_null(w)!=0{return 3;}
while i!=0{if native_json_writer_end_array(w)!=0{return 4;}i-=1;}
let view:NativeByteSlice=native_json_writer_view(w);
if !view.valid || view.length!=132 || native_json_parse(view).status!=0{return 5;}return 42;''')

    def test_empty_storage_reset_and_invalid_control(self):
        self.program('json_writer_empty', '''
if native_json_writer_null(w)!=6 || native_json_writer_object(w)!=6 || writer.root
|| writer.buffer.length!=0 || bytes[0]!=77{return 1;}
if native_json_writer_reset(w)!=0 || native_json_writer_view(w).valid{return 2;}
if native_json_writer_null(null)!=1 || native_json_writer_reset(null)!=1{return 3;}return 42;''', capacity=0)

    def test_unicode_keys_duplicate_names_and_state_reset(self):
        self.program('json_writer_keys', '''let name:[u8;2]=[195,169];
let key:NativeByteSlice=native_text_open(unsafe{name as *const u8},2);
if native_json_writer_object(w)!=0 || native_json_writer_key(w,key)!=0 || native_json_writer_u32(w,20)!=0
|| native_json_writer_key(w,key)!=0 || native_json_writer_u32(w,99)!=0 || native_json_writer_end_object(w)!=0{return 1;}
let parsed:NativeJsonResult=native_json_parse(native_json_writer_view(w));
if native_json_u32(native_json_object_get(parsed.value,key).value).value!=20{return 2;}
if native_json_writer_reset(w)!=0 || native_json_writer_array(w)!=0
|| native_json_writer_bool(w,true)!=0 || native_json_writer_end_array(w)!=0
|| !native_json_writer_view(w).valid{return 3;}return 42;''')

    def test_escape_capacity_and_bad_keys_preserve_object_state(self):
        self.program('json_writer_escape_capacity', '''let zero:[u8;1]=[0];
let control:NativeByteSlice=native_text_open(unsafe{zero as *const u8},1);
if native_json_writer_string(w,control)!=6 || writer.buffer.length!=0 || bytes[0]!=77{return 1;}
if native_json_writer_object(w)!=0{return 2;}
let invalid:[u8;1]=[255];let bad:NativeByteSlice=native_text_open(unsafe{invalid as *const u8},1);
if native_json_writer_key(w,bad)!=3 || writer.buffer.length!=1 || writer.frames[0]!=3{return 3;}
if native_json_writer_end_object(w)!=0 || !native_json_writer_view(w).valid{return 4;}return 42;''', capacity=7)

    def test_corrupt_control_and_backing_alias_are_rejected_without_writes(self):
        self.program('json_writer_corrupt', '''
writer.depth=65;
if native_json_writer_null(w)!=1 || native_json_writer_view(w).valid || bytes[0]!=77{return 1;}
writer.depth=0;writer.buffer.length=257;
if native_json_writer_array(w)!=1 || bytes[0]!=77{return 2;}
writer.buffer.length=0;
let address:usize=unsafe{w as usize};let control:*mut u8=unsafe{address as *mut u8};
writer.buffer.data=control;writer.buffer.capacity=span_of::<NativeJsonWriter>();
if native_json_writer_null(w)!=1 || native_json_writer_reset(w)!=1{return 3;}return 42;''')
