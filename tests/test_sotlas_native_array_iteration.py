"""Snapshot array iteration through the native structured CFG."""
import unittest
import test_sotlas_native_i32 as previous


class NativeArrayIterationTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_scalar_array_sum(self):
        self.program('each_sum','''pub fn main_entry()->u32{let values:[u32;3]=[10,12,20];
let mut total:u32=0;for item in values{total=total+item;}return total;}''')

    def test_snapshot_is_independent_from_original_updates(self):
        self.program('each_snapshot','''pub fn main_entry()->u32{let mut values:[u32;2]=[20,22];
let mut total:u32=0;for item in values{values[1]=99;total=total+item;}return total;}''')

    def test_record_items_are_independent_copies(self):
        self.program('each_records','''struct Row{pub value:u32;}
pub fn main_entry()->u32{let rows:[Row;2]=[Row{value:20},Row{value:22}];let mut total:u32=0;
for mut row in rows{total=total+row.value;row.value=1;}if rows[0].value!=20{return 1;}return total;}''')

    def test_returned_array_expression_runs_once(self):
        self.program('each_call','''static mut calls:u32=0;fn make()->[u32;2]{unsafe{calls=calls+1;}return [20,22];}
pub fn main_entry()->u32{let mut total:u32=0;for item in make(){total=total+item;}
if unsafe{calls}!=1{return 1;}return total;}''')

    def test_record_field_array(self):
        self.program('each_field','''struct Batch{pub values:[u32;2];}
pub fn main_entry()->u32{let b:Batch=Batch{values:[20,22]};let mut total:u32=0;
for item in b.values{total=total+item;}return total;}''')

    def test_nested_loops_and_hidden_name_hygiene(self):
        self.program('each_nested','''pub fn main_entry()->u32{let outer:[u32;2]=[3,4];let inner:[u32;2]=[2,4];
let mut total:u32=0;for a in outer{for b in inner{total=total+a*b;}}return total;}''')

    def test_continue_break_and_nested_branches(self):
        self.program('each_jumps','''pub fn main_entry()->u32{let a:[u32;5]=[1,20,22,99,100];
let mut sum:u32=0;for n in a{if n==1{continue;}if n==99{break;}sum=sum+n;}return sum;}''')

    def test_defer_runs_for_normal_continue_break_paths(self):
        self.program('each_cleanup','''static mut trace:u32=0;fn mark(n:u32)->void{unsafe{trace=trace+n;}return;}
pub fn main_entry()->u32{let a:[u32;3]=[10,12,20];for n in a{defer mark(n);if n==10{continue;}if n==20{break;}}
return unsafe{trace};}''')

    def test_early_return_and_named_dimensions(self):
        self.program('each_return','''const COUNT:usize=2;fn find()->u32{let a:[u32;COUNT]=[1,42];
for n in a{if n==42{return n;}}return 0;}pub fn main_entry()->u32{return find();}''')

    def test_scalar_widths_and_boolean_values(self):
        for typ,value,condition in (('u8','21','n==21'),('i16','-21','n==-21'),
                                    ('u64','4294967297','n==4294967297'),('f64','1.5','n==1.5'),('bool','true','n')):
            with self.subTest(typ=typ):
                self.program('each_'+typ,'pub fn main_entry()->u32{let a:['+typ+';2]=['+value+';2];'
                             'let mut total:u32=0;for n in a{if '+condition+'{total=total+21;}else{return 1;}}return total;}')

    def test_immutable_binding_and_out_of_scope_use_rejected(self):
        for index,body in enumerate(('for n in a{n=1;}return 42;','for n in a{}return n;')):
            self.compile('each_scope_bad_'+str(index),'pub fn main_entry()->u32{let a:[u32;2]=[20,22];'+body+'}',False)

    def test_non_arrays_and_qualified_arrays_rejected(self):
        self.compile('each_scalar_bad','pub fn main_entry()->u32{let a:u32=42;for n in a{}return 42;}',False)
        for domain in ('sole','exclusive','shared','whisper','direct'):
            self.compile('each_domain_'+domain,'pub fn main_entry()->u32{let a:'+domain+' [u32;2]=[20,22];for n in a{}return 42;}',False)

    def test_array_parameters_and_mutable_scalar_copies(self):
        self.program('each_param','''fn sum(a:[u32;2])->u32{let mut total:u32=0;
for mut n in a{n=n+1;total=total+n;}return total;}
pub fn main_entry()->u32{let a:[u32;2]=[19,21];let result:u32=sum(a);if a[0]!=19{return 1;}return result;}''')

    def test_success_array_and_error_propagation_cleanup(self):
        self.program('each_try','''enum Outcome{Ok([u32;2]),Err(u32)}static mut trace:u32=0;
fn source(ok:bool)->Outcome{if ok{return Outcome::Ok([20,22]);}return Outcome::Err(42);}
fn work(ok:bool)->Outcome{defer{unsafe{trace=trace+1;}}for n in source(ok)?{unsafe{trace=trace+n;}}return Outcome::Ok([0;2]);}
pub fn main_entry()->u32{let success:Outcome=work(true);if unsafe{trace}!=43{return 1;}
unsafe{trace=0;}let failure:Outcome=work(false);if unsafe{trace}!=1{return 2;}
return match failure{Outcome::Ok(a)=>3,Outcome::Err(e)=>e};}''')

    def test_range_loops_can_nest_in_array_loops(self):
        self.program('each_range','''pub fn main_entry()->u32{let a:[u32;2]=[10,11];let mut total:u32=0;
for n in a{for i in 0..2{total=total+n;}}return total;}''')

    def test_shadowing_and_repeated_loops_keep_scopes(self):
        self.program('each_shadow','''pub fn main_entry()->u32{let n:u32=99;let a:[u32;2]=[10,11];
let mut total:u32=0;for n in a{total=total+n;}for n in a{total=total+n;}if n!=99{return 1;}return total;}''')

    def test_empty_body_still_evaluates_the_source_once(self):
        self.program('each_empty','''static mut calls:u32=0;fn make()->[u32;2]{unsafe{calls=calls+1;}return [1,2];}
pub fn main_entry()->u32{for n in make(){}if unsafe{calls}!=1{return 1;}return 42;}''')

    def test_pointer_resource_and_excessive_snapshot_rejected(self):
        cases=('let p:*const u32=null;for n in p{}',
               'let a:[u8;257]=[0;257];for n in a{}',
               'let a:[u32;2]=[20,22];for n in [20,22]{}')
        for index,body in enumerate(cases):
            self.compile('each_shape_bad_'+str(index),'pub fn main_entry()->u32{'+body+'return 42;}',False)
        self.compile('each_pointer_record','''struct Cell{pub p:*mut u32;}
pub fn main_entry()->u32{let a:[Cell;2]=[Cell{p:null};2];for cell in a{}return 42;}''',False)

    def test_payload_enum_items_can_be_matched(self):
        self.program('each_enum','''enum Event{Skip=1,Value(u32)=9}
pub fn main_entry()->u32{let events:[Event;3]=[Event::Value(20),Event::Skip,Event::Value(22)];
let mut total:u32=0;for event in events{match event{Event::Skip=>{},Event::Value(n)=>{total=total+n;}}}return total;}''')

    def test_maximum_iteration_count(self):
        self.program('each_max','''pub fn main_entry()->u32{let values:[u8;256]=[1;256];let mut count:u32=0;
for n in values{count=count+n as u32;}if count!=256{return 1;}return 42;}''')

    def test_return_runs_current_iteration_cleanup(self):
        self.program('each_return_cleanup','''static mut trace:u32=0;fn mark(n:u32)->void{unsafe{trace=trace+n;}return;}
fn work()->u32{let a:[u32;2]=[20,22];for n in a{defer mark(n);if n==22{return n;}}return 0;}
pub fn main_entry()->u32{let n:u32=work();if n!=22 || unsafe{trace}!=42{return 1;}return 42;}''')


if __name__ == '__main__':
    unittest.main()
