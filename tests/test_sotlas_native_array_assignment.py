"""Whole-array assignment stages values before publishing native storage."""
import unittest
import test_sotlas_native_i32 as previous


class NativeArrayAssignmentTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_local_scalar_widths_and_boolean_values(self):
        for typ,value,result in (('u8','21','(a[0]+a[1]) as u32'),('i8','-21','(-a[0]-a[1]) as u32'),
                                ('u16','21','(a[0]+a[1]) as u32'),('i16','-21','(-a[0]-a[1]) as u32'),
                                ('u32','21','a[0]+a[1]'),('i32','-21','(-a[0]-a[1]) as u32'),
                                ('u64','21','(a[0]+a[1]) as u32'),('i64','-21','(-a[0]-a[1]) as u32'),
                                ('f32','21.0','(a[0]+a[1]) as u32'),('f64','21.0','(a[0]+a[1]) as u32'),
                                ('bool','true','if a[0] && a[1]{42}else{0}')):
            with self.subTest(typ=typ):
                self.program('array_assign_'+typ, 'pub fn main_entry()->u32{let mut a:['+typ+';2]=0;'
                             'a=['+value+';2];return '+result+';}')

    def test_stored_only_assignment_and_shape_whitespace(self):
        self.program('array_assign_stored', '''pub fn main_entry()->u32{
let mut a:[u32;2]=0;let mut b:[ u32 ; 2 ]=0;b[0]=20;b[1]=22;
a=b;b[0]=0;return a[0]+a[1];}''')

    def test_self_reordering_is_a_complete_snapshot(self):
        self.program('array_assign_self', '''pub fn main_entry()->u32{
let mut a:[u32;2]=[20,22];a=[a[1],a[0]];
if a[0]!=22 || a[1]!=20{return 1;}a=a;return a[0]+a[1];}''')

    def test_repetition_evaluates_once_and_lists_in_order(self):
        self.program('array_assign_order', '''static mut calls:u32=0;
fn next()->u32{unsafe{calls=calls+1;return calls;}}
pub fn main_entry()->u32{let mut a:[u32;2]=0;a=[next();2];
if unsafe{calls}!=1 || a[0]!=1 || a[1]!=1{return 1;}
a=[next(),next()];if unsafe{calls}!=3 || a[0]!=2 || a[1]!=3{return 2;}return 42;}''')

    def test_call_match_and_conditional_results(self):
        self.program('array_assign_values', '''fn make()->[u32;2]{return [20,22];}
pub fn main_entry()->u32{let mut a:[u32;2]=0;a=make();
if a[0]+a[1]!=42{return 1;}a=match true{true=>[21;2],false=>[0;2]};
if a[0]+a[1]!=42{return 2;}a=if false{[0;2]}else{make()};return a[0]+a[1];}''')

    def test_value_block_tail_is_captured_before_defer(self):
        self.program('array_assign_defer', '''pub fn main_entry()->u32{
let mut a:[u32;2]=[20,22];a=match true{true=>{defer{a[0]=0;}a},false=>[0;2]};
return a[0]+a[1];}''')

    def test_early_return_does_not_publish_incomplete_assignment(self):
        self.program('array_assign_early', '''static mut observed:u32=0;
fn work()->u32{let mut a:[u32;2]=[20,22];defer{unsafe{observed=a[0]+a[1];}}
a=match true{true=>{return 7;},false=>[0;2]};return 9;}
pub fn main_entry()->u32{if work()!=7{return 1;}return unsafe{observed};}''')

    def test_record_arrays_copy_all_nested_storage(self):
        self.program('array_assign_records', '''struct Row{pub n:u32;pub bytes:[u8;2];}
pub fn main_entry()->u32{let mut a:[Row;2]=[Row{n:20,bytes:[7;2]},Row{n:22,bytes:[9;2]}];
a=[a[1],a[0]];if a[0].n!=22 || a[0].bytes[1]!=9 || a[1].bytes[0]!=7{return 1;}
a=[Row{n:21,bytes:[3;2]};2];return a[0].n+a[1].n;}''')

    def test_inline_fields_accept_all_contextual_array_forms(self):
        self.program('array_assign_fields', '''struct Row{pub items:[u32;2];}
fn make()->[u32;2]{return [20,22];}
pub fn main_entry()->u32{let mut r:Row=Row{items:[0;2]};r.items=make();
r.items=match true{true=>[r.items[1],r.items[0]],false=>[0;2]};
if r.items[0]!=22{return 1;}r.items=if true{[21;2]}else{[0;2]};return r.items[0]+r.items[1];}''')

    def test_nested_record_array_field_destination_is_evaluated_once(self):
        self.program('array_assign_destination', '''struct Row{pub items:[u32;2];}
static mut calls:u32=0;fn index()->u32{unsafe{calls=calls+1;}return 1;}
pub fn main_entry()->u32{let mut rows:[Row;2]=[Row{items:[0;2]};2];
rows[index()].items=[20,22];if unsafe{calls}!=1 || rows[0].items[0]!=0{return 1;}
return rows[1].items[0]+rows[1].items[1];}''')

    def test_pointer_destination_is_captured_before_rhs_mutation(self):
        self.program('array_assign_pointer', '''struct Row{pub items:[u32;2];}
pub fn main_entry()->u32{let mut a:Row=Row{items:[0;2]};let mut b:Row=Row{items:[1;2]};
let mut p:*mut Row=unsafe{(&mut a) as *mut Row};
unsafe{p.items=match true{true=>{p=(&mut b) as *mut Row;[20,22]},false=>[0;2]};}
if b.items[0]!=1{return 1;}return a.items[0]+a.items[1];}''')

    def test_mutable_value_parameter_is_private_to_the_callee(self):
        self.program('array_assign_param', '''fn work(mut a:[u32;2])->u32{a=[20,22];return a[0]+a[1];}
pub fn main_entry()->u32{let a:[u32;2]=[1;2];if work(a)!=42 || a[0]!=1{return 1;}return 42;}''')

    def test_moved_owner_can_be_reinitialized(self):
        self.program('array_assign_owner', '''fn consume(a:sole [u32;2])->u32{return a[0]+a[1];}
pub fn main_entry()->u32{let mut a:sole [u32;2]=[1;2];let first:u32=consume(a);
a=[20,22];if first!=2{return 1;}return consume(a);}''')

    def test_moved_owner_can_receive_another_owner(self):
        self.program('array_assign_owner_move', '''fn consume(a:sole [u32;2])->u32{return a[0]+a[1];}
pub fn main_entry()->u32{let mut a:sole [u32;2]=[1;2];let b:sole [u32;2]=[20,22];
let ignored:u32=consume(a);a=b;return consume(a);}''')

    def test_definite_moved_join_can_reinitialize_but_maybe_moved_cannot(self):
        prefix='fn consume(a:sole [u32;2])->u32{return a[0]+a[1];}'
        self.program('array_assign_owned_join',prefix+'''pub fn main_entry()->u32{
let mut a:sole [u32;2]=[1;2];if true{consume(a);}else{consume(a);}
a=[20,22];return consume(a);}''')
        self.compile('array_assign_owned_maybe',prefix+'''pub fn main_entry()->u32{
let mut a:sole [u32;2]=[1;2];if true{consume(a);}a=[20,22];return consume(a);}''',False)

    def test_global_array_assignment_requires_mutability_and_unsafe(self):
        self.program('array_assign_global', '''static mut a:[u32;2]=[0;2];
pub fn main_entry()->u32{unsafe{a=[20,22];}return unsafe{a[0]+a[1]};}''')
        for i,source in enumerate(('static a:[u32;2]=[0;2];pub fn main_entry()->u32{unsafe{a=[20,22];}return 42;}',
                                  'static mut a:[u32;2]=[0;2];pub fn main_entry()->u32{a=[20,22];return 42;}')):
            self.compile('array_assign_global_bad_'+str(i),source,False)

    def test_global_pod_record_arrays_and_nested_fields(self):
        self.program('array_assign_global_records', '''struct Row{pub n:u32;pub bytes:[u8;2];}
static mut rows:[Row;2]=[Row{n:0,bytes:[0;2]};2];
fn make()->[Row;2]{return [Row{n:20,bytes:[7;2]},Row{n:22,bytes:[9;2]}];}
pub fn main_entry()->u32{unsafe{rows=make();rows[0].bytes=[3;2];
if rows[0].bytes[1]!=3 || rows[1].bytes[0]!=9{return 1;}return rows[0].n+rows[1].n;}}''')

    def test_maximum_bounded_assignment_and_loop_edges(self):
        self.program('array_assign_max', '''pub fn main_entry()->u32{let mut a:[u64;256]=0;
let mut n:u32=0;while n<3{a=[21;256];n=n+1;if n==1{continue;}break;}
return (a[0]+a[255]) as u32;}''')

    def test_bad_shape_type_and_nominal_identity_rejected_even_in_dead_code(self):
        for i,value in enumerate(('[42]','[1,2,3]','[21;3]','[true,false]','[1.0,2.0]',
                                  'match true{true=>[20,22],false=>[42]}','if true{[20,22]}else{[42]}')):
            self.compile('array_assign_bad_'+str(i),
                         'pub fn main_entry()->u32{let mut a:[u32;2]=0;return 42;a='+value+';}',False)
        self.compile('array_assign_nominal', '''struct A{pub n:u32;}struct B{pub n:u32;}
pub fn main_entry()->u32{let mut a:[A;2]=[A{n:21};2];a=[B{n:21};2];return 42;}''',False)

    def test_immutable_borrowed_and_live_owned_destinations_rejected(self):
        cases=('pub fn main_entry()->u32{let a:[u32;2]=[0;2];a=[20,22];return 42;}',
               'fn bad(mut a:whisper [u32;2])->u32{a=[20,22];return 42;}pub fn main_entry()->u32{return 42;}',
               'fn bad(mut a:direct [u32;2])->u32{a=[20,22];return 42;}pub fn main_entry()->u32{return 42;}',
               'pub fn main_entry()->u32{let mut a:sole [u32;2]=[0;2];a=[20,22];return 42;}',
               'struct R{pub items:[u32;2];}pub fn main_entry()->u32{let mut r:R=R{items:[0;2]};'
               'let mut p:*const R=unsafe{(&mut r) as *const R};unsafe{p.items=[20,22];}return 42;}')
        for i,source in enumerate(cases):
            self.compile('array_assign_immutable_'+str(i),source,False)

    def test_resource_and_oversized_whole_assignments_remain_rejected(self):
        for i,source in enumerate(('pub fn main_entry()->u32{let mut a:[u32;257]=0;a=[0;257];return 42;}',
                                  'pub fn main_entry()->u32{let mut a:[*mut u8;2]=0;a=[null;2];return 42;}')):
            self.compile('array_assign_bounds_'+str(i),source,False)


if __name__ == '__main__':
    unittest.main()
