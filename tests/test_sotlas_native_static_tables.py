"""Initialized global record tables execute through the Sotlas native backend."""
from pathlib import Path
import signal
import struct
import subprocess
import sys
import unittest
import test_sotlas_native_i32 as previous


class NativeStaticTableTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute
    windows_process_exit_code=previous.NativeI32Tests.windows_process_exit_code

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_list_with_padded_elements(self):
        self.program('static_table_list','''struct Item{pub tag:u8;pub value:u64;}
static mut table:[Item;2]=[Item{tag:1,value:20},Item{tag:2,value:22}];
pub fn main_entry()->u32{unsafe{if table[1].tag!=2{return 1;}return (table[0].value+table[1].value) as u32;}}''')

    def test_repeat_and_persistent_independent_mutation(self):
        self.program('static_table_repeat','''struct Item{pub value:u32;}
static mut table:[Item;3]=[Item{value:14};3];
fn update(){unsafe{table[0].value=10;table[2].value=18;}}
pub fn main_entry()->u32{update();unsafe{return table[0].value+table[1].value+table[2].value;}}''')

    def test_dynamic_index_and_element_replacement(self):
        self.program('static_table_dynamic','''struct Item{pub value:u32;}
static mut table:[Item;2]=[Item{value:1};2];
pub fn main_entry()->u32{unsafe{table[0]=Item{value:20};table[1]=Item{value:22};
let mut total:u32=0;let mut index:usize=0;
while index<2{total=total+table[index].value;index=index+1;}return total;}}''')

    def test_element_copy_and_return_are_independent(self):
        self.program('static_table_copy','''struct Item{pub value:u32;}
static mut table:[Item;2]=[Item{value:20},Item{value:22}];
fn load(index:usize)->Item{unsafe{return table[index];}}
pub fn main_entry()->u32{let mut local:Item=load(0);local.value=1;
unsafe{return table[0].value+table[1].value;}}''')

    def test_nested_fields_and_nested_record_arrays(self):
        self.program('static_table_nested','''struct Item{pub value:u16;}
struct Row{pub tag:u8;pub items:[Item;2];pub values:[u32;2];}
static mut table:[Row;2]=[Row{tag:1,items:[Item{value:10};2],values:[1,2]};2];
pub fn main_entry()->u32{unsafe{table[1].items[1].value=12;
return table[0].items[0].value as u32+table[0].items[1].value as u32
+table[1].items[0].value as u32+table[1].items[1].value as u32;}}''')

    def test_zero_table_stays_independent_of_initialized_data(self):
        self.program('static_table_zero','''struct Item{pub value:u32;}
static mut empty:[Item;2]=[Item{value:0};2];
static mut ready:[Item;2]=[Item{value:21};2];
pub fn main_entry()->u32{unsafe{return empty[1].value+ready[0].value+ready[1].value;}}''')

    def test_static_table_shapes_types_and_runtime_initializers_fail_closed(self):
        prefix='struct A{pub value:u32;}struct B{pub value:u32;}'
        for declaration in (
            'static mut table:[A;2]=[A{value:42}];',
            'static mut table:[A;2]=[A{value:42};3];',
            'static mut table:[A;2]=[B{value:21};2];',
            'fn make()->A{return A{value:21};}static mut table:[A;2]=[make();2];',
            'static mut table:[A;2]=[A{value:4294967296};2];',
            'static mut table:[A;0]=[];',
            'static mut table:[A;257]=[A{value:1};257];',
            'static mut table:[A;2]=1;',
        ):
            with self.subTest(declaration=declaration):
                self.compile('static_table_bad',prefix+declaration+'pub fn main_entry()->u32{return 42;}',False)

    def test_pointer_resource_and_capacity_initializers_are_rejected(self):
        for source in (
            'struct A{pub pointer:*mut u32;}static mut table:[A;2]=[A{pointer:null};2];',
            'struct A{pub value:sole u32;}static mut table:[A;2]=[A{value:21};2];',
            'struct A{pub values:[u64;256];}static mut table:[A;3]=[A{values:[1;256]};3];',
        ):
            with self.subTest(source=source):
                self.compile('static_table_resource',source+'pub fn main_entry()->u32{return 42;}',False)

    def test_immutable_table_rejects_field_and_element_mutation(self):
        for mutation in ('table[0].value=1;','table[0]=A{value:1};'):
            with self.subTest(mutation=mutation):
                self.compile('static_table_immutable','''struct A{pub value:u32;}
static table:[A;2]=[A{value:21};2];pub fn main_entry()->u32{unsafe{'''+mutation+'}return 42;}',False)

    def test_invalid_literal_index_is_rejected(self):
        self.compile('static_table_literal_bound','''struct A{pub value:u32;}
static mut table:[A;2]=[A{value:21};2];pub fn main_entry()->u32{unsafe{return table[2].value;}}''',False)

    def test_dynamic_out_of_bounds_traps(self):
        obj=self.compile('static_table_dynamic_bound','''struct A{pub value:u32;}
static mut table:[A;2]=[A{value:21};2];
fn read(index:usize)->u32{unsafe{return table[index].value;}}
pub fn main_entry()->u32{return read(2);}''')
        image=self.link_image(obj)
        if sys.platform=='win32':
            code,stderr=self.windows_process_exit_code(image)
            self.assertEqual(code,0xC000001D,stderr)
        else:
            result=subprocess.run([str(image)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,-signal.SIGILL)

    def test_local_shadowing_cannot_reuse_global_table_layout(self):
        self.program('static_table_shadow','''struct A{pub value:u32;}
static mut table:[A;2]=[A{value:1};2];
pub fn main_entry()->u32{let table:[u32;2]=[20,22];return table[0]+table[1];}''')
        self.compile('static_table_shadow_field','''struct A{pub value:u32;}
static mut table:[A;2]=[A{value:1};2];
pub fn main_entry()->u32{let table:[u32;2]=[20,22];return table[0].value;}''',False)

    def test_constants_floats_booleans_and_internal_borrow(self):
        self.program('static_table_constants','''struct A{pub value:u32;pub scale:f64;pub valid:bool;}
const BASE:u32=20;
static mut table:[A;2]=[A{value:BASE+1,scale:1.5,valid:true};2];
fn read(value:whisper A)->u32{if !value.valid||value.scale!=1.5{return 1;}return value.value;}
pub fn main_entry()->u32{unsafe{return read(table[0])+read(table[1]);}}''')

    def test_object_bytes_include_padding_and_zero_table_is_bss(self):
        obj=self.compile('static_table_bytes','''struct A{pub tag:u8;pub value:u64;}
static mut table:[A;2]=[A{tag:1,value:20},A{tag:2,value:22}];
static mut empty:[A;2]=[A{tag:0,value:0};2];
pub fn main_entry()->u32{return 42;}''')
        raw=obj.read_bytes();shoff=struct.unpack_from('<Q',raw,40)[0]
        size,count,names_index=struct.unpack_from('<HHH',raw,58)
        headers=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*size) for i in range(count)]
        names=headers[names_index];strings=raw[names[4]:names[4]+names[5]]
        sections={strings[h[0]:].split(b'\0',1)[0].decode():h for h in headers}
        data=sections['.data'];zero=sections['.bss']
        self.assertEqual(raw[data[4]:data[4]+data[5]],struct.pack('<B7xQB7xQ',1,20,2,22))
        self.assertEqual((zero[1],zero[5]),(8,32))

    def test_zero_shorthand_record_table_can_be_updated(self):
        self.program('static_table_zero_shorthand','''struct A{pub value:u32;}
static mut table:[A;2]=0;
pub fn main_entry()->u32{unsafe{table[1]=A{value:42};return table[0].value+table[1].value;}}''')

    def test_checked_in_dispatch_example(self):
        path=Path(__file__).resolve().parents[1]/'examples/static_dispatch/main.sotlas'
        self.program('static_table_example',path.read_text(encoding='utf-8').split(';',1)[1])

    def test_full_element_capacity_and_element_to_element_copy(self):
        self.program('static_table_full','''struct A{pub value:u32;}
static mut table:[A;256]=[A{value:21};256];
pub fn main_entry()->u32{unsafe{table[255]=table[0];table[0].value=1;
return table[254].value+table[255].value;}}''')

    def test_exact_byte_pool_capacity(self):
        self.program('static_table_pool_full','''struct A{pub values:[u64;256];}
static mut table:[A;2]=[A{values:[21;256]};2];
pub fn main_entry()->u32{unsafe{return (table[0].values[255]+table[1].values[0]) as u32;}}''')

    def test_single_record_table_is_now_executable(self):
        self.program('static_table_single','''struct Token{pub value:u32;}
static mut DATA:[Token;1]=[Token{value:42}];
pub fn main_entry()->u32{unsafe{return DATA[0].value;}}''')


if __name__=='__main__':
    unittest.main()
