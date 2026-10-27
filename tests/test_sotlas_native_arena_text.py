"""Arena-allocated UTF-8 growth, relocation, epochs and failure atomicity."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT=Path(__file__).resolve().parents[1]


class NativeArenaTextTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body,capacity=2048,helpers=''):
        sources=[]
        for module in ('results','managed','text','unicode','utf8_buffer','arena_text'):
            source=(ROOT/('runtime/native/'+module+'.sotlas')).read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines() if not line.startswith(('module ','import '))))
        self.execute(self.compile(name,'\n'.join(sources)+'\n'+helpers+'''
pub fn main_entry()->u32{let mut storage:[u8;CAP]=[77;CAP];let data:*mut u8=unsafe{storage as *mut u8};
let mut arena:NativeArena=native_arena_init(data,CAP);let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};
let mut text:NativeArenaText=native_arena_text_empty();let t:*mut NativeArenaText=unsafe{(&mut text) as *mut NativeArenaText};
'''.replace('CAP',str(capacity))+body+'}'))

    def test_lazy_initialization_and_growth_beyond_inline_capacity(self):
        self.program('arena_text_large','''if native_arena_text_init(t,a,0).status!=0 || arena.used!=0{return 1;}
let mut i:u32=0;while i<600{if native_arena_text_append(t,"x",1).status!=0{return 2;}i=i+1;}
if text.buffer.length!=600 || text.buffer.capacity!=1024 || arena.used!=1024
|| native_arena_text_check(t).value!=600 || storage[599]!=120 || storage[600]!=77{return 3;}return 42;''')

    def test_last_allocation_grows_in_place(self):
        self.program('arena_text_last','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
let old:*mut u8=text.buffer.data;if native_arena_text_append(t,"q",1).status!=0
|| text.buffer.data!=old || arena.used!=32 || !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijklmnopq",17)){return 1;}return 42;''')

    def test_nonlast_allocation_relocates_without_overwriting_neighbors(self):
        self.program('arena_text_move','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
let old:*mut u8=text.buffer.data;let neighbor:*mut u8=native_arena_alloc(a,8,1);
unsafe{*neighbor=99;}if native_arena_text_append(t,"q",1).status!=0 || text.buffer.data==old
|| unsafe{*neighbor}!=99 || unsafe{*old}!=97 || arena.used!=56
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijklmnopq",17)){return 1;}return 42;''')

    def test_exact_capacity_fallback_for_last_and_relocated_allocations(self):
        self.program('arena_text_exact_last','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
if native_arena_text_append(t,"q",1).status!=0 || text.buffer.capacity!=17 || arena.used!=17{return 1;}return 42;''',17)
        self.program('arena_text_exact_move','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
native_arena_alloc(a,16,1);if native_arena_text_append(t,"q",1).status!=0
|| text.buffer.capacity!=17 || arena.used!=49{return 1;}return 42;''',50)

    def test_exhaustion_preserves_arena_descriptor_and_contents(self):
        self.program('arena_text_exhaustion','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
let old:*mut u8=text.buffer.data;let r:NativeU32Result=native_arena_text_append(t,"more!",5);
if r.status!=10 || arena.used!=16 || text.buffer.capacity!=16 || text.buffer.length!=16
|| text.buffer.data!=old || storage[16]!=77 || !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijklmnop",16)){return 1;}return 42;''',20)

    def test_invalid_utf8_and_free_tail_alias_do_not_allocate(self):
        self.program('arena_text_preflight','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
let invalid:[u8;2]=[226,130];if native_arena_text_append(t,unsafe{invalid as *const u8},2).status!=8
|| native_arena_text_replace(t,0,1,unsafe{invalid as *const u8},2).status!=8
|| native_arena_text_append(t,unsafe{data+16},1).status!=7
|| arena.used!=16 || text.buffer.capacity!=16 || text.buffer.length!=16 || storage[16]!=77{return 1;}return 42;''')

    def test_self_append_across_relocation(self):
        self.program('arena_text_self','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghij",10);
native_arena_alloc(a,8,1);let view:NativeByteSlice=native_arena_text_view(t);
if native_arena_text_append_slice(t,view).status!=0 || text.buffer.length!=20
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijabcdefghij",20)){return 1;}return 42;''')

    def test_replacement_growth_and_alias_rejection(self):
        self.program('arena_text_edit','''native_arena_text_init(t,a,0);native_arena_text_append(t,"a=1;z",5);
if native_arena_text_replace(t,2,3,"12345678901234567890",20).status!=0
|| !native_text_equal(native_arena_text_view(t),native_text_open("a=12345678901234567890;z",24)){return 1;}
let old:usize=arena.used;let p:*mut u8=text.buffer.data;
if native_arena_text_replace(t,0,1,p,2).status!=7 || arena.used!=old || text.buffer.length!=24{return 2;}
if native_arena_text_replace(t,0,2,null,0).status!=0 || text.buffer.length!=22{return 3;}return 42;''')

    def test_unicode_boundaries_and_numeric_append(self):
        self.program('arena_text_unicode','''native_arena_text_init(t,a,0);native_arena_text_append_u32(t,42);
native_arena_text_append_scalar(t,8364);if native_arena_text_check(t).value!=3
|| native_arena_text_truncate(t,3).status!=8 || native_arena_text_replace(t,2,4,"x",1).status!=8
|| native_arena_text_append_scalar(t,55296).status!=8 || text.buffer.length!=5{return 1;}
if native_arena_text_truncate(t,2).status!=0 || !native_text_equal(native_arena_text_view(t),native_text_open("42",2)){return 2;}return 42;''')

    def test_rewind_rejects_stale_owner_before_backing_access(self):
        self.program('arena_text_epoch','''let mark:NativeArenaMark=native_arena_mark(a);native_arena_text_init(t,a,16);
native_arena_text_append(t,"42",2);if !native_arena_rewind(a,mark){return 1;}
let address:u64=18446744073709551615;text.buffer.data=unsafe{address as *mut u8};
if native_arena_text_check(t).status!=7 || native_arena_text_view(t).valid
|| native_arena_text_append(t,"x",1).status!=7 || native_arena_text_close(t,true).status!=7{return 2;}
if !native_arena_text_detach(t) || native_arena_text_init(t,a,0).status!=0
|| native_arena_text_append_u32(t,42).status!=0{return 3;}return 42;''')

    def test_init_and_reserve_failure_leave_cursors_unchanged(self):
        self.program('arena_text_init_fail','''if native_arena_text_init(t,a,100).status!=10 || arena.used!=0 || text.arena!=null{return 1;}
if native_arena_text_init(t,a,0).status!=0 || native_arena_text_init(t,a,0).status!=7
|| native_arena_text_reserve(t,4294967296).status!=7 || arena.used!=0{return 2;}return 42;''',32)

    def test_invalid_headers_and_forged_ranges_are_rejected(self):
        self.program('arena_text_invalid','''if native_arena_text_check(null).status!=7 || native_arena_text_init(t,null,1).status!=7{return 1;}
native_arena_text_init(t,a,16);text.buffer.capacity=2049;
if native_arena_text_check(t).status!=7 || native_arena_text_reset(t,true).status!=7 || storage[0]!=77{return 2;}
native_arena_text_detach(t);arena.used=2049;if native_arena_text_init(t,a,0).status!=7{return 3;}return 42;''')

    def test_close_wipes_used_bytes_without_rewinding_other_owners(self):
        self.program('arena_text_close','''native_arena_text_init(t,a,16);native_arena_text_append_u32(t,42);
let used:usize=arena.used;let epoch:u64=arena.epoch;
if native_arena_text_close(t,true).status!=0 || text.arena!=null || arena.used!=used || arena.epoch!=epoch
|| storage[0]!=0 || storage[1]!=0 || storage[2]!=77 || native_arena_text_check(t).status!=7{return 1;}return 42;''')

    def test_deferred_close_on_success_and_propagated_error(self):
        self.program('arena_text_defer','''native_arena_text_init(t,a,0);let good:NativeU32Result=work(t,false);
if good.status!=0 || good.value!=2 || text.arena!=null || storage[0]!=0{return 1;}
native_arena_text_init(t,a,0);let bad:NativeU32Result=work(t,true);
if bad.status!=7 || text.arena!=null{return 2;}return 42;''',2048,
'''fn work(t:*mut NativeArenaText,fail:bool)->NativeU32Result{
defer native_arena_text_close(t,true);native_arena_text_append_u32(t,42)?;
if fail{native_arena_text_replace(t,100,101,null,0)?;}return native_arena_text_check(t);}''')

    def test_replacement_exhaustion_preserves_cursor_and_text(self):
        self.program('arena_text_replace_oom','''native_arena_text_init(t,a,16);native_arena_text_append(t,"abcdefghijklmnop",16);
let result:NativeU32Result=native_arena_text_replace(t,0,1,"123456",6);
if result.status!=10 || arena.used!=16 || text.buffer.capacity!=16 || text.buffer.length!=16
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijklmnop",16)){return 1;}return 42;''',20)

    def test_reset_retains_capacity_and_can_recover_malformed_content(self):
        self.program('arena_text_reset','''native_arena_text_init(t,a,16);native_arena_text_append(t,"42",2);
let used:usize=arena.used;let pointer:*mut u8=text.buffer.data;unsafe{*pointer=255;}
if native_arena_text_check(t).status!=8 || native_arena_text_reset(t,true).status!=0
|| text.buffer.capacity!=16 || text.buffer.length!=0 || arena.used!=used
|| unsafe{*pointer}!=0 || native_arena_text_append_u32(t,42).status!=0{return 1;}return 42;''')



    def test_scalar_positions_and_slices_across_all_utf8_widths(self):
        self.program('arena_scalar_positions','''native_arena_text_init(t,a,0);
native_arena_text_append_scalar(t,65);native_arena_text_append_scalar(t,162);
native_arena_text_append_scalar(t,8364);native_arena_text_append_scalar(t,128512);
native_arena_text_append_scalar(t,90);
if native_arena_text_check(t).value!=5 || text.buffer.length!=11
|| native_arena_text_scalar_offset(t,0).value!=0
|| native_arena_text_scalar_offset(t,1).value!=1
|| native_arena_text_scalar_offset(t,2).value!=3
|| native_arena_text_scalar_offset(t,3).value!=6
|| native_arena_text_scalar_offset(t,4).value!=10
|| native_arena_text_scalar_offset(t,5).value!=11
|| native_arena_text_scalar_at(t,3).value!=128512
|| native_arena_text_scalar_at(t,4).value!=90{return 1;}
let part:NativeByteSlice=native_arena_text_slice_scalars(t,1,4);
if !part.valid || part.length!=9
|| !native_text_equal(part,native_text_sub(native_arena_text_view(t),1,9))
|| native_arena_text_scalar_offset(t,6).status!=7
|| native_arena_text_scalar_at(t,5).status!=7
|| native_arena_text_slice_scalars(t,3,2).valid
|| native_arena_text_slice_scalars(t,0,6).valid{return 2;}return 42;''')

    def test_insert_replace_remove_and_pop_use_scalar_indices(self):
        self.program('arena_scalar_edits','''native_arena_text_init(t,a,0);
native_arena_text_append(t,"AC",2);
if native_arena_text_insert_scalar(t,1,8364).status!=0
|| native_arena_text_replace_scalars(t,2,3,"B",1).status!=0
|| native_arena_text_check(t).value!=3 || text.buffer.length!=5{return 1;}
let removed:NativeU32Result=native_arena_text_remove_scalar(t,1);
if removed.status!=0 || removed.value!=8364
|| !native_text_equal(native_arena_text_view(t),native_text_open("AB",2)){return 2;}
native_arena_text_append_scalar(t,128512);
let popped:NativeU32Result=native_arena_text_pop_scalar(t);
if popped.status!=0 || popped.value!=128512
|| !native_text_equal(native_arena_text_view(t),native_text_open("AB",2))
|| native_arena_text_scalar_at(t,0).value!=65{return 3;}return 42;''')

    def test_self_append_after_relocation_and_scalar_range_copy(self):
        self.program('arena_scalar_alias','''native_arena_text_init(t,a,16);
native_arena_text_append(t,"abcdefghij",10);
let old:*mut u8=text.buffer.data;let neighbor:*mut u8=native_arena_alloc(a,8,1);
unsafe{*neighbor=99;}
if native_arena_text_append_text(t,t).status!=0 || text.buffer.data==old
|| unsafe{*neighbor}!=99 || unsafe{*old}!=97 || text.buffer.length!=20
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijabcdefghij",20)){return 1;}
if native_arena_text_append_scalars(t,t,0,2).status!=0
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijabcdefghijab",22)){return 2;}return 42;''')

    def test_append_from_another_live_arena_text(self):
        self.program('arena_scalar_other','''native_arena_text_init(t,a,0);
native_arena_text_append(t,"prefix",6);
let mut other:NativeArenaText=native_arena_text_empty();
let p:*mut NativeArenaText=unsafe{(&mut other) as *mut NativeArenaText};
native_arena_text_init(p,a,0);native_arena_text_append_scalar(p,8364);
native_arena_text_append_scalar(p,128512);
if native_arena_text_append_scalars(t,p,1,2).status!=0
|| native_arena_text_append_text(t,p).status!=0
|| native_arena_text_check(t).value!=9
|| text.buffer.length!=17
|| native_arena_text_scalar_at(t,6).value!=128512
|| native_arena_text_scalar_at(t,7).value!=8364{return 1;}return 42;''')

    def test_invalid_index_and_scalar_are_atomic(self):
        self.program('arena_scalar_invalid','''native_arena_text_init(t,a,16);
native_arena_text_append(t,"abcd",4);let used:usize=arena.used;
let old:*mut u8=text.buffer.data;
if native_arena_text_insert_scalar(t,2,55296).status!=8
|| native_arena_text_insert_scalar(t,9,8364).status!=7
|| native_arena_text_replace_scalars(t,3,2,"x",1).status!=7
|| native_arena_text_replace_scalars(t,0,5,"x",1).status!=7
|| native_arena_text_remove_scalar(t,4).status!=7
|| arena.used!=used || text.buffer.data!=old || text.buffer.length!=4
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcd",4)){return 1;}
native_arena_text_reset(t,false);
if native_arena_text_pop_scalar(t).status!=7 || arena.used!=used{return 2;}return 42;''')

    def test_scalar_insert_out_of_memory_preserves_arena_and_bytes(self):
        # Sixteen bytes plus a three-byte scalar need 19 bytes, so use only 18.
        self.program('arena_scalar_oom','''native_arena_text_init(t,a,16);
native_arena_text_append(t,"abcdefghijklmnop",16);
let old:*mut u8=text.buffer.data;let used:usize=arena.used;
if native_arena_text_insert_scalar(t,8,8364).status!=10
|| native_arena_text_replace_scalars(t,0,1,"123456",6).status!=10
|| arena.used!=used || text.buffer.data!=old || text.buffer.capacity!=16
|| text.buffer.length!=16 || storage[16]!=77
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghijklmnop",16)){return 1;}return 42;''',18)

    def test_scalar_insert_succeeds_at_exact_byte_capacity(self):
        self.program('arena_scalar_exact','''native_arena_text_init(t,a,16);
native_arena_text_append(t,"abcdefghijklmnop",16);
if native_arena_text_insert_scalar(t,8,8364).status!=0 || arena.used!=19
|| text.buffer.capacity!=19 || text.buffer.length!=19
|| native_arena_text_check(t).value!=17 || native_arena_text_scalar_at(t,8).value!=8364
|| native_arena_text_scalar_at(t,9).value!=105{return 1;}return 42;''',19)

    def test_stale_epoch_and_corrupt_utf8_fail_before_scalar_read(self):
        self.program('arena_scalar_stale','''let mark:NativeArenaMark=native_arena_mark(a);
native_arena_text_init(t,a,16);native_arena_text_append(t,"42",2);
if !native_arena_rewind(a,mark){return 1;}
let address:u64=18446744073709551615;
text.buffer.data=unsafe{address as *mut u8};
if native_arena_text_scalar_offset(t,0).status!=7
|| native_arena_text_scalar_at(t,0).status!=7
|| native_arena_text_slice_scalars(t,0,0).valid
|| native_arena_text_pop_scalar(t).status!=7{return 2;}
native_arena_text_detach(t);native_arena_text_init(t,a,0);
native_arena_text_append(t,"abc",3);
unsafe{*text.buffer.data=255;}
if native_arena_text_scalar_offset(t,1).status!=8
|| native_arena_text_scalar_at(t,0).status!=8
|| native_arena_text_append_text(t,t).status!=7
|| native_arena_text_slice_scalars(t,0,1).valid{return 3;}return 42;''')

    def test_utf8_replacement_alias_and_invalid_source_fail_before_growth(self):
        self.program('arena_scalar_source','''native_arena_text_init(t,a,16);
native_arena_text_append(t,"abcdefghij",10);
let used:usize=arena.used;let source:*mut u8=text.buffer.data;
let broken:[u8;2]=[226,130];
if native_arena_text_replace_scalars(t,2,3,source,3).status!=7
|| native_arena_text_replace_scalars(t,2,3,unsafe{broken as *const u8},2).status!=8
|| native_arena_text_append_scalars(t,t,9,11).status!=7
|| arena.used!=used || text.buffer.length!=10
|| !native_text_equal(native_arena_text_view(t),native_text_open("abcdefghij",10)){return 1;}return 42;''')

if __name__=='__main__':unittest.main()
