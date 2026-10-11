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

    def test_native_lowering_preserves_parameter_binding_and_return_domains(self):
        program='module unit;struct Token{pub value:u32;}fn read(value:whisper Token)->u32{return value.value;}fn make()->sole Token{return Token{value:42};}fn transfer(value:sole Token)->sole Token{return value;}pub fn main_entry()->u32{let owner:sole Token=make();return read(owner);}'
        source='''import sotlas::compiler::token::*;
import sotlas::compiler::ast::*;import sotlas::compiler::lexer::*;
import sotlas::compiler::parser::*;import sotlas::compiler::sema::*;
import sotlas::compiler::backend::target_ir::*;
import sotlas::compiler::backend::lower_scalar::*;
static mut text_bytes:[u8;4194304]=0;
static mut tokens:[Token;1024]=0;static mut nodes:[AstNode;1024]=0;
static mut values:[TargetValue;256]=0;static mut parameters:[TargetParameter;32]=0;
static mut instructions:[TargetInstruction;512]=0;static mut operands:[TargetOperand;512]=0;
static mut incoming:[TargetPhiInput;64]=0;static mut blocks:[TargetBlock;128]=0;
static mut edges:[u32;256]=0;static mut functions:[TargetFunction;16]=0;
pub fn main_entry()->u32{
let input:*const u8="PROGRAM";let length:usize=LENGTH;
let text:*mut u8=unsafe{text_bytes as *mut u8};let mut index:usize=0;
while index<length{unsafe{*(text+index)=*(input+index);}index=index+1;}
unsafe{g_extended_len=length;}
let tok:*mut Token=unsafe{tokens as *mut Token};let ast:*mut AstNode=unsafe{nodes as *mut AstNode};
let vals:*mut TargetValue=unsafe{values as *mut TargetValue};
let pars:*mut TargetParameter=unsafe{parameters as *mut TargetParameter};
let mut lexer:Lexer=Lexer::new(text,length);let mut count:usize=0;
while count<1024{let token:Token=lexer.next_token();unsafe{*(tok+count)=token;}count=count+1;if token.kind==TokenKind::Eof{break;}}
if lexer.error_count!=0 || count==1024{return 1;}
let mut parser:Parser=Parser::new(tok,count,ast,1024);let unit:usize=parser.parse_module();
if unit==0 || parser.error_count!=0{return 2;}
let mut sema:Sema=Sema::new();
if !sema.check_top_level_declarations(ast,parser.node_count,unit,text,length){return 3;}
let mut lowering:ScalarLowering=ScalarLowering::new(ast,parser.node_count,text,length,
vals,256,pars,32,unsafe{instructions as *mut TargetInstruction},512,
unsafe{operands as *mut TargetOperand},512,unsafe{incoming as *mut TargetPhiInput},64,
unsafe{blocks as *mut TargetBlock},128,unsafe{edges as *mut u32},256,
unsafe{functions as *mut TargetFunction},16);
let mut ir:TargetModule=TargetModule{version:1,function_count:0,parameter_count:0,
block_count:0,instruction_count:0,value_count:0,operand_count:0,phi_input_count:0,target_count:0};
if !lower_scalar_module(&mut lowering,unit,&mut ir){return 4;}
let mut exclusive:usize=0;let mut borrowed_values:usize=0;index=0;
while index<ir.value_count as usize{let flags:u32=unsafe{(*(vals+index)).flags};
let domain:u32=(flags&TARGET_VALUE_DOMAIN_MASK)>>TARGET_VALUE_DOMAIN_SHIFT;
if domain==1{exclusive=exclusive+1;}else if domain==4{borrowed_values=borrowed_values+1;}else if domain!=0{return 5;}index=index+1;}
if exclusive<4 || borrowed_values!=1{return 6;}
let first:TargetParameter=unsafe{*pars};
if first.type_tag!=TargetTypeTag::Pointer || unsafe{(*(vals+first.value_id as usize-1)).flags}!=1024{return 7;}
return 42;}'''.replace('PROGRAM',program).replace('LENGTH',str(len(program)))
        self.execute(self.compile('native_owned_ir_domains',source))

    def test_native_whisper_reads_and_forwarding_preserve_owner(self):
        source='''struct Token{pub value:u32;}
fn read(value:whisper Token)->u32{return value.value;}
fn forward(value:whisper Token)->u32{return read(value);}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:21};
if forward(owner)!=21 || read(owner)!=21{return 1;}return consume(owner)+21;}'''
        self.execute(self.compile('whisper_internal_forward',source))

    def test_native_exclusive_static_and_receiver_calls_preserve_transfers(self):
        source='''struct Token{pub value:u32;}struct Factory{pub initial:u32;}
impl Token{pub fn create()->sole Token{return Token{value:21};}
pub fn consume(value:sole Token)->u32{return value.value;}}
impl Factory{pub fn build(self:&Self)->sole Token{return Token{value:self.initial};}}
pub fn main_entry()->u32{let factory:Factory=Factory{initial:21};
let first:sole Token=Token::create();let second:sole Token=factory.build();
return Token::consume(first)+Token::consume(second);}'''
        self.execute(self.compile('exclusive_method_transfers',source))
        self.compile('exclusive_method_moved',source.replace('return Token::consume(first)+Token::consume(second);','Token::consume(first);return first.value+second.value;'),success=False)
        self.compile('exclusive_receiver_erasure',source.replace('let second:sole Token=factory.build();','let second:Token=factory.build();'),success=False)

    def test_native_exclusive_unsafe_wrapper_preserves_consumption(self):
        source='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=Token{value:42};let second:sole Token=unsafe{first};return consume(second);}'''
        self.execute(self.compile('exclusive_unsafe_transfer',source))
        self.compile('exclusive_unsafe_moved',source.replace('return consume(second);','return first.value+consume(second);'),success=False)

    def test_unsafe_pod_value_bindings_keep_independent_storage(self):
        source='''struct Token{pub value:u32;}
pub fn main_entry()->u32{let mut original:Token=Token{value:42};
let copied:Token=unsafe{original};original.value=99;return copied.value;}'''
        self.execute(self.compile('unsafe_pod_value_copy',source))

    def test_native_whisper_rejects_mutation_escape_and_overlapping_move(self):
        prefix='struct Token{pub value:u32;}'
        cases=(
            'fn write(value:whisper Token)->u32{value.value=0;return value.value;}',
            'fn erase(value:whisper Token)->Token{return value;}',
            'fn escape(value:whisper Token)->u32{let copied:Token=value;return copied.value;}',
            'fn escape(value:whisper Token)->u32{let copied:Token=unsafe{value};return copied.value;}',
            'fn escape(value:whisper Token)->*const Token{return unsafe{(&value) as *const Token};}',
            'fn consume(value:sole Token)->u32{return value.value;}fn bad(value:whisper Token)->u32{return consume(value);}',
            'fn overlap(borrowed:whisper Token,owned:sole Token)->u32{return borrowed.value+owned.value;}pub fn main_entry()->u32{let owner:sole Token=Token{value:21};return overlap(owner,owner);}',
            'fn overlap(borrowed:whisper Token,owned:sole Token)->u32{return borrowed.value+owned.value;}pub fn main_entry()->u32{let owner:sole Token=Token{value:21};return overlap(unsafe{owner},owner);}',
            'fn overlap(owned:sole Token,borrowed:whisper Token)->u32{return borrowed.value+owned.value;}pub fn main_entry()->u32{let owner:sole Token=Token{value:21};return overlap(owner,owner);}',
            'pub fn main_entry()->u32{let value:whisper Token=Token{value:42};return value.value;}',
            '@extern(C) fn escape(value:whisper Token)->u32;',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('whisper_native_reject_'+str(index),prefix+body,success=False)

    def test_native_exclusive_conditional_consumption_has_path_states(self):
        source='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}
fn choose(flag:bool)->u32{let value:sole Token=Token{value:42};
let answer:u32=if flag{consume(value)}else{consume(value)};return answer;}
pub fn main_entry()->u32{if choose(true)!=42 || choose(false)!=42{return 1;}return 42;}'''
        self.execute(self.compile('exclusive_conditional_calls',source))
        invalid=source.replace('else{consume(value)}','else{42}').replace('return answer;','return value.value;')
        self.compile('exclusive_conditional_maybe_moved',invalid,success=False)

    def test_native_exclusive_else_if_merges_only_reachable_paths(self):
        source='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}
fn choose(n:u32)->u32{let value:sole Token=Token{value:42};
if n==0{return consume(value);}else if n==1{return consume(value);}return value.value;}
pub fn main_entry()->u32{if choose(0)!=42 || choose(1)!=42 || choose(2)!=42{return 1;}return 42;}'''
        self.execute(self.compile('exclusive_else_if_returns',source))
        self.compile('exclusive_else_if_moved',source.replace('else if n==1{return consume(value);}','else if n==1{consume(value);}'),success=False)

    def test_native_exclusive_rejects_erasure_through_returned_values(self):
        prefix='''struct Token{pub value:u32;}fn create()->sole Token{return Token{value:42};}'''
        cases=(
            'pub fn main_entry()->u32{let value:Token=create();return value.value;}',
            'pub fn main_entry()->u32{let value:Token=unsafe{create()};return value.value;}',
            'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let value:Token=unsafe{owner};return value.value;}',
            'fn erase()->Token{return create();}pub fn main_entry()->u32{return erase().value;}',
            'impl Token{pub fn create()->sole Token{return Token{value:42};}}pub fn main_entry()->u32{let value:Token=Token::create();return value.value;}',
            'pub fn main_entry()->u32{let mut value:Token=Token{value:0};value=create();return value.value;}',
            'pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut value:Token=Token{value:0};value=owner;return value.value;}',
            'struct Box{pub inner:Token;}pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let value:Box=Box{inner:owner};return value.inner.value;}',
        )
        for index,body in enumerate(cases):
            with self.subTest(index=index):
                self.compile('exclusive_domain_erasure_'+str(index),prefix+body,success=False)

    def test_native_exclusive_pod_call_binding_and_return_transfers(self):
        source='''struct Token{pub value:u32;}
fn create()->sole Token{return Token{value:42};}
fn forward(value:sole Token)->sole Token{return value;}
fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let first:sole Token=create();let second:exclusive Token=first;
let third:sole Token=forward(second);return consume(third);}'''
        obj=self.compile('exclusive_pod_transfers',source)
        self.execute(obj)
        # The reference grammar spells exclusive POD values with a sole
        # declaration. Compare layout and execution through that equivalent
        # spelling; native move violations have separate rejection gates.
        path=obj.with_suffix('.sotlas')
        original=path.read_text(encoding='utf-8')
        reference=original.replace('struct Token{','sole struct Token{').replace('sole Token','Token').replace('exclusive Token','Token')
        path.write_text(reference,encoding='utf-8')
        try:
            self.assert_c11_reference(obj)
        finally:
            path.write_text(original,encoding='utf-8')

    def test_native_exclusive_branch_merge_and_live_return_path(self):
        source='''struct Token{pub value:u32;}
fn consume(value:sole Token)->u32{return value.value;}
fn select(flag:bool)->u32{let value:sole Token=Token{value:42};
if flag{return consume(value);}return value.value;}
pub fn main_entry()->u32{if select(true)!=42 || select(false)!=42{return 1;}return 42;}'''
        self.execute(self.compile('exclusive_live_paths',source))
        invalid='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:42};if true{consume(value);}return value.value;}'''
        self.compile('exclusive_maybe_moved',invalid,success=False)

    def test_native_exclusive_loop_rejects_repeated_outer_consumption(self):
        source='''struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}
pub fn main_entry()->u32{let value:sole Token=Token{value:42};let mut index:u32=0;
while index<2{consume(value);index=index+1;}return 42;}'''
        self.compile('exclusive_loop_move',source,success=False)

    def test_native_exclusive_pod_rejects_moves_aliases_and_pointer_escapes(self):
        prefix='struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}'
        cases=(
            'let first:sole Token=Token{value:42};consume(first);return first.value;',
            'let first:sole Token=Token{value:42};let second:sole Token=first;return first.value;',
            'let first:sole Token=Token{value:42};consume(first);return consume(first);',
            'let first:sole Token=Token{value:42};let alias:Token=first;return alias.value;',
            'let first:sole Token=Token{value:42};let alias:*const Token=unsafe{(&first) as *const Token};return 42;',
        )
        for index,body in enumerate(cases):
            self.compile('exclusive_violation_'+str(index),prefix+'pub fn main_entry()->u32{'+body+'}',success=False)

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
