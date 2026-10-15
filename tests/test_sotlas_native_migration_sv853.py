"""Four native execution contracts in each of six compiler/runtime areas."""
import unittest
import test_sotlas_native_migration_sv851 as previous


class NativeMigrationSV853Tests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeMigrationSV851Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeMigrationSV851Tests.tearDownClass.__func__)
    compile = previous.NativeMigrationSV851Tests.compile
    execute = previous.NativeMigrationSV851Tests.execute
    link_image = previous.NativeMigrationSV851Tests.link_image
    runtime = previous.NativeMigrationSV851Tests.runtime
    ir = previous.NativeMigrationSV851Tests.ir

    def test_frontend_hex_byte_character_escapes_preserve_all_eight_bits(self):
        self.execute(self.compile('hex_byte', r'''pub fn main_entry()->u32{
let high:u8='\xff';let answer:u8='\x2A';if high!=255{return 1;}return answer as u32;}'''))
        for index, value in enumerate((r"'\x1'", r"'\xGG'", r"'\x100'")):
            self.compile('bad_byte_'+str(index), 'fn number()->u8{return '+value+';}', success=False)

    def test_frontend_radix_local_array_dimensions_execute(self):
        self.execute(self.compile('radix_shape', '''pub fn main_entry()->u32{
let a:[u32;0x2]=[20,22];let b:[u8;0b10]=[1,2];let c:[u8;0o2]=[3,4];
if b[1]!=2 || c[1]!=4{return 1;}return a[0]+a[1];}'''))
        self.compile('bad_shape', 'fn bad()->u32{let a:[u32;0x1001]=[0;0x1001];return 0;}', success=False)

    def test_frontend_repeat_counts_compare_numeric_values_across_radices(self):
        self.execute(self.compile('repeat_shape', '''pub fn main_entry()->u32{
let a:[u8;0x3]=[14;0b11];return (a[0] as u32)+(a[1] as u32)+(a[2] as u32);}'''))
        self.compile('bad_repeat_shape', 'fn bad()->u32{let a:[u8;0x3]=[14;0b10];return 0;}', success=False)

    def test_frontend_radix_record_array_fields_preserve_owned_layout(self):
        self.execute(self.compile('record_shape', '''struct Packet{pub bytes:[u8;0o3];}
fn take(value:sole Packet)->u32{return (value.bytes[0] as u32)+(value.bytes[1] as u32)+(value.bytes[2] as u32);}
pub fn main_entry()->u32{let packet:sole Packet=Packet{bytes:[14;0x3]};return take(packet);}'''))
        self.compile('bad_record_shape', 'struct Packet{pub bytes:[u8;0x101];}fn take(v:sole Packet)->void{return;}', success=False)

    def test_ownership_batch_retain_rejects_overflow_without_partial_mutation(self):
        self.runtime('retain_many', '''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
if !native_ref_retain_many(p,4) || h.strong!=5{return 1;}
if native_ref_retain_many(p,18446744073709551615) || h.strong!=5{return 2;}
if !native_ref_retain_many(p,0) || native_ref_retain_many(null,1){return 3;}return 42;''')

    def test_ownership_batch_release_authorizes_exactly_one_final_destruction(self):
        self.runtime('release_many', '''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
native_ref_retain_many(p,4);if native_ref_release_many(p,6)!=0 || h.strong!=5{return 1;}
if native_ref_release_many(p,2)!=1 || h.strong!=3 || native_ref_release_many(p,0)!=0{return 2;}
if native_ref_release_many(p,3)!=2 || h.live || native_ref_release_many(p,1)!=0{return 3;}return 42;''')

    def test_ownership_weak_observation_never_acquires_a_strong_reference(self):
        self.runtime('weak_observe', '''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
let token:NativeWeakToken=native_ref_weak(p);if !native_weak_current(token) || h.strong!=1{return 1;}
native_ref_release(p);native_ref_recycle(p);if native_weak_current(token) || h.strong!=1{return 2;}return 42;''')

    def test_ownership_unique_observation_rejects_shared_dead_and_null_headers(self):
        self.runtime('unique_observe', '''let mut h:NativeRefHeader=native_ref_init();let p:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
if !native_ref_is_unique(p) || native_ref_is_unique(null){return 1;}native_ref_retain(p);
if native_ref_is_unique(p){return 2;}native_ref_release(p);if !native_ref_is_unique(p){return 3;}
native_ref_release(p);if native_ref_is_unique(p){return 4;}return 42;''')

    def test_memory_fill_checks_address_wrap_before_writing(self):
        self.runtime('memory_fill', '''let mut bytes:[u8;4]=[0;4];let p:*mut u8=unsafe{bytes as *mut u8};
if !native_memory_fill(p,4,42) || bytes[3]!=42 || !native_memory_fill(null,0,1){return 1;}
if native_memory_fill(null,1,1) || native_memory_fill(unsafe{18446744073709551615 as *mut u8},2,1){return 2;}return 42;''')

    def test_memory_equality_handles_empty_null_mismatch_and_wrapping_ranges(self):
        self.runtime('memory_equal', '''let a:[u8;3]=[1,2,3];let b:[u8;3]=[1,2,4];
let x:*const u8=unsafe{a as *const u8};let y:*const u8=unsafe{b as *const u8};
if !native_memory_equal(x,y,2) || native_memory_equal(x,y,3) || !native_memory_equal(null,null,0){return 1;}
if native_memory_equal(null,y,1) || native_memory_equal(unsafe{18446744073709551615 as *const u8},y,2){return 2;}return 42;''')

    def test_memory_remaining_capacity_rejects_corrupt_cursors(self):
        self.runtime('arena_remaining', '''let mut bytes:[u8;16]=0;let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},16);
let p:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};native_arena_alloc(p,4,1);
if native_arena_remaining(p)!=12 || native_arena_remaining(null)!=0{return 1;}
arena.used=17;if native_arena_remaining(p)!=0{return 2;}return 42;''')

    def test_memory_reset_clears_used_bytes_and_invalidates_old_marks(self):
        self.runtime('arena_reset', '''let mut bytes:[u8;8]=[7;8];let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},8);
let p:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};let old:NativeArenaMark=native_arena_mark(p);native_arena_alloc(p,4,1);
if !native_arena_reset_zero(p) || arena.used!=0 || bytes[0]!=0 || bytes[3]!=0 || bytes[4]!=7{return 1;}
if native_arena_rewind(p,old){return 2;}arena.epoch=18446744073709551615;
if native_arena_reset_zero(p) || native_arena_reset_zero(null){return 3;}return 42;''')

    def test_authority_capture_rejects_missing_rights_and_null_authorities(self):
        self.runtime('authority_capture', '''let mut a:NativeAuthority=native_authority_init(3);let p:*const NativeAuthority=unsafe{(&mut a) as *const NativeAuthority};
let good:NativeAuthorityToken=native_authority_capture(p,1);let bad:NativeAuthorityToken=native_authority_capture(p,4);
let empty:NativeAuthorityToken=native_authority_capture(null,0);
if good.owner!=p || good.required!=1 || good.generation!=1 || bad.owner!=null || empty.owner!=null{return 1;}return 42;''')

    def test_authority_tokens_observe_revocation_through_the_original_owner(self):
        self.runtime('authority_tokens', '''let mut a:NativeAuthority=native_authority_init(3);let p:*mut NativeAuthority=unsafe{(&mut a) as *mut NativeAuthority};
let token:NativeAuthorityToken=native_authority_capture(p,1);if !native_authority_token_current(token){return 1;}
native_authority_revoke(p,2);if native_authority_token_current(token){return 2;}return 42;''')

    def test_authority_delegation_cannot_widen_a_token_or_reuse_a_stale_token(self):
        self.runtime('authority_delegate', '''let mut a:NativeAuthority=native_authority_init(7);let p:*mut NativeAuthority=unsafe{(&mut a) as *mut NativeAuthority};
let token:NativeAuthorityToken=native_authority_capture(p,3);let small:NativeAuthorityToken=native_authority_delegate(token,1);
let wide:NativeAuthorityToken=native_authority_delegate(token,4);
if !native_authority_token_current(small) || wide.owner!=null{return 1;}
native_authority_revoke(p,4);let stale:NativeAuthorityToken=native_authority_delegate(token,1);
if stale.owner!=null{return 2;}return 42;''')

    def test_state_token_transitions_require_current_rights_and_destination_mask(self):
        self.runtime('state_token', '''let mut a:NativeAuthority=native_authority_init(1);let p:*mut NativeAuthority=unsafe{(&mut a) as *mut NativeAuthority};
let token:NativeAuthorityToken=native_authority_capture(p,1);let mut state:u32=0;let s:*mut u32=unsafe{(&mut state) as *mut u32};
if !native_state_transition_token(s,0,1,2,token) || state!=1{return 1;}
if native_state_transition_token(s,1,2,2,token) || state!=1{return 2;}
native_authority_revoke(p,1);if native_state_transition_token(s,1,0,1,token) || state!=1{return 3;}return 42;''')

    def metadata(self, name, opcode, field):
        self.ir(name, '''let mut value:TargetInstruction=TargetInstruction::new(TargetOpcode::'''+opcode+''');
if !target_instruction_metadata_valid(value){return 1;}'''+field+'''
if target_instruction_metadata_valid(value){return 2;}return 42;''')

    def test_ir_integer_constants_reject_hidden_symbols(self):
        self.metadata('const_int_metadata','ConstInt','value.symbol=TargetSourceSlice{offset:0,length:1};')

    def test_ir_float_constants_reject_reserved_flags(self):
        self.metadata('const_float_metadata','ConstFloat','value.flags=16;')

    def test_ir_returns_reject_hidden_immediates(self):
        self.metadata('return_metadata','Return','value.immediate_bits=42;')

    def test_ir_control_transfers_reject_unrelated_phi_metadata(self):
        self.metadata('branch_metadata','Branch','value.phi_input_count=1;')
        self.metadata('cond_branch_metadata','CondBranch','value.flags=1;')

    def offset(self, name, typ, value, expression):
        self.execute(self.compile(name, '''pub fn main_entry()->u32{let bytes:[u32;3]=[42,1,2];
let p:*const u32=unsafe{bytes as *const u32};let middle:*const u32=unsafe{p+1};
let step:'''+typ+'='+value+';return unsafe{*('+expression+')};}'))

    def test_backend_i8_pointer_offsets_sign_extend_before_scaling(self):
        self.offset('offset_i8','i8','-1','middle+step')

    def test_backend_i16_pointer_offsets_sign_extend_before_scaling(self):
        self.offset('offset_i16','i16','-1','middle+step')

    def test_backend_u8_pointer_offsets_zero_extend_before_scaling(self):
        self.offset('offset_u8','u8','1','middle-step')

    def test_backend_u16_pointer_offsets_zero_extend_before_scaling(self):
        self.offset('offset_u16','u16','1','middle-step')


if __name__ == '__main__':
    unittest.main()
