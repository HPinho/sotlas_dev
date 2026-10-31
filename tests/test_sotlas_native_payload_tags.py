"""Explicit payload discriminants reach native storage, match and propagation."""
import unittest
import test_sotlas_native_i32 as previous


class NativePayloadTagTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_explicit_tag_is_stored_in_memory(self):
        self.program('payload_tag_bytes','''enum Packet{Empty=3,Data(u64)=32,Tail(u8)}
pub fn main_entry()->u32{let packet:Packet=Packet::Data(42);let p:*const Packet=unsafe{(&packet) as *const Packet};
let address:usize=unsafe{p as usize};let tag:*const u32=unsafe{address as *const u32};if unsafe{*tag}!=32{return 1;}
return match packet{Packet::Empty=>2,Packet::Data(n)=>n as u32,Packet::Tail(n)=>3};}''')

    def test_implicit_tag_follows_explicit_payload_value(self):
        self.program('payload_tag_next','''enum Packet{Empty=3,Data(u64)=32,Tail(u8),Done}
pub fn main_entry()->u32{let packet:Packet=Packet::Tail(42);let p:*const Packet=unsafe{(&packet) as *const Packet};
let address:usize=unsafe{p as usize};let tag:*const u32=unsafe{address as *const u32};if unsafe{*tag}!=33{return 1;}
return match packet{Packet::Empty=>2,Packet::Data(n)=>3,Packet::Tail(n)=>n as u32,Packet::Done=>4};}''')

    def test_radix_tags_and_nonmonotonic_resets(self):
        self.program('payload_tag_radix','''enum Packet{A(u32)=0x20,B(u32)=0b10,C(u32)=0o10,D(u32)}
pub fn main_entry()->u32{let packet:Packet=Packet::D(42);let p:*const Packet=unsafe{(&packet) as *const Packet};
let address:usize=unsafe{p as usize};let tag:*const u32=unsafe{address as *const u32};if unsafe{*tag}!=9{return 1;}
return match packet{Packet::A(n)=>1,Packet::B(n)=>2,Packet::C(n)=>3,Packet::D(n)=>n};}''')

    def test_zero_and_maximum_tags(self):
        self.program('payload_tag_max','''enum Packet{Zero(u32)=0,Max(u32)=4294967295}
pub fn main_entry()->u32{let packet:Packet=Packet::Max(42);let p:*const Packet=unsafe{(&packet) as *const Packet};
let address:usize=unsafe{p as usize};let tag:*const u32=unsafe{address as *const u32};if unsafe{*tag}!=4294967295{return 1;}
return match packet{Packet::Zero(n)=>2,Packet::Max(n)=>n};}''')

    def test_record_array_and_multi_field_payloads(self):
        self.program('payload_tag_fields','''struct Pair{pub a:u32;pub b:u32;}
enum Packet{Data(Pair,[u8;2])=41,Empty=4}
fn make()->Packet{return Packet::Data(Pair{a:20,b:22},[7,9]);}
pub fn main_entry()->u32{return match make(){Packet::Data(p,a)=>if a[1]==9{p.a+p.b}else{1},Packet::Empty=>2};}''')

    def test_nested_tagged_payloads(self):
        self.program('payload_tag_nested','''enum Inner{None=7,Value(u32)=12}enum Outer{Data(Inner)=90,Empty=3}
pub fn main_entry()->u32{let packet:Outer=Outer::Data(Inner::Value(42));return match packet{
Outer::Data(Inner::Value(n))=>n,Outer::Data(Inner::None)=>1,Outer::Empty=>2};}''')

    def test_static_tables_preserve_explicit_tags(self):
        self.program('payload_tag_static','''enum Packet{Empty=5,Data(u32)=33}
static TABLE:[Packet;2]=[Packet::Data(42);2];
pub fn main_entry()->u32{let copy:Packet=unsafe{TABLE[1]};let p:*const Packet=unsafe{(&copy) as *const Packet};
let address:usize=unsafe{p as usize};let tag:*const u32=unsafe{address as *const u32};if unsafe{*tag}!=33{return 1;}return match copy{Packet::Empty=>2,Packet::Data(n)=>n};}''')

    def test_tagged_result_propagation_uses_explicit_success_tag(self):
        self.program('payload_tag_try','''enum Outcome{Err(u32)=7,Ok(u32)=42}
fn source(ok:bool)->Outcome{if ok{return Outcome::Ok(40);}return Outcome::Err(42);}
fn work(ok:bool)->Outcome{let n:u32=source(ok)?;return Outcome::Ok(n+2);}
pub fn main_entry()->u32{let a:u32=match work(true){Outcome::Ok(n)=>n,Outcome::Err(e)=>0};
let b:u32=match work(false){Outcome::Ok(n)=>0,Outcome::Err(e)=>e};if a!=42 || b!=42{return 1;}return 42;}''')

    def test_payload_tag_does_not_change_layout(self):
        self.program('payload_tag_layout','''enum Plain{Empty,Data(u64)}enum Explicit{Empty=9,Data(u64)=77}
pub fn main_entry()->u32{if span_of::<Plain>()!=span_of::<Explicit>() || align_of::<Explicit>()!=8{return 1;}return 42;}''')

    def test_explicit_reset_after_maximum_tag(self):
        self.program('payload_tag_reset','''enum Packet{Max(u32)=4294967295,Zero(u32)=0,Next(u32)}
pub fn main_entry()->u32{let packet:Packet=Packet::Next(42);let p:*const Packet=unsafe{(&packet) as *const Packet};
let address:usize=unsafe{p as usize};let tag:*const u32=unsafe{address as *const u32};if unsafe{*tag}!=1{return 1;}
return match packet{Packet::Max(n)=>2,Packet::Zero(n)=>3,Packet::Next(n)=>n};}''')

    def test_float_and_signed_payloads_keep_explicit_tags(self):
        self.program('payload_tag_float','''enum Packet{Signed(i64)=11,Real(f64)=19}
fn make()->Packet{return Packet::Real(1.5);}pub fn main_entry()->u32{return match make(){
Packet::Signed(n)=>1,Packet::Real(n)=>if n==1.5{42}else{2}};}''')

    def test_qualified_pod_moves_keep_payload_tags(self):
        self.program('payload_tag_move','''enum Packet{Empty=3,Data(u32)=11}
fn take(p:sole Packet)->u32{return match p{Packet::Empty=>1,Packet::Data(n)=>n};}
pub fn main_entry()->u32{let owner:sole Packet=Packet::Data(42);return take(owner);}''')

    def test_duplicate_tags_and_implicit_collisions_rejected(self):
        for index,variants in enumerate(('A(u32)=7,B(u32)=7','A=8,B(u32)=8',
                                         'A(u32)=4,B,C(u32)=5','A(u32)=4294967295,B(u32)')):
            self.compile('payload_tag_duplicate_'+str(index),'enum Packet{'+variants+'}pub fn main_entry()->u32{return 42;}',False)

    def test_invalid_tag_literals_and_expressions_rejected(self):
        for index,tag in enumerate(('-1','4294967296','18446744073709551615','1.5','true','missing','1+2','')):
            self.compile('payload_tag_bad_'+str(index),'enum Packet{Data(u32)='+tag+'}pub fn main_entry()->u32{return 42;}',False)

    def test_wrong_arity_and_unknown_variants_remain_rejected(self):
        for index,constructor in enumerate(('Packet::Data()','Packet::Data(1,2)','Packet::Missing(42)')):
            self.compile('payload_tag_constructor_'+str(index),'enum Packet{Data(u32)=7,Empty=1}'
                         'pub fn main_entry()->u32{let p:Packet='+constructor+';return 42;}',False)


if __name__ == '__main__':
    unittest.main()
