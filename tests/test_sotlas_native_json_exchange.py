"""Closure cases for native in-memory JSON traversal and value re-emission."""
import unittest
import test_sotlas_native_i32 as harness
import test_sotlas_native_json as reader
import test_sotlas_native_json_writer as writer


class NativeJsonExchangeTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute
    program = writer.NativeJsonWriterTests.program
    input = reader.NativeJsonTests.input

    def test_object_iteration_preserves_duplicates_order_and_decoded_keys(self):
        source = '{ "a":[1,2], "a":null, "\\u00e9":{"x":true}, "":false }'
        self.program('json_iter_object', self.input(source) + '''
let parsed:NativeJsonResult=native_json_parse(input);let mut cursor:NativeJsonIter=native_json_iter(parsed.value);
let kinds:[u32;4]=[2,7,1,6];let mut count:u32=0;
while true{let item:NativeJsonItem=native_json_next(cursor);
if item.status!=0{return 1;}if item.done{cursor=item.next;break;}
if count>=4 || !item.key.valid || item.value.kind!=kinds[count]{return 2;}
let mut key:[u8;8]=0;let copied:NativeJsonStringResult=native_json_string_copy(item.key,unsafe{key as *mut u8},8);
if copied.status!=0{return 3;}
if count<2 && (copied.length!=1 || key[0]!=97){return 4;}
if count==2 && (copied.length!=2 || key[0]!=195 || key[1]!=169){return 5;}
if count==3 && copied.length!=0{return 6;}
cursor=item.next;count+=1;}
let again:NativeJsonItem=native_json_next(cursor);
if count!=4 || again.status!=0 || !again.done || again.value.valid{return 7;}return 42;''')

    def test_array_iteration_covers_every_value_kind_and_nested_values(self):
        self.program('json_iter_array', self.input('[{},[],"x",1e999,true,false,null,[20,22]]') + '''
let root:NativeJsonResult=native_json_parse(input);let mut cursor:NativeJsonIter=native_json_iter(root.value);
let kinds:[u32;8]=[1,2,3,4,5,6,7,2];let mut count:u32=0;
while true{let item:NativeJsonItem=native_json_next(cursor);if item.status!=0{return 1;}if item.done{break;}
if count>=8 || item.key.valid || item.value.kind!=kinds[count]{return 2;}
if count==7{let mut nested:NativeJsonIter=native_json_iter(item.value);let mut sum:u32=0;
while true{let child:NativeJsonItem=native_json_next(nested);if child.status!=0{return 3;}if child.done{break;}
sum+=native_json_u32(child.value).value;nested=child.next;}
if sum!=42{return 4;}}
cursor=item.next;count+=1;}if count!=8{return 5;}return 42;''')

    def test_cursor_rejects_interior_positions_wrong_kinds_and_false_done(self):
        self.program('json_iter_invalid', self.input('[ [20,22], "x,y" ]') + '''
let parsed:NativeJsonResult=native_json_parse(input);let cursor:NativeJsonIter=native_json_iter(parsed.value);
let interior:NativeJsonIter=NativeJsonIter{owner:parsed.value,position:4,valid:true,done:false};
if native_json_next(interior).status!=1{return 1;}
let premature:NativeJsonIter=NativeJsonIter{owner:parsed.value,position:cursor.position,valid:true,done:true};
if native_json_next(premature).status!=1{return 2;}
let outside:NativeJsonIter=NativeJsonIter{owner:parsed.value,position:parsed.value.end,valid:true,done:false};
if native_json_next(outside).status!=1{return 3;}
let scalar:NativeJsonValue=native_json_array_at(parsed.value,1).value;
if native_json_iter(scalar).valid || native_json_next(native_json_iter(scalar)).status!=1{return 4;}
let first:NativeJsonItem=native_json_next(cursor);
if first.status!=0 || first.value.kind!=2{return 5;}return 42;''')

    def test_empty_container_iteration_and_depth_ignores_escaped_delimiters(self):
        source = '[{},[],"[{}]\\\"", {"x":[[null]]}]'
        self.program('json_depth_and_empty', self.input(source) + '''
let root:NativeJsonResult=native_json_parse(input);if root.status!=0 || native_json_depth(root.value).value!=4{return 1;}
let object:NativeJsonValue=native_json_array_at(root.value,0).value;
let array:NativeJsonValue=native_json_array_at(root.value,1).value;
let a:NativeJsonItem=native_json_next(native_json_iter(object));let b:NativeJsonItem=native_json_next(native_json_iter(array));
if a.status!=0 || !a.done || b.status!=0 || !b.done{return 2;}
let string:NativeJsonValue=native_json_array_at(root.value,2).value;
if native_json_depth(string).value!=0{return 3;}return 42;''')

    def test_copy_all_kinds_and_keep_lexical_numbers_and_whitespace(self):
        source = '[ {"a": 1, "a":2}, [true, null], "\\u00e9", -1.20e+999, true, false, null ]'
        self.program('json_copy_values', self.input(source) + '''
let root:NativeJsonResult=native_json_parse(input);let mut cursor:NativeJsonIter=native_json_iter(root.value);
if native_json_writer_array(w)!=0{return 1;}
while true{let item:NativeJsonItem=native_json_next(cursor);if item.status!=0{return 2;}if item.done{break;}
if native_json_writer_value(w,item.value)!=0{return 3;}cursor=item.next;}
if native_json_writer_end_array(w)!=0{return 4;}
let out:NativeJsonResult=native_json_parse(native_json_writer_view(w));if out.status!=0{return 5;}
let number:NativeByteSlice=native_json_raw(native_json_array_at(out.value,3).value);
let mut ordering:i32=0;if !native_text_compare(number,native_text_open("-1.20e+999",10),unsafe{&mut ordering}) || ordering!=0{return 6;}
let first:NativeJsonValue=native_json_array_at(out.value,0).value;
if native_json_u32(native_json_object_get(first,native_text_open("a",1)).value).value!=1{return 7;}return 42;''')

    def test_copy_capacity_failure_does_not_append_separator_or_consume_slot(self):
        self.program('json_copy_capacity', self.input('[20,22]') + '''
let root:NativeJsonResult=native_json_parse(input);
if native_json_writer_array(w)!=0 || native_json_writer_u32(w,1)!=0{return 1;}
if native_json_writer_value(w,root.value)!=6 || writer.buffer.length!=2 || writer.frames[0]!=2
|| bytes[2]!=77 || bytes[3]!=77{return 2;}
if native_json_writer_end_array(w)!=0 || !native_json_writer_view(w).valid{return 3;}return 42;''', capacity=8)

    def test_combined_depth_is_checked_before_copy(self):
        raw = '[' * 64 + 'null' + ']' * 64
        self.program('json_copy_depth', self.input(raw) + '''
let parsed:NativeJsonResult=native_json_parse(input);if parsed.status!=0{return 1;}
if native_json_writer_array(w)!=0{return 2;}
if native_json_writer_value(w,parsed.value)!=5 || writer.buffer.length!=1 || writer.frames[0]!=1 || bytes[1]!=77{return 3;}
if native_json_writer_null(w)!=0 || native_json_writer_end_array(w)!=0{return 4;}
if native_json_writer_reset(w)!=0 || native_json_writer_value(w,parsed.value)!=0
|| !native_json_writer_view(w).valid{return 5;}
let inner:NativeJsonValue=native_json_array_at(parsed.value,0).value;
if native_json_writer_reset(w)!=0 || native_json_writer_array(w)!=0 || native_json_writer_value(w,inner)!=0
|| native_json_writer_end_array(w)!=0 || !native_json_writer_view(w).valid{return 6;}return 42;''')

    def test_copy_alias_and_invalid_value_fail_without_mutation(self):
        self.program('json_copy_alias', '''
if native_json_writer_array(w)!=0 || native_json_writer_u32(w,42)!=0 || native_json_writer_end_array(w)!=0{return 1;}
let parsed:NativeJsonResult=native_json_parse(native_json_writer_view(w));
let before:usize=writer.buffer.length;
if native_json_writer_reset(w)!=0{return 2;}
if native_json_writer_value(w,parsed.value)!=7 || writer.buffer.length!=0 || writer.root || bytes[0]!=91{return 3;}
let invalid:NativeJsonValue=NativeJsonValue{source:native_text_open(null,1),start:0,end:1,kind:4,valid:true};
if native_json_writer_value(w,invalid)!=1 || writer.buffer.length!=0 || before!=4{return 4;}
if native_json_writer_u32(w,42)!=0 || !native_json_writer_view(w).valid{return 5;}return 42;''')
