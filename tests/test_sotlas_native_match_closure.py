"""Native match bindings, open ranges and POD aggregate values."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous


class NativeMatchClosureTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,source):self.execute(self.compile(name,source))

    def test_open_ranges_cover_signed_and_unsigned_domains(self):
        self.program('match_open','''fn sign(x:i8)->u32{return match x{..0=>20,0..=>22};}
fn full(x:u64)->u32{return match x{..=>42};}
pub fn main_entry()->u32{if full(18446744073709551615)!=42{return 1;}return sign(-128)+sign(127);}''')

    def test_inclusive_open_range(self):
        self.program('match_open_inclusive','''fn choose(x:u8)->u32{return match x{..=20=>20,21..=>22};}
pub fn main_entry()->u32{return choose(0)+choose(255);}''')

    def test_capture_subject_in_guard_and_result(self):
        self.program('match_binding','''fn choose(x:u32)->u32{return match x{n if n<20=>n,other=>other+2};}
pub fn main_entry()->u32{return choose(10)+choose(30);}''')

    def test_binding_scope_and_outer_shadow(self):
        self.program('match_binding_shadow','''pub fn main_entry()->u32{let n:u32=20;
let chosen:u32=match 2 as u32{n=>n};return n+chosen+20;}''')
        self.compile('match_binding_escape','''pub fn main_entry()->u32{
let chosen:u32=match 42 as u32{n=>n};return n;}''',False)

    def test_constant_identifiers_remain_patterns(self):
        self.program('match_binding_const','''const ANSWER:u32=42;
pub fn main_entry()->u32{return match 42 as u32{ANSWER=>42,_=>1};}''')

    def test_binding_in_statement_match(self):
        self.program('match_statement_binding','''pub fn main_entry()->u32{
match 40 as u32{n if n<20=>{return 1;},n=>{return n+2;}}}''')

    def test_pod_record_result_and_return(self):
        self.program('match_record_result','''struct Pair{pub left:u32;pub right:u32;}
fn choose(x:bool)->Pair{return match x{true=>Pair{left:20,right:22},false=>Pair{left:1,right:2}};}
pub fn main_entry()->u32{let p:Pair=choose(true);return p.left+p.right;}''')

    def test_record_arms_copy_independent_storage(self):
        self.program('match_record_copy','''struct Pair{pub values:[u32;2];}
pub fn main_entry()->u32{let original:Pair=Pair{values:[20,22]};
let mut copy:Pair=match true{true=>original,false=>Pair{values:[1,2]}};
copy.values[0]=1;return original.values[0]+original.values[1];}''')

    def test_record_result_nominal_mismatch_is_rejected(self):
        self.compile('match_record_nominal','''struct A{pub value:u32;}struct B{pub value:u32;}
pub fn main_entry()->u32{let result:A=match true{true=>B{value:42},false=>B{value:1}};return result.value;}''',False)

    def test_pointer_record_results_remain_rejected(self):
        self.compile('match_record_pointer','''struct A{pub value:*mut u32;}
pub fn main_entry()->u32{let result:A=match true{true=>A{value:null},false=>A{value:null}};return 42;}''',False)

    def test_value_blocks_with_locals_and_mutation(self):
        self.program('match_value_block','''pub fn main_entry()->u32{
let value:u32=match 20 as u32{n=>{let mut x:u32=n;x=x+2;x+20}};return value;}''')
        self.compile('match_block_scope','''pub fn main_entry()->u32{
let value:u32=match true{true=>{let x:u32=42;x},false=>0};return x;}''',False)

    def test_value_block_defers_run_after_value_is_captured(self):
        self.program('match_block_defer','''static mut trace:u32=0;
fn observe(x:u32){unsafe{trace=trace*10+x;}}
pub fn main_entry()->u32{let mut x:u32=42;
let result:u32=match true{true=>{defer observe(1);defer observe(2);x},false=>0};
if unsafe{trace}!=21{return 1;}return result;}''')

    def test_value_block_early_return_cleans_up_enclosing_defers(self):
        self.program('match_block_return','''static mut trace:u32=0;
fn observe(x:u32){unsafe{trace=trace*10+x;}}
fn choose()->u32{defer observe(1);let ignored:u32=match true{
true=>{defer observe(2);return 42;0},false=>0};return ignored;}
pub fn main_entry()->u32{let result:u32=choose();if unsafe{trace}!=21{return 1;}return result;}''')

    def test_record_tail_blocks_and_nested_matches(self):
        self.program('match_record_block','''struct A{pub value:u32;}
fn choose(x:u32)->A{return match x{n=>{let value:u32=match n{0=>1,_=>42};A{value:value}}};}
pub fn main_entry()->u32{let a:A=choose(1);return a.value;}''')

    def test_nominal_enum_results_in_returns_arguments_and_inference(self):
        self.program('match_enum_result','''enum Kind{A=1,B=2}
fn choose(x:bool)->Kind{return match x{true=>Kind::A,false=>Kind::B};}
fn read(x:Kind)->u32{return match x{Kind::A=>20,Kind::B=>22};}
pub fn main_entry()->u32{let kind=match true{true=>Kind::A,false=>Kind::B};
return read(kind)+read(choose(false));}''')

    def test_enum_results_reject_nominal_erasure_and_mismatch(self):
        prefix='enum A{One=1,Two=2}enum B{One=1,Two=2}'
        for code in (
            'pub fn main_entry()->u32{let x:B=match true{true=>A::One,false=>A::Two};return 42;}',
            'fn wrong()->B{return match true{true=>A::One,false=>A::Two};}pub fn main_entry()->u32{return 42;}',
            'fn read(x:B)->u32{return 42;}pub fn main_entry()->u32{return read(match true{true=>A::One,false=>A::Two});}',
            'pub fn main_entry()->u32{let x:A=match true{true=>A::One,false=>B::Two};return 42;}',
        ):
            with self.subTest(code=code):self.compile('match_enum_mismatch',prefix+code,False)

    def test_diverging_value_arm_needs_no_fake_tail(self):
        self.program('match_diverging_arm','''fn choose(x:bool)->u32{
return match x{true=>{return 42;},false=>1};}
pub fn main_entry()->u32{return choose(true);}''')
        self.compile('match_missing_value','''pub fn main_entry()->u32{
return match true{true=>{let x:u32=42;},false=>0};}''',False)

    def test_binding_is_immutable_and_sibling_scoped(self):
        for value in ('match 42 as u32{n=>{n=1;n}}','match true{true=>{let x:u32=42;x},false=>x}'):
            with self.subTest(value=value):self.compile('match_binding_bad','pub fn main_entry()->u32{return '+value+';}',False)

    def test_open_range_rejects_invalid_endpoints_and_overlaps(self):
        for value in ('match 0 as u8{..0=>1,_=>42}','match 0 as u8{..=256=>42}',
                      'match 0 as u8{..=10=>1,10..=>42}','match true{..=>42}',
                      'match 0 as i8{..-129=>1,_=>42}'):
            with self.subTest(value=value):self.compile('match_open_bad','pub fn main_entry()->u32{return '+value+';}',False)

    def test_deferred_mutation_cannot_change_the_captured_result(self):
        self.program('match_capture_before_defer','''pub fn main_entry()->u32{
let mut x:u32=42;let result:u32=match true{true=>{defer x=1;x},false=>0};
if x!=1{return 1;}return result;}''')
        self.program('match_record_before_defer','''struct A{pub value:u32;}
pub fn main_entry()->u32{let mut original:A=A{value:42};
let result:A=match true{true=>{defer original.value=1;original},false=>A{value:0}};
if original.value!=1{return 1;}return result.value;}''')

    def test_enum_result_with_early_return_arm(self):
        self.program('match_enum_early','''enum Kind{A=1,B=2}
fn choose(x:bool)->Kind{return match x{true=>{return Kind::A;},false=>Kind::B};}
pub fn main_entry()->u32{return match choose(true){Kind::A=>42,Kind::B=>1};}''')

    def test_nested_blocks_preserve_result_context(self):
        self.program('match_nested_context','''pub fn main_entry()->u32{
let result:u32=match true{true=>{let x:u32=match true{true=>{let n:u32=20;n},false=>0};x+22},false=>0};return result;}''')

    def test_pattern_binding_shadows_owner_without_capturing_it(self):
        self.program('match_binding_owned_shadow','''pub fn main_entry()->u32{
let n:sole u32=40;let value:u32=match 2 as u32{n=>n};return n+value;}''')

    def test_checked_in_full_match_example(self):
        path=Path(__file__).resolve().parents[1]/'examples/native_match_values/main.sotlas'
        self.program('match_closure_example',path.read_text(encoding='utf-8').split(';',1)[1])

    def test_binding_respects_local_storage_capacity(self):
        prefix=''.join('let v'+str(i)+':u32=0;' for i in range(127))
        self.program('match_binding_capacity','pub fn main_entry()->u32{'+prefix+'return match 42 as u32{n=>n};}')
        self.compile('match_binding_capacity_overflow','pub fn main_entry()->u32{'+prefix+'let extra:u32=0;return match 42 as u32{n=>n};}',False)


if __name__=='__main__':unittest.main()
