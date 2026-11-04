"""Variable-sized native allocations, relocation and failure preservation."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT=Path(__file__).resolve().parents[1]


class NativeHeapTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body):
        sources=[]
        for module in ('managed','heap'):
            sources.append('\n'.join(line for line in (ROOT/f'runtime/native/{module}.sotlas').read_text().splitlines()
                                     if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'''
pub fn main_entry()->u32 {
let mut bytes:[u8;512]=[77;512];let data:*mut u8=unsafe{bytes as *mut u8};
let mut words:[u64;128]=0;let metadata:*mut u64=unsafe{words as *mut u64};
let address:usize=unsafe{metadata as usize};let slots:*mut NativeHeapSlot=unsafe{address as *mut NativeHeapSlot};
let mut heap:NativeHeap=native_heap_empty();let p:*mut NativeHeap=unsafe{(&mut heap) as *mut NativeHeap};
if !native_heap_open(p,data,512,slots,32){return 90;}
'''+body+'}'))

    def test_variable_sizes_and_actual_alignment(self):
        self.program('heap_alignment','''let a:NativeHeapHandle=native_heap_allocate(p,13,1,false);
let b:NativeHeapHandle=native_heap_allocate(p,37,64,true);
if !native_heap_current(a) || !native_heap_current(b) || heap.used!=50
|| (unsafe{native_heap_address(b) as usize})%64!=0{return 1;}
let memory:*mut u8=native_heap_address(b);let mut i:usize=0;
unsafe{while i<37{if *(memory+i)!=0{return 2;}i+=1;}}
if native_heap_length(a)!=13 || !native_heap_release(a,false) || !native_heap_release(b,false){return 3;}return 42;''')

    def test_adjacent_holes_coalesce_and_exact_full_capacity(self):
        self.program('heap_holes','''let a:NativeHeapHandle=native_heap_allocate(p,128,1,false);
let b:NativeHeapHandle=native_heap_allocate(p,128,1,false);let c:NativeHeapHandle=native_heap_allocate(p,256,1,false);
if native_heap_allocate(p,1,1,false).owner!=null || heap.used!=512{return 1;}
native_heap_release(a,false);native_heap_release(b,false);
let d:NativeHeapHandle=native_heap_allocate(p,256,1,false);if native_heap_address(d)!=data{return 2;}
native_heap_release(c,false);native_heap_release(d,false);
let all:NativeHeapHandle=native_heap_allocate(p,512,1,false);if all.owner==null || heap.used!=512{return 3;}return 42;''')

    def test_fragmented_total_free_does_not_imply_fit(self):
        self.program('heap_fragmentation','''let a:NativeHeapHandle=native_heap_allocate(p,128,1,false);
native_heap_allocate(p,128,1,false);let c:NativeHeapHandle=native_heap_allocate(p,128,1,false);
native_heap_allocate(p,128,1,false);native_heap_release(a,false);native_heap_release(c,false);
if native_heap_allocate(p,200,1,false).owner!=null || heap.used!=256{return 1;}return 42;''')

    def test_resize_moves_preserves_bytes_and_invalidates_old_handle(self):
        self.program('heap_resize','''let a:NativeHeapHandle=native_heap_allocate(p,16,1,false);
let b:NativeHeapHandle=native_heap_allocate(p,16,1,false);let memory:*mut u8=native_heap_address(a);
unsafe{*memory=12;*(memory+15)=34;}
let grown:NativeHeapHandle=native_heap_resize(a,100,16,true);
if grown.owner==null || native_heap_current(a) || native_heap_release(a,false) || !native_heap_current(b){return 1;}
let output:*mut u8=native_heap_address(grown);
unsafe{if *output!=12 || *(output+15)!=34 || *(output+16)!=0 || *(output+99)!=0{return 2;}}
if heap.used!=116 || native_heap_length(grown)!=100{return 3;}
let shrunk:NativeHeapHandle=native_heap_resize(grown,8,1,false);
if shrunk.owner==null || native_heap_current(grown) || heap.used!=24{return 4;}
if unsafe{*native_heap_address(shrunk)}!=12{return 5;}return 42;''')

    def test_overlap_relocation_uses_memmove(self):
        self.program('heap_overlap','''let prefix:NativeHeapHandle=native_heap_allocate(p,8,1,false);
let value:NativeHeapHandle=native_heap_allocate(p,32,1,false);let memory:*mut u8=native_heap_address(value);
let mut i:usize=0;unsafe{while i<32{*(memory+i)=i as u8;i+=1;}}
native_heap_release(prefix,false);let moved:NativeHeapHandle=native_heap_resize(value,40,1,true);
if native_heap_address(moved)!=data{return 1;}i=0;
unsafe{while i<32{if *(data+i)!=i as u8{return 2;}i+=1;}while i<40{if *(data+i)!=0{return 3;}i+=1;}}return 42;''')

    def test_failure_does_not_modify_live_buffer(self):
        self.program('heap_failed_resize','''let a:NativeHeapHandle=native_heap_allocate(p,128,1,false);
let memory:*mut u8=native_heap_address(a);unsafe{*memory=42;}
native_heap_allocate(p,384,1,false);
if native_heap_resize(a,129,1,true).owner!=null || native_heap_resize(a,0,1,false).owner!=null
|| native_heap_resize(a,64,3,false).owner!=null || !native_heap_current(a) || heap.used!=512{return 1;}
if native_heap_length(a)!=128 || unsafe{*memory}!=42{return 2;}return 42;''')

    def test_stale_duplicate_foreign_and_out_of_bounds_handles(self):
        self.program('heap_handles','''let a:NativeHeapHandle=native_heap_allocate(p,512,1,false);
if !native_heap_release(a,true) || native_heap_release(a,false){return 1;}
let b:NativeHeapHandle=native_heap_allocate(p,512,1,false);
if b.generation==a.generation || native_heap_current(a) || native_heap_address(a)!=null{return 2;}
let mut bad:NativeHeapHandle=b;bad.index=32;if native_heap_release(bad,false){return 3;}
bad=b;bad.owner=null;if native_heap_current(bad){return 4;}
let memory:*mut u8=native_heap_address(b);unsafe{if *memory!=0 || *(memory+511)!=0{return 5;}}return 42;''')

    def test_close_reopen_does_not_resurrect_handles(self):
        self.program('heap_reopen','''let a:NativeHeapHandle=native_heap_allocate(p,1,1,false);
if native_heap_close(p){return 1;}native_heap_release(a,false);
if !native_heap_close(p) || native_heap_allocate(p,1,1,false).owner!=null{return 2;}
if !native_heap_open(p,data,512,slots,32){return 3;}
let b:NativeHeapHandle=native_heap_allocate(p,1,1,false);
if b.generation==a.generation || native_heap_current(a){return 4;}return 42;''')

    def test_overflow_invalid_alignment_and_generation_exhaustion(self):
        self.program('heap_overflow','''if native_heap_calloc(p,18446744073709551615,2,1).owner!=null
|| native_heap_allocate(p,0,1,false).owner!=null || native_heap_allocate(p,1,8192,false).owner!=null
|| native_heap_allocate(p,1,0,false).owner!=null || heap.used!=0{return 1;}
let a:NativeHeapHandle=native_heap_allocate(p,1,1,false);heap.sequence=18446744073709551615;
if native_heap_allocate(p,1,1,false).owner!=null || native_heap_resize(a,2,1,false).owner!=null
|| !native_heap_current(a) || heap.used!=1{return 2;}return 42;''')

    def test_slot_exhaustion_is_distinct_from_byte_capacity(self):
        self.program('heap_slots','''let first:NativeHeapHandle=native_heap_allocate(p,1,1,false);
let mut i:u32=1;while i<32 {
if native_heap_allocate(p,1,1,false).owner==null{return 1;}i+=1;}
if heap.used!=32 || native_heap_allocate(p,1,1,false).owner!=null{return 2;}
let grown:NativeHeapHandle=native_heap_resize(first,100,1,true);
if grown.owner==null || native_heap_current(first) || heap.used!=131{return 3;}return 42;''')

    def test_control_and_payload_overlap_rejected(self):
        self.program('heap_metadata','''let mut other:NativeHeap=native_heap_empty();
let q:*mut NativeHeap=unsafe{(&mut other) as *mut NativeHeap};let raw:usize=unsafe{q as usize};
if native_heap_open(q,unsafe{raw as *mut u8},32,slots,32)
|| native_heap_open(p,data,512,slots,32) || other.live{return 1;}return 42;''')

    def test_checked_copy_rejects_stale_and_out_of_bounds_access(self):
        self.program('heap_copy','''let a:NativeHeapHandle=native_heap_allocate(p,8,1,true);
let mut output:[u8;8]=0;let out:*mut u8=unsafe{output as *mut u8};
if !native_heap_write(a,0,"12345678",8) || !native_heap_read(a,0,out,8) || output[7]!=56
|| native_heap_write(a,7,"xx",2) || native_heap_read(a,9,out,0){return 1;}
if !native_heap_write(a,2,native_heap_address(a),6) || !native_heap_read(a,0,out,8)
|| output[2]!=49 || output[7]!=54{return 2;}
native_heap_release(a,false);
if native_heap_write(a,0,"x",1) || native_heap_read(a,0,out,0){return 3;}return 42;''')

    def test_mixed_allocation_resize_release_keeps_live_bytes_disjoint(self):
        self.program('heap_mixed','''let mut records:[u64;48]=0;let raw:*mut u64=unsafe{records as *mut u64};
let raw_address:usize=unsafe{raw as usize};let handles:*mut NativeHeapHandle=unsafe{raw_address as *mut NativeHeapHandle};
let mut step:usize=0;
unsafe{while step<2000 {
let index:usize=(step*13+step/17)%16;let old:NativeHeapHandle=*(handles+index);
let mut next:NativeHeapHandle=native_heap_invalid();let mut kept:usize=0;
if native_heap_current(old) {
let old_length:usize=native_heap_length(old);
if step%3==0 {next=native_heap_resize(old,1+step%83,1,true);kept=old_length;
if next.owner==null{next=old;}else if kept>native_heap_length(next){kept=native_heap_length(next);}}
else{if !native_heap_release(old,false){return 1;}}
}else{next=native_heap_allocate(p,1+step%91,1,true);}
if next.owner!=null {
let memory:*mut u8=native_heap_address(next);let length:usize=native_heap_length(next);let mut j:usize=0;
while j<length {let expected:u8=0;if j<kept {if *(memory+j)!=(index+1) as u8{return 2;}}
else if *(memory+j)!=expected{return 3;}*(memory+j)=(index+1) as u8;j+=1;}
}
*(handles+index)=next;step+=1;
let mut a:usize=0;while a<16 {
let first:NativeHeapHandle=*(handles+a);
if native_heap_current(first) {
let start:usize=native_heap_address(first) as usize;let length:usize=native_heap_length(first);let mut b:usize=a+1;
while b<16 {let second:NativeHeapHandle=*(handles+b);
if native_heap_current(second) {let other:usize=native_heap_address(second) as usize;
if start<other+native_heap_length(second) && other<start+length{return 4;}}b+=1;}
let memory:*mut u8=native_heap_address(first);let mut j:usize=0;
while j<length {if *(memory+j)!=(a+1) as u8{return 5;}j+=1;}
}a+=1;}
}
step=0;while step<16{let value:NativeHeapHandle=*(handles+step);if native_heap_current(value){native_heap_release(value,true);}step+=1;}}
if heap.used!=0 || !native_heap_close(p){return 6;}return 42;''')
