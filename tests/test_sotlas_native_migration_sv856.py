"""SV8.56 compound assignment, preserving early jumps and checked native APIs."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv855 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV856Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV855Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV855Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV855Tests.compile
    execute=previous.NativeMigrationSV855Tests.execute
    link_image=previous.NativeMigrationSV855Tests.link_image
    runtime=previous.NativeMigrationSV855Tests.runtime
    ir=previous.NativeMigrationSV855Tests.ir
    word=previous.NativeMigrationSV855Tests.word

    def compound(self,name,operator,initial,operand):
        self.execute(self.compile(name,'pub fn main_entry()->u32{let mut value:u32='+str(initial)+';value'+operator+str(operand)+';return value;}'))
        self.compile(name+'_immutable','fn bad()->u32{let value:u32='+str(initial)+';value'+operator+str(operand)+';return value;}',success=False)

    def test_frontend_plus_equal_preserves_mutability_and_evaluates_rhs_once(self):
        self.compound('plus_equal','+=',40,2)
        self.execute(self.compile('plus_once','''static mut calls:u32=0;fn addend()->u32{unsafe{calls=calls+1;}return 2;}
pub fn main_entry()->u32{let mut value:u32=40;value+=addend();if unsafe{calls}!=1{return 1;}return value;}'''))

    def test_frontend_minus_equal_executes_and_rejects_immutable_bindings(self):self.compound('minus_equal','-=',44,2)
    def test_frontend_star_equal_executes_and_rejects_immutable_bindings(self):self.compound('star_equal','*=',21,2)
    def test_frontend_slash_equal_executes_and_rejects_general_places(self):
        self.compound('slash_equal','/=',84,2)
        self.compile('compound_place','fn bad()->u32{let mut items:[u32;1]=[42];items[0]+=1;return items[0];}',success=False)

    def ownership(self,name,body):
        prefix='''struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;'''
        self.execute(self.compile(name,prefix+body+'}return owner.value;}'))
        # Moves before the conditional jump must never be hidden by a
        # returning/falling-through sibling, even when both paths stop later.
        bad=prefix+'consume(owner);'+body+'}return 42;}'
        self.compile(name+'_premoved',bad,success=False)

    def test_ownership_preserving_then_break_can_have_implicit_fallthrough(self):
        self.ownership('then_break','if count==2{break;}if owner.value!=42{return 1;}')
    def test_ownership_preserving_else_break_can_have_live_then_fallthrough(self):
        self.ownership('else_break','if count==1{let seen:u32=owner.value;}else{break;}')
    def test_ownership_preserving_then_continue_uses_the_loop_entry_snapshot(self):
        self.ownership('then_continue','if count==1{continue;}if owner.value!=42{return 1;}')
    def test_ownership_preserving_else_continue_restores_nested_loop_entries(self):
        self.ownership('else_continue','let mut inner:u32=0;while inner<1{inner=inner+1;}if count==2{let seen:u32=owner.value;}else{continue;}')

    def test_memory_buffer_initialization_bounds_null_storage(self):
        self.runtime('buffer_init','''let mut bytes:[u8;8]=0;let buffer:NativeByteBuffer=native_buffer_init(unsafe{bytes as *mut u8},8);
let empty:NativeByteBuffer=native_buffer_init(null,8);if buffer.capacity!=8 || buffer.used!=0 || empty.capacity!=0{return 1;}return 42;''')
    def test_memory_buffer_append_handles_overlap_and_preserves_failed_lengths(self):
        self.runtime('buffer_append','''let mut bytes:[u8;8]=[1,2,3,4,0,0,0,0];let data:*mut u8=unsafe{bytes as *mut u8};
let mut buffer:NativeByteBuffer=native_buffer_init(data,8);let p:*mut NativeByteBuffer=unsafe{(&mut buffer) as *mut NativeByteBuffer};
if !native_buffer_append(p,data,4) || !native_buffer_append(p,unsafe{data+1},3) || buffer.used!=7 || bytes[4]!=2 || bytes[6]!=4{return 1;}
if native_buffer_append(p,data,2) || buffer.used!=7{return 2;}return 42;''')
    def test_memory_buffer_truncation_clears_only_the_discarded_suffix(self):
        self.runtime('buffer_truncate','''let mut bytes:[u8;6]=[7;6];let data:*mut u8=unsafe{bytes as *mut u8};
let mut buffer:NativeByteBuffer=native_buffer_init(data,6);let p:*mut NativeByteBuffer=unsafe{(&mut buffer) as *mut NativeByteBuffer};native_buffer_append(p,data,6);
if !native_buffer_truncate_zero(p,2) || buffer.used!=2 || bytes[1]!=7 || bytes[2]!=0 || bytes[5]!=0{return 1;}
if native_buffer_truncate_zero(p,3) || buffer.used!=2{return 2;}return 42;''')
    def test_memory_buffer_consumption_compacts_and_clears_the_old_tail(self):
        self.runtime('buffer_consume','''let mut bytes:[u8;6]=[1,2,3,4,5,6];let data:*mut u8=unsafe{bytes as *mut u8};
let mut buffer:NativeByteBuffer=native_buffer_init(data,6);let p:*mut NativeByteBuffer=unsafe{(&mut buffer) as *mut NativeByteBuffer};native_buffer_append(p,data,6);
if !native_buffer_consume(p,2) || buffer.used!=4 || bytes[0]!=3 || bytes[3]!=6 || bytes[4]!=0 || bytes[5]!=0{return 1;}
if native_buffer_consume(p,5) || buffer.used!=4{return 2;}return 42;''')

    def signed(self,name,function,left,right,bad_left,bad_right):
        self.runtime(name,'''let mut value:i64=7;let out:*mut i64=unsafe{(&mut value) as *mut i64};
if !'''+function+'('+left+','+right+''',out) || value!=42{return 1;}
if '''+function+'('+bad_left+','+bad_right+''',out) || value!=42{return 2;}return 42;''')
    def test_contract_i64_add_rejects_signed_overflow_without_publishing(self):
        self.signed('i64_add','native_contract_i64_add','40','2','9223372036854775807','1')
    def test_contract_i64_sub_rejects_signed_underflow_without_publishing(self):
        self.signed('i64_sub','native_contract_i64_sub','44','2','-9223372036854775808','1')
    def test_contract_i64_mul_checks_sign_combinations_and_minimum(self):
        self.signed('i64_mul','native_contract_i64_mul','-21','-2','-9223372036854775808','-1')
        self.runtime('signed_mul_signs','''let mut value:i64=0;let out:*mut i64=unsafe{(&mut value) as *mut i64};
if !native_contract_i64_mul(6,-7,out) || value!=-42 || !native_contract_i64_mul(-6,7,out) || value!=-42
|| !native_contract_i64_mul(0,-9223372036854775808,out) || value!=0{return 1;}return 42;''')
    def test_contract_i64_div_rejects_the_minimum_over_minus_one(self):
        self.signed('i64_div','native_contract_i64_div','-84','-2','-9223372036854775808','-1')

    def metadata(self,name,opcode,field):
        self.ir(name,'''let mut instruction:TargetInstruction=TargetInstruction::new(TargetOpcode::'''+opcode+''');
if !target_instruction_metadata_valid(instruction){return 1;}'''+field+'''
if target_instruction_metadata_valid(instruction){return 2;}return 42;''')
    def test_ir_stack_allocations_reject_unrelated_edge_metadata(self):self.metadata('alloc_metadata','AllocStack','instruction.target_count=1;')
    def test_ir_calls_reject_reserved_flags(self):self.metadata('call_metadata','Call','instruction.flags=128;')
    def test_ir_system_operations_reject_unrelated_symbols(self):self.metadata('system_metadata','SystemOp','instruction.symbol=TargetSourceSlice{offset:0,length:1};')
    def test_ir_debug_slices_reject_source_range_overflow(self):
        self.ir('debug_ranges','''let mut block:TargetBlock=TargetBlock::empty();let mut instruction:TargetInstruction=TargetInstruction::new(TargetOpcode::Return);
let b:*const TargetBlock=unsafe{(&mut block) as *const TargetBlock};let i:*const TargetInstruction=unsafe{(&mut instruction) as *const TargetInstruction};
if !target_debug_slices_valid(42,1,b,1,i){return 1;}instruction.source_point=TargetSourceSlice{offset:1,length:18446744073709551615};
if target_debug_slices_valid(42,1,b,1,i){return 2;}return 42;''')

    def test_backend_word_leading_zeros_has_a_defined_zero_result(self):
        self.word('leading_zeros','''if native_word_leading_zeros(0)!=64 || native_word_leading_zeros(1)!=63
|| native_word_leading_zeros(9223372036854775808)!=0{return 1;}return 42;''')
    def test_backend_word_trailing_zeros_has_a_defined_zero_result(self):
        self.word('trailing_zeros','''if native_word_trailing_zeros(0)!=64 || native_word_trailing_zeros(8)!=3
|| native_word_trailing_zeros(1)!=0{return 1;}return 42;''')
    def test_backend_word_bit_reversal_preserves_all_sixty_four_bits(self):
        self.word('reverse_bits','''if native_word_reverse_bits(1)!=9223372036854775808
|| native_word_reverse_bits(native_word_reverse_bits(42))!=42{return 1;}return 42;''')
    def test_backend_word_extraction_checks_width_and_keeps_failed_output(self):
        self.word('extract_bits','''let mut value:u64=7;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_word_extract(672,4,6,out) || value!=42{return 1;}
if native_word_extract(1,63,2,out) || value!=42 || !native_word_extract(42,0,64,out) || value!=42{return 2;}
if !native_word_extract(42,64,0,out) || value!=0{return 3;}return 42;''')

if __name__=='__main__':unittest.main()
