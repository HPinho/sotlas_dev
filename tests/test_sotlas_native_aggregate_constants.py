"""Native immutable named storage for concrete POD aggregate constants."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous


class NativeAggregateConstantTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_record_constant_and_forward_scalar_fields(self):
        self.program('const_record','''struct Pair{pub a:u32;pub b:u32;}
const PAIR:Pair=Pair{a:LEFT,b:22};const LEFT:u32=20;
pub fn main_entry()->u32{return PAIR.a+PAIR.b;}''')

    def test_scalar_array_lists_and_repetitions(self):
        self.program('const_arrays','''const N:usize=3;const VALUES:[u32;N]=[10,12,20];const ZERO:[u8;2]=[0;2];
pub fn main_entry()->u32{let mut sum:u32=0;for n in VALUES{sum=sum+n;}return sum+ZERO[0]as u32;}''')

    def test_record_array_constants_and_named_dimensions(self):
        self.program('const_record_array','''struct Item{pub n:u32;}const N:usize=2;
const ITEMS:[Item;N]=[Item{n:20},Item{n:22}];pub fn main_entry()->u32{
let mut sum:u32=0;for item in ITEMS{sum=sum+item.n;}return sum;}''')

    def test_nested_records_and_record_array_fields(self):
        self.program('const_nested','''struct Item{pub n:u16;}struct Config{pub items:[Item;2];pub gains:[f64;2];pub enabled:bool;}
const CONFIG:Config=Config{items:[Item{n:20},Item{n:22}],gains:[1.5,2.5],enabled:true};
pub fn main_entry()->u32{if !CONFIG.enabled||CONFIG.gains[0]!=1.5||CONFIG.gains[1]!=2.5{return 1;}
return CONFIG.items[0].n as u32+CONFIG.items[1].n as u32;}''')

    def test_payload_enum_constant_with_explicit_tag(self):
        self.program('const_enum','''enum Message{None=97,Pair([u32;2])=11}
const MESSAGE:Message=Message::Pair([20,22]);
pub fn main_entry()->u32{return if let Message::Pair(items)=MESSAGE{items[0]+items[1]}else{0};}''')

    def test_payload_enum_array_and_unit_variant(self):
        self.program('const_enum_array','''enum Message{None=7,Number(u32)=99}
const MESSAGES:[Message;3]=[Message::Number(20),Message::None,Message::Number(22)];
pub fn main_entry()->u32{let mut sum:u32=0;for message in MESSAGES{
sum=sum+(if let Message::Number(n)=message{n}else{0});}return sum;}''')

    def test_local_copies_are_independent(self):
        self.program('const_copy','''struct Pair{pub items:[u32;2];}const SOURCE:Pair=Pair{items:[20,22]};
const TABLE:[Pair;2]=[Pair{items:[20,22]};2];pub fn main_entry()->u32{
let mut value:Pair=SOURCE;value.items[0]=1;let mut rows:[Pair;2]=TABLE;rows[0]=value;
if SOURCE.items[0]!=20||TABLE[0].items[0]!=20{return 1;}return TABLE[1].items[0]+TABLE[1].items[1];}''')

    def test_constants_in_internal_calls_and_returns(self):
        self.program('const_abi','''struct Pair{pub a:u32;pub b:u32;}const VALUE:Pair=Pair{a:20,b:22};
const VALUES:[u32;2]=[20,22];fn get()->Pair{return VALUE;}fn numbers()->[u32;2]{return VALUES;}
fn read(p:Pair)->u32{return p.a+p.b;}pub fn main_entry()->u32{let xs:[u32;2]=numbers();
if xs[0]+xs[1]!=42{return 1;}return read(get());}''')

    def test_local_and_parameter_shadowing(self):
        self.program('const_shadow','''struct Pair{pub n:u32;}const VALUE:Pair=Pair{n:1};
fn read(VALUE:Pair)->u32{return VALUE.n;}pub fn main_entry()->u32{let VALUE:Pair=Pair{n:20};return VALUE.n+read(Pair{n:22});}''')

    def test_zero_and_nonzero_storage_coexist(self):
        self.program('const_zero','''struct Pair{pub a:u32;pub b:u32;}const EMPTY:Pair=Pair{a:0,b:0};
const READY:Pair=Pair{a:20,b:22};static mut scratch:u32=0;
pub fn main_entry()->u32{scratch=EMPTY.a+1;if scratch!=1{return 1;}return READY.a+READY.b;}''')

    def test_packed_record_constants(self):
        self.program('const_packed','''@packed struct Pair{pub a:u8;pub b:u64;}
const VALUE:Pair=Pair{a:20,b:22};pub fn main_entry()->u32{return VALUE.a as u32+VALUE.b as u32;}''')

    def test_readonly_interior_address(self):
        self.program('const_address','''struct Pair{pub a:u32;pub b:u32;}const VALUE:Pair=Pair{a:20,b:22};
pub fn main_entry()->u32{let p:*const u32=unsafe{(&VALUE.b)as *const u32};return VALUE.a+unsafe{*p};}''')

    def test_float_and_boolean_arrays(self):
        self.program('const_scalar_families','''const VALUES:[f64;2]=[1.5,2.5];const FLAGS:[bool;2]=[true,false];
pub fn main_entry()->u32{if VALUES[0]!=1.5||VALUES[1]!=2.5||!FLAGS[0]||FLAGS[1]{return 1;}return 42;}''')

    def test_readonly_receiver_and_mutable_copy(self):
        self.program('const_methods','''struct Pair{pub n:u32;}impl Pair{
fn read(self:&Self)->u32{return self.n;}fn set(mut self:&mut Self,n:u32){self.n=n;}}
const VALUE:Pair=Pair{n:42};pub fn main_entry()->u32{let mut copy:Pair=VALUE;copy.set(1);
if copy.read()!=1{return 1;}return VALUE.read();}''')
        self.compile('const_mut_method','''struct Pair{pub n:u32;}impl Pair{fn set(mut self:&mut Self,n:u32){self.n=n;}}
const VALUE:Pair=Pair{n:42};pub fn main_entry()->u32{VALUE.set(1);return 42;}''',False)

    def test_mutations_and_mutable_addresses_reject(self):
        for i,operation in enumerate(('VALUE.a=1;','VALUE=Pair{a:1,b:1};','TABLE[0].a=1;',
                                      'TABLE[0]=Pair{a:1,b:1};','let p=&mut VALUE.a;')):
            with self.subTest(operation=operation):
                self.compile('const_mutation_'+str(i),'''struct Pair{pub a:u32;pub b:u32;}
const VALUE:Pair=Pair{a:20,b:22};const TABLE:[Pair;2]=[Pair{a:20,b:22};2];
pub fn main_entry()->u32{unsafe{'''+operation+'''}return 42;}''',False)

    def test_pointer_and_resource_graphs_reject(self):
        for i,declaration in enumerate((
            'const VALUE:[*const u32;2]=0;',
            'struct R{pub p:*const u32;}const VALUE:R=R{p:null};',
            'struct R{pub n:sole u32;}const VALUE:R=R{n:42};',
            'struct R{pub p:*const u32;}const VALUE:[R;1]=[R{p:null}];',
            'enum R{None,Pointer(*const u32)}const VALUE:R=R::None;',
        )):
            with self.subTest(declaration=declaration):
                self.compile('const_resource_'+str(i),declaration+'pub fn main_entry()->u32{return 42;}',False)

    def test_runtime_initializers_and_aggregate_aliases_reject(self):
        for i,declaration in enumerate((
            'struct R{pub n:u32;}fn make()->R{return R{n:42};}const VALUE:R=make();',
            'struct R{pub n:u32;}const FIRST:R=R{n:42};const VALUE:R=FIRST;',
            'struct R{pub n:u32;}const VALUE:[R;2]=[make(),make()];fn make()->R{return R{n:21};}',
        )):
            with self.subTest(declaration=declaration):
                self.compile('const_dynamic_'+str(i),declaration+'pub fn main_entry()->u32{return 42;}',False)

    def test_shapes_nominal_types_and_capacities_reject(self):
        for i,declaration in enumerate((
            'const VALUE:[u32;2]=[42];',
            'const VALUE:[u32;257]=[1;257];',
            'struct R{pub n:u32;}struct Other{pub n:u32;}const VALUE:R=Other{n:42};',
            'struct R{pub n:u8;}const VALUE:R=R{n:256};',
            'struct R{pub items:[u64;256];}const VALUE:[R;3]=[R{items:[1;256]};3];',
            'enum E{None=97,Some(u32)=11}const VALUE:[E;1]=0;',
            'struct R{pub n:u32;}const VALUE:[R;1]=0;',
        )):
            with self.subTest(declaration=declaration):
                self.compile('const_shape_'+str(i),declaration+'pub fn main_entry()->u32{return 42;}',False)

    def test_scalar_constants_keep_forward_resolution_and_cycles_reject(self):
        self.program('const_scalar_compat','''struct R{pub n:u32;}const VALUE:R=R{n:ANSWER};
const ANSWER:u32=LEFT+RIGHT;const LEFT:u32=20;const RIGHT:u32=22;
pub fn main_entry()->u32{return VALUE.n;}''')
        self.compile('const_cycle','''struct R{pub n:u32;}const VALUE:R=R{n:A};const A:u32=B;const B:u32=A;
pub fn main_entry()->u32{return 42;}''',False)

    def test_aggregate_constant_is_not_an_array_dimension(self):
        self.compile('const_not_dimension','''struct R{pub n:usize;}const VALUE:R=R{n:2};
pub fn main_entry()->u32{let xs:[u32;VALUE]=[21;VALUE];return 42;}''',False)

    def test_mutable_receivers_cannot_cross_const_projections(self):
        for i,call in enumerate(('VALUE.set(1);','TABLE[0].set(1);','WRAPPED.item.set(1);','return VALUE.change();')):
            with self.subTest(call=call):
                self.compile('const_receiver_'+str(i),'''struct Pair{pub n:u32;}struct Wrap{pub item:Pair;}
impl Pair{fn set(mut self:&mut Self,n:u32){self.n=n;}fn change(mut self:&mut Self)->u32{self.n=1;return 42;}}
const VALUE:Pair=Pair{n:42};const TABLE:[Pair;1]=[Pair{n:42}];const WRAPPED:Wrap=Wrap{item:Pair{n:42}};
pub fn main_entry()->u32{'''+call+'return 42;}',False)

    def test_readonly_void_receiver_can_observe_a_constant(self):
        self.program('const_receiver_observe','''struct Pair{pub n:u32;}static mut seen:u32=0;
impl Pair{fn observe(self:&Self){unsafe{seen=self.n;}}}const VALUE:Pair=Pair{n:42};
pub fn main_entry()->u32{VALUE.observe();return unsafe{seen};}''')

    def test_checked_in_profile_application(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'examples/native_aggregate_constants/main.sotlas').read_text(encoding='utf-8')
        self.program('const_profiles',source.split(';',1)[1])


if __name__ == '__main__':
    unittest.main()
