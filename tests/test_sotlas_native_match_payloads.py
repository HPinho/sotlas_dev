"""Native tagged payload construction, ABI, pattern bindings and coverage."""
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchPayloadTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_scalar_payload_parameter_and_return(self):
        self.program('payload_abi', '''enum Value{Empty,Number(u32)}
fn make(n:u32)->Value{return Value::Number(n);}
fn read(v:Value)->u32{return match v{Value::Empty=>0,Value::Number(n)=>n};}
pub fn main_entry()->u32{return read(make(42));}''')

    def test_multiple_fields_and_unit_variant(self):
        self.program('payload_tuple', '''enum Value{Empty,Pair(u16,u32)}
fn read(v:Value)->u32{return match v{Value::Empty=>2,Value::Pair(a,b)=>(a as u32)+b};}
pub fn main_entry()->u32{let empty:Value=Value::Empty;return read(Value::Pair(20,20))+read(empty);}''')

    def test_guard_fallthrough_and_wildcard_fields(self):
        self.program('payload_guards', '''enum Value{None,Pair(u32,u32)}
fn read(v:Value)->u32{return match v{Value::Pair(a,b) if a>b=>1,
Value::Pair(_,answer)=>answer,Value::None=>0};}
pub fn main_entry()->u32{return read(Value::Pair(2,42));}''')

    def test_record_payload_and_nested_array(self):
        self.program('payload_record', '''struct Pair{pub data:[u32;2];}
enum Value{None,Some(Pair)}
fn read(v:Value)->u32{return match v{Value::None=>0,Value::Some(p)=>p.data[0]+p.data[1]};}
pub fn main_entry()->u32{return read(Value::Some(Pair{data:[20,22]}));}''')

    def test_payload_enum_as_match_result(self):
        self.program('payload_result', '''enum Value{None,Some(u32)}
fn choose(b:bool)->Value{return match b{true=>Value::Some(42),false=>Value::None};}
pub fn main_entry()->u32{let v:Value=choose(true);return match v{Value::None=>0,Value::Some(n)=>n};}''')

    def test_statement_match_and_arm_cleanup(self):
        self.program('payload_cleanup', '''enum Value{None,Some(u32)}
pub fn main_entry()->u32{let mut count:u32=0;let v:Value=Value::Some(40);
match v{Value::None=>{return 1;},Value::Some(n)=>{defer{count=count+2;}count=n;}}
return count;}''')

    def test_payload_expression_subject(self):
        self.program('payload_subject', '''enum Value{None,Some(i32)}
pub fn main_entry()->u32{return match Value::Some(-42){Value::None=>0,Value::Some(n)=>(-n) as u32};}''')

    def test_bindings_do_not_escape(self):
        self.compile('payload_escape', '''enum V{A(u32)}pub fn main_entry()->u32{
let v:V=V::A(42);let r:u32=match v{V::A(n)=>n};return n;}''', False)

    def test_binding_names_must_be_distinct(self):
        self.compile('payload_duplicate', '''enum V{A(u32,u32)}pub fn main_entry()->u32{
let v:V=V::A(20,22);return match v{V::A(n,n)=>n};}''', False)

    def test_pattern_arity(self):
        for pattern in ('V::A()', 'V::A(a,b)', 'V::A'):
            with self.subTest(pattern=pattern):
                self.compile('payload_arity_'+str(len(pattern)), '''enum V{A(u32)}pub fn main_entry()->u32{
let v:V=V::A(42);return match v{'''+pattern+'''=>42};}''', False)

    def test_constructor_arity(self):
        for call in ('V::A()', 'V::A(1,2)'):
            with self.subTest(call=call):
                self.compile('constructor_arity_'+str(len(call)), '''enum V{A(u32)}pub fn main_entry()->u32{
let v:V='''+call+''';return 42;}''', False)

    def test_constructor_type_and_overflow(self):
        for value in ('256', 'true'):
            with self.subTest(value=value):
                self.compile('constructor_type_'+value, '''enum V{A(u8)}pub fn main_entry()->u32{
let v:V=V::A('''+value+''');return 42;}''', False)

    def test_coverage_and_nominal_identity(self):
        for arms in ('V::A(n)=>n', 'Other::A(n)=>n,V::B=>0', 'V::A(n) if n>0=>n,V::B=>0'):
            with self.subTest(arms=arms):
                self.compile('payload_coverage_'+str(len(arms)), '''enum V{A(u32),B}enum Other{A(u32)}
pub fn main_entry()->u32{let v:V=V::A(42);return match v{'''+arms+'''};}''', False)

    def test_resource_and_pointer_payloads_fail_closed(self):
        for typ in ('*mut u32', 'sole u32'):
            with self.subTest(typ=typ):
                self.compile('payload_resource_'+str(len(typ)), 'enum V{A('+typ+''')}
pub fn main_entry()->u32{return 42;}''', False)

    def test_duplicate_discriminants(self):
        self.compile('payload_discriminants', '''enum V{A(u32),B=0}
pub fn main_entry()->u32{return 42;}''', False)

    def test_float_and_boolean_payloads(self):
        self.program('payload_float_bool', '''enum V{Data(f64,bool)}
pub fn main_entry()->u32{let v:V=V::Data(40.0,true);return match v{
V::Data(n,ready)=>{if ready{return (n as u32)+2;}0}};}''')

    def test_inferred_enum_locals(self):
        self.program('payload_inferred', '''enum V{Empty,Some(u32)}
fn read(value:V)->u32{return match value{V::Empty=>2,V::Some(n)=>n};}
pub fn main_entry()->u32{let value=V::Some(40);let empty=V::Empty;return read(value)+read(empty);}''')

    def test_nested_enum_binding(self):
        self.program('payload_nested', '''enum Inner{None,Some(u32)}enum Outer{Value(Inner)}
pub fn main_entry()->u32{let v:Outer=Outer::Value(Inner::Some(42));return match v{
Outer::Value(inner)=>match inner{Inner::None=>0,Inner::Some(n)=>n}};}''')

    def test_binding_can_return_record_payload(self):
        self.program('payload_record_return', '''struct Box{pub value:u32;}enum V{Some(Box)}
fn unpack(v:V)->Box{return match v{V::Some(box)=>box};}
pub fn main_entry()->u32{let box:Box=unpack(V::Some(Box{value:42}));return box.value;}''')

    def test_constructor_copies_payload_storage(self):
        self.program('payload_record_independent', '''struct Box{pub value:u32;}enum V{Some(Box)}
pub fn main_entry()->u32{let mut box:Box=Box{value:42};let v:V=V::Some(box);box.value=1;
return match v{V::Some(captured)=>captured.value};}''')

    def test_subject_and_eligible_guard_execute_once(self):
        self.program('payload_once', '''let mut calls:u32=0;enum V{Some(u32)}
fn create()->V{calls=calls+1;return V::Some(40);}
fn eligible(n:u32)->bool{calls=calls+1;return true;}
pub fn main_entry()->u32{let result:u32=match create(){V::Some(n) if eligible(n)=>n,V::Some(n)=>0};
return result+calls;}''')

    def test_bindings_are_immutable_and_scoped_per_arm(self):
        for expression in ('V::Some(n)=>{n=42;n}', 'V::Some(n) if false=>n,V::Some(other)=>n'):
            with self.subTest(expression=expression):
                self.compile('payload_binding_scope_'+str(len(expression)), '''enum V{Some(u32)}
pub fn main_entry()->u32{let v:V=V::Some(42);return match v{'''+expression+'''};}''', False)

    def test_unknown_variant_is_not_discriminant_zero(self):
        self.compile('payload_unknown', '''enum V{Some(u32)}
pub fn main_entry()->u32{let v:V=V::Some(42);return match v{V::Missing(n)=>n};}''', False)

    def test_unsupported_forward_layouts_fail_closed(self):
        for declarations in ('enum Outer{Wrap(Inner)}enum Inner{Some(u32)}',
                             'enum V{Some(u32)}struct Box{pub value:V;}',
                             'enum V{Some(u32)}struct Box{pub value:[V;2];}'):
            with self.subTest(declarations=declarations):
                self.compile('payload_layout_'+str(len(declarations)), declarations+
                             'pub fn main_entry()->u32{return 42;}', False)


if __name__ == '__main__':
    unittest.main()
