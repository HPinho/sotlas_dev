"""Inline enum arrays and read-only matching of native owned POD payloads."""
import os
import subprocess
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchArrayPayloadTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_scalar_array_literals_and_all_memory_widths(self):
        for typ, value, expression in (
            ('u8', '21', 'a[0] as u32+a[1] as u32'),
            ('i8', '-21', '(-a[0]-a[1]) as u32'),
            ('u16', '21', 'a[0] as u32+a[1] as u32'),
            ('i16', '-21', '(-a[0]-a[1]) as u32'),
            ('u32', '21', 'a[0]+a[1]'), ('i32', '-21', '(-a[0]-a[1]) as u32'),
            ('u64', '21', '(a[0]+a[1]) as u32'), ('i64', '-21', '(-a[0]-a[1]) as u32'),
            ('f32', '21.0', '(a[0]+a[1]) as u32'), ('f64', '21.0', '(a[0]+a[1]) as u32'),
            ('bool', 'true', 'if a[0] && a[1] {42} else {0}'),
        ):
            with self.subTest(typ=typ):
                self.program('payload_array_'+typ, f'''enum Data{{Empty,Values([{typ};2]),}}
pub fn main_entry()->u32{{let d:Data=Data::Values([{value},{value}]);
return match d{{Data::Values(a)=>{expression},Data::Empty=>0}};}}''')

    def test_repetition_evaluates_once_and_list_keeps_order(self):
        self.program('payload_array_order', '''static mut calls:u32=0;
fn next()->u32{unsafe{calls=calls+1;return calls;}}
enum Data{Values([u32;3]),}
pub fn main_entry()->u32{let repeated:Data=Data::Values([next();3]);
let listed:Data=Data::Values([next(),next(),next()]);
let n:u32=match repeated{Data::Values(a)=>a[0]+a[1]+a[2]};
let m:u32=match listed{Data::Values(a)=>a[0]*100+a[1]*10+a[2]};
if n==3 && m==234 && unsafe{calls}==4{return 42;}return 1;}''')

    def test_local_and_record_field_arrays_copy_independently(self):
        self.program('payload_array_copy', '''struct Buffer{pub items:[u32;2];}
enum Data{Values([u32;2]),}
pub fn main_entry()->u32{let mut a:[u32;2]=0;unsafe{a[0]=21;a[1]=21;}let mut b:Buffer=Buffer{items:[20,22]};
let first:Data=Data::Values(a);let second:Data=Data::Values(b.items);
unsafe{a[0]=0;b.items[0]=0;}
return match first{Data::Values(x)=>match second{Data::Values(y)=>x[0]+y[1]-1}};}''')

    def test_record_arrays_nested_patterns_and_nominal_types(self):
        self.program('payload_record_array', '''struct Pair{pub x:u32;pub y:u32;}
enum Inner{Rows([Pair;2]),} enum Outer{None,Some(Inner),}
pub fn main_entry()->u32{let d:Outer=Outer::Some(Inner::Rows([Pair{x:20,y:1},Pair{x:21,y:0}]));
return match d{Outer::Some(Inner::Rows(rows))=>rows[0].x+rows[1].x+rows[0].y,Outer::None=>0};}''')

    def test_record_repeat_and_local_record_array(self):
        self.program('payload_record_repeat', '''struct Item{pub value:u32;}
enum Rows{Data([Item;2]),}
pub fn main_entry()->u32{let items:[Item;2]=[Item{value:21};2];
let d:Rows=Rows::Data(items);return match d{Rows::Data(a)=>a[0].value+a[1].value};}''')

    def test_aggregate_call_return_and_match_result(self):
        self.program('payload_array_abi', '''enum Data{Empty,Values([u64;2]),}
fn make()->Data{return Data::Values([20,22]);}
fn pass(v:Data)->Data{return v;}
pub fn main_entry()->u32{let d:Data=match false{true=>Data::Empty,false=>pass(make())};
return match d{Data::Values(a)=>(a[0]+a[1]) as u32,Data::Empty=>0};}''')

    def test_guard_capture_copies_do_not_alias_later_arms(self):
        self.program('payload_array_guard_copy', '''enum Data{Values([u32;2]),}
fn alter(p:*mut u32)->bool{unsafe{*p=0;}return false;}
pub fn main_entry()->u32{let d:Data=Data::Values([20,22]);
return match d{Data::Values(a) if alter(unsafe{a as *mut u32})=>0,
Data::Values(b)=>b[0]+b[1]};}''')

    def test_alternatives_bind_compatible_arrays(self):
        self.program('payload_array_or', '''enum Data{Left([u32;2]),Right([u32;2]),}
pub fn main_entry()->u32{let d:Data=Data::Right([20,22]);
return match d{Data::Left(a)|Data::Right(a)=>a[0]+a[1]};}''')

    def test_owned_payload_can_be_read_then_consumed(self):
        self.program('payload_owner_read', '''enum Data{Empty,Values([u32;2]),}
fn consume(d:sole Data)->u32{return match d{Data::Values(a)=>a[0]+a[1],Data::Empty=>0};}
pub fn main_entry()->u32{let d:sole Data=Data::Values([20,22]);
let n:u32=match d{Data::Values(a)=>a[0]+a[1],Data::Empty=>0};
if n!=42{return 1;}return consume(d);}''')

    def test_borrowed_payload_parameters_and_statement_match(self):
        self.program('payload_owner_borrows', '''enum Data{Empty,Values([u32;2]),}
fn read(d:whisper Data)->u32{match d{Data::Values(a)=>{return a[0]+a[1];},Data::Empty=>{return 0;}}}
fn forward(d:direct Data)->u32{return read(d);}
pub fn main_entry()->u32{let d:sole Data=Data::Values([20,22]);return forward(d);}''')

    def test_selected_arm_may_consume_original_after_snapshot(self):
        self.program('payload_owner_arm', '''enum Data{Empty,Value(u32),}
fn consume(d:sole Data)->u32{return match d{Data::Value(n)=>n,Data::Empty=>0};}
pub fn main_entry()->u32{let d:sole Data=Data::Value(21);
return match d{Data::Value(n)=>n+consume(d),Data::Empty=>consume(d)};}''')

    def test_borrowed_named_record_subject(self):
        self.program('record_owner_match', '''struct Box{pub n:u32;}
fn read(v:whisper Box)->u32{return match v{Box{n}=>n};}
pub fn main_entry()->u32{let v:sole Box=Box{n:42};return read(v);}''')

    def test_array_payload_return_preserves_lifo_defers(self):
        self.program('payload_array_cleanup', '''static mut trace:u32=0;
enum Data{Values([u32;2]),}
fn mark(n:u32)->void{unsafe{trace=trace*10+n;}return;}
fn choose(d:sole Data)->u32{defer mark(1);return match d{
Data::Values(a)=>{defer mark(2);a[0]+a[1]}};}
pub fn main_entry()->u32{let d:sole Data=Data::Values([20,22]);
let n:u32=choose(d);if unsafe{trace}!=21{return 1;}return n;}''')

    def test_owned_array_subject_on_loop_break_and_continue(self):
        self.program('payload_array_loop', '''enum Data{Values([u32;2]),}
pub fn main_entry()->u32{let d:sole Data=Data::Values([20,22]);let mut i:u32=0;
while i<3{i=i+1;match d{Data::Values(a)=>{if i<3{continue;}return a[0]+a[1];}}}
return 0;}''')

    def test_payload_storage_limit_and_padding(self):
        self.program('payload_array_layout', '''enum Data{A([u64;256]),B([u64;254],u32),}
pub fn main_entry()->u32{let d:Data=Data::B([0;254],42);
return match d{Data::A(a)=>a[0] as u32,Data::B(a,n)=>a[253] as u32+n};}''')

    def test_capture_scope_and_mutability_rejected(self):
        prefix='enum D{V([u32;2]),}pub fn main_entry()->u32{let d:D=D::V([21;2]);'
        bodies=(
            'match d{D::V(a)=>{}}return a[0];}',
            'return match d{D::V(a)=>{a[0]=42;a[0]}};}',
            'return match d{D::V(a)=>{a=[0;2];a[0]}};}',
        )
        for index, body in enumerate(bodies):
            with self.subTest(index=index):
                self.compile('payload_array_capture_invalid_'+str(index), prefix+body, False)

    def test_array_capture_out_of_bounds_traps(self):
        for index in ('2', 'position()'):
            with self.subTest(index=index):
                obj=self.compile('payload_array_bound_'+str(len(index)), '''enum D{V([u32;2]),}
fn position()->u32{return 2;}pub fn main_entry()->u32{let d:D=D::V([21;2]);
return match d{D::V(a)=>a['''+index+''']};}''')
                image=self.link_image(obj)
                if os.name == 'nt':
                    code,_=previous.NativeI32Tests.windows_process_exit_code(self,image)
                else:
                    code=subprocess.run([str(image)],capture_output=True,timeout=15).returncode
                self.assertNotEqual(code,0)
                self.assertNotEqual(code,42)

    def test_wrong_shapes_types_and_unsupported_resources_rejected(self):
        cases = (
            'enum D{V([u32;2]),}pub fn main_entry()->u32{let d:D=D::V([42]);return 42;}',
            'enum D{V([u32;2]),}pub fn main_entry()->u32{let d:D=D::V([1,2,3]);return 42;}',
            'enum D{V([u32;2]),}pub fn main_entry()->u32{let d:D=D::V([21;3]);return 42;}',
            'enum D{V([u32;2]),}pub fn main_entry()->u32{let a:[u64;2]=21;let d:D=D::V(a);return 42;}',
            'enum D{V([u32;2]),}pub fn main_entry()->u32{let d:D=D::V([true,false]);return 42;}',
            'enum D{V([u32;0]),}pub fn main_entry()->u32{return 42;}',
            'enum D{V([u32;257]),}pub fn main_entry()->u32{return 42;}',
            'enum D{A([u64;256]),B([u64;256]),}pub fn main_entry()->u32{return 42;}',
            'enum D{V([*mut u8;2]),}pub fn main_entry()->u32{return 42;}',
            'struct R{pub p:*mut u8;}enum D{V([R;2]),}pub fn main_entry()->u32{return 42;}',
            'struct A{pub n:u32;}struct B{pub n:u32;}enum D{V([A;2]),}pub fn main_entry()->u32{let d:D=D::V([B{n:21};2]);return 42;}',
            'enum D{A([u32;2]),B([u32;3]),}pub fn main_entry()->u32{let d:D=D::A([21;2]);return match d{D::A(a)|D::B(a)=>a[0]};}',
            'enum D{V([u32;2]),}pub fn main_entry()->u32{let d:D=D::V([21;2]);return match d{D::V([a,b])=>a+b};}',
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('payload_array_invalid_'+str(index), source, False)

    def test_owner_moves_guard_consumption_and_borrow_escape_rejected(self):
        prefix='enum D{V(u32),}fn consume(d:sole D)->bool{return true;} '
        bodies=(
            'let d:sole D=D::V(42);consume(d);return match d{D::V(n)=>n};',
            'let d:sole D=D::V(42);return match d{D::V(n) if consume(d)=>n,_=>0};',
            'let d:sole D=D::V(42);match d{D::V(n) if consume(d)=>{return n;},_=>{return 0;}}',
            'let d:sole D=D::V(42);let n:u32=match d{D::V(n) if n==42=>{consume(d);n},_=>0};return match d{D::V(k)=>k};',
        )
        for index, body in enumerate(bodies):
            with self.subTest(index=index):
                self.compile('payload_owner_invalid_'+str(index),prefix+'pub fn main_entry()->u32{'+body+'}',False)


if __name__ == '__main__':
    unittest.main()
