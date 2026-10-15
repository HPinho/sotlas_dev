"""Native contracts added after SV8.50; no host tools in generated execution."""
from pathlib import Path
import unittest
import struct
import test_sotlas_native_i32 as integer
import test_sotlas_native_boundary_expansion as boundary

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV851Tests(unittest.TestCase):
    setUpClass=classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass=classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile=integer.NativeI32Tests.compile
    link_image=integer.NativeI32Tests.link_image
    execute=integer.NativeI32Tests.execute
    reject_object=boundary.NativeBoundaryExpansionTests.reject_object

    def runtime(self,name,body):
        text=(ROOT/'runtime/native/managed.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,text+'\npub fn main_entry()->u32{'+body+'}'))

    def test_frontend_hex_literals_execute_in_constants_arrays_matches_and_signed_returns(self):
        self.execute(self.compile('sv851_hex', '''const VALUE:u32=0x2_A;
fn minimum()->i8{return -0X80;}
pub fn main_entry()->u32{let values:[u32;2]=[0x10,0x1a];
if minimum()!=-128{return 1;}match VALUE{0x2a=>{return values[0]+values[1];},_=>{return 2;}}}'''))
        for index,literal in enumerate(('0x1_00','0xfffffffffffffffff','0xg')):
            self.compile('sv851_bad_hex_'+str(index),'fn number()->u8{return '+literal+';}',success=False)

    def test_frontend_binary_literals_preserve_width_and_reject_invalid_digits(self):
        self.execute(self.compile('sv851_binary','pub fn main_entry()->u32{let byte:u8=0b0010_1010;return byte as u32;}'))
        for index,literal in enumerate(('0b2','0b','0b_1','0b100000000')):
            self.compile('sv851_bad_binary_'+str(index),'fn number()->u8{return '+literal+';}',success=False)

    def test_frontend_octal_literals_preserve_width_and_reject_invalid_digits(self):
        self.execute(self.compile('sv851_octal','pub fn main_entry()->u32{let byte:u8=0o52;return byte as u32;}'))
        for index,literal in enumerate(('0o8','0o','0o_7','0o400')):
            self.compile('sv851_bad_octal_'+str(index),'fn number()->u8{return '+literal+';}',success=False)

    def test_frontend_ascii_character_literals_and_escapes_execute(self):
        self.execute(self.compile('sv851_character',r'''pub fn main_entry()->u32{let value:u8='*';
let newline:u8='\n';let zero:u8='\0';if newline!=10 || zero!=0{return 1;}return value as u32;}'''))
        for index,literal in enumerate(("''","'ab'",r"'\q'","'é'")):
            self.compile('sv851_bad_character_'+str(index),'fn number()->u8{return '+literal+';}',success=False)

    def test_ownership_weak_tokens_bind_upgrade_to_the_original_control_block(self):
        self.runtime('sv851_weak_identity','''let mut a:NativeRefHeader=native_ref_init();let mut b:NativeRefHeader=native_ref_init();
let first:*mut NativeRefHeader=unsafe{(&mut a) as *mut NativeRefHeader};
let second:*mut NativeRefHeader=unsafe{(&mut b) as *mut NativeRefHeader};let token:NativeWeakToken=native_ref_weak(first);
if !native_weak_upgrade(token) || a.strong!=2 || b.strong!=1{return 1;}
if native_ref_release_checked(first)!=1 || native_ref_release_checked(first)!=2{return 2;}
if native_weak_upgrade(token) || !native_ref_retain(second){return 3;}return 42;''')

    def test_ownership_weak_capture_rejects_dead_and_null_control_blocks(self):
        self.runtime('sv851_weak_capture','''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
native_ref_release(p);let dead:NativeWeakToken=native_ref_weak(p);let empty:NativeWeakToken=native_ref_weak(null);
if dead.owner!=null || empty.owner!=null || native_weak_upgrade(dead) || native_weak_upgrade(empty){return 1;}return 42;''')

    def test_ownership_recycling_invalidates_prior_tokens_and_rejects_live_headers(self):
        self.runtime('sv851_recycle','''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
let old:NativeWeakToken=native_ref_weak(p);if native_ref_recycle(p){return 1;}
if !native_ref_release(p) || !native_ref_recycle(p) || native_weak_upgrade(old){return 2;}
let current:NativeWeakToken=native_ref_weak(p);if !native_weak_upgrade(current) || h.strong!=2{return 3;}
native_ref_release(p);native_ref_release(p);h.generation=18446744073709551615;
if native_ref_recycle(p){return 4;}return 42;''')

    def test_ownership_checked_release_distinguishes_invalid_retained_and_final(self):
        self.runtime('sv851_release_status','''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
if !native_ref_retain(p) || native_ref_release_checked(p)!=1 || native_ref_release_checked(p)!=2
|| native_ref_release_checked(p)!=0 || native_ref_release_checked(null)!=0{return 1;}return 42;''')

    def test_memory_zero_allocations_clear_previous_backing_bytes(self):
        self.runtime('sv851_zero_alloc','''let mut bytes:[u8;32]=[255;32];let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},32);
let p:*mut u8=native_arena_alloc_zero(unsafe{(&mut arena) as *mut NativeArena},16,8);
if p==null{return 1;}let mut i:usize=0;while i<16{if unsafe{*(p+i)}!=0{return 2;}i=i+1;}return 42;''')

    def test_memory_copy_checks_overlap_and_keeps_rejected_destinations(self):
        self.runtime('sv851_copy','''let mut bytes:[u8;8]=[1,2,3,4,0,0,0,0];let p:*mut u8=unsafe{bytes as *mut u8};
if native_memory_copy(unsafe{p+1},p,4) || bytes[1]!=2{return 1;}
if !native_memory_copy(unsafe{p+4},p,4) || bytes[7]!=4 || !native_memory_copy(null,null,0){return 2;}return 42;''')

    def test_memory_move_handles_both_overlap_directions(self):
        self.runtime('sv851_move','''let mut bytes:[u8;8]=[1,2,3,4,5,6,7,8];let p:*mut u8=unsafe{bytes as *mut u8};
if !native_memory_move(unsafe{p+1},p,6) || bytes[6]!=6{return 1;}
if !native_memory_move(p,unsafe{p+1},6) || bytes[0]!=1 || bytes[5]!=6{return 2;}return 42;''')

    def test_memory_scrub_rewind_clears_only_discarded_bytes_and_invalidates_mark(self):
        self.runtime('sv851_scrub','''let mut bytes:[u8;16]=[77;16];let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},16);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};native_arena_alloc(a,4,1);
let mark:NativeArenaMark=native_arena_mark(a);native_arena_alloc(a,8,1);
if !native_arena_rewind_zero(a,mark) || arena.used!=4 || bytes[3]!=77 || bytes[4]!=0 || bytes[11]!=0 || bytes[12]!=77{return 1;}
if native_arena_rewind_zero(a,mark){return 2;}return 42;''')

    def test_authority_creation_preserves_mask_and_nonzero_generation(self):
        self.runtime('sv851_authority_create','''let authority:NativeAuthority=native_authority_init(42);
if authority.bits!=42 || authority.generation!=1{return 1;}return 42;''')

    def test_authority_revocation_changes_generation_and_cannot_wrap(self):
        self.runtime('sv851_authority_revoke','''let mut a:NativeAuthority=native_authority_init(7);let p:*mut NativeAuthority=unsafe{(&mut a) as *mut NativeAuthority};
if !native_authority_revoke(p,2) || a.bits!=5 || a.generation!=2{return 1;}
a.generation=18446744073709551615;if native_authority_revoke(p,1) || a.bits!=5{return 2;}return 42;''')

    def test_authority_checks_reject_stale_generation_even_for_remaining_bits(self):
        self.runtime('sv851_authority_stale','''let mut a:NativeAuthority=native_authority_init(7);let p:*mut NativeAuthority=unsafe{(&mut a) as *mut NativeAuthority};
native_authority_revoke(p,2);if native_authority_current(p,1,1) || !native_authority_current(p,2,1)
|| native_authority_current(p,2,2) || native_authority_current(null,1,1){return 1;}return 42;''')

    def test_state_transitions_require_current_authority_and_an_allowed_destination(self):
        self.runtime('sv851_state_current','''let mut state:u32=1;let s:*mut u32=unsafe{(&mut state) as *mut u32};
let mut a:NativeAuthority=native_authority_init(1);let p:*mut NativeAuthority=unsafe{(&mut a) as *mut NativeAuthority};
if native_state_transition_current(s,1,64,4,p,1,1) || native_state_transition_current(s,1,3,4,p,1,1){return 1;}
if !native_state_transition_current(s,1,2,4,p,1,1) || state!=2{return 2;}
native_authority_revoke(p,1);if native_state_transition_current(s,2,2,4,p,1,0){return 3;}return 42;''')

    def test_backend_signed_i32_pointer_offsets_sign_extend(self):
        self.execute(self.compile('sv851_i32_offset','''pub fn main_entry()->u32{let values:[u32;3]=[42,1,2];
let p:*const u32=unsafe{values as *const u32};let middle:*const u32=unsafe{p+1};let offset:i32=-1;
return unsafe{*(middle+offset)};}'''))

    def test_backend_signed_i64_pointer_offsets_work_in_both_directions(self):
        self.execute(self.compile('sv851_i64_offset','''pub fn main_entry()->u32{let values:[u32;3]=[42,1,2];
let p:*const u32=unsafe{values as *const u32};let offset:i64=-1;let middle:*const u32=unsafe{p+1};
if unsafe{*(middle-offset)}!=2{return 1;}
return unsafe{*(middle+offset)};}'''))

    def test_backend_signed_isize_pointer_offsets_match_machine_width(self):
        self.execute(self.compile('sv851_isize_offset','''pub fn main_entry()->u32{let values:[u32;3]=[42,1,2];
let p:*const u32=unsafe{values as *const u32};let offset:isize=-1;let middle:*const u32=unsafe{p+1};
return unsafe{*(middle+offset)};}'''))

    def test_backend_literal_addresses_keep_64_bits_and_require_unsafe(self):
        self.execute(self.compile('sv851_literal_address','''pub fn main_entry()->u32{
let p:*const u8=unsafe{0xffffffffffffffff as *const u8};let address:u64=unsafe{p as u64};
if address!=18446744073709551615{return 1;}return 42;}'''))
        self.compile('sv851_safe_address','fn bad()->*const u8{return 4096 as *const u8;}',success=False)

    def ir(self,name,body):
        text=(ROOT/'bootstrap/sotlas/native_compiler/backend/target_ir.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,text+'\npub fn main_entry()->u32{'+body+'}'))

    def test_ir_rejects_opcode_ids_outside_the_declared_schema(self):
        self.ir('sv851_opcode','''let invalid:TargetOpcode=unsafe{43 as TargetOpcode};
if target_opcode_is_valid(invalid) || !target_opcode_is_valid(TargetOpcode::PointerCast){return 1;}return 42;''')

    def test_ir_rejects_unknown_function_flags(self):
        self.ir('sv851_function_flags','''if target_function_flags_valid(128)
|| !target_function_flags_valid(TARGET_FLAG_SYSTEM) || !target_function_flags_valid(0){return 1;}return 42;''')

    def test_ir_rejects_unknown_value_flags_without_erasing_domain_bits(self):
        self.ir('sv851_value_flags','''if target_value_flags_valid(16) || !target_value_flags_valid(1024)
|| !target_value_flags_valid(1536) || target_value_flags_valid(2304){return 1;}return 42;''')

    def test_ir_pointer_cast_metadata_cannot_smuggle_symbols_or_immediates(self):
        self.ir('sv851_cast_metadata','''let mut instruction:TargetInstruction=TargetInstruction::new(TargetOpcode::PointerCast);
if !target_instruction_metadata_valid(instruction){return 1;}instruction.immediate_bits=1;
if target_instruction_metadata_valid(instruction){return 2;}instruction.immediate_bits=0;
instruction.symbol=TargetSourceSlice{offset:0,length:1};
if target_instruction_metadata_valid(instruction){return 3;}return 42;''')

    @staticmethod
    def symbols(data):
        headers=struct.unpack_from('<Q',data,40)[0];count=struct.unpack_from('<H',data,60)[0]
        for index in range(1,count):
            header=headers+index*64
            if struct.unpack_from('<I',data,header+4)[0]==2:
                symbols=struct.unpack_from('<Q',data,header+24)[0]
                linked=struct.unpack_from('<I',data,header+40)[0]
                strings,size=struct.unpack_from('<QQ',data,headers+linked*64+24)
                return symbols+24,strings,size,headers
        raise AssertionError('no symbol table')

    def test_object_symbol_names_must_terminate_inside_their_string_table(self):
        def mutate(data):
            symbol,strings,size,_=self.symbols(data);data[strings+size-1]=88
        self.reject_object('sv851_symbol_names',mutate)

    def test_object_unsupported_symbol_bindings_are_rejected(self):
        def mutate(data):
            symbol,_,_,_=self.symbols(data);data[symbol+4]=50
        self.reject_object('sv851_symbol_binding',mutate)

    def test_object_indirect_functions_and_reserved_visibility_bits_are_rejected(self):
        def mutate(data):
            symbol,_,_,_=self.symbols(data);data[symbol+4]=26
        self.reject_object('sv851_symbol_ifunc',mutate)
        def visibility(data):
            symbol,_,_,_=self.symbols(data);data[symbol+5]=128
        self.reject_object('sv851_symbol_visibility',visibility)

    def test_object_defined_symbol_spans_must_fit_their_declared_section(self):
        def mutate(data):
            symbol,_,_,headers=self.symbols(data);section=struct.unpack_from('<H',data,symbol+6)[0]
            size=struct.unpack_from('<Q',data,headers+section*64+32)[0]
            struct.pack_into('<Q',data,symbol+8,size+1)
        self.reject_object('sv851_symbol_span',mutate)

if __name__=='__main__':unittest.main()
