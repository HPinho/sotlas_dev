"""Execute checked numeric parsing/formatting and native error propagation."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT=Path(__file__).resolve().parents[1]


class NativeNumericResultTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,body,helpers=''):
        source=(ROOT/'runtime/native/results.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,source+'\n'+helpers+'\npub fn main_entry()->u32{'+body+'}'))

    def test_checked_add_and_sub_boundaries(self):
        self.program('numeric_add_sub','''let sum:NativeU32Result=native_u32_add(20,22);
let max:NativeU32Result=native_u32_add(4294967295,0);
if sum.status!=0 || sum.value!=42 || max.status!=0 || max.value!=4294967295
|| native_u32_add(4294967295,1).status!=4 || native_u32_sub(0,1).status!=5
|| native_u32_sub(42,0).value!=42 || native_u32_sub(42,42).value!=0{return 1;}return 42;''')

    def test_multiply_zero_exact_limit_and_overflow(self):
        self.program('numeric_mul','''if native_u32_mul(4294967295,0).status!=0
|| native_u32_mul(4294967295,0).value!=0 || native_u32_mul(4294967295,1).value!=4294967295
|| native_u32_mul(65535,65537).value!=4294967295 || native_u32_mul(65536,65536).status!=4{return 1;}
return native_u32_mul(6,7).value;''')

    def test_division_and_remainder_do_not_trap_on_zero(self):
        self.program('numeric_div_rem','''if native_u32_div(1,0).status!=6 || native_u32_rem(1,0).status!=6
|| native_u32_div(4294967295,1).value!=4294967295 || native_u32_rem(43,7).value!=1{return 1;}
return native_u32_div(84,2).value;''')

    def test_narrowing_preserves_the_u32_limit(self):
        self.program('numeric_narrow','''if native_u32_narrow(4294967295).value!=4294967295
|| native_u32_narrow(4294967296).status!=7 || native_u32_narrow(18446744073709551615).status!=7{return 1;}
return native_u32_narrow(42).value;''')

    def test_decimal_success_zero_leading_zero_and_maximum(self):
        self.program('numeric_parse','''if native_parse_u32("0",1).value!=0 || native_parse_u32("00042",5).value!=42
|| native_parse_u32("4294967295",10).value!=4294967295 || native_parse_u32("4294967295",10).status!=0{return 1;}
return native_parse_u32("42",2).value;''')

    def test_decimal_overflow_reports_the_offending_byte(self):
        self.program('numeric_parse_overflow','''let r:NativeU32Result=native_parse_u32("4294967296",10);
let long:NativeU32Result=native_parse_u32("99999999999",11);
if r.status!=4 || r.error.kind!=4 || r.error.offset!=9 || long.status!=4 || long.error.offset!=9{return 1;}return 42;''')

    def test_decimal_invalid_ascii_sign_whitespace_and_zero_terminator(self):
        for index,(text,length,offset) in enumerate((('4x',2,1),('-1',2,0),('+1',2,0),(' 1',2,0),('1 ',2,1),('4',2,1))):
            with self.subTest(text=text):
                self.program('numeric_invalid_'+str(index),
                             'let r:NativeU32Result=native_parse_u32("'+text+'",'+str(length)+');'
                             'if r.status!=3 || r.error.offset!='+str(offset)+'{return 1;}return 42;')

    def test_null_empty_and_wrapping_ranges_do_not_dereference_input(self):
        self.program('numeric_ranges','''if native_parse_u32(null,0).status!=2 || native_parse_u32(null,1).status!=1{return 1;}
let address:u64=18446744073709551615;let p:*const u8=unsafe{address as *const u8};
if native_parse_u32(p,1).status!=7{return 2;}return 42;''')

    def test_bounded_parse_and_sum_propagate_structured_errors(self):
        self.program('numeric_bounded_sum','''if native_parse_u32_bounded("42",2,42).value!=42
|| native_parse_u32_bounded("43",2,42).status!=7{return 1;}
let bad:NativeU32Result=native_parse_u32_sum("2x",2,"22",2);
if bad.status!=3 || bad.error.offset!=1{return 2;}
if native_parse_u32_sum("4294967295",10,"1",1).status!=4{return 3;}
return native_parse_u32_sum("20",2,"22",2).value;''')

    def test_decimal_format_zero_and_maximum(self):
        self.program('numeric_format','''let mut bytes:[u8;12]=[99;12];let p:*mut u8=unsafe{bytes as *mut u8};
let r:NativeU32Result=native_format_u32(4294967295,p,10);
if r.status!=0 || r.value!=10 || bytes[0]!=52 || bytes[9]!=53 || bytes[10]!=99{return 1;}
let zero:NativeU32Result=native_format_u32(0,p,1);
if zero.value!=1 || bytes[0]!=48 || bytes[1]!=50{return 2;}return 42;''')

    def test_format_failure_preserves_the_destination(self):
        self.program('numeric_format_fail','''let mut bytes:[u8;4]=[77;4];let p:*mut u8=unsafe{bytes as *mut u8};
if native_format_u32(1000,p,3).status!=7 || bytes[0]!=77 || bytes[3]!=77
|| native_format_u32(0,p,0).status!=7 || native_format_u32(42,null,2).status!=1{return 1;}
let address:u64=18446744073709551615;let invalid:*mut u8=unsafe{address as *mut u8};
if native_format_u32(42,invalid,2).status!=7{return 2;}return 42;''')

    def test_parse_format_roundtrip_for_representative_values(self):
        self.program('numeric_roundtrip','''let numbers:[u32;8]=[0,1,9,10,42,999,1000000,4294967295];
let mut buffer:[u8;10]=0;let p:*mut u8=unsafe{buffer as *mut u8};let mut i:u32=0;
while i<8{let count:NativeU32Result=native_format_u32(numbers[i],p,10);
let parsed:NativeU32Result=native_parse_u32(p,count.value as usize);
if count.status!=0 || parsed.status!=0 || parsed.value!=numbers[i]{return 1;}i=i+1;}return 42;''')

    def test_question_operator_integrates_arithmetic_parse_and_cleanup(self):
        self.program('numeric_pipeline','''let good:NativeU32Result=work(true);let bad:NativeU32Result=work(false);
if good.value!=42 || bad.status!=6 || unsafe{trace}!=2121{return 1;}return good.value;''',
                     '''static mut trace:u32=0;
fn work(ok:bool)->NativeU32Result{defer{unsafe{trace=trace*10+1;}}defer{unsafe{trace=trace*10+2;}}
let first:u32=native_parse_u32("20",2)?;let second:u32=native_parse_u32("22",2)?;
let sum:u32=native_u32_add(first,second)?;let divisor:u32=if ok{1}else{0};
let result:u32=native_u32_div(sum,divisor)?;return native_u32_ok(result);}''')

    def test_error_constructor_cannot_encode_failure_as_success(self):
        self.program('numeric_nonzero_error','''let r:NativeU32Result=native_u32_error(0,9);
if r.status==0 || r.error.kind==0 || r.error.offset!=9 || r.value!=0{return 1;}return 42;''')

    def test_resource_scope_is_closed_on_success_and_propagated_error(self):
        managed=(ROOT/'runtime/native/managed.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.program('numeric_managed_cleanup','''let mut bytes:[u8;2]=[21;2];
let mut header:NativeRefHeader=native_ref_init();let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
let mut resource:NativeManagedBytes=native_managed_bytes_open(h,unsafe{bytes as *mut u8},2);
let slot:*mut NativeManagedBytes=unsafe{(&mut resource) as *mut NativeManagedBytes};
let weak:NativeWeakToken=native_managed_bytes_weak(slot);
let mut table:[usize;2]=0;let mut scope:NativeManagedScope=native_managed_scope_init(unsafe{table as *mut usize},2);
let s:*mut NativeManagedScope=unsafe{(&mut scope) as *mut NativeManagedScope};
if !native_managed_scope_push(s,slot){return 1;}let bad:NativeU32Result=work(s,true);
if bad.status!=6 || header.live || bytes[0]!=0 || scope.used!=0 || native_weak_current(weak){return 2;}
if !native_ref_recycle(h){return 3;}resource=native_managed_bytes_open(h,unsafe{bytes as *mut u8},2);
if !native_managed_scope_push(s,slot){return 4;}let good:NativeU32Result=work(s,false);
if good.status!=0 || header.live || scope.used!=0 || header.strong!=0{return 5;}
native_managed_scope_close(s);return good.value;''',
                     managed+'''fn work(scope:*mut NativeManagedScope,fail:bool)->NativeU32Result{
defer native_managed_scope_close(scope);let divisor:u32=if fail{0}else{1};
let n:u32=native_u32_div(42,divisor)?;return native_u32_ok(n);}''')


if __name__=='__main__':
    unittest.main()
