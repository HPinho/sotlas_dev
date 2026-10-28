"""Owned UTF-8 map operations, failure atomicity and cleanup as native programs."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT = Path(__file__).resolve().parents[1]


class NativeTextMapTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, body, helpers='', pool_slots=8, entries=4):
        sources = []
        for module in ('results', 'managed', 'text', 'unicode', 'utf8_buffer', 'pool', 'pool_text', 'text_map'):
            source = (ROOT / f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines()
                                     if not line.startswith(('module ', 'import '))))
        setup = '''
pub fn main_entry()->u32{
let mut bytes:[u8;BYTE_COUNT]=0;let data:*mut u8=unsafe{bytes as *mut u8};
let mut slots:[u64;SLOT_WORDS]=0;let words:*mut u64=unsafe{slots as *mut u64};
let mut pool:NativePool=native_pool_empty();let p:*mut NativePool=unsafe{(&mut pool) as *mut NativePool};
if !native_pool_open_words(p,data,BYTE_COUNT,words,SLOT_WORDS,SLOT_COUNT,32){return 90;}
let mut entries:[u64;ENTRY_WORDS]=0;let table:*mut u64=unsafe{entries as *mut u64};
let mut map:NativeTextMap=native_text_map_empty();let m:*mut NativeTextMap=unsafe{(&mut map) as *mut NativeTextMap};
if !native_text_map_open(m,p,table,ENTRY_WORDS,ENTRY_COUNT){return 91;}
'''
        for key, value in {'BYTE_COUNT': pool_slots * 32, 'SLOT_WORDS': pool_slots * 4,
                           'SLOT_COUNT': pool_slots, 'ENTRY_WORDS': entries * 7,
                           'ENTRY_COUNT': entries}.items():
            setup = setup.replace(key, str(value))
        self.execute(self.compile(name, '\n'.join(sources) + '\n' + helpers + setup + body + '}'))

    def test_insert_lookup_update_and_missing_key(self):
        self.program('map_basic', '''if native_text_map_set(m,"name",4,"Sotlas",6).value!=1
|| native_text_map_set_u32(m,"answer",6,42).value!=2 || native_text_map_get_u32(m,"answer",6).value!=42{return 1;}
let v:NativePoolView=native_text_map_get(m,"name",4);let mut out:[u8;6]=0;
if !native_pool_read(v,unsafe{out as *mut u8},6) || out[0]!=83 || out[5]!=115{return 2;}
if native_text_map_set(m,"name",4,"native",6).value!=2 || native_pool_view_current(v)
|| native_text_map_find(m,"missing",7).status!=9 || native_text_map_get(m,"missing",7).valid{return 3;}return 42;''')

    def test_full_pool_updates_without_a_spare_slot(self):
        self.program('map_full_update', '''native_text_map_set_u32(m,"a",1,20);native_text_map_set_u32(m,"b",1,22);
let old:NativePoolView=native_text_map_get(m,"a",1);
if native_text_map_set_u32(m,"a",1,42).status!=0 || native_text_map_get_u32(m,"a",1).value!=42
|| native_pool_view_current(old) || map.count!=2{return 1;}
if native_text_map_set(m,"c",1,"x",1).status!=10 || map.count!=2{return 2;}return 42;''', pool_slots=4)

    def test_removal_reuses_slots_without_invalidating_other_values(self):
        self.program('map_remove', '''native_text_map_set_u32(m,"a",1,1);native_text_map_set_u32(m,"b",1,42);
let a:NativePoolView=native_text_map_get(m,"a",1);let b:NativePoolView=native_text_map_get(m,"b",1);
if native_text_map_remove(m,"a",1,true).value!=1 || native_pool_view_current(a)
|| !native_pool_view_current(b) || native_text_map_remove(m,"a",1,false).status!=9{return 1;}
native_text_map_set_u32(m,"c",1,9);
if native_pool_view_current(a) || native_text_map_get_u32(m,"b",1).value!=42{return 2;}return 42;''', pool_slots=4)

    def test_utf8_key_value_and_empty_entries(self):
        self.program('map_unicode', '''if native_text_map_set(m,"€",3,"😀",4).status!=0
|| native_text_map_set(m,null,0,null,0).status!=0 || map.count!=2{return 1;}
let v:NativePoolView=native_text_map_get(m,"€",3);let mut out:[u8;4]=0;
if !native_pool_read(v,unsafe{out as *mut u8},4) || out[0]!=240 || out[3]!=128
|| !native_text_map_get(m,null,0).valid{return 2;}return 42;''')

    def test_malformed_and_oversized_inputs_preserve_values_and_cursors(self):
        self.program('map_invalid_input', '''native_text_map_set_u32(m,"a",1,42);
let v:NativePoolView=native_text_map_get(m,"a",1);let cursor:NativeTextMapCursor=native_text_map_cursor(m);
let bad:[u8;2]=[226,130];let raw:*const u8=unsafe{bad as *const u8};
if native_text_map_set(m,raw,2,"x",1).status!=8 || native_text_map_set(m,"a",1,raw,2).status!=8
|| native_text_map_set(m,"a",1,"12345678901234567890123456789012345",33).status!=7
|| !native_pool_view_current(v) || !native_text_map_next(cursor).valid || map.count!=1{return 1;}return 42;''')

    def test_exhaustion_does_not_leak_a_half_inserted_key(self):
        self.program('map_exhaustion', '''native_text_map_set_u32(m,"a",1,42);
let view:NativePoolView=native_text_map_get(m,"a",1);let epoch:u64=pool.epoch;
if native_text_map_set_u32(m,"b",1,7).status!=10 || map.count!=1 || pool.epoch!=epoch
|| !native_pool_view_current(view){return 1;}
let remaining:NativePoolHandle=native_pool_allocate(p,1);if !native_pool_current(remaining){return 2;}
native_pool_release(remaining,true);if !native_text_map_close(m,true) || !native_pool_close(p){return 3;}return 42;''',pool_slots=3)

    def test_entry_capacity_failure_preserves_available_pool_storage(self):
        self.program('map_table_full', '''native_text_map_set_u32(m,"a",1,42);
if native_text_map_set_u32(m,"b",1,1).status!=10 || map.count!=1{return 1;}
let a:NativePoolHandle=native_pool_allocate(p,1);let b:NativePoolHandle=native_pool_allocate(p,1);
if !native_pool_current(a) || !native_pool_current(b){return 2;}return 42;''',entries=1,pool_slots=4)

    def test_iteration_holes_end_and_mutation_invalidation(self):
        self.program('map_iterate', '''native_text_map_set_u32(m,"a",1,1);native_text_map_set_u32(m,"b",1,2);
native_text_map_set_u32(m,"c",1,39);native_text_map_remove(m,"b",1,true);
let mut cursor:NativeTextMapCursor=native_text_map_cursor(m);let mut total:u32=0;let mut count:u32=0;
loop{let item:NativeTextMapItem=native_text_map_next(cursor);if !item.valid{return 1;}if item.done{break;}
total=total+native_pool_text_parse_u32(item.value).value;count=count+1;cursor=item.next;}
if total!=40 || count!=2 || !native_text_map_next(cursor).done{return 2;}
native_text_map_set_u32(m,"a",1,3);if native_text_map_next(cursor).valid{return 3;}return 42;''')

    def test_clear_and_close_release_only_owned_allocations(self):
        self.program('map_clear', '''let outside:NativePoolHandle=native_pool_text_create(p,"outside",7);
native_text_map_set_u32(m,"a",1,42);let view:NativePoolView=native_text_map_get(m,"a",1);
if !native_text_map_clear(m,true) || map.count!=0 || native_pool_view_current(view)
|| !native_pool_current(outside) || native_pool_close(p){return 1;}
native_text_map_set_u32(m,"b",1,42);if !native_text_map_close(m,true){return 2;}
native_pool_release(outside,true);if !native_pool_close(p){return 3;}return 42;''')

    def test_pool_reset_rejects_stale_table_before_access_and_can_reopen(self):
        self.program('map_epoch', '''native_text_map_set_u32(m,"a",1,42);let old:NativeTextMapCursor=native_text_map_cursor(m);
native_pool_reset(p,true);let saved:*mut u64=map.entries;map.entries=null;
if native_text_map_shape(m) || native_text_map_get(m,"a",1).valid || native_text_map_next(old).valid{return 1;}
if !native_text_map_detach_stale(m){return 2;}map.entries=saved;
if !native_text_map_open(m,p,table,28,4) || native_text_map_next(old).valid{return 3;}
if native_text_map_set_u32(m,"new",3,42).status!=0 || native_text_map_get_u32(m,"new",3).value!=42{return 4;}return 42;''')

    def test_external_value_mutation_fails_closed_before_cleanup(self):
        self.program('map_alias', '''native_text_map_set_u32(m,"a",1,42);
let view:NativePoolView=native_text_map_get(m,"a",1);native_pool_write(view.handle,0,"99",2);
if native_text_map_shape(m) || native_text_map_clear(m,true) || native_text_map_detach_stale(m){return 1;}
if !native_pool_current(view.handle){return 2;}native_pool_reset(p,true);
if !native_text_map_detach_stale(m){return 3;}return 42;''')

    def test_revision_saturation_preserves_views_and_contents(self):
        self.program('map_revision', '''native_text_map_set_u32(m,"a",1,42);
let view:NativePoolView=native_text_map_get(m,"a",1);map.revision=18446744073709551615;
if native_text_map_set_u32(m,"a",1,1).status!=7 || native_text_map_remove(m,"a",1,true).status!=7
|| native_text_map_clear(m,true) || !native_pool_view_current(view) || native_text_map_get_u32(m,"a",1).value!=42{return 1;}return 42;''')

    def test_numeric_error_details_are_preserved(self):
        self.program('map_numbers', '''native_text_map_set(m,"bad",3,"4x",2);
let bad:NativeU32Result=native_text_map_get_u32(m,"bad",3);
native_text_map_set(m,"large",5,"4294967296",10);
if bad.status!=3 || bad.error.offset!=1 || native_text_map_get_u32(m,"large",5).status!=4
|| native_text_map_get_u32(m,"none",4).status!=9{return 1;}return 42;''')

    def test_sources_cannot_overlap_map_table_or_pool_backing(self):
        self.program('map_overlap', '''native_text_map_set_u32(m,"a",1,42);
let table_address:usize=unsafe{table as usize};let control_address:usize=unsafe{m as usize};
if native_text_map_set(m,"b",1,data,1).status!=7
|| native_text_map_set(m,"b",1,unsafe{table_address as *const u8},1).status!=7
|| native_text_map_find(m,unsafe{control_address as *const u8},1).status!=7 || map.count!=1{return 1;}return 42;''')

    def test_invalid_open_is_atomic_and_control_must_be_disjoint(self):
        self.program('map_layout', '''native_text_map_close(m,true);let rev:u64=map.revision;
let control:usize=unsafe{m as usize};let storage:usize=unsafe{data as usize};
if native_text_map_open(m,p,table,27,4) || native_text_map_open(m,p,table,28,0)
|| native_text_map_open(m,p,unsafe{control as *mut u64},28,4)
|| native_text_map_open(m,p,unsafe{storage as *mut u64},28,4)
|| native_text_map_open(m,p,words,28,4) || map.live || map.revision!=rev{return 1;}
if !native_text_map_open(m,p,table,28,4){return 2;}return 42;''')

    def test_defer_cleans_map_on_propagated_failure(self):
        self.program('map_defer', '''let result:NativeU32Result=map_task(m);
if result.status!=11 || map.live || !native_pool_close(p){return 1;}return 42;''',helpers='''
fn map_fail()->NativeU32Result{return native_u32_error(11,7);}
fn map_task(map:*mut NativeTextMap)->NativeU32Result{
defer{native_text_map_close(map,true);}
native_text_map_set_u32(map,"answer",6,42)?;let result:u32=map_fail()?;return native_u32_ok(result);
}
''')

    def test_checked_split_field_copies_from_same_pool_then_survives_release(self):
        self.program('map_field_views', '''let source:NativePoolHandle=native_pool_text_create(p,"answer=42",9);
let fields:NativePoolTextSplit=native_pool_text_split_once(source,"=",1);
if !fields.found || native_text_map_set_views(m,fields.before,fields.after).status!=0{return 1;}
native_pool_release(source,true);
if native_text_map_get_u32(m,"answer",6).value!=42 || native_pool_view_current(fields.after){return 2;}
if !native_text_map_close(m,true) || !native_pool_close(p){return 3;}return 42;''')

    def test_stale_or_partial_utf8_source_views_leave_map_unchanged(self):
        self.program('map_field_stale', '''let source:NativePoolHandle=native_pool_text_create(p,"€=42",6);
let fields:NativePoolTextSplit=native_pool_text_split_once(source,"=",1);
let partial:NativePoolView=native_pool_view(source,1,1);
if native_text_map_set_views(m,partial,fields.after).status!=8 || map.count!=0{return 1;}
native_pool_text_append(source,"!",1);
if native_text_map_set_views(m,fields.before,fields.after).status!=7 || map.count!=0{return 2;}return 42;''')

    def test_checked_views_from_another_pool_are_copied_independently(self):
        self.program('map_cross_pool', '''let mut other_bytes:[u8;64]=0;let mut other_words:[u64;8]=0;
let mut other:NativePool=native_pool_empty();let o:*mut NativePool=unsafe{(&mut other) as *mut NativePool};
if !native_pool_open_words(o,unsafe{other_bytes as *mut u8},64,unsafe{other_words as *mut u64},8,2,32){return 1;}
let source:NativePoolHandle=native_pool_text_create(o,"a=42",4);
let fields:NativePoolTextSplit=native_pool_text_split_once(source,"=",1);
if native_text_map_set_views(m,fields.before,fields.after).status!=0{return 2;}
native_pool_reset(o,true);if native_text_map_get_u32(m,"a",1).value!=42{return 3;}return 42;''')

    def test_checked_sources_do_not_allow_overlapping_in_place_replacement(self):
        self.program('map_self_value', '''native_text_map_set(m,"key",3,"value",5);
let key:NativePoolView=native_pool_text_view(native_text_map_handle(m,0,false));
let value:NativePoolView=native_text_map_get(m,"key",3);
if native_text_map_set_views(m,key,value).status!=7 || !native_pool_view_current(value)
|| map.count!=1{return 1;}return 42;''')


if __name__ == '__main__':
    unittest.main()
