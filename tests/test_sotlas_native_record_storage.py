"""Typed local record-array storage addresses and native allocation integration."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT = Path(__file__).resolve().parents[1]


class NativeRecordStorageTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_local_record_array_pointer_reads_original_storage(self):
        self.program('record_array_read', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let rows:[Row;2]=[Row{n:20},Row{n:22}];
let p:*const Row=unsafe{rows as *const Row};return unsafe{p.n+(*(p+1)).n};}''')

    def test_mutable_record_array_pointer_writes_original_storage(self):
        self.program('record_array_write', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{n:1};2];
let mut p:*mut Row=unsafe{rows as *mut Row};unsafe{p.n=20;p=p+1;p.n=22;}
return rows[0].n+rows[1].n;}''')

    def test_aligned_stride_includes_record_padding(self):
        self.program('record_array_stride', '''struct Row{pub small:u8;pub wide:u64;pub tail:u8;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{small:3,wide:17,tail:9};2];
let p:*mut Row=unsafe{rows as *mut Row};let mut q:*mut Row=unsafe{p+1};unsafe{q.wide=42;q.tail=7;}
if rows[0].wide!=17 || rows[0].tail!=9 || rows[1].tail!=7{return 1;}return rows[1].wide as u32;}''')

    def test_nested_record_and_array_fields_preserve_layout(self):
        self.program('record_array_nested', '''struct Cell{pub n:u32;}struct Row{pub cell:Cell;pub bytes:[u8;3];}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{cell:Cell{n:1},bytes:[2;3]};2];
let p:*mut Row=unsafe{rows as *mut Row};let mut q:*mut Row=unsafe{p+1};
unsafe{q.cell.n=40;q.bytes[2]=2;}if rows[0].cell.n!=1{return 1;}
return rows[1].cell.n+(rows[1].bytes[2] as u32);}''')

    def test_float_and_signed_members_round_trip(self):
        self.program('record_array_float', '''struct Row{pub n:i16;pub x:f64;pub live:bool;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{n:-7,x:1.5,live:false};2];
let p:*mut Row=unsafe{rows as *mut Row};let mut q:*mut Row=unsafe{p+1};
unsafe{q.x=3.0;q.live=true;}if rows[1].n!=-7 || rows[1].x!=3.0 || !rows[1].live || rows[0].live{return 1;}return 42;}''')

    def test_call_accepts_typed_storage_and_returns_interior_pointer(self):
        self.program('record_array_call', '''struct Row{pub n:u32;}
fn second(p:*mut Row)->*mut Row{return unsafe{p+1};}
fn fill(mut p:*mut Row)->u32{unsafe{p.n=42;}return 0;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{n:1};2];
let p:*mut Row=unsafe{rows as *mut Row};fill(second(p));if rows[0].n!=1{return 1;}return rows[1].n;}''')

    def test_pointer_receiver_is_loaded_after_array_assignment(self):
        self.program('record_array_replace', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{n:1};2];let p:*const Row=unsafe{rows as *const Row};
rows=[Row{n:20},Row{n:22}];return unsafe{p.n+(*(p+1)).n};}''')

    def test_readonly_view_of_mutable_storage_preserves_identity(self):
        self.program('record_array_const', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;1]=[Row{n:1};1];
let p:*const Row=unsafe{rows as *const Row};rows[0].n=42;return unsafe{p.n};}''')

    def test_explicit_record_snapshot_remains_independent(self):
        self.program('record_array_snapshot', '''struct Row{pub n:u32;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{n:42};2];let mut p:*mut Row=unsafe{rows as *mut Row};
let copy:Row=unsafe{*p};unsafe{p.n=1;}return copy.n;}''')

    def test_returned_array_value_storage_is_addressable_after_binding(self):
        self.program('record_array_returned', '''struct Row{pub n:u32;}
fn make()->[Row;2]{return [Row{n:20},Row{n:22}];}
pub fn main_entry()->u32{let rows:[Row;2]=make();let p:*const Row=unsafe{rows as *const Row};
return unsafe{p.n+(*(p+1)).n};}''')

    def test_scalar_member_widths_and_stride(self):
        for typ in ('u8','u16','u32','u64','usize','i8','i16','i32','i64','f32','f64'):
            with self.subTest(typ=typ):
                one='1.0' if typ.startswith('f') else '1'
                value='42.0' if typ.startswith('f') else '42'
                self.program('record_width_'+typ,'struct Row{pub value:'+typ+';}'
                             'pub fn main_entry()->u32{let mut rows:[Row;3]=[Row{value:'+one+'};3];'
                             'let p:*mut Row=unsafe{rows as *mut Row};let mut q:*mut Row=unsafe{p+2};'
                             'unsafe{q.value='+value+';}if rows[0].value!='+one+' || rows[1].value!='+one+
                             ' || rows[2].value!='+value+'{return 1;}return 42;}')

    def test_mutable_value_parameter_uses_its_private_storage(self):
        self.program('record_array_parameter','''struct Row{pub n:u32;}
fn change(mut rows:[Row;2])->u32{let mut p:*mut Row=unsafe{rows as *mut Row};unsafe{p.n=42;}return rows[0].n;}
pub fn main_entry()->u32{let rows:[Row;2]=[Row{n:1};2];let result:u32=change(rows);
if rows[0].n!=1{return 1;}return result;}''')

    def test_deferred_read_observes_current_storage(self):
        self.program('record_array_defer','''struct Row{pub n:u32;}static mut observed:u32=0;
fn work()->u32{let mut rows:[Row;2]=[Row{n:1};2];let p:*const Row=unsafe{rows as *const Row};
defer{unsafe{observed=p.n+(*(p+1)).n;}}rows=[Row{n:20},Row{n:22}];return 0;}
pub fn main_entry()->u32{work();return unsafe{observed};}''')

    def test_existing_static_record_storage_stays_compatible(self):
        self.program('record_array_static','''struct Row{pub n:u32;}static mut rows:[Row;2]=[Row{n:20},Row{n:1}];
pub fn main_entry()->u32{let p:*mut Row=unsafe{rows as *mut Row};let mut q:*mut Row=unsafe{p+1};
unsafe{q.n=22;}return unsafe{rows[0].n+rows[1].n};}''')

    def test_unsafe_exact_type_and_const_rules_reject_invalid_programs(self):
        cases = (
            'let mut rows:[Row;2]=[Row{n:1};2];let p:*mut Row=rows as *mut Row;',
            'let rows:[Row;2]=[Row{n:1};2];let p:*mut Row=unsafe{rows as *mut Row};',
            'let mut rows:[Row;2]=[Row{n:1};2];let p:*mut Other=unsafe{rows as *mut Other};',
            'let mut rows:[Row;2]=[Row{n:1};2];let p:*mut u32=unsafe{rows as *mut u32};',
            'let rows:[Row;2]=[Row{n:1};2];let mut p:*const Row=unsafe{rows as *const Row};unsafe{p.n=42;}',
            'let rows:[Row;2]=[Row{n:1};2];let p:*const Row=rows as *const Row;',
            'let mut rows:sole [Row;2]=[Row{n:1};2];let p:*mut Row=unsafe{rows as *mut Row};',
        )
        for index, body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('record_array_reject_' + str(index),
                             'struct Row{pub n:u32;}struct Other{pub n:u32;}'
                             'pub fn main_entry()->u32{' + body + 'return 42;}', False)

    def test_resource_pointer_fields_remain_fail_closed(self):
        self.compile('record_array_pointer_field', '''struct Row{pub data:*mut u8;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{data:null};2];
let p:*mut Row=unsafe{rows as *mut Row};return 42;}''', False)

    def test_pool_accepts_typed_metadata_without_integer_pointer_bridge(self):
        sources=[]
        for module in ('managed','pool'):
            source=(ROOT / f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines()
                                     if not line.startswith(('module ', 'import '))))
        self.program('record_array_pool','\n'.join(sources)+'''
pub fn main_entry()->u32{let mut bytes:[u8;64]=0;
let mut slots:[NativePoolSlot;2]=[NativePoolSlot{generation:0,revision:0,length:0,live:false};2];
let metadata:*mut NativePoolSlot=unsafe{slots as *mut NativePoolSlot};
let mut pool:NativePool=native_pool_empty();let p:*mut NativePool=unsafe{(&mut pool) as *mut NativePool};
if !native_pool_open(p,unsafe{bytes as *mut u8},64,metadata,2,32){return 1;}
let a:NativePoolHandle=native_pool_allocate(p,2);if !native_pool_write(a,0,"42",2){return 2;}
if slots[0].length!=2 || !slots[0].live || slots[1].live{return 3;}
native_pool_release(a,true);if slots[0].live || !native_pool_close(p){return 4;}return 42;}''')


if __name__ == '__main__':
    unittest.main()
