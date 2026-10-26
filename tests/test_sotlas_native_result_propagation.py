"""Native status/value result propagation, extraction and lexical cleanup."""
import unittest
import test_sotlas_native_i32 as previous


class NativeResultPropagationTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def scalar(self,name,body,helpers=''):
        self.program(name,'''struct ReadResult{pub status:u32;pub value:u32;pub detail:u64;}
fn read(ok:bool)->ReadResult{if ok{return ReadResult{status:0,value:42,detail:0};}
return ReadResult{status:7,value:0,detail:99};}
'''+helpers+'\npub fn main_entry()->u32{'+body+'}')

    def test_success_extracts_value_and_failure_preserves_all_fields(self):
        self.scalar('try_scalar','''let a:ReadResult=work(true);let b:ReadResult=work(false);
if a.status!=0 || a.value!=42 || b.status!=7 || b.detail!=99{return 1;}return a.value;''',
                    '''fn work(ok:bool)->ReadResult{let n:u32=read(ok)?;return ReadResult{status:0,value:n,detail:0};}''')

    def test_chaining_and_inferred_locals_evaluate_once(self):
        self.scalar('try_chain','''let a:ReadResult=work();if unsafe{calls}!=2{return 1;}return a.value;''',
                    '''static mut calls:u32=0;
fn counted()->ReadResult{unsafe{calls=calls+1;}return read(true);}
fn work()->ReadResult{let a=counted()?;let b=counted()?;return ReadResult{status:0,value:(a+b)/2,detail:0};}''')

    def test_later_operations_do_not_run_after_failure(self):
        self.scalar('try_skip','''let result:ReadResult=work();if unsafe{calls}!=0 || result.detail!=99{return 1;}return 42;''',
                    '''static mut calls:u32=0;
fn later()->u32{unsafe{calls=calls+1;}return 1;}
fn work()->ReadResult{let n:u32=read(false)?+later();return ReadResult{status:0,value:n,detail:0};}''')

    def test_error_return_captured_before_lifo_cleanup(self):
        self.scalar('try_defer','''let result:ReadResult=work();if unsafe{trace}!=21
|| result.status!=7 || result.detail!=99{return 1;}return 42;''',
                    '''static mut trace:u32=0;
fn work()->ReadResult{let mut result:ReadResult=read(false);
defer{unsafe{trace=trace*10+1;}}defer{result.detail=0;unsafe{trace=trace*10+2;}}
let n:u32=result?;return ReadResult{status:0,value:n,detail:0};}''')

    def test_status_enum_and_static_self_constructors(self):
        self.program('try_methods','''enum Status{Ok=0,Err=1,}
struct ReadResult{pub status:Status;pub value:u32;}
impl ReadResult{pub fn ok(n:u32)->Self{return ReadResult{status:Status::Ok,value:n};}
pub fn err()->Self{return ReadResult{status:Status::Err,value:0};}}
fn work(ok:bool)->ReadResult{let r:ReadResult=if ok{ReadResult::ok(42)}else{ReadResult::err()};
let n:u32=r?;return ReadResult::ok(n);}
pub fn main_entry()->u32{if work(false).status!=Status::Err{return 1;}return work(true).value;}''')

    def test_record_success_value_and_direct_field_projection(self):
        self.program('try_record','''struct Item{pub n:u32;pub bytes:[u8;2];}
struct ReadResult{pub status:u32;pub value:Item;}
fn read()->ReadResult{return ReadResult{status:0,value:Item{n:42,bytes:[7;2]}};}
fn work()->ReadResult{let item=read()?;if item.bytes[1]!=7{return ReadResult{status:1,value:item};}
let n:u32=read()?.n;return ReadResult{status:0,value:Item{n:n,bytes:[0;2]}};}
pub fn main_entry()->u32{return work().value.n;}''')

    def test_enum_success_value_can_be_matched(self):
        self.program('try_enum','''struct ReadResult{pub status:u32;pub value:E;}
enum E{None,Value(u32),}fn read()->ReadResult{return ReadResult{status:0,value:E::Value(42)};}
fn work()->ReadResult{let n:u32=match read()?{E::None=>0,E::Value(n)=>n};
return ReadResult{status:0,value:E::Value(n)};}
pub fn main_entry()->u32{return match work().value{E::None=>0,E::Value(n)=>n};}''')

    def test_array_success_initialization_and_assignment(self):
        self.program('try_array','''struct ReadResult{pub status:u32;pub value:[u32;2];}
fn read()->ReadResult{return ReadResult{status:0,value:[20,22]};}
fn work()->ReadResult{let mut a:[u32;2]=read()?;a=read()?;return ReadResult{status:0,value:a};}
pub fn main_entry()->u32{let r:ReadResult=work();return r.value[0]+r.value[1];}''')

    def test_standalone_propagation_discards_only_success_value(self):
        self.scalar('try_statement','''if work(false).status!=7{return 1;}return work(true).value;''',
                    '''fn work(ok:bool)->ReadResult{read(ok)?;return ReadResult{status:0,value:42,detail:0};}''')

    def test_temporary_arrays_support_direct_scalar_and_record_indexing(self):
        self.program('try_temporary_index','''struct Item{pub n:u32;}struct ReadResult{pub status:u32;pub value:[Item;2];}
fn read()->ReadResult{return ReadResult{status:0,value:[Item{n:20},Item{n:22}]};}
fn work()->ReadResult{let n:u32=read()?[0].n+read()?[1].n;
return ReadResult{status:0,value:[Item{n:n};2]};}
pub fn main_entry()->u32{return work().value[0].n;}''')
        self.program('try_plain_array_index','''fn make()->[u32;2]{return [20,22];}
pub fn main_entry()->u32{return make()[0]+make()[1];}''')

    def test_scalar_success_values_preserve_widths_and_float_bits(self):
        for typ,value,result in (('u8','21','(r.value+r.value) as u32'),('i8','-21','(-r.value-r.value) as u32'),
                                ('u16','21','(r.value+r.value) as u32'),('i16','-21','(-r.value-r.value) as u32'),
                                ('u32','21','r.value+r.value'),('i32','-21','(-r.value-r.value) as u32'),
                                ('u64','21','(r.value+r.value) as u32'),('i64','-21','(-r.value-r.value) as u32'),
                                ('f32','21.0','(r.value+r.value) as u32'),('f64','21.0','(r.value+r.value) as u32'),
                                ('bool','true','if r.value{42}else{0}')):
            with self.subTest(typ=typ):
                self.program('try_width_'+typ,'''struct ReadResult{pub status:u32;pub value:TYPE;}
fn read()->ReadResult{return ReadResult{status:0,value:VALUE};}
fn work()->ReadResult{let n:TYPE=read()?;return ReadResult{status:0,value:n};}
pub fn main_entry()->u32{let r:ReadResult=work();return RESULT;}'''.replace('TYPE',typ).replace('VALUE',value).replace('RESULT',result))

    def test_lazy_boolean_paths_do_not_invoke_skipped_failures(self):
        self.program('try_lazy','''struct ReadResult{pub status:u32;pub value:bool;}
static mut calls:u32=0;
fn failed()->ReadResult{unsafe{calls=calls+1;}return ReadResult{status:9,value:false};}
fn work(fail:bool)->ReadResult{let a:bool=false&&failed()?;let b:bool=true||failed()?;
if a || !b{return ReadResult{status:1,value:false};}
if fail{let n:bool=false||failed()?;return ReadResult{status:0,value:n};}
return ReadResult{status:0,value:true};}
pub fn main_entry()->u32{let good:ReadResult=work(false);if !good.value || unsafe{calls}!=0{return 1;}
let bad:ReadResult=work(true);if bad.status!=9 || unsafe{calls}!=1{return 2;}return 42;}''')

    def test_loop_failure_closes_nested_scopes_in_lifo_order_once(self):
        self.scalar('try_loop_defer','''let result:ReadResult=work();
if result.status!=7 || unsafe{trace}!=32321{return 1;}return 42;''',
                    '''static mut trace:u32=0;
fn work()->ReadResult{defer{unsafe{trace=trace*10+1;}}let mut i:u32=0;
while i<3{defer{unsafe{trace=trace*10+2;}}{defer{unsafe{trace=trace*10+3;}}
let n:u32=read(i==0)?;}i=i+1;}return ReadResult{status:0,value:42,detail:0};}''')

    def test_match_guard_failure_returns_before_fallthrough(self):
        self.scalar('try_guard','''let good:ReadResult=work(true);let bad:ReadResult=work(false);
if good.value!=42 || bad.status!=7 || bad.detail!=99{return 1;}return good.value;''',
                    '''fn work(ok:bool)->ReadResult{let n:u32=match true{true if read(ok)?==42=>42,_=>0};
return ReadResult{status:0,value:n,detail:0};}''')

    def test_argument_evaluation_stops_at_the_failing_operand(self):
        self.scalar('try_argument_order','''let r:ReadResult=work();if r.status!=7 || unsafe{trace}!=1{return 1;}return 42;''',
                    '''static mut trace:u32=0;fn mark(n:u32)->u32{unsafe{trace=trace*10+n;}return n;}
fn combine(a:u32,b:u32,c:u32)->ReadResult{return ReadResult{status:0,value:a+b+c,detail:0};}
fn work()->ReadResult{return combine(mark(1),read(false)?,mark(3));}''')

    def test_try_in_struct_initializer_does_not_evaluate_later_fields(self):
        self.scalar('try_literal_order','''let r:ReadResult=work();if r.status!=7 || r.detail!=99 || unsafe{calls}!=0{return 1;}return 42;''',
                    '''static mut calls:u32=0;fn later()->u64{unsafe{calls=calls+1;}return 0;}
fn work()->ReadResult{return ReadResult{status:0,value:read(false)?,detail:later()};}''')

    def test_zero_error_detail_and_nonzero_value_are_not_success_tags(self):
        self.scalar('try_explicit_tag','''let r:ReadResult=work();if r.status!=7 || r.value!=42 || r.detail!=0{return 1;}return 42;''',
                    '''fn work()->ReadResult{let r:ReadResult=ReadResult{status:7,value:42,detail:0};
let n:u32=r?;return ReadResult{status:0,value:n,detail:99};}''')

    def test_direct_static_constructor_call_can_propagate(self):
        self.program('try_static_constructor','''struct ReadResult{pub status:u32;pub value:u32;}
impl ReadResult{fn ok(n:u32)->Self{return ReadResult{status:0,value:n};}}
fn work()->ReadResult{let n:u32=ReadResult::ok(42)?;return ReadResult::ok(n);}
pub fn main_entry()->u32{return work().value;}''')

    def test_owner_consumption_in_operand_is_preserved(self):
        self.program('try_owner_call','''struct Token{pub n:u32;}struct ReadResult{pub status:u32;pub value:u32;}
fn read(t:sole Token)->ReadResult{return ReadResult{status:0,value:t.n};}
fn work()->ReadResult{let t:sole Token=Token{n:42};let n:u32=read(t)?;return ReadResult{status:0,value:n};}
pub fn main_entry()->u32{return work().value;}''')
        self.compile('try_owner_moved','''struct Token{pub n:u32;}struct ReadResult{pub status:u32;pub value:u32;}
fn read(t:sole Token)->ReadResult{return ReadResult{status:0,value:t.n};}
fn work()->ReadResult{let t:sole Token=Token{n:42};let n:u32=read(t)?;return ReadResult{status:0,value:t.n};}
pub fn main_entry()->u32{return 42;}''',False)

    def test_try_in_dead_code_is_still_validated(self):
        self.compile('try_dead_invalid','''struct ReadResult{pub status:u32;pub value:u32;}
fn work()->ReadResult{return ReadResult{status:0,value:42};let n:u32=42?;}
pub fn main_entry()->u32{return 42;}''',False)

    def test_foreign_and_owned_result_boundaries_remain_rejected(self):
        for index,body in enumerate(('@extern(C) fn read()->ReadResult;fn work()->ReadResult{let n:u32=unsafe{read()}?;return ReadResult{status:0,value:n};}',
                                     'fn work(r:sole ReadResult)->ReadResult{let n:u32=r?;return ReadResult{status:0,value:n};}',
                                     'fn work(r:ReadResult)->sole ReadResult{let n:u32=r?;return ReadResult{status:0,value:n};}',
                                     'fn work(r:direct ReadResult)->ReadResult{let n:u32=r?;return ReadResult{status:0,value:n};}')):
            self.compile('try_boundary_'+str(index),'struct ReadResult{pub status:u32;pub value:u32;}'+body+
                         'pub fn main_entry()->u32{return 42;}',False)

    def test_invalid_shapes_contexts_and_nominal_return_types_rejected(self):
        cases=('fn work()->u32{let n:u32=42?;return n;}',
               'struct R{pub status:u32;pub value:u32;}fn read()->R{return R{status:0,value:42};}'
               'fn work()->u32{return read()?;}',
               'struct R{pub status:u32;pub value:u32;}struct Other{pub status:u32;pub value:u32;}'
               'fn work(r:R)->Other{let n:u32=r?;return Other{status:0,value:n};}',
               'struct R{pub status:bool;pub value:u32;}fn work(r:R)->R{let n:u32=r?;return r;}',
               'struct R{pub value:u32;}fn work(r:R)->R{let n:u32=r?;return r;}',
               'struct R{pub status:u32;pub value:*mut u8;}fn work(r:R)->R{let n:*mut u8=r?;return r;}',
               'struct R{pub status:u32;pub value:u32;}fn work(r:whisper R)->R{let n:u32=r?;return R{status:0,value:n};}',
               'struct R{pub status:u32;pub value:u32;}fn work(r:R)->R{defer{let n:u32=r?;}return r;}')
        for index,source in enumerate(cases):
            with self.subTest(index=index):
                self.compile('try_invalid_'+str(index),source+'pub fn main_entry()->u32{return 42;}',False)


if __name__=='__main__':
    unittest.main()
