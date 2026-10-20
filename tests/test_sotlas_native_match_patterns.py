"""Recursive native variant patterns and refutable field decision paths."""
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchPatternTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_nested_variants_bind_in_guards_and_results(self):
        self.program('pattern_nested', '''enum Inner{Empty,Number(u32)}enum Outer{Empty,Wrap(Inner)}
fn read(value:Outer)->u32{return match value{
Outer::Wrap(Inner::Number(n)) if n>0=>n,
Outer::Wrap(Inner::Empty)=>1,Outer::Wrap(_)=>0,Outer::Empty=>2};}
pub fn main_entry()->u32{return read(Outer::Wrap(Inner::Number(42)));}''')

    def test_literal_fields_and_boolean_fields(self):
        self.program('pattern_literal', '''enum V{Pair(u8,bool)}
fn read(v:V)->u32{return match v{V::Pair(7,true)=>42,V::Pair(_,_)=>0};}
pub fn main_entry()->u32{if read(V::Pair(7,false))!=0{return 1;}return read(V::Pair(7,true));}''')

    def test_signed_open_and_closed_field_ranges(self):
        self.program('pattern_ranges', '''enum V{Number(i8)}
fn read(v:V)->u32{return match v{V::Number(..0)=>20,V::Number(0..=100)=>22,V::Number(_)=>0};}
pub fn main_entry()->u32{return read(V::Number(-128))+read(V::Number(100));}''')

    def test_constants_remain_value_patterns_inside_fields(self):
        self.program('pattern_const', '''const KEY:u32=7;enum V{Number(u32)}
pub fn main_entry()->u32{let value:V=V::Number(7);return match value{V::Number(KEY)=>42,V::Number(_)=>0};}''')

    def test_scalar_enum_fields_keep_nominal_identity(self):
        self.program('pattern_scalar_enum', '''enum Code{A,B}enum V{Code(Code)}
pub fn main_entry()->u32{let value:V=V::Code(Code::B);
return match value{V::Code(Code::A)=>0,V::Code(Code::B)=>42,V::Code(_)=>1};}''')

    def test_failed_field_pattern_skips_guard(self):
        self.program('pattern_guard_order', '''static mut calls:u32=0;enum V{Pair(u32,u32)}
fn guard(n:u32)->bool{calls=calls+1;return false;}
pub fn main_entry()->u32{let value:V=V::Pair(2,42);let result:u32=match value{
V::Pair(1,n) if guard(n)=>0,V::Pair(2,n) if guard(n)=>0,V::Pair(_,n)=>n};
if calls!=1{return 1;}return result;}''')

    def test_nested_tuple_fields_and_shadowing(self):
        self.program('pattern_nested_scope', '''enum Inner{Pair(u32,u32)}enum Outer{Wrap(Inner,u32)}
pub fn main_entry()->u32{let n:sole u32=20;let value:Outer=Outer::Wrap(Inner::Pair(10,10),2);
let result:u32=match value{Outer::Wrap(Inner::Pair(n,m),bias)=>n+m+bias,Outer::Wrap(_,_)=>0};return n+result;}''')

    def test_statement_patterns_keep_cleanup(self):
        self.program('pattern_statement', '''enum Inner{N(u32)}enum Outer{Wrap(Inner)}
pub fn main_entry()->u32{let mut result:u32=0;let value:Outer=Outer::Wrap(Inner::N(40));
match value{Outer::Wrap(Inner::N(n))=>{defer{result=result+2;}result=n;},Outer::Wrap(_)=>{}}
return result;}''')

    def test_nested_bindings_cannot_escape_or_repeat(self):
        for arms in ('Outer::Wrap(Inner::Pair(n,n))=>n,Outer::Wrap(_)=>0',
                     'Outer::Wrap(Inner::Pair(n,m)) if false=>n,Outer::Wrap(other)=>n'):
            with self.subTest(arms=arms):
                self.compile('pattern_scope_'+str(len(arms)), '''enum Inner{Pair(u32,u32)}enum Outer{Wrap(Inner)}
pub fn main_entry()->u32{let value:Outer=Outer::Wrap(Inner::Pair(20,22));return match value{'''+arms+'''};}''',False)

    def test_wrong_nested_type_and_arity_are_rejected(self):
        for pattern in ('Outer::Wrap(Other::N(n))','Outer::Wrap(Inner::N())','Outer::Wrap(Inner::Missing(n))'):
            with self.subTest(pattern=pattern):
                self.compile('pattern_wrong_'+str(len(pattern)), '''enum Inner{N(u32)}enum Other{N(u32)}enum Outer{Wrap(Inner)}
pub fn main_entry()->u32{let v:Outer=Outer::Wrap(Inner::N(42));return match v{'''+pattern+'''=>42,Outer::Wrap(_)=>0};}''',False)

    def test_refutable_fields_do_not_claim_whole_variant_coverage(self):
        self.compile('pattern_partial', '''enum V{Number(u32)}pub fn main_entry()->u32{
let value:V=V::Number(42);return match value{V::Number(42)=>42};}''',False)

    def test_field_pattern_type_and_bounds_are_checked(self):
        for pattern in ('256','42..=1','true','..='):
            with self.subTest(pattern=pattern):
                self.compile('pattern_field_'+str(len(pattern)), '''enum V{Number(u8)}pub fn main_entry()->u32{
let value:V=V::Number(42);return match value{V::Number('''+pattern+''')=>42,V::Number(_)=>0};}''',False)

    def test_nested_record_binding_can_be_returned(self):
        self.program('pattern_record_result', '''struct Pair{pub items:[u32;2];}
enum Inner{Pair(Pair)}enum Outer{Wrap(Inner)}
fn unpack(v:Outer)->Pair{return match v{Outer::Wrap(Inner::Pair(p))=>p,
Outer::Wrap(_)=>Pair{items:[0,0]}};}
pub fn main_entry()->u32{let p:Pair=unpack(Outer::Wrap(Inner::Pair(Pair{items:[20,22]})));return p.items[0]+p.items[1];}''')

    def test_nested_early_return_and_tail_cleanup(self):
        self.program('pattern_early_cleanup', '''static mut trace:u32=0;enum Inner{N(u32)}enum Outer{Wrap(Inner)}
fn choose(v:Outer)->u32{defer{trace=trace+2;}return match v{
Outer::Wrap(Inner::N(40))=>{return 40;},Outer::Wrap(_)=>0};}
pub fn main_entry()->u32{let answer:u32=choose(Outer::Wrap(Inner::N(40)));return answer+trace;}''')

    def test_full_width_unsigned_field(self):
        self.program('pattern_u64', '''enum V{N(u64)}
pub fn main_entry()->u32{let v:V=V::N(18446744073709551615);return match v{
V::N(18446744073709551615)=>42,V::N(_)=>0};}''')

    def test_float_patterns_and_boolean_ranges_remain_closed(self):
        self.compile('pattern_float','''enum V{N(f64)}pub fn main_entry()->u32{
let v:V=V::N(1.0);return match v{V::N(1.0)=>42,V::N(_)=>0};}''',False)
        self.compile('pattern_bool_range','''enum V{N(bool)}pub fn main_entry()->u32{
let v:V=V::N(true);return match v{V::N(0..=1)=>42,V::N(_)=>0};}''',False)


if __name__ == '__main__':
    unittest.main()
