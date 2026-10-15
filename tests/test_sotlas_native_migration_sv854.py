"""Native SV8.54 frontend, nested ownership edges, arena and IR contracts."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv851 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV854Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV851Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV851Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV851Tests.compile
    execute=previous.NativeMigrationSV851Tests.execute
    link_image=previous.NativeMigrationSV851Tests.link_image
    runtime=previous.NativeMigrationSV851Tests.runtime
    ir=previous.NativeMigrationSV851Tests.ir

    def controls(self,name,escape,code):
        source="pub fn main_entry()->u32{let value:u8='\\"+escape+"';"
        source+='let bytes:*const u8="\\'+escape+'";if value!='+str(code)
        source+=' || unsafe{*bytes}!='+str(code)+'{return 1;}return 42;}'
        self.execute(self.compile(name,source))

    def test_frontend_backspace_escape_matches_character_and_string_bytes(self):
        self.controls('backspace','b',8)

    def test_frontend_form_feed_escape_matches_character_and_string_bytes(self):
        self.controls('form_feed','f',12)

    def test_frontend_vertical_tab_escape_matches_character_and_string_bytes(self):
        self.controls('vertical_tab','v',11)

    def test_frontend_unknown_string_escapes_fail_instead_of_dropping_the_backslash(self):
        for index,escape in enumerate(('q','z','u1234')):
            self.compile('unknown_string_'+str(index),'fn bad()->*const u8{return "\\'+escape+'";}',success=False)
        self.execute(self.compile('escaped_quote',r'''pub fn main_entry()->u32{let text:*const u8="\'";
if unsafe{*text}!=39{return 1;}return 42;}'''))

    def ownership(self,name,body):
        prefix='''struct Token{pub value:u32;}fn consume(value:sole Token)->void{return;}
pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;
while count<3{count=count+1;'''
        self.execute(self.compile(name,prefix+body+'}return owner.value;}'))
        moved=body.replace('break;','consume(owner);break;',1)
        self.compile(name+'_moved',prefix+moved+'}return owner.value;}',success=False)

    def test_ownership_nested_mixed_then_edges_keep_break_and_continue_states_separate(self):
        self.ownership('nested_then','if count==2{if count==2{break;}else{continue;}}else{continue;}')

    def test_ownership_nested_mixed_else_edges_preserve_live_owners(self):
        self.ownership('nested_else','if count==1{continue;}else{if count==2{break;}else{continue;}}')

    def test_ownership_match_arms_accept_closed_nested_mixed_edges(self):
        self.ownership('match_mixed','match count{1=>{continue;},_=>{if count==2{break;}else{continue;}}}')

    def test_ownership_nested_matches_do_not_overwrite_sibling_break_summaries(self):
        self.ownership('nested_match','match count{1=>{continue;},_=>{match count{2=>{break;},_=>{continue;}}}}')
        # Earlier consuming arms must survive evaluation of later nested arms.
        source='''struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}
fn bad()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;while count<3{count=count+1;
match count{1=>{consume(owner);break;},_=>{match count{2=>{break;},_=>{continue;}}}}}return owner.value;}'''
        self.compile('sibling_break_summary',source,success=False)

    def test_memory_calloc_checks_product_overflow_and_clears_elements(self):
        self.runtime('calloc','''let mut bytes:[u8;16]=[7;16];let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},16);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};
if native_arena_calloc(a,18446744073709551615,2,1)!=null || arena.used!=0{return 1;}
if native_arena_calloc(a,3,4,1)==null || arena.used!=12 || bytes[11]!=0 || bytes[12]!=7{return 2;}return 42;''')

    def test_memory_contains_checks_allocated_extent_and_rejects_cursor_corruption(self):
        self.runtime('contains','''let mut bytes:[u8;16]=0;let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},16);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};let p:*mut u8=native_arena_alloc(a,4,1);
if !native_arena_contains(a,p,4) || native_arena_contains(a,p,5) || native_arena_contains(null,p,1){return 1;}
arena.used=17;if native_arena_contains(a,p,1){return 2;}return 42;''')

    def test_memory_grow_last_preserves_content_and_rejects_nonlast_allocations(self):
        self.runtime('grow_last','''let mut bytes:[u8;16]=[42;16];let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},16);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};let p:*mut u8=native_arena_alloc(a,4,1);
if !native_arena_grow_last(a,p,4,8) || arena.used!=8 || bytes[0]!=42{return 1;}
native_arena_alloc(a,4,1);if native_arena_grow_last(a,p,8,9) || arena.used!=12{return 2;}return 42;''')

    def test_memory_shrink_last_invalidates_marks_without_changing_rejected_cursors(self):
        self.runtime('shrink_last','''let mut bytes:[u8;16]=0;let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},16);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};let p:*mut u8=native_arena_alloc(a,8,1);let mark:NativeArenaMark=native_arena_mark(a);
if !native_arena_shrink_last(a,p,8,4) || arena.used!=4 || native_arena_rewind(a,mark){return 1;}
if native_arena_shrink_last(a,p,8,2) || arena.used!=4{return 2;}return 42;''')

    def contract(self,name,function,good_left,good_right,bad_left,bad_right):
        self.runtime(name,'''let mut result:u64=7;let p:*mut u64=unsafe{(&mut result) as *mut u64};
if !'''+function+'('+good_left+','+good_right+''',p) || result!=42{return 1;}
if '''+function+'('+bad_left+','+bad_right+''',p) || result!=42{return 2;}
if '''+function+'(1,1,null){return 3;}return 42;')

    def test_contract_checked_add_preserves_output_on_overflow(self):
        self.contract('contract_add','native_contract_add','40','2','18446744073709551615','1')

    def test_contract_checked_sub_preserves_output_on_underflow(self):
        self.contract('contract_sub','native_contract_sub','44','2','1','2')

    def test_contract_checked_mul_preserves_output_on_overflow(self):
        self.contract('contract_mul','native_contract_mul','21','2','18446744073709551615','2')

    def test_contract_checked_alignment_rejects_invalid_masks_and_wraparound(self):
        self.contract('contract_align','native_contract_align','41','2','18446744073709551615','2')
        self.runtime('invalid_alignment','''let mut value:u64=7;let p:*mut u64=unsafe{(&mut value) as *mut u64};
if native_contract_align(1,3,p) || native_contract_align(1,0,p) || value!=7{return 1;}return 42;''')

    def metadata(self,name,opcode,field):
        self.ir(name,'''let mut value:TargetInstruction=TargetInstruction::new(TargetOpcode::'''+opcode+''');
if !target_instruction_metadata_valid(value){return 1;}'''+field+'''
if target_instruction_metadata_valid(value){return 2;}return 42;''')

    def test_ir_phi_rejects_hidden_symbols(self):
        self.metadata('phi_metadata','Phi','value.symbol=TargetSourceSlice{offset:1,length:1};')

    def test_ir_load_rejects_hidden_symbols(self):
        self.metadata('load_metadata','Load','value.symbol=TargetSourceSlice{offset:0,length:1};')

    def test_ir_store_rejects_reserved_flags(self):
        self.metadata('store_metadata','Store','value.flags=16;')

    def test_ir_scalar_casts_reject_unrelated_branch_metadata(self):
        for opcode in ('IntCast','FloatCast','FloatNeg','NumericCast'):
            self.metadata('cast_metadata_'+opcode,opcode,'value.target_count=1;')

    def immediate(self,typ,maximum):
        source=(ROOT/'bootstrap/sotlas/native_compiler/backend/x86_64_scalar.sotlas').read_text(encoding='utf-8')
        start=source.index('pub fn object_integer_immediate_valid(')
        helper=source[start:source.index('\n}',start)+2]
        ir=(ROOT/'bootstrap/sotlas/native_compiler/backend/target_ir.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile('immediate_'+typ,ir+'\n'+helper+'''\npub fn main_entry()->u32{
if !object_integer_immediate_valid(TargetTypeTag::'''+typ+','+str(maximum)+''')
|| object_integer_immediate_valid(TargetTypeTag::'''+typ+','+str(maximum+1)+'''){return 1;}return 42;}'''))

    def test_backend_u8_immediates_cannot_truncate_high_bits(self):self.immediate('U8',255)
    def test_backend_i8_immediates_require_an_eight_bit_twos_complement_pattern(self):self.immediate('I8',255)
    def test_backend_u16_immediates_cannot_truncate_high_bits(self):self.immediate('U16',65535)
    def test_backend_i16_immediates_require_a_sixteen_bit_twos_complement_pattern(self):self.immediate('I16',65535)

if __name__=='__main__':unittest.main()
