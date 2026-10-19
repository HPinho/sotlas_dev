"""Static POD records are serialized by Sotlas and executed as native data."""
from pathlib import Path
import struct
import unittest
import test_sotlas_native_i32 as previous


class NativeStaticRecordTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_checked_in_configuration_example(self):
        example=Path(__file__).resolve().parents[1]/'examples/static_config/main.sotlas'
        self.program('static_record_example',example.read_text(encoding='utf-8').split(';',1)[1])

    def test_scalar_fields_padding_and_declaration_order(self):
        self.program('static_record_padding', '''
struct Config{pub tag:u8;pub value:u64;pub tail:u16;}
static mut config:Config=Config{tail:2,value:40,tag:7};
pub fn main_entry()->u32{unsafe{
if config.tag!=7{return 1;}return (config.value+config.tail as u64) as u32;}}''')

    def test_nested_records_and_constant_expressions(self):
        self.program('static_record_nested', '''
struct Pair{pub left:u32;pub right:u32;}struct Config{pub tag:u8;pub pair:Pair;}
const BASE:u32=20;
static mut config:Config=Config{tag:1,pair:Pair{left:BASE,right:BASE+2}};
pub fn main_entry()->u32{unsafe{return config.pair.left+config.pair.right;}}''')

    def test_scalar_arrays_in_static_record(self):
        self.program('static_record_array', '''
struct Config{pub items:[u16;3];pub repeat:[u8;2];}
static mut config:Config=Config{items:[10,11,19],repeat:[1;2]};
pub fn main_entry()->u32{unsafe{
return config.items[0] as u32+config.items[1] as u32+config.items[2] as u32
+config.repeat[0] as u32+config.repeat[1] as u32;}}''')

    def test_record_arrays_in_static_record(self):
        self.program('static_record_table', '''
struct Item{pub tag:u8;pub value:u64;}struct Config{pub items:[Item;2];}
static mut config:Config=Config{items:[Item{tag:1,value:20},Item{tag:2,value:22}]};
pub fn main_entry()->u32{unsafe{return (config.items[0].value+config.items[1].value) as u32;}}''')

    def test_zero_record_and_data_record_do_not_overlap(self):
        self.program('static_record_zero', '''
struct Item{pub value:u32;}
static mut zero:Item=Item{value:0};static mut answer:Item=Item{value:42};
pub fn main_entry()->u32{unsafe{return answer.value+zero.value;}}''')

    def test_mutate_static_nested_fields(self):
        self.program('static_record_mutation', '''
struct Item{pub value:u32;}struct Config{pub items:[Item;2];}
static mut config:Config=Config{items:[Item{value:1};2]};
fn update(){unsafe{config.items[0].value=20;config.items[1]=Item{value:22};}}
pub fn main_entry()->u32{update();unsafe{return config.items[0].value+config.items[1].value;}}''')

    def test_copy_static_record_is_independent(self):
        self.program('static_record_copy', '''
struct Item{pub value:u32;}
static mut config:Item=Item{value:42};
pub fn main_entry()->u32{unsafe{let mut copy:Item=config;copy.value=1;return config.value;}}''')

    def test_nonconstant_or_resource_initializers_fail(self):
        for name, source in (
            ('call','struct Item{pub value:u32;}fn make()->u32{return 42;}static mut config:Item=Item{value:make()};'),
            ('pointer','struct Item{pub value:*mut u32;}static mut config:Item=Item{value:null};'),
            ('count','struct Item{pub values:[u32;2];}static mut config:Item=Item{values:[42]};'),
            ('overflow','struct Item{pub value:u8;}static mut config:Item=Item{value:256};'),
            ('missing','struct Item{pub value:u32;}static mut config:Item=Item{};'),
            ('duplicate','struct Item{pub value:u32;}static mut config:Item=Item{value:1,value:2};'),
        ):
            with self.subTest(name=name):
                self.compile('static_record_bad_'+name,source+'pub fn main_entry()->u32{return 42;}',False)

    def test_direct_field_and_whole_record_replacement(self):
        self.program('static_record_replace', '''
struct Item{pub value:u32;}
static mut config:Item=Item{value:1};
pub fn main_entry()->u32{unsafe{config.value=2;config=Item{value:42};return config.value;}}''')

    def test_immutable_global_rejects_nested_mutation(self):
        for body in ('config.value=1;','config=Item{value:1};'):
            with self.subTest(body=body):
                self.compile('static_record_immutable','''struct Item{pub value:u32;}
static config:Item=Item{value:42};pub fn main_entry()->u32{unsafe{'''+body+'}return 42;}',False)

    def test_global_record_name_cannot_override_a_scalar_local(self):
        self.program('static_record_shadow', '''struct Item{pub value:u32;}
static mut config:Item=Item{value:1};
pub fn main_entry()->u32{let config:u32=42;return config;}''')
        self.compile('static_record_shadow_field', '''struct Item{pub value:u32;}
static mut config:Item=Item{value:1};
pub fn main_entry()->u32{let config:u32=42;return config.value;}''',False)

    def test_static_float_signed_bool_fields(self):
        self.program('static_record_float', '''struct Config{pub negative:i8;pub ready:bool;pub scale:f64;}
static mut config:Config=Config{negative:-2,ready:true,scale:1.5};
pub fn main_entry()->u32{unsafe{
if config.negative != -2 || !config.ready || config.scale != 1.5{return 1;}return 42;}}''')

    def test_static_pool_capacity_fails_before_output(self):
        self.compile('static_record_capacity','''struct Large{pub bytes:[u64;256];}
static mut first:Large=Large{bytes:[1;256]};
static mut second:Large=Large{bytes:[2;256]};
static mut third:Large=Large{bytes:[3;256]};
pub fn main_entry()->u32{return 42;}''',False)

    def test_static_record_crosses_internal_return_and_borrow(self):
        self.program('static_record_return', '''struct Item{pub value:u32;}
static mut config:Item=Item{value:42};
fn load()->Item{unsafe{return config;}}
fn read(item:whisper Item)->u32{return item.value;}
pub fn main_entry()->u32{let mut copy:Item=load();copy.value=1;unsafe{return read(config);}}''')

    def test_static_scalar_field_mutation_persists_across_calls(self):
        self.program('static_record_calls', '''struct Counter{pub value:u32;}
static mut counter:Counter=Counter{value:40};
fn tick(){unsafe{counter.value=counter.value+1;}}
pub fn main_entry()->u32{tick();tick();unsafe{return counter.value;}}''')

    def test_static_array_fields_whole_assignment_and_dynamic_index(self):
        self.program('static_record_dynamic', '''struct Item{pub value:u32;}
struct Table{pub items:[Item;2];}
static mut table:Table=Table{items:[Item{value:1};2]};
pub fn main_entry()->u32{unsafe{table.items=[Item{value:20},Item{value:22}];
let mut index:usize=0;let mut total:u32=0;
while index<2{total=total+table.items[index].value;index=index+1;}return total;}}''')

    def test_static_data_pool_exact_capacity(self):
        self.program('static_record_capacity_exact', '''struct Large{pub bytes:[u64;256];}
static mut first:Large=Large{bytes:[20;256]};
static mut second:Large=Large{bytes:[22;256]};
pub fn main_entry()->u32{unsafe{return (first.bytes[255]+second.bytes[0]) as u32;}}''')

    def test_static_record_type_and_array_nominality_are_checked(self):
        for declaration in (
            'struct A{pub value:u32;}struct B{pub value:u32;}static mut config:A=B{value:42};',
            'struct A{pub value:u32;}struct B{pub value:u32;}struct Table{pub items:[A;2];}static mut config:Table=Table{items:[B{value:21};2]};',
            'struct A{pub value:u32;}static mut config:sole A=A{value:42};',
            'struct A{pub value:u32;}struct Owned{pub item:sole A;}static mut config:Owned=Owned{item:A{value:42}};',
        ):
            with self.subTest(declaration=declaration):
                self.compile('static_record_nominal',declaration+'pub fn main_entry()->u32{return 42;}',False)

    def test_object_padding_is_zero_and_zero_record_uses_bss(self):
        obj=self.compile('static_record_data_bytes','''struct Item{pub tag:u8;pub value:u64;pub tail:u16;}
static mut config:Item=Item{tail:2,value:40,tag:7};
static mut empty:Item=Item{tag:0,value:0,tail:0};
pub fn main_entry()->u32{return 42;}''')
        raw=obj.read_bytes()
        shoff=struct.unpack_from('<Q',raw,40)[0]
        entry_size,count,names_index=struct.unpack_from('<HHH',raw,58)
        headers=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*entry_size) for i in range(count)]
        names=headers[names_index]
        strings=raw[names[4]:names[4]+names[5]]
        sections={strings[h[0]:].split(b'\0',1)[0].decode():h for h in headers}
        data=sections['.data'];zero=sections['.bss']
        self.assertEqual(raw[data[4]:data[4]+data[5]],struct.pack('<B7xQH6x',7,40,2))
        self.assertEqual((zero[1],zero[5]),(8,24))


if __name__ == '__main__':
    unittest.main()
