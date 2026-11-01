"""Concrete native Some/None propagation and checked optional text lookup."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous


class NativeOptionalTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, source):
        self.execute(self.compile(name, source))

    def library(self, name, body):
        root=Path(__file__).resolve().parents[1]
        sources=[]
        for module in ('results','text','optional'):
            source=(root/f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
            sources.append('\n'.join(line for line in source.splitlines() if not line.startswith(('module ','import '))))
        self.program(name,'\n'.join(sources)+'\npub fn main_entry()->u32{'+body+'}')

    def test_some_extracts_value_and_none_propagates(self):
        self.program('optional_basic','''enum Maybe{Some(u32),None}
fn source(found:bool)->Maybe{if found{return Maybe::Some(40);}return Maybe::None;}
fn work(found:bool)->Maybe{let n:u32=source(found)?;return Maybe::Some(n+2);}
pub fn main_entry()->u32{let a:u32=match work(true){Maybe::Some(n)=>n,Maybe::None=>0};
let absent:bool=match work(false){Maybe::Some(n)=>false,Maybe::None=>true};if !absent{return 1;}return a;}''')

    def test_both_orders_and_explicit_tags(self):
        for index,variants in enumerate(('None,Some(u32)', 'Some(u32)=32,None=7', 'None=29,Some(u32)=41')):
            self.program('optional_tags_'+str(index),'enum Maybe{'+variants+'}'
                         'fn work(found:bool)->Maybe{let n:u32=(if found{Maybe::Some(42)}else{Maybe::None})?;return Maybe::Some(n);}'
                         'pub fn main_entry()->u32{let absent:bool=match work(false){Maybe::Some(n)=>false,Maybe::None=>true};'
                         'if !absent{return 1;}return match work(true){Maybe::Some(n)=>n,Maybe::None=>2};}')

    def test_direct_none_expression_returns_before_later_code(self):
        self.program('optional_direct_none','''enum Maybe{Some(u32),None}static mut calls:u32=0;
fn work()->Maybe{let n:u32=Maybe::None?;unsafe{calls=calls+1;}return Maybe::Some(n);}
pub fn main_entry()->u32{let r:Maybe=work();if unsafe{calls}!=0{return 1;}
return match r{Maybe::Some(n)=>2,Maybe::None=>42};}''')

    def test_none_cleanup_snapshot_lifo(self):
        self.program('optional_cleanup','''enum Maybe{Some(u32),None}static mut trace:u32=0;
fn mark(n:u32)->void{unsafe{trace=trace*10+n;}return;}
fn work()->Maybe{let mut r:Maybe=Maybe::None;defer mark(1);defer mark(2);defer{r=Maybe::Some(1);}
let n:u32=r?;return Maybe::Some(n);}
pub fn main_entry()->u32{let r:Maybe=work();if unsafe{trace}!=21{return 1;}return match r{Maybe::Some(n)=>2,Maybe::None=>42};}''')

    def test_operand_once_and_later_arguments_are_skipped_on_none(self):
        self.program('optional_order','''enum Maybe{Some(u32),None}static mut trace:u32=0;
fn source(found:bool)->Maybe{unsafe{trace=trace+1;}if found{return Maybe::Some(40);}return Maybe::None;}
fn later()->u32{unsafe{trace=trace+10;}return 2;}fn add(a:u32,b:u32)->u32{return a+b;}
fn work(found:bool)->Maybe{return Maybe::Some(add(source(found)?,later()));}
pub fn main_entry()->u32{let good:Maybe=work(true);if unsafe{trace}!=11{return 1;}unsafe{trace=0;}
let absent:Maybe=work(false);if unsafe{trace}!=1{return 2;}let missing:bool=match absent{Maybe::Some(n)=>false,Maybe::None=>true};
if !missing{return 3;}return match good{Maybe::Some(n)=>n,Maybe::None=>4};}''')

    def test_scalar_widths_and_success_snapshot(self):
        for index,(typ,value,condition) in enumerate((('i64','-42','n==-42'),('f64','1.5','n==1.5'),
                                                     ('bool','true','n'),('bool','false','!n'))):
            self.program('optional_width_'+str(index),'enum Maybe{Some('+typ+'),None}'
                         'fn work()->Maybe{let mut r:Maybe=Maybe::Some('+value+');defer{r=Maybe::None;}'
                         'let n:'+typ+'=r?;return Maybe::Some(n);}'
                         'pub fn main_entry()->u32{return match work(){Maybe::Some(n)=>if '+condition+'{42}else{1},Maybe::None=>2};}')

    def test_array_record_and_nested_payloads(self):
        self.program('optional_record','''struct Pair{pub a:u32;pub b:u32;}enum Maybe{None,Some(Pair)}
fn source()->Maybe{return Maybe::Some(Pair{a:20,b:22});}fn work()->Maybe{let p:Pair=source()?;return Maybe::Some(p);}
pub fn main_entry()->u32{return match work(){Maybe::None=>1,Maybe::Some(p)=>p.a+p.b};}''')
        self.program('optional_array_iteration','''enum Maybe{None,Some([u32;2])}
fn source()->Maybe{return Maybe::Some([20,22]);}fn work()->Maybe{let mut sum:u32=0;
for n in source()?{sum=sum+n;}return Maybe::Some([sum,0]);}
pub fn main_entry()->u32{return match work(){Maybe::None=>1,Maybe::Some(a)=>a[0]};}''')

    def test_mixed_schemas_and_invalid_payloads_rejected(self):
        for index,variants in enumerate(('Some(u32),Err(u32)','Ok(u32),None','Some, None',
                                         'Some(u32),None(u32)','Some(u32,u32),None','Some(u32),None,Other',
                                         'Some(*mut u32),None')):
            self.compile('optional_schema_'+str(index),'enum Maybe{'+variants+'}'
                         'fn work(r:Maybe)->Maybe{let n:u32=r?;return r;}pub fn main_entry()->u32{return 42;}',False)

    def test_nominal_ownership_and_defer_boundaries(self):
        cases=('fn work(r:Maybe)->Other{let n:u32=r?;return Other::Some(n);}',
               'fn work(r:sole Maybe)->Maybe{let n:u32=r?;return Maybe::Some(n);}',
               'fn work(r:Maybe)->Maybe{defer{let n:u32=r?;}return r;}',
               'fn work(r:Maybe)->u32{return 42;let n:u32=r?;}')
        for index,body in enumerate(cases):
            self.compile('optional_boundary_'+str(index),'enum Maybe{Some(u32),None}enum Other{Some(u32),None}'
                         +body+'pub fn main_entry()->u32{return 42;}',False)

    def test_pointer_and_borrowed_record_payloads_are_not_enabled(self):
        self.compile('optional_pointer_exact','''enum Maybe{Some(*mut u32),None}
fn work(r:Maybe)->Maybe{let p:*mut u32=r?;return Maybe::Some(p);}pub fn main_entry()->u32{return 42;}''',False)
        self.compile('optional_record_pointer','''struct Borrowed{pub data:*const u8;pub length:usize;}
enum Maybe{Some(Borrowed),None}fn work(r:Maybe)->Maybe{let b:Borrowed=r?;return Maybe::Some(b);}
pub fn main_entry()->u32{return 42;}''',False)

    def test_library_zero_index_is_not_absence(self):
        self.library('optional_zero','''let r:NativeIndexResult=native_text_find_option(native_text_open("answer",6),native_text_open("an",2));
if r.status!=0{return 1;}return match r.value{NativeIndexOption::Some(n)=>if n==0{42}else{2},NativeIndexOption::None=>3};''')

    def test_library_missing_and_invalid_are_distinct(self):
        self.library('optional_missing','''let missing:NativeIndexResult=native_text_find_option(native_text_open("abc",3),native_text_open("x",1));
let absent:bool=match missing.value{NativeIndexOption::Some(n)=>false,NativeIndexOption::None=>true};
let invalid:NativeIndexResult=native_text_find_option(native_text_invalid(),native_text_open("x",1));
if missing.status!=0 || !absent || invalid.status!=7 || invalid.error.kind!=7{return 1;}return 42;''')

    def test_library_start_offset_empty_needle_and_range_error(self):
        self.library('optional_from','''let text:NativeByteSlice=native_text_open("ababa",5);let needle:NativeByteSlice=native_text_open("ba",2);
let next:NativeIndexResult=native_text_find_option_from(text,needle,2);
let end:NativeIndexResult=native_text_find_option_from(text,native_text_open(null,0),5);
let invalid:NativeIndexResult=native_text_find_option_from(text,needle,6);
if next.status!=0 || native_index_or(next.value,99)!=3 || native_index_or(end.value,99)!=5
|| invalid.status!=7 || invalid.error.offset!=6{return 1;}return 42;''')

    def test_library_optional_add_and_overflow(self):
        self.library('optional_add','''let a:NativeIndexOption=native_index_add(native_index_some(40),2);
let b:NativeIndexOption=native_index_add(native_index_some(18446744073709551615),1);
let c:NativeIndexOption=native_index_add(native_index_none(),1);
if native_index_or(a,0)!=42 || native_index_or(b,7)!=7 || native_index_or(c,9)!=9{return 1;}return 42;''')

    def test_library_full_unsigned_domain_has_no_sentinel(self):
        self.library('optional_max','''let maximum:usize=18446744073709551615;
let unchanged:NativeIndexOption=native_index_add(native_index_some(maximum),0);
let boundary:NativeIndexOption=native_index_add(native_index_some(18446744073709551614),1);
if native_index_or(unchanged,0)!=maximum || native_index_or(boundary,0)!=maximum{return 1;}return 42;''')

    def test_library_invalid_needle_is_an_error(self):
        self.library('optional_bad_needle','''let r:NativeIndexResult=native_text_find_option(native_text_open("abc",3),native_text_open(null,1));
let absent:bool=match r.value{NativeIndexOption::Some(n)=>false,NativeIndexOption::None=>true};
if r.status!=7 || r.error.kind!=7 || !absent{return 1;}return 42;''')

    def test_library_embedded_zero_and_empty_inputs(self):
        self.library('optional_bytes','''let mut bytes:[u8;3]=[97,0,98];let text:NativeByteSlice=native_text_open(unsafe{bytes as *const u8},3);
let r:NativeIndexResult=native_text_find_option(text,native_text_open("b",1));
let empty:NativeIndexResult=native_text_find_option(native_text_open(null,0),native_text_open(null,0));
if r.status!=0 || native_index_or(r.value,99)!=2 || empty.status!=0 || native_index_or(empty.value,99)!=0{return 1;}return 42;''')

    def test_library_checked_record_propagation_preserves_optional_value(self):
        root=Path(__file__).resolve().parents[1]
        sources=[]
        for module in ('results','text','optional'):
            sources.append('\n'.join(line for line in (root/f'runtime/native/{module}.sotlas').read_text(encoding='utf-8').splitlines()
                                     if not line.startswith(('module ','import '))))
        self.program('optional_layered','\n'.join(sources)+'''
fn lookup(valid:bool)->NativeIndexResult{let text:NativeByteSlice=if valid{native_text_open("answer",6)}else{native_text_invalid()};
let value:NativeIndexOption=native_text_find_option(text,native_text_open("an",2))?;return native_index_result(value);}
pub fn main_entry()->u32{let good:NativeIndexResult=lookup(true);let bad:NativeIndexResult=lookup(false);
if good.status!=0 || native_index_or(good.value,99)!=0 || bad.status!=7{return 1;}return 42;}''')


if __name__ == '__main__':
    unittest.main()
