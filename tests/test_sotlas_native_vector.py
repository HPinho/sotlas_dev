"""Heap-backed POD vectors, failure atomicity and checked borrowed views."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous
ROOT=Path(__file__).resolve().parents[1]

class NativeVectorTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body,stride=1,alignment=1):
        sources=[]
        for module in ('managed','heap','vector'):
            sources.append('\n'.join(line for line in (ROOT/f'runtime/native/{module}.sotlas').read_text().splitlines()
                                     if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'''
pub fn main_entry()->u32{
let mut bytes:[u8;512]=0;let data:*mut u8=unsafe{bytes as *mut u8};
let mut words:[u64;128]=0;let raw:*mut u64=unsafe{words as *mut u64};
let address:usize=unsafe{raw as usize};let slots:*mut NativeHeapSlot=unsafe{address as *mut NativeHeapSlot};
let mut heap:NativeHeap=native_heap_empty();let h:*mut NativeHeap=unsafe{(&mut heap) as *mut NativeHeap};
if !native_heap_open(h,data,512,slots,32){return 90;}
let mut vector:NativeVector=native_vector_empty();let v:*mut NativeVector=unsafe{(&mut vector) as *mut NativeVector};
'''+f'if !native_vector_open(v,h,{stride},{alignment}){{return 91;}}'+body+'}'))

    def test_growth_insertion_removal_and_checked_read(self):
        self.program('vector_edit','''if !native_vector_append(v,"ac",2) || !native_vector_insert(v,1,"b",1)
|| !native_vector_append(v,"defgh",5) || !native_vector_remove(v,2,3){return 1;}
let view:NativeVectorView=native_vector_view(v,0,5);let mut out:[u8;5]=0;
if !native_vector_read(view,0,unsafe{out as *mut u8},5) || out[0]!=97 || out[1]!=98 || out[2]!=102 || out[4]!=104{return 2;}
if native_vector_read(view,4,unsafe{out as *mut u8},2) || native_vector_view_current(native_vector_view(v,6,0)){return 3;}
if !native_vector_close(v) || heap.used!=0 || !native_heap_close(h){return 4;}return 42;''')

    def test_self_insertion_survives_growth_and_tail_shift(self):
        self.program('vector_self','''native_vector_append(v,"abcd",4);
let source:*mut u8=native_heap_address(vector.storage);
if !native_vector_insert(v,1,source+1,3){return 1;}
let mut out:[u8;7]=0;
if !native_vector_read(native_vector_view(v,0,7),0,unsafe{out as *mut u8},7)
|| out[0]!=97 || out[1]!=98 || out[2]!=99 || out[3]!=100 || out[4]!=98 || out[6]!=100{return 2;}
if heap.used!=vector.capacity{return 3;}return 42;''')

    def test_failed_growth_preserves_bytes_handle_and_view(self):
        self.program('vector_failure','''native_vector_append(v,"abcd",4);
let old:NativeHeapHandle=vector.storage;let view:NativeVectorView=native_vector_view(v,0,4);
let full:NativeHeapHandle=native_heap_allocate(h,508,1,false);
if full.owner==null || native_vector_append(v,"e",1) || !native_vector_view_current(view)
|| vector.length!=4 || vector.storage.generation!=old.generation{return 1;}
let mut out:[u8;4]=0;if !native_vector_read(view,0,unsafe{out as *mut u8},4) || out[3]!=100{return 2;}return 42;''')

    def test_failed_alias_snapshot_does_not_mutate_vector(self):
        self.program('vector_alias_failure','''native_vector_append(v,"abcd",4);
let source:*mut u8=native_heap_address(vector.storage);native_heap_allocate(h,508,1,false);
let view:NativeVectorView=native_vector_view(v,0,4);
if native_vector_insert(v,0,source,4) || vector.length!=4 || !native_vector_view_current(view) || heap.used!=512{return 1;}return 42;''')

    def test_snapshot_is_released_when_growth_fails_after_copy(self):
        self.program('vector_snapshot_cleanup','''native_vector_append(v,"abcd",4);
let source:*mut u8=native_heap_address(vector.storage);native_heap_allocate(h,504,1,false);
let view:NativeVectorView=native_vector_view(v,0,4);
if heap.used!=508 || native_vector_insert(v,0,source,4) || heap.used!=508
|| vector.length!=4 || !native_vector_view_current(view){return 1;}
let mut out:[u8;4]=0;if !native_vector_read(view,0,unsafe{out as *mut u8},4) || out[0]!=97 || out[3]!=100{return 2;}return 42;''')

    def test_revision_and_reopen_invalidate_views(self):
        self.program('vector_views','''native_vector_append(v,"abc",3);
let old:NativeVectorView=native_vector_view(v,0,3);
if !native_vector_set(v,1,"Z") || native_vector_view_current(old){return 1;}
let fresh:NativeVectorView=native_vector_view(v,0,3);
if !native_vector_close(v) || native_vector_view_current(fresh) || !native_vector_open(v,h,1,1){return 2;}
native_vector_append(v,"abc",3);if native_vector_view_current(old) || native_vector_view_current(fresh){return 3;}return 42;''')

    def test_shrink_clear_and_exact_capacity_fallback(self):
        self.program('vector_shrink','''let blocker:NativeHeapHandle=native_heap_allocate(h,505,1,false);
if !native_vector_append(v,"1234567",7) || vector.capacity!=7 || heap.used!=512{return 1;}
native_heap_release(blocker,false);native_vector_remove(v,2,5);
if !native_vector_shrink(v) || vector.capacity!=2 || heap.used!=2{return 2;}
if !native_vector_clear(v) || !native_vector_shrink(v) || vector.capacity!=0 || heap.used!=0{return 3;}
if !native_vector_append(v,"x",1) || vector.length!=1{return 4;}return 42;''')

    def test_u64_elements_preserve_stride_and_alignment(self):
        self.program('vector_words','''let mut input:[u64;3]=[10,20,30];let values:*const u64=unsafe{input as *const u64};
let input_address:usize=unsafe{values as usize};let source:*const u8=unsafe{input_address as *const u8};
if !native_vector_append(v,source,3) || (unsafe{native_heap_address(vector.storage) as usize})%8!=0{return 1;}
native_vector_remove(v,1,1);let mut output:[u64;2]=0;let output_words:*mut u64=unsafe{output as *mut u64};
let dest:usize=unsafe{output_words as usize};
if !native_vector_read(native_vector_view(v,0,2),0,unsafe{dest as *mut u8},2) || output[0]!=10 || output[1]!=30{return 2;}return 42;''',8,8)

    def test_overflow_bad_indices_and_revision_exhaustion(self):
        self.program('vector_bounds','''native_vector_append(v,"abc",3);let view:NativeVectorView=native_vector_view(v,0,3);
if native_vector_insert(v,4,"x",1) || native_vector_remove(v,2,2) || native_vector_set(v,3,"x")
|| native_vector_append(v,"x",18446744073709551615) || native_vector_reserve(v,18446744073709551615)
|| !native_vector_view_current(view){return 1;}
vector.revision=18446744073709551615;
if native_vector_append(v,"x",1) || !native_vector_close(v) || heap.used!=0 || native_vector_open(v,h,1,1){return 2;}return 42;''')

    def test_empty_operations_and_stale_heap_storage(self):
        self.program('vector_empty','''let empty:NativeVectorView=native_vector_view(v,0,0);
if !native_vector_read(empty,0,null,0) || !native_vector_append(v,null,0) || !native_vector_remove(v,0,0)
|| !native_vector_view_current(empty){return 1;}
native_vector_append(v,"x",1);let old:NativeVectorView=native_vector_view(v,0,1);
native_heap_release(vector.storage,false);
if native_vector_shape(v) || native_vector_view_current(old) || native_vector_read(old,0,null,0){return 2;}return 42;''')

    def test_uninitialized_aliases_and_readback_into_vector_are_rejected(self):
        self.program('vector_alias_bounds','''native_vector_append(v,"abc",3);
let memory:*mut u8=native_heap_address(vector.storage);let old:NativeVectorView=native_vector_view(v,0,3);
if native_vector_append(v,memory+3,1) || native_vector_read(old,0,memory,3)
|| vector.length!=3 || !native_vector_view_current(old){return 1;}return 42;''')

    def test_invalid_layout_and_descriptor_overlap(self):
        self.program('vector_layout','''let mut other:NativeVector=native_vector_empty();
let q:*mut NativeVector=unsafe{(&mut other) as *mut NativeVector};
if native_vector_open(q,h,0,1) || native_vector_open(q,h,8,3) || native_vector_open(q,h,7,8)
|| native_vector_open(q,h,4097,1) || native_vector_open(v,h,1,1){return 1;}
let raw_address:usize=unsafe{data as usize};
if native_vector_open(unsafe{raw_address as *mut NativeVector},h,1,1) || heap.used!=0{return 2;}return 42;''')

    def test_mixed_edits_match_an_independent_fixed_array_model(self):
        self.program('vector_model','''let mut expected:[u8;64]=0;let mut actual:[u8;64]=0;
let output:*mut u8=unsafe{actual as *mut u8};let mut length:usize=0;let mut step:usize=0;
while step<500 {
if length==64 {if !native_vector_clear(v){return 1;}length=0;}
else if step%4==0 && length!=0 {
let index:usize=step%length;if !native_vector_remove(v,index,1){return 2;}
let mut j:usize=index;while j+1<length{expected[j]=expected[j+1];j+=1;}length-=1;
}else{
let index:usize=step%(length+1);let mut value:u8=(step%251) as u8;
let pointer:*mut u8=unsafe{(&mut value) as *mut u8};
if !native_vector_insert(v,index,pointer,1){return 3;}
let mut j:usize=length;while j>index{expected[j]=expected[j-1];j-=1;}expected[index]=value;length+=1;
}
if vector.length!=length || !native_vector_read(native_vector_view(v,0,length),0,output,length){return 4;}
let mut j:usize=0;while j<length{if actual[j]!=expected[j]{return 5;}j+=1;}step+=1;
}
if !native_vector_close(v) || heap.used!=0{return 6;}return 42;''')
