"""Reusable allocation identities and persistent UTF-8, executed as native code."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT = Path(__file__).resolve().parents[1]


class NativePoolTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, body, helpers=''):
        sources = []
        for module in ('results', 'managed', 'text', 'unicode', 'utf8_buffer', 'pool', 'pool_text'):
            source = (ROOT / f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines()
                                     if not line.startswith(('module ', 'import '))))
        self.execute(self.compile(name, '\n'.join(sources) + '\n' + helpers + '''
pub fn main_entry()->u32{
let mut bytes:[u8;128]=[77;128];let data:*mut u8=unsafe{bytes as *mut u8};
let mut slots:[u64;16]=0;
let words:*mut u64=unsafe{slots as *mut u64};
let metadata_address:usize=unsafe{words as usize};
let metadata:*mut NativePoolSlot=unsafe{metadata_address as *mut NativePoolSlot};
let mut pool:NativePool=native_pool_empty();let p:*mut NativePool=unsafe{(&mut pool) as *mut NativePool};
if !native_pool_open(p,data,128,metadata,4,32){return 90;}
''' + body + '}'))

    def test_individual_release_reuse_and_generation(self):
        self.program('pool_reuse', '''let a:NativePoolHandle=native_pool_allocate(p,32);
let b:NativePoolHandle=native_pool_allocate(p,2);native_pool_write(b,0,"42",2);
if !native_pool_release(a,true) || native_pool_release(a,false){return 1;}
let c:NativePoolHandle=native_pool_allocate(p,32);
if c.index!=a.index || c.generation==a.generation || native_pool_current(a) || !native_pool_current(b){return 2;}
let mut out:[u8;2]=0;if !native_pool_read(native_pool_view(b,0,2),unsafe{out as *mut u8},2)
|| out[0]!=52 || out[1]!=50{return 3;}return 42;''')

    def test_full_pool_failure_and_reuse_zeroing(self):
        self.program('pool_full', '''let a:NativePoolHandle=native_pool_allocate(p,32);
native_pool_allocate(p,32);native_pool_allocate(p,32);native_pool_allocate(p,32);
native_pool_write(a,0,"secret",6);
if native_pool_current(native_pool_allocate(p,1)) || native_pool_current(native_pool_allocate(p,33)){return 1;}
native_pool_release(a,false);let b:NativePoolHandle=native_pool_allocate(p,32);
let mut out:[u8;32]=[77;32];if !native_pool_read(native_pool_view(b,0,32),unsafe{out as *mut u8},32){return 2;}
let mut i:usize=0;while i<32{if out[i]!=0{return 3;}i=i+1;}return 42;''')

    def test_checked_views_track_mutations_and_failed_writes(self):
        self.program('pool_views', '''let a:NativePoolHandle=native_pool_allocate(p,8);
let v:NativePoolView=native_pool_view(a,0,8);
if native_pool_write(a,8,"x",1) || !native_pool_view_current(v){return 1;}
if !native_pool_write(a,0,"abcd",4) || native_pool_view_current(v){return 2;}
let w:NativePoolView=native_pool_view(a,0,4);native_pool_resize(a,4,true);
if native_pool_view_current(w) || native_pool_view(a,0,5).valid{return 3;}return 42;''')

    def test_overlapping_write_and_read_cannot_mutate_pool_silently(self):
        self.program('pool_overlap', '''let a:NativePoolHandle=native_pool_allocate(p,8);native_pool_write(a,0,"abcdefgh",8);
if !native_pool_write(a,2,data,6){return 1;}
let v:NativePoolView=native_pool_view(a,0,8);let mut out:[u8;8]=0;
let control:usize=unsafe{p as usize};
if native_pool_read(v,data,128) || native_pool_read(v,unsafe{metadata_address as *mut u8},128)
|| native_pool_read(v,unsafe{control as *mut u8},128) || !native_pool_read(v,unsafe{out as *mut u8},8){return 2;}
if out[0]!=97 || out[2]!=97 || out[7]!=102 || !native_pool_view_current(v){return 3;}return 42;''')

    def test_clone_has_independent_lifetime(self):
        self.program('pool_clone', '''let a:NativePoolHandle=native_pool_text_create(p,"hello",5);
let b:NativePoolHandle=native_pool_clone(a);if !native_pool_current(b) || b.index==a.index{return 1;}
native_pool_release(a,true);if native_pool_text_append(b,"!",1).status!=0{return 2;}
let mut out:[u8;6]=0;if !native_pool_read(native_pool_text_view(b),unsafe{out as *mut u8},6)
|| out[0]!=104 || out[5]!=33{return 3;}return 42;''')

    def test_reset_close_reopen_and_stale_checks(self):
        self.program('pool_epoch', '''let a:NativePoolHandle=native_pool_allocate(p,4);
let v:NativePoolView=native_pool_view(a,0,4);if native_pool_close(p){return 1;}
if !native_pool_reset(p,true) || native_pool_current(a) || native_pool_view_current(v){return 2;}
let b:NativePoolHandle=native_pool_allocate(p,4);native_pool_release(b,false);
if !native_pool_close(p) || !native_pool_open(p,data,128,metadata,4,32) || native_pool_current(b){return 3;}
let c:NativePoolHandle=native_pool_allocate(p,4);if !native_pool_current(c) || native_pool_current(a){return 4;}
native_pool_reset(p,false);pool.slots=null;pool.data=null;
if native_pool_current(c) || native_pool_view_current(v){return 5;}return 42;''')

    def test_layout_bounds_and_failed_open_preserve_storage(self):
        self.program('pool_layout', '''native_pool_close(p);let epoch:u64=pool.epoch;
let base:usize=unsafe{data as usize};let control:usize=unsafe{p as usize};let odd:usize=base+1;
if native_pool_open(p,data,128,metadata,0,32) || native_pool_open(p,data,127,metadata,4,32)
|| native_pool_open(p,data,128,unsafe{base as *mut NativePoolSlot},4,32)
|| native_pool_open(p,unsafe{control as *mut u8},128,metadata,4,32)
|| native_pool_open(p,data,128,unsafe{odd as *mut NativePoolSlot},1,1)
|| native_pool_open(p,data,128,metadata,4,4294967296) || pool.live || pool.epoch!=epoch || bytes[0]!=77{return 1;}
if native_pool_range(18446744073709551615,1) || native_pool_range(0,1)
|| !native_pool_overlap(18446744073709551615,1,1,1){return 2;}return 42;''')

    def test_generation_and_revision_never_wrap(self):
        self.program('pool_wrap', '''slots[0]=18446744073709551615;
let a:NativePoolHandle=native_pool_allocate(p,4);if a.index!=1{return 1;}
slots[5]=18446744073709551615;let v:NativePoolView=native_pool_view(a,0,4);
if native_pool_write(a,0,"x",1) || native_pool_resize(a,5,false)
|| native_pool_text_append(a,"x",1).status==0 || !native_pool_view_current(v){return 2;}
pool.epoch=18446744073709551615;if native_pool_reset(p,true){return 3;}
pool.epoch=a.epoch;if !native_pool_current(a){return 4;}return 42;''')

    def test_resize_zeroes_growth_and_optional_truncated_bytes(self):
        self.program('pool_resize', '''let a:NativePoolHandle=native_pool_allocate(p,8);native_pool_write(a,0,"abcdefgh",8);
if !native_pool_resize(a,2,true) || bytes[2]!=0 || bytes[7]!=0 || !native_pool_resize(a,8,false){return 1;}
if bytes[0]!=97 || bytes[1]!=98 || bytes[2]!=0 || native_pool_resize(a,33,false){return 2;}return 42;''')

    def test_utf8_edits_boundaries_and_view_invalidation(self):
        self.program('pool_utf8', '''let a:NativePoolHandle=native_pool_text_create(p,"a€z",5);
if native_pool_text_check(a).value!=3{return 1;}let v:NativePoolView=native_pool_text_view(a);
if native_pool_text_replace(a,2,4,"x",1).status!=8 || !native_pool_view_current(v){return 2;}
if native_pool_text_replace(a,1,4,"xy",2).status!=0 || native_pool_view_current(v)
|| native_pool_text_check(a).value!=4{return 3;}
if native_pool_text_truncate(a,3).status!=0 || native_pool_length(a)!=3{return 4;}
let mut out:[u8;3]=0;if !native_pool_read(native_pool_text_view(a),unsafe{out as *mut u8},3)
|| out[0]!=97 || out[1]!=120 || out[2]!=121{return 5;}return 42;''')

    def test_text_failures_are_atomic_and_invalid_bytes_rejected(self):
        self.program('pool_utf8_failure', '''let a:NativePoolHandle=native_pool_text_create(p,"hello",5);
let v:NativePoolView=native_pool_text_view(a);let bad:[u8;2]=[226,130];
if native_pool_text_append(a,unsafe{bad as *const u8},2).status!=8
|| native_pool_text_append(a,"abcdefghijklmnopqrstuvwxyz012345",32).status!=7
|| native_pool_text_replace(a,0,1,data,1).status!=7
|| native_pool_current(native_pool_text_create(p,data,5)) || !native_pool_view_current(v){return 1;}
native_pool_write(a,0,unsafe{bad as *const u8},2);
if native_pool_text_check(a).status!=8 || native_pool_text_view(a).valid{return 2;}return 42;''')

    def test_text_self_append_and_release_invalidate_views(self):
        self.program('pool_utf8_alias', '''let a:NativePoolHandle=native_pool_text_create(p,"abc",3);
if native_pool_text_append(a,data,3).status!=0 || native_pool_length(a)!=6{return 1;}
let v:NativePoolView=native_pool_text_view(a);native_pool_release(a,true);
if native_pool_view_current(v) || native_pool_text_check(a).status==0 || bytes[0]!=0{return 2;}return 42;''')

    def test_word_backing_capacity_and_open_validation(self):
        self.program('pool_words', '''native_pool_close(p);
if native_pool_open_words(p,data,128,words,15,4,32)
|| native_pool_open_words(p,data,128,words,2305843009213693952,4,32)
|| native_pool_open_words(p,data,128,null,16,4,32) || pool.live{return 1;}
if !native_pool_open_words(p,data,128,words,16,4,32){return 2;}return 42;''')

    def test_empty_allocation_noop_and_failed_clone_keep_views(self):
        self.program('pool_empty', '''let a:NativePoolHandle=native_pool_allocate(p,0);
let v:NativePoolView=native_pool_view(a,0,0);
if !native_pool_current(a) || !native_pool_read(v,null,0) || !native_pool_write(a,0,null,0)
|| !native_pool_resize(a,0,false) || !native_pool_view_current(v){return 1;}
native_pool_allocate(p,1);native_pool_allocate(p,1);native_pool_allocate(p,1);
if native_pool_current(native_pool_clone(a)) || !native_pool_view_current(v){return 2;}return 42;''')

    def test_counter_terminal_generation_and_reset_recovery(self):
        self.program('pool_terminal', '''slots[0]=18446744073709551614;
let a:NativePoolHandle=native_pool_allocate(p,1);if a.generation!=18446744073709551615 || !native_pool_current(a){return 1;}
native_pool_release(a,false);let b:NativePoolHandle=native_pool_allocate(p,1);if b.index!=1{return 2;}
native_pool_reset(p,false);let c:NativePoolHandle=native_pool_allocate(p,1);
if c.index!=0 || native_pool_current(a) || native_pool_current(b){return 3;}return 42;''')

    def test_metadata_sources_and_wrapping_ranges_fail_without_mutation(self):
        self.program('pool_source', '''let a:NativePoolHandle=native_pool_allocate(p,8);let v:NativePoolView=native_pool_view(a,0,8);
let control:usize=unsafe{p as usize};let top:usize=18446744073709551615;
if native_pool_write(a,0,unsafe{metadata_address as *const u8},1)
|| native_pool_write(a,0,unsafe{control as *const u8},1)
|| native_pool_write(a,0,unsafe{top as *const u8},2)
|| native_pool_read(v,unsafe{top as *mut u8},8) || !native_pool_view_current(v){return 1;}return 42;''')

    def test_unicode_scalar_reads_slices_replacement_and_numeric_append(self):
        self.program('pool_scalars', '''let a:NativePoolHandle=native_pool_text_create(p,"a€😀z",9);
if native_pool_text_scalar_at(a,1).value!=8364 || native_pool_text_scalar_at(a,2).value!=128512
|| native_pool_text_scalar_offset(a,4).value!=9 || native_pool_text_scalar_at(a,4).status!=7{return 1;}
let v:NativePoolView=native_pool_text_slice_scalars(a,1,2);let mut out:[u8;7]=0;
if !native_pool_read(v,unsafe{out as *mut u8},7) || out[0]!=226 || out[3]!=240{return 2;}
if native_pool_text_replace_scalars(a,1,2,"=",1).status!=0 || native_pool_view_current(v)
|| native_pool_text_append_u32(a,4294967295).status!=0 || native_pool_length(a)!=13{return 3;}return 42;''')

    def test_scalar_range_failures_preserve_text_and_views(self):
        self.program('pool_scalar_bounds', '''let a:NativePoolHandle=native_pool_text_create(p,"a€",4);
let v:NativePoolView=native_pool_text_view(a);
if native_pool_text_slice_scalars(a,1,18446744073709551615).valid
|| native_pool_text_replace_scalars(a,1,18446744073709551615,"x",1).status!=7
|| native_pool_text_replace_scalars(a,3,0,"x",1).status!=7 || !native_pool_view_current(v){return 1;}return 42;''')

    def test_zeroing_and_layout_match_native_field_offsets(self):
        self.program('pool_layout_words', '''let a:NativePoolHandle=native_pool_allocate(p,3);
if slots[0]!=a.generation || slots[1]!=1 || slots[2]!=3 || slots[3]!=1{return 1;}
native_pool_write(a,0,"xyz",3);if slots[1]!=2{return 2;}
let b:NativePoolHandle=native_pool_allocate(p,1);if slots[4]!=b.generation || slots[6]!=1 || slots[7]!=1{return 3;}
native_pool_release(a,true);if slots[3]!=0 || slots[2]!=0 || bytes[0]!=0 || bytes[31]!=0{return 4;}return 42;''')

    def test_invalid_and_closed_handles_are_rejected(self):
        self.program('pool_invalid', '''let bad:NativePoolHandle=native_pool_invalid();
if native_pool_current(bad) || native_pool_release(bad,false) || native_pool_write(bad,0,null,0)
|| native_pool_resize(bad,0,false) || native_pool_view(bad,0,0).valid
|| native_pool_text_check(bad).status==0{return 1;}
native_pool_close(p);if native_pool_shape(p) || native_pool_current(native_pool_allocate(p,1)){return 2;}return 42;''')

    def test_repeated_reuse_keeps_neighbor_and_its_view_alive(self):
        self.program('pool_churn', '''let stable:NativePoolHandle=native_pool_text_create(p,"persistent",10);
let view:NativePoolView=native_pool_text_view(stable);let mut i:u32=0;
while i<1000{let value:NativePoolHandle=native_pool_text_create(p,"temporary",9);
if !native_pool_current(value) || !native_pool_release(value,false){return 1;}i=i+1;}
let mut out:[u8;10]=0;if !native_pool_read(view,unsafe{out as *mut u8},10)
|| out[0]!=112 || out[9]!=116{return 2;}return 42;''')

    def test_deferred_release_on_success_and_propagated_error(self):
        self.program('pool_defer', '''let ok:NativeU32Result=pool_task(p,false);
let failed:NativeU32Result=pool_task(p,true);
if ok.status!=0 || ok.value!=42 || failed.status!=9 || failed.error.offset!=17
|| !native_pool_close(p){return 1;}return 42;''', '''
fn pool_failure(fail:bool)->NativeU32Result{if fail{return native_u32_error(9,17);}return native_u32_ok(42);}
fn pool_task(pool:*mut NativePool,fail:bool)->NativeU32Result{
let text:NativePoolHandle=native_pool_text_create(pool,"scope",5);
defer{native_pool_release(text,true);}
let answer:u32=pool_failure(fail)?;return native_u32_ok(answer);
}
''')

    def test_text_failed_truncate_and_numeric_append_are_atomic(self):
        self.program('pool_text_atomic', '''let a:NativePoolHandle=native_pool_text_create(p,"€abcdefghijklmnopqrstuvwxyz",29);
let v:NativePoolView=native_pool_text_view(a);
if native_pool_text_truncate(a,1).status!=8 || native_pool_text_truncate(a,30).status!=7
|| native_pool_text_append_u32(a,4294967295).status!=7 || !native_pool_view_current(v)
|| native_pool_length(a)!=29 || native_pool_text_check(a).value!=27{return 1;}return 42;''')

    def test_two_and_four_byte_scalar_edits_and_empty_slice(self):
        self.program('pool_scalar_widths', '''let a:NativePoolHandle=native_pool_text_create(p,"¢😀",6);
if native_pool_text_scalar_offset(a,1).value!=2 || native_pool_text_scalar_offset(a,2).value!=6
|| native_pool_text_scalar_at(a,0).value!=162 || !native_pool_text_slice_scalars(a,2,0).valid{return 1;}
if native_pool_text_replace_scalars(a,0,1,"€",3).status!=0 || native_pool_length(a)!=7
|| native_pool_text_scalar_at(a,0).value!=8364 || native_pool_text_scalar_at(a,1).value!=128512{return 2;}return 42;''')



    def test_scalar_insert_remove_and_pop_persisted_text(self):
        self.program('pool_text_scalar_edit', '''let a:NativePoolHandle=native_pool_text_create(p,"AC",2);
if native_pool_text_insert_scalar(a,1,8364).status!=0
|| native_pool_text_replace_scalars(a,2,1,"B",1).status!=0
|| native_pool_text_check(a).value!=3{return 1;}
let removed:NativeU32Result=native_pool_text_remove_scalar(a,1);
if removed.status!=0 || removed.value!=8364 || native_pool_length(a)!=2{return 2;}
native_pool_text_append_scalar(a,128512);
let popped:NativeU32Result=native_pool_text_pop_scalar(a);
if popped.status!=0 || popped.value!=128512 || native_pool_text_check(a).value!=2
|| native_pool_text_scalar_at(a,1).value!=66{return 3;}return 42;''')

    def test_unicode_scalar_widths_and_insert_at_end(self):
        self.program('pool_text_scalar_width', '''let a:NativePoolHandle=native_pool_text_create(p,"¢😀",6);
if native_pool_text_insert_scalar(a,1,8364).status!=0 || native_pool_length(a)!=9
|| native_pool_text_scalar_offset(a,2).value!=5{return 1;}
if native_pool_text_insert_scalar(a,3,90).status!=0 || native_pool_text_check(a).value!=4
|| native_pool_text_scalar_at(a,3).value!=90{return 2;}
if native_pool_text_remove_scalar(a,0).value!=162 || native_pool_text_scalar_at(a,0).value!=8364{return 3;}
return 42;''')

    def test_self_append_and_self_scalar_ranges(self):
        self.program('pool_text_self_compose', '''let a:NativePoolHandle=native_pool_text_create(p,"abc",3);
let v:NativePoolView=native_pool_text_view(a);
if native_pool_text_append_from(a,a).status!=0 || native_pool_length(a)!=6
|| native_pool_view_current(v){return 1;}
if native_pool_text_append_scalars(a,a,1,3).status!=0 || native_pool_length(a)!=9{return 2;}
let mut out:[u8;9]=0;
if !native_pool_read(native_pool_text_view(a),unsafe{out as *mut u8},9)
|| out[0]!=97 || out[3]!=97 || out[6]!=98 || out[8]!=97{return 3;}
return 42;''')

    def test_cross_slot_append_replace_and_source_views(self):
        self.program('pool_text_cross_slot', '''let a:NativePoolHandle=native_pool_text_create(p,"a=42",4);
let b:NativePoolHandle=native_pool_text_create(p,"€x",4);
let v:NativePoolView=native_pool_text_view(b);
if native_pool_text_append_scalars(a,b,0,1).status!=0
|| native_pool_text_replace_from(a,2,2,b,1,1).status!=0
|| native_pool_text_check(a).value!=4 || native_pool_length(a)!=6
|| !native_pool_view_current(v) || native_pool_text_scalar_at(a,3).value!=8364{return 1;}
return 42;''')

    def test_clone_scalar_range_independent_and_reusable(self):
        self.program('pool_text_clone_part', '''let a:NativePoolHandle=native_pool_text_create(p,"a€😀z",9);
let v:NativePoolView=native_pool_text_view(a);
let b:NativePoolHandle=native_pool_text_clone_scalars(a,1,2);
if !native_pool_current(b) || b.index==a.index || native_pool_text_check(b).value!=2
|| !native_pool_view_current(v) || native_pool_length(b)!=7{return 1;}
native_pool_release(a,true);
if native_pool_current(a) || native_pool_text_append_scalar(b,90).status!=0
|| native_pool_text_scalar_at(b,2).value!=90{return 2;}
let c:NativePoolHandle=native_pool_text_create(p,"new",3);
if c.index!=a.index || native_pool_current(a) || !native_pool_current(b){return 3;}return 42;''')

    def test_clone_out_of_slots_preserves_source_revision(self):
        self.program('pool_text_clone_full', '''let a:NativePoolHandle=native_pool_text_create(p,"abc",3);
let old:NativePoolView=native_pool_text_view(a);
native_pool_allocate(p,1);native_pool_allocate(p,1);native_pool_allocate(p,1);
let clone:NativePoolHandle=native_pool_text_clone_scalars(a,0,2);
if native_pool_current(clone) || !native_pool_view_current(old)
|| native_pool_length(a)!=3 || native_pool_text_scalar_at(a,2).value!=99{return 1;}
return 42;''')

    def test_reset_wipes_content_and_invalidates_checked_views(self):
        self.program('pool_text_reset', '''let a:NativePoolHandle=native_pool_text_create(p,"secret",6);
let before:NativePoolView=native_pool_text_view(a);
if native_pool_text_reset(a,true).status!=0 || native_pool_view_current(before)
|| native_pool_length(a)!=0 || bytes[0]!=0 || bytes[5]!=0{return 1;}
if native_pool_text_pop_scalar(a).status!=7 || native_pool_text_append_u32(a,42).status!=0
|| native_pool_text_scalar_at(a,1).value!=50{return 2;}return 42;''')

    def test_recover_malformed_utf8_with_explicit_reset(self):
        self.program('pool_text_recover', '''let a:NativePoolHandle=native_pool_text_create(p,"abc",3);
let corrupt:[u8;1]=[255];native_pool_write(a,0,unsafe{corrupt as *const u8},1);
if native_pool_text_check(a).status!=8 || native_pool_text_append_from(a,a).status!=8{return 1;}
if native_pool_text_reset(a,true).status!=0 || native_pool_text_append_scalar(a,8364).status!=0
|| native_pool_text_check(a).value!=1{return 2;}return 42;''')

    def test_split_views_and_checked_numeric_field(self):
        self.program('pool_text_split', '''let a:NativePoolHandle=native_pool_text_create(p,"answer=42",9);
let parts:NativePoolTextSplit=native_pool_text_split_once(a,"=",1);
if !parts.found || !native_pool_view_current(parts.before)
|| !native_pool_view_current(parts.after) || parts.before.length!=6
|| native_pool_text_parse_u32(parts.after).value!=42{return 1;}
native_pool_text_append(a,"!",1);
if native_pool_view_current(parts.before) || native_pool_view_current(parts.after)
|| native_pool_text_parse_u32(parts.after).status!=7{return 2;}return 42;''')

    def test_split_unicode_separator_and_empty_tail(self):
        self.program('pool_text_split_utf8', '''let a:NativePoolHandle=native_pool_text_create(p,"a€42",6);
let parts:NativePoolTextSplit=native_pool_text_split_once(a,"€",3);
if !parts.found || parts.before.length!=1 || parts.after.length!=2
|| native_pool_text_parse_u32(parts.after).value!=42{return 1;}
let end:NativePoolTextSplit=native_pool_text_split_once(a,"42",2);
if !end.found || end.after.length!=0 || !native_pool_view_current(end.after){return 2;}return 42;''')

    def test_split_rejects_empty_malformed_and_metadata_separator(self):
        self.program('pool_text_split_invalid', '''let a:NativePoolHandle=native_pool_text_create(p,"key=42",6);
let broken:[u8;2]=[226,130];let old:NativePoolView=native_pool_text_view(a);
if native_pool_text_split_once(a,"",0).found
|| native_pool_text_split_once(a,unsafe{broken as *const u8},2).found
|| native_pool_text_split_once(a,unsafe{metadata_address as *const u8},1).found
|| native_pool_text_split_once(a,"missing",7).found
|| !native_pool_view_current(old){return 1;}return 42;''')

    def test_failed_edits_stale_handles_and_revision_saturation(self):
        self.program('pool_text_composition_guards', '''let a:NativePoolHandle=native_pool_text_create(p,"abcdefghij",10);
let v:NativePoolView=native_pool_text_view(a);
if native_pool_text_insert_scalar(a,99,8364).status!=7
|| native_pool_text_append_scalar(a,55296).status!=8
|| native_pool_text_append_from(a,a).status!=0{return 1;}
let after:NativePoolView=native_pool_text_view(a);
if native_pool_text_append_from(a,a).status!=7
|| !native_pool_view_current(after) || native_pool_text_replace_from(a,0,1,a,0,1).status!=7
|| !native_pool_view_current(after){return 2;}
slots[1]=18446744073709551615;
if native_pool_text_reset(a,true).status!=7
|| native_pool_text_remove_scalar(a,0).status!=7
|| native_pool_text_insert_scalar(a,0,65).status!=7{return 3;}
slots[1]=after.revision;
if !native_pool_release(a,true) || native_pool_text_pop_scalar(a).status!=7
|| native_pool_text_split_once(a,"=",1).found
|| native_pool_current(native_pool_text_clone_scalars(a,0,1)){return 4;}return 42;''')

    def test_source_invalid_range_and_self_replace_are_atomic(self):
        self.program('pool_text_source_guards', '''let a:NativePoolHandle=native_pool_text_create(p,"ab€cd",7);
let v:NativePoolView=native_pool_text_view(a);
if native_pool_text_append_scalars(a,a,2,99).status!=7
|| native_pool_text_replace_from(a,1,1,a,0,1).status!=7
|| native_pool_current(native_pool_text_clone_scalars(a,0,99))
|| native_pool_text_remove_scalar(a,5).status!=7
|| !native_pool_view_current(v) || native_pool_length(a)!=7{return 1;}
return 42;''')

    def test_cross_copy_then_source_release_keeps_destination(self):
        self.program('pool_text_cross_lifetime', '''let a:NativePoolHandle=native_pool_text_create(p,"ab",2);
let b:NativePoolHandle=native_pool_text_create(p,"cd",2);
if native_pool_text_append_from(a,b).status!=0 || native_pool_text_equal_handles(a,b){return 1;}
native_pool_release(b,true);
let c:NativePoolHandle=native_pool_text_create(p,"ab",2);
if !native_pool_current(a) || native_pool_text_equal_handles(a,c)
|| native_pool_text_scalar_at(a,3).value!=100{return 2;}
let d:NativePoolHandle=native_pool_text_clone_scalars(a,0,4);
if !native_pool_text_equal_handles(a,d){return 3;}return 42;''')


    def test_numeric_split_reports_overflow_empty_and_bad_digits(self):
        self.program('pool_text_decimal_contract', '''let a:NativePoolHandle=native_pool_text_create(p,"count=4294967296",16);
let too_big:NativePoolTextSplit=native_pool_text_split_once(a,"=",1);
let number:NativeU32Result=native_pool_text_parse_u32(too_big.after);
if !too_big.found || number.status!=4 || number.error.offset!=9{return 1;}
let b:NativePoolHandle=native_pool_text_create(p,"bad=-2",6);
let negative:NativePoolTextSplit=native_pool_text_split_once(b,"=",1);
let invalid:NativeU32Result=native_pool_text_parse_u32(negative.after);
if invalid.status!=3 || invalid.error.offset!=0{return 2;}
let c:NativePoolHandle=native_pool_text_create(p,"empty=",6);
let empty:NativePoolTextSplit=native_pool_text_split_once(c,"=",1);
if !empty.found || native_pool_text_parse_u32(empty.after).status!=2{return 3;}return 42;''')

    def test_independent_empty_scalar_copy_and_zero_length_noop(self):
        self.program('pool_text_empty_clone', '''let a:NativePoolHandle=native_pool_text_create(p,"hello",5);
let view:NativePoolView=native_pool_text_view(a);
let b:NativePoolHandle=native_pool_text_clone_scalars(a,5,0);
if !native_pool_current(b) || native_pool_length(b)!=0 || !native_pool_view_current(view)
|| native_pool_text_check(b).value!=0{return 1;}
if native_pool_text_append_scalars(b,a,0,0).status!=0
|| native_pool_text_append_from(b,b).status!=0 || native_pool_length(b)!=0{return 2;}
if native_pool_text_append_scalars(b,a,1,3).status!=0
|| native_pool_text_scalar_at(b,0).value!=101 || native_pool_length(b)!=3{return 3;}
return 42;''')

if __name__ == '__main__':
    unittest.main()
