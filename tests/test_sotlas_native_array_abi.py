"""Bounded native value-array calls and caller-owned aggregate returns."""
import unittest
import test_sotlas_native_i32 as previous


class NativeArrayAbiTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def test_scalar_array_parameter_return_all_widths(self):
        for typ,value,result in (('u8','21','(a+b) as u32'),('i8','-21','(-a-b) as u32'),
                                ('u16','21','(a+b) as u32'),('i16','-21','(-a-b) as u32'),
                                ('u32','21','a+b'),('i32','-21','(-a-b) as u32'),
                                ('u64','21','(a+b) as u32'),('i64','-21','(-a-b) as u32'),
                                ('f32','21.0','(a+b) as u32'),('f64','21.0','(a+b) as u32'),
                                ('bool','true','if a && b{42}else{0}')):
            with self.subTest(typ=typ):
                self.program('array_abi_'+typ,f'''fn pass(values:[{typ};2])->[{typ};2]{{return values;}}
pub fn main_entry()->u32{{let result:[{typ};2]=pass([{value};2]);return match result{{[a,b]=>{result}}};}}''')

    def test_mutable_parameter_is_a_value_copy(self):
        self.program('array_abi_mutation','''fn change(mut values:[u32;2])->u32{values[0]=0;return values[1];}
pub fn main_entry()->u32{let values:[u32;2]=[20,22];if change(values)!=22{return 1;}return values[0]+values[1];}''')

    def test_duplicate_arguments_are_independent(self):
        self.program('array_abi_alias_args','''fn read(mut a:[u32;2],b:[u32;2])->u32{a[0]=0;return b[0]+b[1];}
pub fn main_entry()->u32{let values:[u32;2]=[20,22];return read(values,values);}''')

    def test_argument_copy_precedes_later_argument_effects(self):
        self.program('array_abi_order','''fn alter(p:*mut u32)->u32{unsafe{*p=0;}return 0;}
fn read(a:[u32;2],unused:u32)->u32{return a[0]+a[1];}
pub fn main_entry()->u32{let mut values:[u32;2]=[20,22];let p:*mut u32=unsafe{values as *mut u32};
let n:u32=read(values,alter(p));if values[0]!=0{return 1;}return n;}''')

    def test_return_literals_matches_and_conditionals(self):
        self.program('array_abi_results','''fn make(flag:bool)->[u32;2]{return match flag{true=>[20,22],false=>[0;2]};}
fn other()->[u32;2]{return if true{[21;2]}else{[0;2]};}
pub fn main_entry()->u32{let a:[u32;2]=make(true);let b:[u32;2]=other();
if b[0]+b[1]!=42{return 1;}return a[0]+a[1];}''')

    def test_return_copy_precedes_lifo_defer(self):
        self.program('array_abi_return_defer','''static mut trace:u32=0;
fn make()->[u32;2]{let mut a:[u32;2]=[20,22];defer{unsafe{trace=trace*10+1;}}
defer{a[0]=0;unsafe{trace=trace*10+2;}}return a;}
pub fn main_entry()->u32{let result:[u32;2]=make();if unsafe{trace}!=21{return 1;}return result[0]+result[1];}''')

    def test_forwarding_nested_calls_and_recursion(self):
        self.program('array_abi_recursive','''fn make(n:u32)->[u32;2]{if n==0{return [20,22];}return make(n-1);}
fn pass(a:[u32;2])->[u32;2]{return a;}fn sum(a:[u32;2])->u32{return a[0]+a[1];}
pub fn main_entry()->u32{return sum(pass(make(3)));}''')

    def test_returned_array_is_a_match_subject_and_inferred_local(self):
        self.program('array_abi_subject','''fn make()->[u32;2]{return [20,22];}
pub fn main_entry()->u32{let a=make();if a[0]+a[1]!=42{return 1;}return match make(){[x,y]=>x+y};}''')

    def test_record_arrays_keep_nominal_layout(self):
        self.program('array_abi_records','''struct Row{pub n:u32;pub bytes:[u8;2];}
fn pass(mut a:[Row;2])->[Row;2]{a[0].n=20;return a;}
pub fn main_entry()->u32{let input:[Row;2]=[Row{n:1,bytes:[7;2]},Row{n:22,bytes:[9;2]}];
let result:[Row;2]=pass(input);if input[0].n!=1 || result[1].bytes[1]!=9{return 1;}
return result[0].n+result[1].n;}''')

    def test_calls_initialize_fields_and_payloads(self):
        self.program('array_abi_containers','''fn make()->[u32;2]{return [20,22];}
struct Table{pub n:u8;pub items:[u32;2];}enum Packet{Data([u32;2]),}
pub fn main_entry()->u32{let t:Table=Table{n:7,items:make()};let p:Packet=Packet::Data(make());
if t.n!=7 || t.items[0]+t.items[1]!=42{return 1;}return match p{Packet::Data([a,b])=>a+b};}''')

    def test_stack_arguments_and_hidden_return_storage(self):
        self.program('array_abi_stack','''fn make(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,v:[u32;2])->[u32;2]{
return [a+b+c+d+e+f+g+v[0],v[1]];}
pub fn main_entry()->u32{let a:[u32;2]=make(1,2,3,4,5,6,7,[7,7]);return a[0]+a[1];}''')

    def test_maximum_bounded_array(self):
        self.program('array_abi_256','''fn pass(a:[u64;256])->[u64;256]{return a;}
pub fn main_entry()->u32{let result:[u64;256]=pass([21;256]);return match result{[a,..,b]=>(a+b) as u32};}''')

    def test_void_functions_and_immutable_parameters(self):
        self.program('array_abi_void','''fn observe(a:[u32;2])->void{if a[0]+a[1]!=42{return;}return;}
pub fn main_entry()->u32{observe([20,22]);return 42;}''')
        self.program('array_abi_deferred_void','''static mut original:u32=0;
fn change(mut a:[u32;2])->void{a[0]=0;return;}
fn make()->[u32;2]{let a:[u32;2]=[20,22];defer{unsafe{original=a[0];}}defer change(a);return a;}
pub fn main_entry()->u32{let a:[u32;2]=make();if unsafe{original}!=20{return 1;}return a[0]+a[1];}''')
        self.compile('array_abi_immutable','''fn bad(a:[u32;2])->void{a[0]=0;return;}
pub fn main_entry()->u32{return 42;}''',False)

    def test_shape_type_and_nominal_mismatches_rejected(self):
        for index,arg in enumerate(('[1]','[1,2,3]','[21;3]','[true,false]','[1.0,2.0]','42')):
            with self.subTest(arg=arg):
                self.compile('array_abi_wrong_arg_'+str(index),'fn read(a:[u32;2])->u32{return 42;}pub fn main_entry()->u32{return read('+arg+');}',False)
        self.compile('array_abi_wrong_return','fn bad()->[u32;2]{return [42];}pub fn main_entry()->u32{return 42;}',False)
        self.compile('array_abi_dead_return','fn bad()->[u32;2]{return [20,22];return [42];}pub fn main_entry()->u32{return 42;}',False)
        self.compile('array_abi_dead_call','fn read(a:[u32;2])->u32{return 42;}pub fn main_entry()->u32{return 42;read([1]);}',False)
        self.compile('array_abi_wrong_nominal','''struct A{pub n:u32;}struct B{pub n:u32;}
fn read(a:[A;2])->u32{return 42;}pub fn main_entry()->u32{return read([B{n:21};2]);}''',False)

    def test_foreign_resource_and_qualified_array_abi_rejected(self):
        cases=(
            '@extern(C) fn read(a:[u32;2])->u32;pub fn main_entry()->u32{return 42;}',
            '@extern(C) fn make()->[u32;2];pub fn main_entry()->u32{return 42;}',
            'fn read(a:[*mut u8;2])->u32{return 42;}pub fn main_entry()->u32{return 42;}',
            'fn read(a:[u32;257])->u32{return 42;}pub fn main_entry()->u32{return 42;}',
            'fn read(a:shared [u32;2])->u32{return 42;}pub fn main_entry()->u32{return 42;}',
        )
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('array_abi_rejected_'+str(index),source,False)


if __name__ == '__main__':
    unittest.main()
