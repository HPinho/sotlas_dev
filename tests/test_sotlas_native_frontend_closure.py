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
            'const BAD:f64=1.0+2.0;',
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
