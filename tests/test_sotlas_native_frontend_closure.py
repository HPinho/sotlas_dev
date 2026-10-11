"""Execution gates for native frontend closure and explicit runtime rejection."""
import unittest
import test_sotlas_native_i32 as integer


class NativeFrontendClosureTests(unittest.TestCase):
    setUpClass = classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile = integer.NativeI32Tests.compile
    link_image = integer.NativeI32Tests.link_image
    execute = integer.NativeI32Tests.execute
    assert_c11_reference = integer.NativeI32Tests.assert_c11_reference

    def test_constant_folding_preserves_operand_and_destination_types(self):
        cases=(
            'const F:f64=1.5;const BAD:u32=F;',
            'const F:f64=1.5;static mut BAD:u32=F;',
            'const F:f64=1.5;const BAD:u32=F+1;',
            'const B:bool=true;static mut BAD:u32=B;',
            'const F:f32=1.5;static mut BAD:[u32;2]=[F;2];',
            'const BAD:bool=0;',
        )
        for index,declaration in enumerate(cases):
            self.compile('constant_type_error_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_boolean_array_fields_preserve_layout_copy_and_mutation(self):
        source='''struct Flags{pub values:[bool;4];pub total:u32;}
fn create()->Flags{return Flags{values:[false;4],total:42};}
pub fn main_entry()->u32{let original:Flags=create();let mut copy:Flags=original;
copy.values[2]=true;if original.values[2] || !copy.values[2] || copy.values[1]{return 1;}return copy.total;}'''
        obj=self.compile('boolean_array_fields',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_boolean_constants_compare_typed_values_and_initialize_arrays(self):
        source='''const NEG:i8=-7;const POS:i8=2;const REAL:f64=-1.5;
const READY:bool=(NEG<POS)&&!(REAL>=1.5)&&true;
pub fn main_entry()->u32{let flags:[bool;3]=[READY,false,!false];
if !flags[0] || flags[1] || !flags[2]{return 1;}return 42;}'''
        obj=self.compile('boolean_constant_comparisons',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_conditional_expressions_select_one_arm_in_loops_calls_and_returns(self):
        source='''static mut COUNT:u32=0;
fn arm(x:u32)->u32{unsafe{COUNT=COUNT+1;}return x;}
fn choose(flag:bool)->u32{return if flag {arm(40)} else {arm(2)};}
fn floating(flag:bool)->f64{return if flag {1.5} else if !flag {2.5} else {9.0};}
pub fn main_entry()->u32{let mut index:u32=0;let mut sum:u32=0;
while index<2{sum=sum+choose(index==0);index=index+1;}
let count:u32=unsafe{COUNT};if count!=2 || floating(true)+floating(false)!=4.0{return 1;}
let yes:bool=if sum==42 {true} else {false};if !yes{return 2;}return sum;}'''
        obj=self.compile('conditional_values',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_conditional_expressions_reject_missing_else_and_type_mismatch(self):
        for index,expression in enumerate(('if true {42}', 'if 7 {42} else {1}', 'if true {42} else {false}')):
            self.compile('bad_conditional_'+str(index),'pub fn main_entry()->u32{return '+expression+';}',success=False)

    def test_unsafe_same_width_integer_float_memory_reinterpretation(self):
        source='''pub fn main_entry()->u32{
let mut small:[u32;1]=[1069547520];let mut wide:[u64;1]=[4609434218613702656];
let small_words:*mut u32=unsafe{small as *mut u32};let wide_words:*mut u64=unsafe{wide as *mut u64};
let small_float:*mut f32=unsafe{small_words as *mut f32};let wide_float:*mut f64=unsafe{wide_words as *mut f64};
let a:f32=unsafe{*small_float};let expected:f32=1.5;let b:f64=unsafe{*wide_float};
if a!=expected || b!=1.5{return 1;}
unsafe{*small_float=2.5;*wide_float=2.5;}
if small[0]!=1075838976 || wide[0]!=4612811918334230528{return 2;}return 42;}'''
        self.execute(self.compile('memory_reinterpretation',source))

    def test_integer_float_memory_reinterpretation_requires_unsafe_and_equal_width(self):
        cases=(
            'let x:*mut f64=words as *mut f64;',
            'let x:*mut f32=unsafe{words as *mut f32};',
        )
        for index,cast in enumerate(cases):
            source='pub fn main_entry()->u32{let mut data:[u64;1]=0;let words:*mut u64=unsafe{data as *mut u64};'+cast+'return 42;}'
            self.compile('bad_reinterpret_'+str(index),source,success=False)

    def test_local_array_lists_and_runtime_repetition_execute(self):
        source='''fn calculate()->u32{let values:[i32;3]=[-7,20,29];
let mut copies:[u32;32]=[values[1] as u32;32];let floats:[f64;2]=[1.5,2.5];
copies[31]=22;let mut index:u32=0;let mut sum:u32=0;
while index<32{sum=sum+copies[index];index=index+1;}
if sum!=642 || floats[0]+floats[1]!=4.0{return 1;}return (values[0]+values[1]+values[2]) as u32;}
pub fn main_entry()->u32{return calculate();}'''
        obj=self.compile('initialized_local_arrays',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_array_initializers_reject_shape_and_element_type_errors(self):
        for index,initializer in enumerate((
            'let values:[u32;3]=[1,2];','let values:[u32;2]=[1,2,3];',
            'let values:[u32;2]=[1,true];','let values:[u8;2]=[1,256];',
            'let values:[u32;3]=[7;2];',
        )):
            self.compile('bad_array_'+str(index),'pub fn main_entry()->u32{'+initializer+'return 42;}',success=False)

    def test_float_and_boolean_constant_expressions_execute(self):
        source='''const A:f32=1.25;const B:f32=A+A;
const SCALE:f64=(1.5+2.5)*3.0/2.0;const READY:bool=true&&false||true;
static mut VALUES:[f32;3]=[B;3];static mut TOTAL:f64=SCALE+0.5;
pub fn main_entry()->u32{let b:f32=B;let expected:f32=2.5;
let last:f32=unsafe{VALUES[2]};let total:f64=unsafe{TOTAL};
if b!=expected || last!=expected || SCALE!=6.0 || total!=6.5 || !READY{return 1;}return 42;}'''
        obj=self.compile('folded_float_boolean',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_float_constant_overflow_is_rejected_before_output(self):
        self.compile('float_constant_overflow','const BAD:f32=1e17*1e17*1e17;pub fn main_entry()->u32{return 42;}',success=False)

    def test_integer_constant_expressions_are_folded_before_emission(self):
        source='''const BASE:u32=6*7;const NEXT:u32=(BASE+5)-5;
const NEG:i16=(-6*7)/2;const BITS:u32=((NEXT<<2)|3)&255;
static mut COUNT:u32=NEXT+1;
pub fn main_entry()->u32{let count:u32=unsafe{COUNT};
if BASE!=42 || NEXT!=42 || NEG!=-21 || BITS!=171 || count!=43{return 1;}return NEXT;}'''
        obj=self.compile('folded_constants',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_invalid_integer_constant_expressions_fail_even_when_unused(self):
        for index,declaration in enumerate((
            'const BAD:i8=127+1;','const BAD:i8=-128-1;',
            'const BAD:i16=300*300;','const BAD:i64=-9223372036854775808/-1;',
            'const BAD:u32=4/0;','const BAD:u32=4%0;',
            'const BAD:u32=1<<32;','const BAD:i32=1<<31;',
        )):
            self.compile('bad_fold_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_scientific_literals_in_calls_constants_and_static_storage(self):
        source='''const FACTOR:f64=1.5e+1;static mut INPUT:f32=1.25E-1;
fn calculate(x:f64)->f64{return x*FACTOR;}
pub fn main_entry()->u32{let small:f32=unsafe{INPUT};let expected:f32=0.125;
if small!=expected || calculate(2e0)!=3.0e1{return 1;}
let tiny:f64=1e-18;if tiny<=0.0{return 2;}return 42;}'''
        obj=self.compile('scientific_literals',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_scientific_literals_reject_bad_exponents_before_output(self):
        for index,literal in enumerate(('1e','1e+','1e-','1e19','1e-19','1.0e99999')):
            self.compile('bad_exponent_'+str(index),'pub fn value()->f64{return '+literal+';}',success=False)

    def test_initialized_scalar_storage_and_repeated_arrays_execute(self):
        source='''static mut COUNT:u32=41;static mut SMALL:i8=-128;
static mut RATIO:f64=-1.5;static mut FLAGS:bool=true;
static mut WORDS:[u16;4]=[7;4];static mut ZEROS:[u32;4]=0;
pub fn main_entry()->u32{
let count:u32=unsafe{COUNT};let small:i8=unsafe{SMALL};let ratio:f64=unsafe{RATIO};let flags:bool=unsafe{FLAGS};
if count!=41 || small!=-128 || ratio!=-1.5 || !flags{return 1;}
let first:u16=unsafe{WORDS[0]};let last:u16=unsafe{WORDS[3]};let zero:u32=unsafe{ZEROS[2]};
if first!=7 || last!=7 || zero!=0{return 2;}
unsafe{COUNT=count+1;WORDS[1]=9;}
let changed:u16=unsafe{WORDS[1]};if changed!=9{return 3;}return unsafe{COUNT};}'''
        obj=self.compile('initialized_storage',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_invalid_static_initializers_do_not_become_zero_storage(self):
        for index,declaration in enumerate((
            'static mut BAD:i8=128;','static mut BAD:u32=-1;',
            'static mut BAD:bool=7;','static mut BAD:f64=true;',
            'static mut BAD:[u8;3]=[4;2];','static mut BAD:[u8;3]=[256;3];',
            'static mut BAD:[u8;3]=9;',
        )):
            self.compile('bad_static_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_typed_module_constants_include_float_bool_and_signed_minimum(self):
        source='''const FRACTION:f32=0.125;const SCALE:f64=-1.5;
const READY:bool=true;const LOW:i8=-128;const MINIMUM:i64=-9223372036854775808;
fn scale(x:f64)->f64{return x*SCALE;}
pub fn main_entry()->u32{let b:bool=READY;let a:f32=FRACTION;let n:i8=LOW;let wide:i64=MINIMUM;
let expected:f32=0.125;if !b || a!=expected || n!=-128 || wide!=-9223372036854775808{return 1;}
if scale(2.0)!=-3.0{return 2;}return 42;}'''
        obj=self.compile('scalar_constants',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_invalid_unused_constants_fail_closed(self):
        for index,declaration in enumerate((
            'const BAD:i8=-129;', 'const BAD:u8=256;',
            'const BAD:bool=42;', 'const BAD:f32=true;',
            'const BAD:f64=0.0000000000000000001;',
            'const BAD:f64=1.0/0.0;',
        )):
            self.compile('unused_bad_'+str(index),declaration+'pub fn main_entry()->u32{return 42;}',success=False)

    def test_unused_constants_do_not_leak_literal_ir_into_functions(self):
        source=''.join(f'const UNUSED{i}:f64=-1.25;' for i in range(40))
        source+='pub fn main_entry()->u32{return 42;}'
        self.execute(self.compile('constant_rollback',source))

    def test_semantic_runtime_markers_are_preserved_but_never_emitted_as_noops(self):
        source = '''import sotlas::compiler::backend::target_ir::*;
import sotlas::compiler::backend::x86_64_scalar::*;
static mut gate_output:[u8;8192]=0;
static mut gate_values:[TargetValue;1]=0;static mut gate_functions:[TargetFunction;1]=0;
static mut gate_blocks:[TargetBlock;1]=0;static mut gate_instructions:[TargetInstruction;3]=0;
static mut gate_operands:[TargetOperand;1]=0;
fn check_runtime_op(op:u32)->u32{
let v:*mut TargetValue=unsafe{gate_values as *mut TargetValue};
let f:*mut TargetFunction=unsafe{gate_functions as *mut TargetFunction};
let b:*mut TargetBlock=unsafe{gate_blocks as *mut TargetBlock};
let i:*mut TargetInstruction=unsafe{gate_instructions as *mut TargetInstruction};
let a:*mut TargetOperand=unsafe{gate_operands as *mut TargetOperand};
let mut value:TargetValue=TargetValue::empty();value.id=1;value.type_tag=TargetTypeTag::U32;
let mut function:TargetFunction=TargetFunction::empty();function.name=TargetSourceSlice{offset:0,length:4};
function.return_type=TargetTypeTag::U32;function.block_count=1;
let mut block:TargetBlock=TargetBlock::empty();block.id=1;block.instruction_count=2;
let mut constant:TargetInstruction=TargetInstruction::new(TargetOpcode::ConstInt);
constant.result_value=1;constant.type_tag=TargetTypeTag::U32;constant.immediate_bits=42;
let argument:TargetOperand=TargetOperand::new(1);
unsafe{*v=value;*f=function;*i=constant;*a=argument;}
let mut last:usize=1;let mut count:u32=2;
if op!=0{let mut marker:TargetInstruction=TargetInstruction::new(op as TargetOpcode);
marker.type_tag=TargetTypeTag::Void;marker.flags=TARGET_FLAG_SEMANTIC_ONLY;
unsafe{*(i+1)=marker;}block.instruction_count=3;last=2;count=3;}
let mut ending:TargetInstruction=TargetInstruction::new(TargetOpcode::Return);
ending.type_tag=TargetTypeTag::U32;ending.operand_count=1;
unsafe{*(i+last)=ending;*b=block;}
let ir:TargetModule=TargetModule{version:1,function_count:1,parameter_count:0,
block_count:1,instruction_count:count,value_count:1,operand_count:1,phi_input_count:0,target_count:0};
let fc:*const TargetFunction=unsafe{f as *const TargetFunction};
let vc:*const TargetValue=unsafe{v as *const TargetValue};
let bc:*const TargetBlock=unsafe{b as *const TargetBlock};
let ic:*const TargetInstruction=unsafe{i as *const TargetInstruction};
let ac:*const TargetOperand=unsafe{a as *const TargetOperand};
let m:*const TargetModule=unsafe{(&ir) as *const TargetModule};
if !target_module_validate_cfg(m,fc,null,vc,bc,ic,ac,null,null){return 1;}
let mut length:usize=999;unsafe{gate_output[0]=77;}
let accepted:bool=emit_elf64_module_object("unit",4,m,fc,null,vc,bc,ic,ac,null,null,
unsafe{gate_output as *mut u8},8192,unsafe{(&mut length) as *mut usize});
if op==0{if !accepted || length==0{return 2;}return 0;}
if accepted || length!=0 || unsafe{gate_output[0]}!=77{return 3;}
if unsafe{(*(i+1)).opcode as u32}!=op{return 4;}return 0;}
pub fn main_entry()->u32{if check_runtime_op(0)!=0{return 1;}
let mut op:u32=15;while op<=25{if check_runtime_op(op)!=0{return op;}op=op+1;}return 42;}'''
        self.execute(self.compile('semantic_gate',source))


if __name__=='__main__':
    unittest.main()
