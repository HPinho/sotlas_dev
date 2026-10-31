"""Concrete tagged Ok/Err propagation through native structured control flow."""
import unittest
import test_sotlas_native_i32 as previous


class NativeTaggedResultTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def test_success_extracts_scalar(self):
        self.program('tagged_success','''enum Outcome{Ok(u32),Err(u32)}
fn source()->Outcome{return Outcome::Ok(40);}fn work()->Outcome{let n:u32=source()?;return Outcome::Ok(n+2);}
pub fn main_entry()->u32{return match work(){Outcome::Ok(n)=>n,Outcome::Err(e)=>1};}''')

    def test_error_returns_complete_record_payload(self):
        self.program('tagged_error','''struct Error{pub code:u32;pub offset:usize;}enum Outcome{Ok(u32),Err(Error)}
fn source()->Outcome{return Outcome::Err(Error{code:7,offset:35});}
fn work()->Outcome{let n:u32=source()?;return Outcome::Ok(n);}
pub fn main_entry()->u32{return match work(){Outcome::Ok(n)=>1,Outcome::Err(e)=>e.code+e.offset as u32};}''')

    def test_reversed_variant_order_does_not_assume_zero_success(self):
        self.program('tagged_reverse','''enum Outcome{Err(u32),Ok(u32)}
fn source(ok:bool)->Outcome{if ok{return Outcome::Ok(40);}return Outcome::Err(42);}
fn work(ok:bool)->Outcome{let n:u32=source(ok)?;return Outcome::Ok(n+2);}
pub fn main_entry()->u32{let a:u32=match work(true){Outcome::Ok(n)=>n,Outcome::Err(e)=>0};
let b:u32=match work(false){Outcome::Ok(n)=>0,Outcome::Err(e)=>e};if a!=42 || b!=42{return 1;}return 42;}''')

    def test_operand_is_evaluated_once(self):
        self.program('tagged_once','''enum Outcome{Ok(u32),Err(u32)}static mut calls:u32=0;
fn source()->Outcome{unsafe{calls=calls+1;}return Outcome::Ok(42);}
fn work()->Outcome{let n:u32=source()?;return Outcome::Ok(n);}
pub fn main_entry()->u32{let result:Outcome=work();if unsafe{calls}!=1{return 1;}return match result{Outcome::Ok(n)=>n,Outcome::Err(e)=>2};}''')

    def test_lifo_cleanup_and_error_snapshot(self):
        self.program('tagged_cleanup','''enum Outcome{Ok(u32),Err(u32)}static mut trace:u32=0;
fn mark(n:u32)->void{unsafe{trace=trace*10+n;}return;}
fn work()->Outcome{let mut result:Outcome=Outcome::Err(42);defer mark(1);defer mark(2);
defer{result=Outcome::Err(1);}let n:u32=result?;return Outcome::Ok(n);}
pub fn main_entry()->u32{let result:Outcome=work();if unsafe{trace}!=21{return 1;}
return match result{Outcome::Ok(n)=>2,Outcome::Err(e)=>e};}''')

    def test_failure_stops_later_operands_and_arguments(self):
        self.program('tagged_order','''enum Outcome{Ok(u32),Err(u32)}static mut calls:u32=0;
fn failed()->Outcome{return Outcome::Err(42);}fn later()->u32{unsafe{calls=calls+1;}return 1;}
fn add(a:u32,b:u32)->u32{return a+b;}fn work()->Outcome{return Outcome::Ok(add(failed()?,later()));}
pub fn main_entry()->u32{let r:Outcome=work();if unsafe{calls}!=0{return 1;}return match r{Outcome::Ok(n)=>2,Outcome::Err(e)=>e};}''')

    def test_record_and_array_success_payloads(self):
        self.program('tagged_record','''struct Pair{pub a:u32;pub b:u32;}enum Outcome{Ok(Pair),Err(u32)}
fn source()->Outcome{return Outcome::Ok(Pair{a:20,b:22});}fn work()->Outcome{let p:Pair=source()?;return Outcome::Ok(p);}
pub fn main_entry()->u32{return match work(){Outcome::Ok(p)=>p.a+p.b,Outcome::Err(e)=>1};}''')
        self.program('tagged_array','''const COUNT:usize=2;enum Outcome{Ok([u32;COUNT]),Err(u32)}
fn source()->Outcome{return Outcome::Ok([20,22]);}fn work()->Outcome{let a:[u32;COUNT]=source()?;return Outcome::Ok(a);}
pub fn main_entry()->u32{return match work(){Outcome::Ok(a)=>a[0]+a[1],Outcome::Err(e)=>1};}''')

    def test_conditional_match_and_inferred_operands(self):
        self.program('tagged_context','''enum Outcome{Ok(u32),Err(u32)}
fn source()->Outcome{return Outcome::Ok(40);}fn work()->Outcome{
let result=if true{source()}else{Outcome::Err(1)};let n:u32=(match true{true=>result,false=>Outcome::Err(2)})?;
return Outcome::Ok(n+2);}pub fn main_entry()->u32{return match work(){Outcome::Ok(n)=>n,Outcome::Err(e)=>1};}''')

    def test_structured_loop_early_return(self):
        self.program('tagged_loop','''enum Outcome{Ok(u32),Err(u32)}
fn step(n:u32)->Outcome{if n==2{return Outcome::Err(42);}return Outcome::Ok(n);}
fn work()->Outcome{let mut i:u32=0;while i<4{let n:u32=step(i)?;i=n+1;}return Outcome::Ok(1);}
pub fn main_entry()->u32{return match work(){Outcome::Ok(n)=>1,Outcome::Err(e)=>e};}''')

    def test_scalar_widths_signed_values_floats_and_bool(self):
        for typ,value,condition in (('u8','42','n==42'),('i8','-42','n==-42'),
                                    ('u16','42','n==42'),('i16','-42','n==-42'),
                                    ('u64','4294967297','n==4294967297'),
                                    ('i64','-4294967297','n==-4294967297'),
                                    ('f32','1.5','n==1.5'),('f64','2.5','n==2.5'),('bool','true','n')):
            with self.subTest(typ=typ):
                self.program('tagged_width_'+typ,'enum Outcome{Ok('+typ+'),Err(u32)}'
                             'fn source()->Outcome{return Outcome::Ok('+value+');}'
                             'fn work()->Outcome{let n:'+typ+'=source()?;return Outcome::Ok(n);}'
                             'pub fn main_entry()->u32{return match work(){Outcome::Ok(n)=>if '+condition+
                             '{42}else{1},Outcome::Err(e)=>2};}')

    def test_nested_tagged_success_and_array_error_payload(self):
        self.program('tagged_nested','''enum Value{Empty,Pair(u32,u32)}enum Outcome{Ok(Value),Err([u32;2])}
fn source(ok:bool)->Outcome{if ok{return Outcome::Ok(Value::Pair(20,22));}return Outcome::Err([19,23]);}
fn work(ok:bool)->Outcome{let v:Value=source(ok)?;return Outcome::Ok(v);}
pub fn main_entry()->u32{let a:u32=match work(true){Outcome::Ok(v)=>match v{Value::Empty=>0,Value::Pair(x,y)=>x+y},Outcome::Err(e)=>0};
let b:u32=match work(false){Outcome::Ok(v)=>0,Outcome::Err(e)=>e[0]+e[1]};if a!=42 || b!=42{return 1;}return 42;}''')

    def test_return_value_is_captured_before_success_cleanup(self):
        self.program('tagged_good_cleanup','''enum Outcome{Ok(u32),Err(u32)}static mut trace:u32=0;
fn work()->Outcome{let mut result:Outcome=Outcome::Ok(42);defer{result=Outcome::Ok(1);unsafe{trace=9;}}
let n:u32=result?;return Outcome::Ok(n);}
pub fn main_entry()->u32{let r:Outcome=work();if unsafe{trace}!=9{return 1;}return match r{Outcome::Ok(n)=>n,Outcome::Err(e)=>2};}''')

    def test_nominal_mismatch_and_wrong_return_rejected(self):
        for index,body in enumerate(('fn work()->u32{let n:u32=source()?;return n;}',
                                     'fn work()->Other{let n:u32=source()?;return Other::Ok(n);}')):
            self.compile('tagged_return_bad_'+str(index),'enum Outcome{Ok(u32),Err(u32)}enum Other{Ok(u32),Err(u32)}'
                         'fn source()->Outcome{return Outcome::Ok(42);}'+body+'pub fn main_entry()->u32{return 42;}',False)

    def test_invalid_variant_schemas_rejected(self):
        for index,variants in enumerate(('Ok(u32),Fail(u32)','Ok(u32),Err(u32),Pending',
                                         'Ok(u32),Err','Ok,Err(u32)','Ok(u32,u32),Err(u32)')):
            self.compile('tagged_schema_bad_'+str(index),'enum Outcome{'+variants+'}'
                         'fn work(r:Outcome)->Outcome{let n:u32=r?;return r;}pub fn main_entry()->u32{return 42;}',False)

    def test_qualified_and_pointer_payloads_rejected(self):
        for index,qualifier in enumerate(('sole','whisper','direct')):
            self.compile('tagged_qualified_'+str(index),'enum Outcome{Ok(u32),Err(u32)}'
                         'fn work(r:'+qualifier+' Outcome)->Outcome{let n:u32=r?;return Outcome::Ok(n);}'
                         'pub fn main_entry()->u32{return 42;}',False)
        self.compile('tagged_pointer','''enum Outcome{Ok(*mut u32),Err(u32)}
fn work(r:Outcome)->Outcome{let p:*mut u32=r?;return Outcome::Ok(p);}pub fn main_entry()->u32{return 42;}''',False)

    def test_try_in_defer_and_unreachable_invalid_schemas_rejected(self):
        self.compile('tagged_defer_bad','''enum Outcome{Ok(u32),Err(u32)}
fn work(r:Outcome)->Outcome{defer{let n:u32=r?;}return r;}pub fn main_entry()->u32{return 42;}''',False)
        self.compile('tagged_dead_bad','''enum Outcome{Ok(u32),Other(u32)}
fn work(r:Outcome)->Outcome{return r;let n:u32=r?;}pub fn main_entry()->u32{return 42;}''',False)


if __name__ == '__main__':
    unittest.main()
