"""Scalar native match expressions share statement coverage/guard rules."""
import unittest
from pathlib import Path
import test_sotlas_native_i32 as previous


class NativeMatchValueTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile=previous.NativeI32Tests.compile
    link_image=previous.NativeI32Tests.link_image
    execute=previous.NativeI32Tests.execute

    def program(self,name,source):self.execute(self.compile(name,source))

    def test_mutable_var_and_bare_loop_inside_value_block(self):
        self.program('match_value_block_loop', '''pub fn main_entry()->u32{
let result:u32=match true{
true=>{var steps:u32=0;loop{
steps=steps+1;
if steps==2{continue;}
if steps==3{break;}
}steps+39},
false=>0};
return result;}''')

    def test_match_value_block_invalid_loop_paths_reject(self):
        self.compile('match_value_block_unscoped_break', '''pub fn main_entry()->u32{
return match true{true=>{break;42},false=>0};}''', False)
        self.compile('match_value_block_missing_yield', '''pub fn main_entry()->u32{
return match true{true=>{var n:u32=0;loop{n=n+1;if n==3{break;}}},false=>0};}''', False)

    def test_let_return_and_call_argument_values(self):
        self.program('match_value_basic','''fn add(x:u32,y:u32)->u32{return x+y;}
fn select(x:u32)->u32{return match x{0=>20,_=>22};}
pub fn main_entry()->u32{let value:u32=match 0 as u32{0=>20,_=>1};
return add(value,match 1 as u32{0=>0,_=>select(1)});}''')

    def test_subject_evaluates_once_and_unselected_arms_are_lazy(self):
        self.program('match_value_once','''static mut calls:u32=0;
fn subject()->u32{unsafe{calls=calls+1;}return 1;}
fn bad()->u32{unsafe{calls=100;}return 0;}
pub fn main_entry()->u32{let value:u32=match subject(){0=>bad(),1=>42,_=>bad()};
if unsafe{calls}!=1{return 1;}return value;}''')

    def test_guards_and_ranges(self):
        self.program('match_value_guard','''fn select(x:u8)->u32{
return match x{0..=10 if x<5=>1,0..=10=>20,11..=255=>22};}
pub fn main_entry()->u32{return select(5)+select(11);}''')

    def test_boolean_coverage_and_boolean_result(self):
        self.program('match_value_bool','''fn yes(x:bool)->bool{return match x{true=>false,false=>true};}
pub fn main_entry()->u32{if yes(false)&&!yes(true){return 42;}return 1;}''')

    def test_signed_float_and_nested_match_results(self):
        self.program('match_value_nested','''fn number(x:u32)->i32{return match x{0=>-42,_=>7};}
fn fraction(x:bool)->f64{return match x{true=>1.5,false=>2.5};}
pub fn main_entry()->u32{let value:u32=match true{true=>match 1 as u32{1=>42,_=>0},false=>0};
if number(0)!=-42||fraction(true)!=1.5{return 1;}return value;}''')

    def test_enum_subject_and_exhaustive_patterns(self):
        self.program('match_value_enum','''enum Kind{First=1,Second=2}
fn select(kind:Kind)->u32{return match kind{Kind::First=>20,Kind::Second=>22};}
pub fn main_entry()->u32{return select(Kind::First)+select(Kind::Second);}''')

    def test_invalid_coverage_types_patterns_and_blocks_fail_closed(self):
        for value in ('match 0 as u32{0=>42}', 'match true{true=>42}',
                      'match 0 as u32{0=>42,0=>1,_=>2}', 'match 0 as u32{_=>42,0=>1}',
                      'match 0 as u32{0=>42,_=>false}', 'match 0 as u32{0=>42,_=>{1;}}',
                      'match 0 as u32{0 if true=>42}', 'match 0 as u32{}'):
            with self.subTest(value=value):
                self.compile('match_value_bad','pub fn main_entry()->u32{return '+value+';}',False)

    def test_inferred_integer_and_match_in_arithmetic(self):
        self.program('match_value_inferred','''pub fn main_entry()->u32{
let first=match true{true=>20,false=>0};
return first+(match 1 as u32{1=>22,_=>0});}''')

    def test_match_is_a_loop_and_branch_condition(self):
        self.program('match_value_condition','''pub fn main_entry()->u32{
let mut n:u32=0;while match n{0..=1=>true,_=>false}{n=n+1;}
if match n{2=>true,_=>false}{return 42;}return 1;}''')

    def test_guards_evaluate_only_after_pattern_and_in_order(self):
        self.program('match_value_guard_order','''static mut seen:u32=0;
fn guard(x:u32)->bool{unsafe{seen=seen*10+x;}return x==2;}
pub fn main_entry()->u32{let result:u32=match 1 as u32{
0 if guard(9)=>1,1 if guard(1)=>2,1 if guard(2)=>42,_=>0};
if unsafe{seen}!=12{return 1;}return result;}''')

    def test_all_result_arms_are_type_checked_even_when_unselected(self):
        for bad in ('256','false','1.5','unknown()', 'null'):
            with self.subTest(bad=bad):
                self.compile('match_value_dead_type','''pub fn main_entry()->u32{
let value:u8=match true{true=>42,false=>'''+bad+'};return value as u32;}',False)

    def test_owned_capture_pointer_record_and_enum_results_are_rejected(self):
        for source in (
            'pub fn main_entry()->u32{let owner:sole u32=42;return match true{true=>owner,false=>0};}',
            'struct A{pub value:*mut u32;}pub fn main_entry()->u32{let a:A=match true{true=>A{value:null},false=>A{value:null}};return 42;}',
            'pub fn main_entry()->u32{let p:*const u8=match true{true=>null,false=>null};return 42;}',
            'enum E{A=1,B=2}pub fn main_entry()->u32{return match true{true=>E::A,false=>E::B};}',
            'fn make()->sole u32{return 42;}pub fn main_entry()->u32{return match true{true=>make(),false=>0};}',
        ):
            with self.subTest(source=source):self.compile('match_value_payload',source,False)

    def test_match_in_defer_runs_at_scope_exit(self):
        self.program('match_value_defer','''static mut result:u32=0;
fn record(x:u32){unsafe{result=x;}}
fn step(){defer record(match true{true=>42,false=>1});}
pub fn main_entry()->u32{step();return unsafe{result};}''')

    def test_match_loop_assignment_and_early_return(self):
        self.program('match_value_loop','''fn compute()->u32{
let mut total:u32=0;let mut i:u32=0;while i<3{
total=total+match i{0=>10,1=>12,_=>20};i=i+1;}
return match total{42=>total,_=>1};}
pub fn main_entry()->u32{return compute();}''')

    def test_syntax_missing_commas_and_incomplete_ranges_are_rejected(self):
        for value in ('match true{true=>42 false=>0}', 'match 0 as u32{0..= =>42,_=>0}',
                      'match true{true=>,false=>42}'):
            with self.subTest(value=value):
                self.compile('match_value_syntax','pub fn main_entry()->u32{return '+value+';}',False)

    def test_inferred_boolean_and_nested_lazy_values(self):
        self.program('match_value_inferred_bool','''pub fn main_entry()->u32{
let ready=match true{true=>true,false=>false};
if ready&&(match false{true=>false,false=>true}){return 42;}return 1;}''')

    def test_arm_capacity_is_explicit(self):
        arms=','.join(str(i)+'=>42' for i in range(63))
        self.program('match_value_capacity','pub fn main_entry()->u32{return match 0 as u32{'+arms+',_=>1};}')
        self.compile('match_value_capacity_overflow','pub fn main_entry()->u32{return match 0 as u32{'+arms+',63=>42,_=>1};}',False)

    def test_checked_in_classification_example(self):
        path=Path(__file__).resolve().parents[1]/'examples/native_match_values/main.sotlas'
        self.program('match_value_example',path.read_text(encoding='utf-8').split(';',1)[1])

    def test_numeric_result_widths(self):
        for typ,value in (('u8','255'),('u16','65535'),('u32','4294967295'),
                          ('u64','18446744073709551615'),('i8','-128'),('i16','-32768'),
                          ('i32','-2147483648'),('i64','-9223372036854775808'),('f32','1.5'),('f64','2.5')):
            with self.subTest(typ=typ):
                zero='0.0' if typ.startswith('f') else '0'
                self.program('match_value_width_'+typ,'fn value(x:bool)->'+typ+'{return match x{true=>'+value+',false=>'+zero+'};}'
                             +'pub fn main_entry()->u32{if value(true)!='+value+'{return 1;}return 42;}')


if __name__=='__main__':unittest.main()
