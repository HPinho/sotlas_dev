"""Native dependency-ordered aggregate layouts and composed value execution."""
import itertools
import struct
import unittest
from pathlib import Path
import test_sotlas_native_i32 as previous


class NativeComposedValueTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_forward_record_dependency_and_alignment(self):
        self.program('composed_forward_records', '''struct Outer{pub prefix:u8;pub inner:Inner;pub suffix:u16;}
struct Inner{pub wide:u64;pub n:u32;}
pub fn main_entry()->u32{let a:Outer=Outer{prefix:7,inner:Inner{wide:99,n:42},suffix:9};
if a.prefix!=7 || a.suffix!=9 || a.inner.wide!=99{return 1;}return a.inner.n;}''')

    def test_checked_in_event_pipeline(self):
        path=Path(__file__).resolve().parents[1]/'examples/native_event_pipeline/main.sotlas'
        self.program('composed_event_pipeline',path.read_text(encoding='utf-8').split(';',1)[1])

    def test_record_with_payload_enum_field(self):
        for forward in (False,True):
            with self.subTest(forward=forward):
                record='struct Envelope{pub prefix:u8;pub value:Event;pub suffix:u64;}'
                enum='enum Event{None,Number(u32),}'
                self.program('composed_enum_field_'+str(forward),(record+enum if forward else enum+record)+'''
pub fn main_entry()->u32{let e:Envelope=Envelope{prefix:7,value:Event::Number(42),suffix:99};
if e.prefix!=7 || e.suffix!=99{return 1;}return match e.value{Event::None=>0,Event::Number(n)=>n};}''')

    def test_forward_nested_payload_enum(self):
        self.program('composed_forward_enums', '''enum Outer{Empty,Some(Inner),}
enum Inner{Missing,Value(u32),}
pub fn main_entry()->u32{let a:Outer=Outer::Some(Inner::Value(42));
return match a{Outer::Empty=>0,Outer::Some(Inner::Missing)=>0,Outer::Some(Inner::Value(n))=>n};}''')

    def test_interleaved_record_enum_and_array_dependency_chain(self):
        self.program('composed_mixed_graph', '''struct Root{pub data:Branch;}
enum Branch{Empty,Data(Table),}struct Table{pub rows:[Row;2];}
struct Row{pub event:Leaf;}enum Leaf{Missing,Number(u32),}
pub fn main_entry()->u32{let r:Root=Root{data:Branch::Data(Table{rows:[Row{event:Leaf::Number(21)};2]})};
return match r.data{Branch::Empty=>0,Branch::Data(t)=>{
let a:u32=match t.rows[0].event{Leaf::Missing=>0,Leaf::Number(n)=>n};
let b:u32=match t.rows[1].event{Leaf::Missing=>0,Leaf::Number(n)=>n};a+b}};}''')

    def test_payload_enum_arrays_local_assignment_and_index_matching(self):
        self.program('composed_enum_array', '''enum Event{None,Number(u32),}
pub fn main_entry()->u32{let mut a:[Event;2]=[Event::Number(20),Event::Number(22)];
a=[a[1],a[0]];a[1]=Event::Number(20);
let x:u32=match a[0]{Event::None=>0,Event::Number(n)=>n};
let y:u32=match a[1]{Event::None=>0,Event::Number(n)=>n};return x+y;}''')

    def test_enum_arrays_in_fields_and_payloads(self):
        self.program('composed_enum_containers', '''enum Packet{Data([Event;2]),}
struct Table{pub events:[Event;2];}enum Event{None,Number(u32),}
pub fn main_entry()->u32{let t:Table=Table{events:[Event::Number(21);2]};
let p:Packet=Packet::Data(t.events);return match p{Packet::Data([Event::Number(a),Event::Number(b)])=>a+b,_=>0};}''')

    def test_composed_records_calls_returns_and_independent_copies(self):
        self.program('composed_value_abi', '''struct Box{pub event:Event;pub n:u8;}enum Event{None,Value(u32),}
fn make()->Box{return Box{event:Event::Value(42),n:7};}
fn change(mut b:Box)->Box{b.event=Event::Value(1);return b;}
pub fn main_entry()->u32{let a:Box=make();let b:Box=change(a);
if match b.event{Event::None=>0,Event::Value(n)=>n}!=1 || a.n!=7{return 1;}
return match a.event{Event::None=>0,Event::Value(n)=>n};}''')

    def test_composed_array_abi_and_owned_transfers(self):
        self.program('composed_owned_arrays', '''enum Event{None,Value(u32),}
fn pass(a:sole [Event;2])->sole [Event;2]{return a;}
fn read(a:whisper [Event;2])->u32{return match a{[Event::Value(x),Event::Value(y)]=>x+y,_=>0};}
pub fn main_entry()->u32{let a:sole [Event;2]=[Event::Value(20),Event::Value(22)];
if read(a)!=42{return 1;}let b:sole [Event;2]=pass(a);return read(b);}''')

    def test_named_record_patterns_containing_enum_patterns(self):
        self.program('composed_named_patterns', '''struct Box{pub prefix:u8;pub event:Event;}
enum Event{None,Value(u32),}
pub fn main_entry()->u32{let b:Box=Box{prefix:7,event:Event::Value(42)};
return match b{Box{event:Event::Value(n),prefix:7}=>n,_=>0};}''')

    def test_record_enum_match_and_conditional_results(self):
        self.program('composed_contextual_results', '''struct Box{pub event:Event;}enum Event{None,Value(u32),}
fn choose(flag:bool)->Box{return match flag{true=>Box{event:Event::Value(42)},false=>Box{event:Event::None}};}
pub fn main_entry()->u32{let b:Box=if true{choose(true)}else{choose(false)};
return match b.event{Event::None=>0,Event::Value(n)=>n};}''')

    def test_finite_graph_with_raw_pointer_cycle_keeps_pointer_layout(self):
        self.program('composed_pointer_edge', '''struct Node{pub value:u32;pub next:*mut Node;}
pub fn main_entry()->u32{let n:Node=Node{value:42,next:null};return n.value;}''')

    def test_direct_and_indirect_by_value_cycles_rejected(self):
        cases=('struct A{pub value:A;}', 'struct A{pub value:B;}struct B{pub value:A;}',
               'enum A{Data(A),}', 'enum A{Data(B),}enum B{Data(A),}',
               'struct A{pub value:B;}enum B{Data(A),}',
               'struct A{pub values:[B;2];}struct B{pub value:A;}',
               'struct A{pub value:Self;}')
        for i,source in enumerate(cases):
            with self.subTest(source=source):
                self.compile('composed_cycle_'+str(i),source+'pub fn main_entry()->u32{return 42;}',False)

    def test_wrong_nominal_enum_and_invalid_layouts_rejected(self):
        cases=('struct Box{pub e:A;}enum A{X(u32),}enum B{X(u32),}'
               'pub fn main_entry()->u32{let b:Box=Box{e:B::X(42)};return 42;}',
               'enum A{X(*mut u8),}struct Box{pub e:A;}pub fn main_entry()->u32{return 42;}',
               'enum A{X(sole u32),}struct Box{pub e:A;}pub fn main_entry()->u32{return 42;}',
               'enum A{X([u64;256],[u64;256]),}pub fn main_entry()->u32{return 42;}')
        for i,source in enumerate(cases):
            self.compile('composed_bad_'+str(i),source,False)

    def test_static_payload_enum_and_nested_record_initializers(self):
        self.program('composed_static_enum', '''struct Config{pub prefix:u8;pub event:Event;pub suffix:u64;}
enum Event{None,Data(u32,[u8;2]),}
static config:Config=Config{prefix:7,event:Event::Data(42,[3;2]),suffix:99};
static empty:Event=Event::None;
pub fn main_entry()->u32{let c:Config=config;if c.prefix!=7 || c.suffix!=99{return 1;}
if match empty{Event::None=>true,_=>false}==false{return 2;}
return match c.event{Event::None=>0,Event::Data(n,bytes)=>{if bytes[1]!=3{return 3;}n}};}''')

    def test_static_enum_arrays_and_mutable_global_replacement(self):
        self.program('composed_static_enum_arrays', '''enum Event{None,Value(u32),}
static mut events:[Event;2]=[Event::Value(20),Event::Value(22)];
pub fn main_entry()->u32{unsafe{events=[events[1],events[0]];}
let x:u32=unsafe{match events[0]{Event::None=>0,Event::Value(n)=>n}};
let y:u32=unsafe{match events[1]{Event::None=>0,Event::Value(n)=>n}};return x+y;}''')

    def test_static_mixed_enum_record_array_graph(self):
        self.program('composed_static_graph', '''enum Packet{Data(Table),Empty,}
struct Table{pub events:[Event;2];}enum Event{Value(u32),None,}
static packet:Packet=Packet::Data(Table{events:[Event::Value(21);2]});
pub fn main_entry()->u32{return match packet{Packet::Data(t)=>match t.events{
[Event::Value(a),Event::Value(b)]=>a+b,_=>0},Packet::Empty=>0};}''')

    def test_zero_discriminant_static_value_can_use_bss(self):
        self.program('composed_static_zero', '''enum Event{None,Value(u32),}
static event:Event=Event::None;
pub fn main_entry()->u32{return match event{Event::None=>42,Event::Value(n)=>n};}''')

    def test_static_aggregate_calls_and_wrong_constructor_rejected(self):
        cases=('enum E{Value(u32),}fn make()->E{return E::Value(42);}static e:E=make();',
               'enum A{Value(u32),}enum B{Value(u32),}static e:A=B::Value(42);',
               'enum E{Value([u32;2]),}static e:E=E::Value([42]);',
               'enum E{Value(u32),}static e:E=E::Value(true);')
        for i,source in enumerate(cases):
            self.compile('composed_static_bad_'+str(i),source+'pub fn main_entry()->u32{return 42;}',False)

    def test_declaration_permutations_execute_the_same_data_model(self):
        declarations=('struct Box{pub event:Event;}', 'enum Event{Value(Leaf),None,}',
                      'struct Leaf{pub value:u64;}')
        body='''pub fn main_entry()->u32{let b:Box=Box{event:Event::Value(Leaf{value:42})};
return match b.event{Event::Value(v)=>v.value as u32,Event::None=>0};}'''
        for index,order in enumerate(itertools.permutations(declarations)):
            with self.subTest(order=order):
                self.program('composed_permutation_'+str(index),''.join(order)+body)

    def test_mixed_stack_argument_and_hidden_return_abi(self):
        self.program('composed_stack_abi', '''struct Box{pub event:Event;pub flag:bool;}
enum Event{None,Value(u64),}
fn pass(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,value:Box)->Box{return value;}
pub fn main_entry()->u32{let b:Box=pass(1,2,3,4,5,6,7,Box{event:Event::Value(42),flag:true});
if !b.flag{return 1;}return match b.event{Event::None=>0,Event::Value(n)=>n as u32};}''')

    def test_exclusive_composed_record_and_deferred_borrow(self):
        self.program('composed_owner_defer', '''struct Box{pub event:Event;}enum Event{None,Value(u32),}
static mut observed:u32=0;
fn observe(b:whisper Box)->void{unsafe{observed=match b.event{Event::None=>0,Event::Value(n)=>n};}return;}
fn pass(b:sole Box)->sole Box{return b;}
fn work()->u32{let a:sole Box=Box{event:Event::Value(42)};let b:sole Box=pass(a);defer observe(b);return 7;}
pub fn main_entry()->u32{if work()!=7{return 1;}return unsafe{observed};}''')

    def test_return_capture_precedes_composed_local_defer(self):
        self.program('composed_return_defer', '''struct Box{pub event:Event;}enum Event{None,Value(u32),}
fn make()->Box{let mut b:Box=Box{event:Event::Value(42)};defer{b.event=Event::None;}return b;}
pub fn main_entry()->u32{return match make().event{Event::None=>0,Event::Value(n)=>n};}''')

    def test_array_guard_cannot_corrupt_the_composed_snapshot(self):
        self.program('composed_guard_snapshot', '''struct Box{pub events:[Event;2];}enum Event{None,Value(u32),}
fn alter(mut b:*mut Box)->bool{unsafe{b.events[0]=Event::Value(0);}return false;}
pub fn main_entry()->u32{let mut b:Box=Box{events:[Event::Value(20),Event::Value(22)]};
let pointer:*mut Box=unsafe{(&mut b) as *mut Box};
let result:u32=match b.events{[Event::Value(a),Event::Value(c)] if alter(pointer)=>0,
[Event::Value(a),Event::Value(c)]=>a+c,_=>0};
if match b.events[0]{Event::Value(n)=>n,Event::None=>1}!=0{return 1;}return result;}''')

    def test_record_pattern_extracts_array_of_enum_values(self):
        self.program('composed_named_array_pattern', '''struct Box{pub events:[Event;2];pub flag:bool;}
enum Event{None,Value(u32),}
pub fn main_entry()->u32{let b:Box=Box{events:[Event::Value(21);2],flag:true};
return match b{Box{events:[Event::Value(a),Event::Value(c)],flag:true}=>a+c,_=>0};}''')

    def test_nominal_array_mismatch_and_owner_use_after_move_rejected(self):
        cases=('enum A{Value(u32),}enum B{Value(u32),}fn read(a:[A;2])->u32{return 42;}'
               'pub fn main_entry()->u32{return read([B::Value(21);2]);}',
               'struct Box{pub event:E;}enum E{Value(u32),}fn take(b:sole Box)->u32{return 42;}'
               'pub fn main_entry()->u32{let b:sole Box=Box{event:E::Value(42)};take(b);'
               'return match b.event{E::Value(n)=>n};}')
        for i,source in enumerate(cases):
            self.compile('composed_nominal_owner_'+str(i),source,False)

    def test_static_padding_inactive_slots_and_bss_bytes(self):
        obj=self.compile('composed_static_bytes', '''enum E{None,Small(u8),Wide(u64),}
static first:E=E::Small(5);static second:E=E::Wide(42);static empty:E=E::None;
pub fn main_entry()->u32{return 42;}''')
        raw=obj.read_bytes();shoff=struct.unpack_from('<Q',raw,40)[0]
        entry_size,count,names_index=struct.unpack_from('<HHH',raw,58)
        headers=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*entry_size) for i in range(count)]
        names=headers[names_index];strings=raw[names[4]:names[4]+names[5]]
        sections={strings[h[0]:].split(b'\0',1)[0].decode():h for h in headers}
        data=sections['.data'];zero=sections['.bss']
        expected=struct.pack('<IB3xQ',1,5,0)+struct.pack('<I4xQ',2,42)
        self.assertEqual(raw[data[4]:data[4]+data[5]],expected)
        self.assertEqual((zero[1],zero[5]),(8,16))

    def test_composed_static_and_call_values_across_scalar_widths(self):
        for typ,value,result in (('u8','21','(a+b) as u32'),('i8','-21','(-a-b) as u32'),
                                ('u16','21','(a+b) as u32'),('i16','-21','(-a-b) as u32'),
                                ('u32','21','a+b'),('i32','-21','(-a-b) as u32'),
                                ('u64','21','(a+b) as u32'),('i64','-21','(-a-b) as u32'),
                                ('f32','21.0','(a+b) as u32'),('f64','21.0','(a+b) as u32'),
                                ('bool','true','if a && b{42}else{0}')):
            with self.subTest(typ=typ):
                self.program('composed_static_width_'+typ,'''struct Box{pub prefix:u8;pub event:E;pub suffix:u16;}
enum E{Data(TYPE,TYPE),Empty,}static box:Box=Box{prefix:7,event:E::Data(VALUE,VALUE),suffix:9};
fn pass(value:Box)->Box{return value;}
pub fn main_entry()->u32{let b:Box=pass(box);if b.prefix!=7 || b.suffix!=9{return 1;}
return match b.event{E::Empty=>0,E::Data(a,b)=>RESULT};}'''.replace('TYPE',typ).replace('VALUE',value).replace('RESULT',result))

    def test_foreign_composed_signatures_and_runtime_arrays_still_rejected(self):
        cases=('struct Box{pub event:E;}enum E{Value(u32),}@extern(C) fn read(value:Box)->u32;',
               'struct Box{pub event:E;}enum E{Value(u32),}@extern(C) fn make()->Box;',
               'struct R{pub pointer:*mut u8;}enum E{Value(R),}struct Box{pub events:[E;2];}',
               'enum E{Value([u8;257]),}struct Box{pub event:E;}',
               'enum E{Value([u32;2]),}struct Box{pub event:E;}static box:Box=Box{event:E::Value([true,false])};')
        for index,source in enumerate(cases):
            self.compile('composed_boundary_'+str(index),source+'pub fn main_entry()->u32{return 42;}',False)

    def test_duplicate_type_names_and_unresolved_fields_rejected(self):
        for index,source in enumerate(('struct E{}enum E{Data(u32),}',
                                       'struct A{}struct A{}', 'enum E{A}enum E{B}',
                                       'struct A{pub missing:Unknown;}',
                                       'enum E{Data(Unknown),}')):
            self.compile('composed_unknown_'+str(index),source+'pub fn main_entry()->u32{return 42;}',False)

    def test_layout_and_variant_capacity_boundaries(self):
        records=''.join('struct R'+str(i)+'{}' for i in range(31))
        self.program('composed_layout_32',records+'enum E{Value(u32),}pub fn main_entry()->u32{return 42;}')
        self.compile('composed_layout_33',records+'struct Extra{}enum E{Value(u32),}pub fn main_entry()->u32{return 42;}',False)
        variants=','.join('V'+str(i) for i in range(255))
        self.program('composed_variants_256','enum E{'+variants+',Data(u32)}pub fn main_entry()->u32{return 42;}')
        self.compile('composed_variants_257','enum E{'+variants+',Data(u32),Extra}pub fn main_entry()->u32{return 42;}',False)
        self.compile('composed_enums_33',''.join('enum E'+str(i)+'{None}' for i in range(33))+
                     'pub fn main_entry()->u32{return 42;}',False)


if __name__ == '__main__':
    unittest.main()
