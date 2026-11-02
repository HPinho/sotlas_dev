"""Concrete native Result error propagation across success types."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous


class NativeErrorCompositionTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self,name,source):
        self.execute(self.compile(name,source))

    def library(self,name,body):
        root=Path(__file__).resolve().parents[1]
        parts=[(root/f'runtime/native/{module}.sotlas').read_text(encoding='utf-8')
               for module in ('results','text','optional','parse')]
        source='\n'.join('\n'.join(line for line in part.splitlines()
                                  if not line.startswith(('module ','import '))) for part in parts)
        self.program(name,source+'\n'+body)

    def test_distinct_success_types_preserve_error(self):
        self.program('error_cross', '''enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err(u32)}
fn read(ok:bool)->A{if ok{return A::Ok(42);}return A::Err(42);}
fn work(ok:bool)->B{let n:u32=read(ok)?;return B::Ok(n==42);}
pub fn main_entry()->u32{if let B::Ok(ok)=work(true){if !ok{return 1;}}else{return 2;}
if let B::Err(e)=work(false){return e;}return 3;}''')

    def test_explicit_tags_and_reversed_orders_are_remapped(self):
        self.program('error_tags', '''enum A{Err(u32)=91,Ok(u32)=7}enum B{Ok(u64)=91,Err(u32)=0}
fn work(a:A)->B{let n:u32=a?;return B::Ok(n as u64);}
pub fn main_entry()->u32{if let B::Ok(n)=work(A::Ok(42)){if n!=42{return 1;}}else{return 2;}
if let B::Err(e)=work(A::Err(42)){return e;}return 3;}''')

    def test_record_error_has_independent_source_and_destination_offsets(self):
        self.program('error_layout', '''struct E{pub code:u32;pub offset:usize;pub bytes:[u8;2];}
enum A{Ok(u8),Err(E)}enum B{Err(E)=19,Ok([u64;8])=11}
fn work(a:A)->B{let n:u8=a?;return B::Ok([n as u64;8]);}
pub fn main_entry()->u32{let e:E=E{code:40,offset:7,bytes:[1,2]};
if let B::Err(found)=work(A::Err(e)){if found.offset!=7||found.bytes[1]!=2{return 1;}return found.code+2;}
return 2;}''')

    def test_chained_conversions_preserve_nominal_error_record(self):
        self.program('error_chain', '''struct E{pub code:u32;}enum A{Ok(u32),Err(E)}
enum B{Ok(bool),Err(E)}enum C{Err(E)=70,Ok([u32;2])=3}
fn first(a:A)->B{let n:u32=a?;return B::Ok(n==42);}
fn second(a:A)->C{let ok:bool=first(a)?;return C::Ok([if ok{42}else{0},0]);}
pub fn main_entry()->u32{if let C::Ok(xs)=second(A::Ok(42)){if xs[0]!=42{return 1;}}else{return 2;}
if let C::Err(e)=second(A::Err(E{code:42})){return e.code;}return 3;}''')

    def test_error_snapshot_precedes_mutating_lifo_cleanup(self):
        self.program('error_cleanup', '''enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err(u32)}static mut trace:u32=0;
fn work()->B{let mut a:A=A::Err(42);defer{unsafe{trace=trace*10+1;}}
defer{a=A::Err(1);unsafe{trace=trace*10+2;}}let n:u32=a?;return B::Ok(false);}
pub fn main_entry()->u32{let result:B=work();if unsafe{trace}!=21{return 1;}
if let B::Err(e)=result{return e;}return 2;}''')

    def test_operand_once_and_later_arguments_skipped(self):
        self.program('error_order', '''enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err(u32)}static mut calls:u32=0;
fn read()->A{unsafe{calls=calls+1;}return A::Err(42);}fn later()->u32{unsafe{calls=calls+100;}return 1;}
fn accept(a:u32,b:u32)->bool{return false;}fn work()->B{return B::Ok(accept(read()?,later()));}
pub fn main_entry()->u32{let r:B=work();if unsafe{calls}!=1{return 1;}if let B::Err(e)=r{return e;}return 2;}''')

    def test_loop_failure_cleans_active_scopes(self):
        self.program('error_loop', '''enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err(u32)}static mut trace:u32=0;
fn step(i:u32)->A{if i==2{return A::Err(42);}return A::Ok(i);}
fn work()->B{defer{unsafe{trace=trace+10;}}for i in 0..4{defer{unsafe{trace=trace+1;}}let n:u32=step(i)?;}
return B::Ok(true);}pub fn main_entry()->u32{let r:B=work();if unsafe{trace}!=13{return 1;}
if let B::Err(e)=r{return e;}return 2;}''')

    def test_scalar_error_families(self):
        for typ,value,check in (('u8','42','e==42'),('i64','-4294967297','e==-4294967297'),
                                ('u64','18446744073709551615','e==18446744073709551615'),
                                ('f32','1.5','e==1.5'),('f64','2.5','e==2.5'),('bool','false','!e')):
            with self.subTest(typ=typ):
                self.program('error_scalar_'+typ,'enum A{Ok(u32),Err('+typ+')}enum B{Ok(bool),Err('+typ+')}'
                             'fn work()->B{let n:u32=A::Err('+value+')?;return B::Ok(true);}'
                             'pub fn main_entry()->u32{if let B::Err(e)=work(){if '+check+'{return 42;}}return 1;}')

    def test_nested_enum_error_record(self):
        self.program('error_nested', '''enum Kind{Empty,Code(u32)}struct E{pub kind:Kind;}
enum A{Ok(u32),Err(E)}enum B{Err(E),Ok(bool)}fn work()->B{let n:u32=A::Err(E{kind:Kind::Code(42)})?;return B::Ok(true);}
pub fn main_entry()->u32{if let B::Err(E{kind:Kind::Code(n)})=work(){return n;}return 1;}''')

    def test_success_payload_can_be_a_record_or_array(self):
        self.program('error_success_aggregate', '''struct Pair{pub n:u32;pub m:u32;}enum A{Ok(Pair),Err(u32)}enum B{Ok([u32;2]),Err(u32)}
fn work(a:A)->B{let p:Pair=a?;return B::Ok([p.n,p.m]);}
pub fn main_entry()->u32{if let B::Ok(items)=work(A::Ok(Pair{n:20,m:22})){return items[0]+items[1];}return 1;}''')

    def test_error_nominal_types_and_scalar_widths_must_match(self):
        for i,error in enumerate(('u64','i32','bool','Other')):
            with self.subTest(error=error):
                self.compile('error_type_bad_'+str(i),'struct Other{pub code:u32;}enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err('+error+')}'
                             'fn work(a:A)->B{let n:u32=a?;return B::Ok(true);}pub fn main_entry()->u32{return 42;}',False)
        self.compile('error_nominal','''struct E{pub code:u32;}struct Other{pub code:u32;}
enum A{Ok(u32),Err(E)}enum B{Ok(bool),Err(Other)}fn work(a:A)->B{let n:u32=a?;return B::Ok(true);}
pub fn main_entry()->u32{return 42;}''',False)

    def test_optional_and_status_record_conversions_remain_nominal(self):
        sources=(
            'enum A{Some(u32),None}enum B{Some(bool),None}fn work(a:A)->B{let n:u32=a?;return B::None;}',
            'struct A{pub status:u32;pub value:u32;}struct B{pub status:u32;pub value:bool;}fn work(a:A)->B{let n:u32=a?;return B{status:0,value:true};}',
            'enum A{Ok(u32),Err(u32)}enum B{Some(bool),None}fn work(a:A)->B{let n:u32=a?;return B::None;}',
        )
        for i,source in enumerate(sources):
            self.compile('error_schema_bad_'+str(i),source+'pub fn main_entry()->u32{return 42;}',False)

    def test_direct_array_errors_and_resource_errors_reject(self):
        for i,error in enumerate(('[u32;2]','*const u32','sole E')):
            with self.subTest(error=error):
                self.compile('error_payload_bad_'+str(i),'struct E{pub code:u32;}enum A{Ok(u32),Err('+error+')}enum B{Ok(bool),Err('+error+')}'
                             'fn work(a:A)->B{let n:u32=a?;return B::Ok(true);}pub fn main_entry()->u32{return 42;}',False)

    def test_extra_variants_and_deferred_propagation_reject(self):
        self.compile('error_extra','''enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err(u32),Pending}
fn work(a:A)->B{let n:u32=a?;return B::Ok(true);}pub fn main_entry()->u32{return 42;}''',False)
        self.compile('error_defer','''enum A{Ok(u32),Err(u32)}enum B{Ok(bool),Err(u32)}
fn work(a:A)->B{defer{let n:u32=a?;}return B::Ok(true);}pub fn main_entry()->u32{return 42;}''',False)

    def test_assignment_remains_nominal_without_question_mark(self):
        for i,source in enumerate((
            'enum A{Ok(u32),Err(u32)}enum B{Ok(u32),Err(u32)}pub fn main_entry()->u32{let a:A=A::Err(42);let b:B=a;return 42;}',
            'enum A{Ok(u32),Err(u32)}enum B{Ok(u32),Err(u32)}struct Holder{pub value:A;}pub fn main_entry()->u32{let h:Holder=Holder{value:A::Err(42)};let b:B=h.value;return 42;}',
            'struct A{pub n:u32;}struct B{pub n:u32;}pub fn main_entry()->u32{let a:A=A{n:42};let b:B=a;return 42;}',
        )):
            self.compile('error_assignment_'+str(i),source,False)

    def test_library_pair_and_sum(self):
        self.library('parse_pair','''pub fn main_entry()->u32{
let text:NativeByteSlice=native_text_open("20::22",6);let separator:NativeByteSlice=native_text_open("::",2);
if let NativeParsedPair::Ok(pair)=native_parse_u32_pair(text,separator){if pair.first!=20||pair.second!=22{return 1;}}else{return 2;}
if let NativeParsedU32::Ok(sum)=native_parse_u32_pair_sum(text,separator){return sum;}return 3;}''')

    def test_library_errors_keep_original_byte_offsets(self):
        self.library('parse_offsets','''pub fn main_entry()->u32{let separator:NativeByteSlice=native_text_open("::",2);
let a:NativeParsedPair=native_parse_u32_pair(native_text_open("x::22",5),separator);
let b:NativeParsedPair=native_parse_u32_pair(native_text_open("20::2x",6),separator);
if let NativeParsedPair::Err(e)=a{if e.kind!=3||e.offset!=0{return 1;}}else{return 2;}
if let NativeParsedPair::Err(e)=b{if e.kind!=3||e.offset!=5{return 3;}}else{return 4;}return 42;}''')

    def test_library_empty_fields_and_missing_separator_are_distinct(self):
        self.library('parse_empty','''pub fn main_entry()->u32{let d:NativeByteSlice=native_text_open(":",1);
let a:NativeParsedPair=native_parse_u32_pair(native_text_open(":22",3),d);
let b:NativeParsedPair=native_parse_u32_pair(native_text_open("20:",3),d);
let c:NativeParsedPair=native_parse_u32_pair(native_text_open("2022",4),d);
if let NativeParsedPair::Err(e)=a{if e.kind!=2||e.offset!=0{return 1;}}else{return 2;}
if let NativeParsedPair::Err(e)=b{if e.kind!=2||e.offset!=3{return 3;}}else{return 4;}
if let NativeParsedPair::Err(e)=c{if e.kind!=7||e.offset!=4{return 5;}}else{return 6;}return 42;}''')

    def test_library_invalid_shapes_and_range_bounds(self):
        self.library('parse_bounds','''pub fn main_entry()->u32{let s:NativeByteSlice=native_text_open("20:22",5);
let a:NativeParsedPair=native_parse_u32_pair(s,native_text_open("",0));
let b:NativeParsedPair=native_parse_u32_pair(native_text_invalid(),native_text_open(":",1));
let c:NativeParsedU32=native_parse_u32_range(s,18446744073709551615,1);
if let NativeParsedPair::Err(e)=a{if e.kind!=7{return 1;}}else{return 2;}
if let NativeParsedPair::Err(e)=b{if e.kind!=7{return 3;}}else{return 4;}
if let NativeParsedU32::Err(e)=c{if e.kind!=7||e.offset!=18446744073709551615{return 5;}}else{return 6;}return 42;}''')

    def test_library_parse_overflow_and_sum_overflow(self):
        self.library('parse_overflow','''pub fn main_entry()->u32{let d:NativeByteSlice=native_text_open(":",1);
let a:NativeParsedU32=native_parse_u32_pair_sum(native_text_open("0:4294967296",12),d);
let b:NativeParsedU32=native_parse_u32_pair_sum(native_text_open("4294967295:1",12),d);
if let NativeParsedU32::Err(e)=a{if e.kind!=4||e.offset!=11{return 1;}}else{return 2;}
if let NativeParsedU32::Err(e)=b{if e.kind!=4||e.offset!=0{return 3;}}else{return 4;}return 42;}''')

    def test_library_strict_parsing_and_first_delimiter(self):
        for i,text in enumerate(('20: 22','+20:22','20:22:1')):
            with self.subTest(text=text):
                self.library('parse_strict_'+str(i),'pub fn main_entry()->u32{let r:NativeParsedPair=native_parse_u32_pair(native_text_open("'+text+'",'+str(len(text))+'),native_text_open(":",1));'
                             'if let NativeParsedPair::Err(e)=r{if e.kind==3{return 42;}}return 1;}')

    def test_library_range_and_zero_values(self):
        self.library('parse_range','''pub fn main_entry()->u32{
if let NativeParsedU32::Ok(n)=native_parse_u32_range(native_text_open("x42y",4),1,2){if n!=42{return 1;}}else{return 2;}
if let NativeParsedU32::Ok(n)=native_parse_u32_pair_sum(native_text_open("0:0",3),native_text_open(":",1)){if n!=0{return 3;}}else{return 4;}
return 42;}''')

    def test_imported_application_source_executes(self):
        root=Path(__file__).resolve().parents[1]
        example=(root/'examples/native_error_composition/main.sotlas').read_text(encoding='utf-8')
        self.library('parse_application','\n'.join(line for line in example.splitlines() if not line.startswith(('module ','import '))))


if __name__ == '__main__':
    unittest.main()
