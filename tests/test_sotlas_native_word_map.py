"""Native word maps: collisions, rehash, failure preservation and cursors."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous
ROOT=Path(__file__).resolve().parents[1]

class NativeWordMapTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body):
        sources=[]
        for module in ('managed','heap','word_map'):
            sources.append('\n'.join(line for line in (ROOT/f'runtime/native/{module}.sotlas').read_text().splitlines()
                                     if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'''
pub fn main_entry()->u32{
let mut memory:[u64;1024]=0;let words:*mut u64=unsafe{memory as *mut u64};
let address:usize=unsafe{words as usize};let data:*mut u8=unsafe{address as *mut u8};
let mut metadata:[u64;128]=0;let raw:*mut u64=unsafe{metadata as *mut u64};
let table_address:usize=unsafe{raw as usize};let slots:*mut NativeHeapSlot=unsafe{table_address as *mut NativeHeapSlot};
let mut heap:NativeHeap=native_heap_empty();let h:*mut NativeHeap=unsafe{(&mut heap) as *mut NativeHeap};
if !native_heap_open(h,data,8192,slots,32){return 90;}
let mut map:NativeWordMap=native_word_map_empty();let p:*mut NativeWordMap=unsafe{(&mut map) as *mut NativeWordMap};
if !native_word_map_open(p,h){return 91;}
'''+body+'}'))

    def test_zero_maximum_keys_and_absent_zero_value(self):
        self.program('word_map_keys','''if !native_word_map_get(p,0).valid || native_word_map_get(p,0).found{return 1;}
if !native_word_map_set(p,0,0) || !native_word_map_set(p,18446744073709551615,18446744073709551615){return 2;}
if !native_word_map_get(p,0).found || native_word_map_get(p,0).value!=0 || map.count!=2
|| native_word_map_get(p,18446744073709551615).value!=18446744073709551615{return 3;}return 42;''')

    def test_collision_chain_survives_deletion_and_reuses_tombstones(self):
        self.program('word_map_collisions','''let mut keys:[u64;6]=0;let mut found:usize=0;let mut key:u64=0;
while found<6{if (native_word_map_hash(key)&7)==7{keys[found]=key;found+=1;}key+=1;}
let mut i:usize=0;while i<6{if !native_word_map_set(p,keys[i],(i as u64)+100){return 1;}i+=1;}
if !native_word_map_remove(p,keys[0]).found || !native_word_map_remove(p,keys[2]).found{return 2;}
i=1;while i<6{if i!=2 && native_word_map_get(p,keys[i]).value!=(i as u64)+100{return 3;}i+=1;}
if !native_word_map_set(p,keys[5],999) || map.count!=4 || !native_word_map_set(p,keys[0],42)
|| map.count!=5 || map.deleted!=1 || native_word_map_get(p,keys[5]).value!=999{return 4;}return 42;''')

    def test_growth_iteration_and_shrinking(self):
        self.program('word_map_grow','''let mut key:u64=0;while key<80{if !native_word_map_set(p,key,key*3){return 1;}key+=1;}
let mut cursor:NativeWordCursor=native_word_map_cursor(p);let mut seen:usize=0;let mut sum:u64=0;
while true{let item:NativeWordItem=native_word_map_next(cursor);if !item.valid{return 2;}if item.done{break;}
if item.value!=item.key*3{return 3;}seen+=1;sum+=item.value;cursor=item.next;}
if seen!=80 || sum!=9480{return 4;}
key=0;while key<78{if !native_word_map_remove(p,key).found{return 5;}key+=1;}
let old:NativeWordCursor=native_word_map_cursor(p);
if !native_word_map_shrink(p) || map.capacity!=8 || map.deleted!=0 || native_word_map_next(old).valid
|| native_word_map_get(p,79).value!=237{return 6;}
if !native_word_map_close(p) || heap.used!=0{return 7;}return 42;''')

    def test_full_heap_update_and_failed_growth_preserve_state(self):
        self.program('word_map_oom','''let mut key:u64=0;while key<6{native_word_map_set(p,key,key);key+=1;}
let blocker:NativeHeapHandle=native_heap_allocate(h,8192-heap.used,1,false);if blocker.owner==null{return 1;}
if !native_word_map_set(p,2,42) || native_word_map_get(p,2).value!=42{return 2;}
let old:NativeWordCursor=native_word_map_cursor(p);let handle:NativeHeapHandle=map.storage;
if native_word_map_set(p,6,99) || map.count!=6 || map.storage.generation!=handle.generation
|| !native_word_map_next(old).valid || heap.used!=8192 || native_word_map_get(p,6).found{return 3;}return 42;''')

    def test_checked_counter_overflow_and_cursor_invalidation(self):
        self.program('word_map_add','''native_word_map_add(p,4,18446744073709551615);
let old:NativeWordCursor=native_word_map_cursor(p);
if native_word_map_add(p,4,1) || !native_word_map_next(old).valid || native_word_map_get(p,4).value!=18446744073709551615{return 1;}
if !native_word_map_add(p,5,2) || native_word_map_next(old).valid || native_word_map_get(p,5).value!=2{return 2;}
let fresh:NativeWordCursor=native_word_map_cursor(p);
if native_word_map_remove(p,99).found || !native_word_map_next(fresh).valid{return 3;}return 42;''')

    def test_clear_release_reopen_and_terminal_revision(self):
        self.program('word_map_close','''native_word_map_set(p,1,2);let old:NativeWordCursor=native_word_map_cursor(p);
if !native_word_map_clear(p) || map.count!=0 || native_word_map_next(old).valid || !native_word_map_shrink(p) || heap.used!=0{return 1;}
native_word_map_set(p,3,4);let fresh:NativeWordCursor=native_word_map_cursor(p);
if !native_word_map_close(p) || native_word_map_get(p,3).valid || !native_word_map_open(p,h){return 2;}
native_word_map_set(p,3,4);if native_word_map_next(fresh).valid{return 3;}
map.revision=18446744073709551615;
if native_word_map_set(p,9,9) || native_word_map_remove(p,3).valid || !native_word_map_close(p)
|| heap.used!=0 || native_word_map_open(p,h){return 4;}return 42;''')

    def test_reserve_overflow_and_metadata_overlap(self):
        self.program('word_map_layout','''let old:NativeWordCursor=native_word_map_cursor(p);
if native_word_map_reserve(p,18446744073709551615) || !native_word_map_next(old).valid || heap.used!=0{return 1;}
if !native_word_map_reserve(p,20) || map.capacity!=32 || map.count!=0{return 2;}
let current:NativeWordCursor=native_word_map_cursor(p);
if !native_word_map_reserve(p,20) || !native_word_map_next(current).valid || native_word_map_open(p,h){return 3;}
let payload_address:usize=unsafe{data as usize};
if native_word_map_open(unsafe{payload_address as *mut NativeWordMap},h){return 4;}return 42;''')

    def test_mixed_operations_match_fixed_array_reference(self):
        self.program('word_map_model','''let mut present:[u8;32]=0;let mut expected:[u64;32]=0;let mut step:usize=0;
while step<1200 {
let index:usize=(step*13+step/19)%32;let key:u64=index as u64;
if step%5==0{let removed:NativeWordLookup=native_word_map_remove(p,key);
if !removed.valid || removed.found!=(present[index]==1){return 1;}present[index]=0;}
else if step%3==0{if !native_word_map_set(p,key,(step as u64)*7){return 2;}present[index]=1;expected[index]=(step as u64)*7;}
else{if !native_word_map_add(p,key,1){return 3;}if present[index]==0{present[index]=1;expected[index]=0;}expected[index]+=1;}
let mut i:usize=0;let mut count:usize=0;
while i<32{let value:NativeWordLookup=native_word_map_get(p,i as u64);
if !value.valid || value.found!=(present[i]==1){return 4;}if present[i]==1{count+=1;if value.value!=expected[i]{return 5;}}i+=1;}
if map.count!=count{return 6;}step+=1;
}
if !native_word_map_close(p) || heap.used!=0{return 7;}return 42;''')

    def test_no_empty_buckets_still_terminates_and_reuses_deleted_slots(self):
        self.program('word_map_full_probe','''let mut keys:[u64;8]=0;let mut bucket:u64=0;
while bucket<8{let mut candidate:u64=0;while (native_word_map_hash(candidate)&7)!=bucket{candidate+=1;}
keys[bucket as usize]=candidate;bucket+=1;}
let mut i:usize=0;while i<6{native_word_map_set(p,keys[i],i as u64);i+=1;}
native_word_map_remove(p,keys[0]);native_word_map_set(p,keys[6],6);
native_word_map_remove(p,keys[1]);native_word_map_set(p,keys[7],7);
if map.count!=6 || map.deleted!=2 || native_word_map_get(p,18446744073709551615).found{return 1;}
native_word_map_remove(p,keys[2]);
if !native_word_map_set(p,18446744073709551615,42) || map.count!=6 || map.capacity!=8
|| native_word_map_get(p,18446744073709551615).value!=42{return 2;}return 42;''')

    def test_failed_compaction_preserves_cursor_then_reclaims_tombstones(self):
        self.program('word_map_compact','''let mut i:u64=0;while i<6{native_word_map_set(p,i,i);i+=1;}
i=0;while i<5{native_word_map_remove(p,i);i+=1;}
let blocker:NativeHeapHandle=native_heap_allocate(h,8192-heap.used,1,false);
let old:NativeWordCursor=native_word_map_cursor(p);
if native_word_map_shrink(p) || !native_word_map_next(old).valid || map.deleted!=5 || native_word_map_get(p,5).value!=5{return 1;}
native_heap_release(blocker,false);
if !native_word_map_shrink(p) || map.deleted!=0 || map.count!=1 || map.capacity!=8
|| native_word_map_next(old).valid{return 2;}return 42;''')

    def test_growth_failure_when_only_metadata_slots_are_exhausted(self):
        self.program('word_map_slot_oom','''let mut i:u64=0;while i<6{native_word_map_set(p,i,i);i+=1;}
i=0;while i<31{if native_heap_allocate(h,1,1,false).owner==null{return 1;}i+=1;}
let old:NativeWordCursor=native_word_map_cursor(p);
if heap.used!=223 || native_word_map_set(p,6,6) || map.count!=6 || !native_word_map_next(old).valid{return 2;}
if !native_word_map_close(p) || heap.used!=31{return 3;}return 42;''')

    def test_stale_allocation_is_rejected_before_bucket_access(self):
        self.program('word_map_stale_storage','''native_word_map_set(p,7,42);
let old:NativeWordCursor=native_word_map_cursor(p);native_heap_release(map.storage,false);
let replacement:NativeHeapHandle=native_heap_allocate(h,192,8,true);
if replacement.owner==null || native_word_map_shape(p) || native_word_map_get(p,7).valid
|| native_word_map_next(old).valid || native_word_map_set(p,7,99){return 1;}
if !native_heap_release(replacement,false) || heap.used!=0{return 2;}return 42;''')
