"""Execute the explicit Sotlas runtime through the owned object/link path."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as integer

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime/native/managed.sotlas"


class NativeManagedRuntimeTests(unittest.TestCase):
    setUpClass = classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile = integer.NativeI32Tests.compile
    link_image = integer.NativeI32Tests.link_image
    execute = integer.NativeI32Tests.execute

    def run_runtime(self, name, body):
        source = RUNTIME.read_text(encoding="utf-8").split(";", 1)[1]
        self.execute(self.compile(name, source + '\npub fn main_entry()->u32{' + body + '}'))

    def test_arena_alignment_accounts_for_unaligned_backing_storage(self):
        self.run_runtime('arena_alignment', '''let mut buffer:[u8;128]=0;
let base:*mut u8=unsafe{buffer as *mut u8};
let mut arena:NativeArena=native_arena_init(unsafe{base+1},127);
let p:*mut u8=native_arena_alloc(unsafe{(&mut arena) as *mut NativeArena},16,32);
if p==null || (unsafe{p as usize}&31)!=0{return 1;}
unsafe{*p=42;}return unsafe{*p} as u32;''')

    def test_arena_failure_does_not_change_cursor(self):
        self.run_runtime('arena_failure', '''let mut buffer:[u8;16]=0;
let mut arena:NativeArena=native_arena_init(unsafe{buffer as *mut u8},16);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};
if native_arena_alloc(a,17,1)!=null || native_arena_alloc(a,1,3)!=null
|| native_arena_alloc(a,0,1)!=null || arena.used!=0{return 1;}return 42;''')

    def test_arena_marks_rewind_and_invalidate_old_marks(self):
        self.run_runtime('arena_marks', '''let mut buffer:[u8;32]=0;
let mut arena:NativeArena=native_arena_init(unsafe{buffer as *mut u8},32);
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};
let mark:NativeArenaMark=native_arena_mark(a);
let p:*mut u8=native_arena_alloc(a,8,1);
if p==null || !native_arena_rewind(a,mark) || arena.used!=0{return 1;}
if native_arena_rewind(a,mark){return 2;}return 42;''')

    def test_arena_marks_cannot_rewind_a_different_arena(self):
        self.run_runtime('arena_mark_identity', '''let mut left:[u8;16]=0;let mut right:[u8;16]=0;
let mut a:NativeArena=native_arena_init(unsafe{left as *mut u8},16);
let mut b:NativeArena=native_arena_init(unsafe{left as *mut u8},16);
let mark:NativeArenaMark=native_arena_mark(unsafe{(&mut a) as *mut NativeArena});
if native_arena_rewind(unsafe{(&mut b) as *mut NativeArena},mark){return 1;}return 42;''')

    def test_arena_rejects_corrupted_cursor_and_address_overflow(self):
        self.run_runtime('arena_overflow', '''let address:u64=18446744073709551614;
let mut arena:NativeArena=NativeArena{
buffer:unsafe{address as *mut u8},capacity:16,used:0,epoch:1};
let a:*mut NativeArena=unsafe{(&mut arena) as *mut NativeArena};
if native_arena_alloc(a,8,1)!=null{return 1;}
arena.used=17;if native_arena_alloc(a,1,1)!=null{return 2;}return 42;''')

    def test_reference_retain_and_last_release_authorize_one_destruction(self):
        self.run_runtime('ref_destroy_once', '''let mut header:NativeRefHeader=native_ref_init();
let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
if !native_ref_retain(h) || header.strong!=2 || native_ref_release(h){return 1;}
if !native_ref_release(h) || native_ref_release(h) || native_ref_retain(h){return 2;}
if header.live || header.strong!=0{return 3;}return 42;''')

    def test_reference_upgrade_owns_a_strong_reference(self):
        self.run_runtime('ref_upgrade', '''let mut header:NativeRefHeader=native_ref_init();
let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
if native_ref_upgrade(h,0) || native_ref_upgrade(h,2) || !native_ref_upgrade(h,1){return 1;}
if header.strong!=2 || native_ref_release(h) || !native_ref_release(h){return 2;}return 42;''')

    def test_reference_weak_token_is_invalid_after_last_release(self):
        self.run_runtime('ref_weak_dead', '''let mut header:NativeRefHeader=native_ref_init();
let generation:u64=header.generation;
let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
if !native_ref_release(h) || native_ref_upgrade(h,generation){return 1;}return 42;''')

    def test_reference_count_overflow_and_null_are_rejected(self):
        self.run_runtime('ref_overflow', '''let mut header:NativeRefHeader=NativeRefHeader{
strong:18446744073709551615,generation:1,live:true};
if native_ref_retain(unsafe{(&mut header) as *mut NativeRefHeader})
|| native_ref_retain(null) || native_ref_release(null) || native_ref_upgrade(null,1){return 1;}
if header.strong!=18446744073709551615{return 2;}return 42;''')

    def test_reference_release_integrates_with_native_defer_and_early_return(self):
        source=RUNTIME.read_text(encoding='utf-8').split(';',1)[1]
        source+='''static mut destroyed:u32=0;
fn release_payload(h:*mut NativeRefHeader)->void{
if native_ref_release(h){unsafe{destroyed=destroyed+1;}}return;}
fn operation(h:*mut NativeRefHeader,early:bool)->u32{
defer release_payload(h);if early{return 7;}return 9;}
pub fn main_entry()->u32{let mut header:NativeRefHeader=native_ref_init();
let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
if !native_ref_retain(h) || operation(h,true)!=7 || header.strong!=1{return 1;}
if operation(h,false)!=9 || header.live || unsafe{destroyed}!=1{return 2;}
if native_ref_release(h) || unsafe{destroyed}!=1{return 3;}return 42;}'''
        self.execute(self.compile('ref_defer_early_return',source))

    def test_authority_check_requires_all_requested_bits(self):
        self.run_runtime('authority_all', '''if !native_authority_allows(7,3)
|| native_authority_allows(3,4) || !native_authority_allows(0,0){return 1;}return 42;''')

    def test_authority_delegation_cannot_escalate_or_change_failed_output(self):
        self.run_runtime('authority_narrow', '''let mut delegated:u64=99;
let p:*mut u64=unsafe{(&mut delegated) as *mut u64};
if native_authority_narrow(3,4,p) || delegated!=99{return 1;}
if !native_authority_narrow(7,3,p) || delegated!=3 || native_authority_narrow(7,3,null){return 2;}return 42;''')

    def test_state_transition_checks_authority_and_expected_state_before_write(self):
        self.run_runtime('state_transition', '''let mut state:u32=1;
let p:*mut u32=unsafe{(&mut state) as *mut u32};
if native_state_transition(p,1,2,0,1) || native_state_transition(p,2,3,1,1) || state!=1{return 1;}
if !native_state_transition(p,1,2,1,1) || state!=2{return 2;}return 42;''')

    def test_range_contract_handles_empty_and_overflowing_ranges(self):
        self.run_runtime('range_contract', '''if !native_contract_range(42,42,0)
|| native_contract_range(42,43,0) || native_contract_range(42,1,18446744073709551615)
|| !native_contract_range(18446744073709551615,18446744073709551615,0){return 1;}return 42;''')


if __name__ == "__main__":
    unittest.main()
