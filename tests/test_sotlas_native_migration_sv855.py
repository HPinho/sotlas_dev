"""SV8.55 native Unicode, returning ownership edges, memory and word APIs."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv851 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV855Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV851Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV851Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV851Tests.compile
    execute=previous.NativeMigrationSV851Tests.execute
    link_image=previous.NativeMigrationSV851Tests.link_image
    runtime=previous.NativeMigrationSV851Tests.runtime
    ir=previous.NativeMigrationSV851Tests.ir

    def unicode(self,name,scalar,expected):
        checks=' || '.join('unsafe{*(text+'+str(index)+')}!='+str(byte) for index,byte in enumerate(expected+b'\0'))
        self.execute(self.compile(name,'pub fn main_entry()->u32{let text:*const u8="\\u{'+scalar+'}";if '+checks+'{return 1;}return 42;}'))

    def test_frontend_unicode_ascii_escape_emits_one_byte_and_terminator(self):
        self.unicode('unicode_ascii','41',b'A')
        for index,value in enumerate(('', 'g', '1234567')):
            self.compile('bad_unicode_'+str(index),'fn bad()->*const u8{return "\\u{'+value+'}";}',success=False)

    def test_frontend_unicode_two_byte_escape_emits_utf8(self):
        self.unicode('unicode_two','e9',bytes((195,169)))

    def test_frontend_unicode_three_byte_escape_rejects_surrogates(self):
        self.unicode('unicode_three','20AC',bytes((226,130,172)))
        self.compile('unicode_surrogate','fn bad()->*const u8{return "\\u{D800}";}',success=False)

    def test_frontend_unicode_four_byte_escape_enforces_the_scalar_ceiling(self):
        self.unicode('unicode_four','1F680',bytes((240,159,154,128)))
        self.compile('unicode_too_large','fn bad()->*const u8{return "\\u{110000}";}',success=False)

    def owner(self,name,body):
        prefix='''struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;'''
        self.execute(self.compile(name,prefix+body+'}return owner.value;}'))

    def test_ownership_returning_arm_can_join_a_break_edge_in_both_orders(self):
        for index,body in enumerate(('if count==1{return owner.value;}else{break;}',
                                     'if count==1{break;}else{return owner.value;}')):
            self.owner('return_break_'+str(index),body)
        self.compile('return_consumed_break','''struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}
fn bad(flag:bool)->u32{let owner:sole Token=Token{value:42};while flag{if flag{return 42;}else{consume(owner);break;}}return owner.value;}''',success=False)

    def test_ownership_returning_arm_can_join_a_preserving_continue_edge(self):
        self.owner('return_continue','if count==2{return owner.value;}else{continue;}')
        self.compile('return_consumed_continue','''struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}
fn bad(flag:bool)->u32{let owner:sole Token=Token{value:42};while flag{if flag{return 42;}else{consume(owner);continue;}}return 42;}''',success=False)

    def test_ownership_returning_arm_preserves_nested_mixed_exit_summaries(self):
        self.owner('return_mixed','if count==1{return owner.value;}else{if count==2{break;}else{continue;}}')
        self.owner('mixed_return','if count==2{if count==2{break;}else{continue;}}else{return owner.value;}')

    def test_ownership_match_arms_accept_nested_returns_and_closed_loop_edges(self):
        self.owner('match_return_edges','match count{1=>{if count==1{continue;}else{return 42;}},_=>{if count==2{break;}else{return 42;}}}')

    def test_memory_find_publishes_the_first_index_only_when_found(self):
        self.runtime('memory_find','''let bytes:[u8;4]=[7,42,42,9];let p:*const u8=unsafe{bytes as *const u8};let mut index:usize=99;
let out:*mut usize=unsafe{(&mut index) as *mut usize};if !native_memory_find(p,4,42,out) || index!=1{return 1;}
if native_memory_find(p,4,3,out) || index!=1 || native_memory_find(null,0,1,out){return 2;}return 42;''')

    def test_memory_reverse_checks_ranges_and_handles_odd_lengths(self):
        self.runtime('memory_reverse','''let mut bytes:[u8;5]=[1,2,3,4,5];let p:*mut u8=unsafe{bytes as *mut u8};
if !native_memory_reverse(p,5) || bytes[0]!=5 || bytes[2]!=3 || bytes[4]!=1{return 1;}
if !native_memory_reverse(null,0) || native_memory_reverse(null,1)
|| native_memory_reverse(unsafe{18446744073709551615 as *mut u8},2){return 2;}return 42;''')

    def test_memory_swap_rejects_overlap_before_mutation(self):
        self.runtime('memory_swap','''let mut bytes:[u8;6]=[1,2,3,4,5,6];let p:*mut u8=unsafe{bytes as *mut u8};
if native_memory_swap(p,unsafe{p+1},3) || bytes[0]!=1{return 1;}
if !native_memory_swap(p,unsafe{p+3},3) || bytes[0]!=4 || bytes[3]!=1 || !native_memory_swap(p,p,6){return 2;}return 42;''')

    def test_memory_arena_copy_copies_bytes_and_preserves_rejected_cursor(self):
        self.runtime('arena_copy','''let input:[u8;3]=[40,1,1];let mut bytes:[u8;8]=0;
let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},8);let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};
let out:*mut u8=native_arena_copy(a,unsafe{input as *const u8},3,1);
if out==null || bytes[0]!=40 || bytes[2]!=1 || arena.used!=3{return 1;}
if native_arena_copy(a,null,1,1)!=null || arena.used!=3{return 2;}return 42;''')

    def test_contract_division_rejects_zero_without_publishing(self):
        self.runtime('checked_div','''let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_contract_div(84,2,out) || value!=42 || native_contract_div(1,0,out) || value!=42{return 1;}return 42;''')

    def test_contract_shift_checks_both_shift_width_and_value_overflow(self):
        self.runtime('checked_shift','''let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_contract_shift_left(21,1,out) || value!=42{return 1;}
if native_contract_shift_left(1,64,out) || native_contract_shift_left(18446744073709551615,1,out) || value!=42{return 2;}return 42;''')

    def test_contract_index_checks_index_stride_and_multiplication(self):
        self.runtime('checked_index','''let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_contract_index(8,7,6,out) || value!=42{return 1;}
if native_contract_index(7,7,6,out) || native_contract_index(8,7,0,out)
|| native_contract_index(18446744073709551615,3,18446744073709551615,out) || value!=42{return 2;}return 42;''')

    def test_contract_extent_checks_the_whole_span_before_publishing(self):
        self.runtime('checked_extent','''let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_contract_extent(2,10,4,42,out) || value!=42{return 1;}
if native_contract_extent(3,10,4,42,out) || native_contract_extent(0,18446744073709551615,2,18446744073709551615,out)
|| value!=42{return 2;}return 42;''')

    def metadata(self,name,opcode,field):
        self.ir(name,'''let mut instruction:TargetInstruction=TargetInstruction::new(TargetOpcode::'''+opcode+''');
if !target_instruction_metadata_valid(instruction){return 1;}'''+field+'''
if target_instruction_metadata_valid(instruction){return 2;}return 42;''')

    def test_ir_arithmetic_rejects_hidden_immediates(self):self.metadata('arithmetic_metadata','Add','instruction.immediate_bits=1;')
    def test_ir_comparisons_reject_unrelated_symbols(self):self.metadata('compare_metadata','Compare','instruction.symbol=TargetSourceSlice{offset:0,length:1};')
    def test_ir_index_addresses_reject_unrelated_branch_targets(self):self.metadata('index_metadata','IndexAddr','instruction.target_count=1;')
    def test_ir_pointer_offsets_reject_reserved_flags(self):self.metadata('offset_metadata','PtrOffset','instruction.flags=16;')

    def word(self,name,body):
        source=(ROOT/'runtime/native/word.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,source+'\npub fn main_entry()->u32{'+body+'}'))

    def test_backend_word_rotate_left_preserves_bits_and_reduces_counts_modulo_64(self):
        self.word('rotate_left','''if native_word_rotate_left(21,65)!=42 || native_word_rotate_left(42,64)!=42
|| native_word_rotate_left(9223372036854775808,1)!=1{return 1;}return 42;''')

    def test_backend_word_rotate_right_preserves_bits_and_reduces_counts_modulo_64(self):
        self.word('rotate_right','''if native_word_rotate_right(84,65)!=42 || native_word_rotate_right(42,0)!=42
|| native_word_rotate_right(1,1)!=9223372036854775808{return 1;}return 42;''')

    def test_backend_word_byte_swap_has_an_involution_and_known_endianness(self):
        self.word('byte_swap','''if native_word_swap_bytes(0x0102030405060708)!=0x0807060504030201
|| native_word_swap_bytes(native_word_swap_bytes(42))!=42{return 1;}return 42;''')

    def test_backend_word_popcount_handles_empty_full_and_sparse_words(self):
        self.word('popcount','''if native_word_popcount(0)!=0 || native_word_popcount(18446744073709551615)!=64
|| native_word_popcount(42)!=3{return 1;}return 42;''')

if __name__=='__main__':unittest.main()
