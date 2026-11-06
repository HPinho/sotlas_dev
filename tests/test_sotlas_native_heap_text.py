"""Growing UTF-8 text, alias-safe splices and allocation failure atomicity."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous
ROOT=Path(__file__).resolve().parents[1]

class NativeHeapTextTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body):
        sources=[]
        for module in ('results','managed','text','unicode','utf8_buffer','heap','vector','heap_text'):
            sources.append('\n'.join(line for line in (ROOT/f'runtime/native/{module}.sotlas').read_text(encoding='utf-8').splitlines()
                                     if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'''
pub fn main_entry()->u32{
let mut bytes:[u8;512]=0;let data:*mut u8=unsafe{bytes as *mut u8};
let mut metadata:[u64;128]=0;let words:*mut u64=unsafe{metadata as *mut u64};
let address:usize=unsafe{words as usize};let slots:*mut NativeHeapSlot=unsafe{address as *mut NativeHeapSlot};
let mut heap:NativeHeap=native_heap_empty();let h:*mut NativeHeap=unsafe{(&mut heap) as *mut NativeHeap};
if !native_heap_open(h,data,512,slots,32){return 90;}
let mut text:NativeHeapText=native_heap_text_empty();let t:*mut NativeHeapText=unsafe{(&mut text) as *mut NativeHeapText};
if !native_heap_text_open(t,h){return 91;}
'''+body+'}'))

    def test_utf8_scalars_and_scalar_boundary_edits(self):
        self.program('heap_text_unicode','''native_heap_text_append(t,"A",1);
if native_heap_text_insert_scalar(t,1,233).status!=0 || native_heap_text_insert_scalar(t,2,128578).status!=0
|| native_heap_text_check(t).value!=3 || native_heap_text_scalar_at(t,1).value!=233{return 1;}
let view:NativeVectorView=native_heap_text_slice(t,1,3);if view.count!=6 || !native_vector_view_current(view){return 2;}
if native_heap_text_replace(t,2,3,"x",1).status!=8 || !native_vector_view_current(view){return 3;}
if native_heap_text_remove_scalar(t,1).value!=233 || native_heap_text_check(t).value!=2
|| native_vector_view_current(view) || native_heap_text_scalar_at(t,1).value!=128578{return 4;}
if !native_heap_text_close(t) || heap.used!=0{return 5;}return 42;''')

    def test_self_replacement_and_self_append_across_growth(self):
        self.program('heap_text_alias','''native_heap_text_append(t,"abcdef",6);
let before:NativeVectorView=native_heap_text_view(t);let source:*mut u8=native_heap_address(text.bytes.storage);
if native_heap_text_replace(t,1,3,source+2,4).status!=0 || native_vector_view_current(before){return 1;}
let mut out:[u8;16]=0;let output:*mut u8=unsafe{out as *mut u8};
if !native_vector_read(native_heap_text_view(t),0,output,8) || out[0]!=97 || out[1]!=99 || out[4]!=102 || out[5]!=100{return 2;}
if native_heap_text_append_from(t,t).value!=16 || !native_vector_read(native_heap_text_view(t),0,output,16)
|| out[0]!=out[8] || out[7]!=out[15]{return 3;}return 42;''')

    def test_shrinking_replacement_works_with_full_heap(self):
        self.program('heap_text_full_shrink','''native_heap_text_append(t,"abcd",4);native_heap_allocate(h,508,1,false);
if native_heap_text_replace(t,1,4,"Z",1).status!=0 || native_heap_text_check(t).value!=2 || heap.used!=512{return 1;}
let mut out:[u8;2]=0;if !native_vector_read(native_heap_text_view(t),0,unsafe{out as *mut u8},2)
|| out[0]!=97 || out[1]!=90{return 2;}return 42;''')

    def test_oom_keeps_text_view_and_contents(self):
        self.program('heap_text_oom','''native_heap_text_append(t,"abcd",4);native_heap_allocate(h,508,1,false);
let old:NativeVectorView=native_heap_text_view(t);let handle:NativeHeapHandle=text.bytes.storage;
if native_heap_text_replace(t,0,1,"longer",6).status!=10 || !native_vector_view_current(old)
|| text.bytes.storage.generation!=handle.generation || text.bytes.length!=4 || heap.used!=512{return 1;}
if native_heap_text_append_i64(t,-42).status!=10 || !native_vector_view_current(old){return 2;}return 42;''')

    def test_alias_snapshot_cleanup_on_failed_replacement(self):
        self.program('heap_text_snapshot','''native_heap_text_append(t,"abcd",4);native_heap_allocate(h,504,1,false);
let old:NativeVectorView=native_heap_text_view(t);let source:*mut u8=native_heap_address(text.bytes.storage);
if native_heap_text_replace(t,0,1,source,4).status!=10 || heap.used!=508 || !native_vector_view_current(old){return 1;}return 42;''')

    def test_malformed_input_is_rejected_before_capacity_changes(self):
        self.program('heap_text_invalid','''native_heap_text_append(t,"ok",2);let old:NativeVectorView=native_heap_text_view(t);
let bad:[u8;3]=[237,160,128];
if native_heap_text_append(t,unsafe{bad as *const u8},3).status!=8 || !native_vector_view_current(old)
|| native_heap_text_insert_scalar(t,0,55296).status!=8 || native_heap_text_insert_scalar(t,0,1114112).status!=8
|| native_heap_text_replace_scalars(t,2,1,"x",1).status!=7 || native_heap_text_scalar_at(t,2).status!=7{return 1;}return 42;''')

    def test_source_error_offset_and_partial_scalar_alias(self):
        self.program('heap_text_offsets','''native_heap_text_insert_scalar(t,0,233);
let old:NativeVectorView=native_heap_text_view(t);let bad:[u8;4]=[65,237,160,128];
let error:NativeU32Result=native_heap_text_append(t,unsafe{bad as *const u8},4);
if error.status!=8 || error.error.offset!=1 || !native_vector_view_current(old){return 1;}
let source:*mut u8=native_heap_address(text.bytes.storage);
if native_heap_text_append(t,source+1,1).status!=8 || !native_vector_view_current(old){return 2;}return 42;''')

    def test_integer_formatting_including_extreme_values(self):
        self.program('heap_text_numbers','''if native_heap_text_append_u64(t,18446744073709551615).value!=20
|| native_heap_text_append(t,"/",1).status!=0{return 1;}
let minimum:i64=(-9223372036854775807 as i64)-1;
if native_heap_text_append_i64(t,minimum).value!=41 || native_heap_text_append_u64(t,0).value!=42{return 2;}
let mut out:[u8;42]=0;if !native_vector_read(native_heap_text_view(t),0,unsafe{out as *mut u8},42)
|| out[0]!=49 || out[19]!=53 || out[20]!=47 || out[21]!=45 || out[22]!=57 || out[40]!=56 || out[41]!=48{return 3;}return 42;''')

    def test_signed_zero_positive_maximum_and_negative_one(self):
        self.program('heap_text_signed','''native_heap_text_append_i64(t,-1);native_heap_text_append(t,"/",1);
native_heap_text_append_i64(t,0);native_heap_text_append(t,"/",1);
if native_heap_text_append_i64(t,9223372036854775807).value!=24{return 1;}
let mut out:[u8;24]=0;if !native_vector_read(native_heap_text_view(t),0,unsafe{out as *mut u8},24)
|| out[0]!=45 || out[1]!=49 || out[3]!=48 || out[5]!=57 || out[23]!=55{return 2;}return 42;''')

    def test_view_invalidation_shrink_reopen_and_terminal_revision(self):
        self.program('heap_text_views','''native_heap_text_append(t,"abc",3);let old:NativeVectorView=native_heap_text_view(t);
if native_heap_text_shrink(t).status!=0 || text.bytes.capacity!=3 || native_vector_view_current(old){return 1;}
let fresh:NativeVectorView=native_heap_text_view(t);
if !native_heap_text_close(t) || native_vector_view_current(fresh) || !native_heap_text_open(t,h){return 2;}
native_heap_text_append(t,"abc",3);if native_vector_view_current(old) || native_vector_view_current(fresh){return 3;}
text.bytes.revision=18446744073709551615;
if native_heap_text_append(t,"x",1).status!=7 || native_heap_text_shrink(t).status!=7
|| !native_heap_text_close(t) || heap.used!=0{return 4;}return 42;''')

    def test_empty_text_null_input_and_corrupt_payload_cleanup(self):
        self.program('heap_text_empty','''let view:NativeVectorView=native_heap_text_view(t);
if !native_vector_view_current(view) || native_heap_text_check(t).value!=0
|| native_heap_text_append(t,null,0).status!=0 || native_heap_text_append(t,null,1).status!=1{return 1;}
native_heap_text_append(t,"x",1);let memory:*mut u8=native_heap_address(text.bytes.storage);unsafe{*memory=255;}
if native_heap_text_check(t).status!=8 || native_vector_view_current(native_heap_text_view(t))
|| !native_heap_text_close(t) || heap.used!=0{return 2;}return 42;''')
