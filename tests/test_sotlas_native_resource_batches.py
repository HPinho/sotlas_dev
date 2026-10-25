"""Execute transactional resource-scope transfers and collective claim checks."""
from pathlib import Path
import unittest
import test_sotlas_native_i32 as previous

ROOT = Path(__file__).resolve().parents[1]


class NativeResourceBatchTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeI32Tests.tearDownClass.__func__)
    compile = previous.NativeI32Tests.compile
    link_image = previous.NativeI32Tests.link_image
    execute = previous.NativeI32Tests.execute

    def program(self, name, body, setup=''):
        runtime = (ROOT/'runtime/native/managed.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        fixture = '''let mut bytes:[u8;4]=[42;4];let mut other_bytes:[u8;4]=[7;4];
let mut header:NativeRefHeader=native_ref_init();let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
let mut other_header:NativeRefHeader=native_ref_init();
let oh:*mut NativeRefHeader=unsafe{(&mut other_header) as *mut NativeRefHeader};
let mut resource:NativeManagedBytes=native_managed_bytes_open(h,unsafe{bytes as *mut u8},4);
let root:*mut NativeManagedBytes=unsafe{(&mut resource) as *mut NativeManagedBytes};
let mut alias:NativeManagedBytes=native_managed_bytes_open(null,null,0);
let copy:*mut NativeManagedBytes=unsafe{(&mut alias) as *mut NativeManagedBytes};
let mut other:NativeManagedBytes=native_managed_bytes_open(oh,unsafe{other_bytes as *mut u8},4);
let extra:*mut NativeManagedBytes=unsafe{(&mut other) as *mut NativeManagedBytes};
let mut first_table:[usize;4]=0;let mut second_table:[usize;4]=0;
let ft:*mut usize=unsafe{first_table as *mut usize};let st:*mut usize=unsafe{second_table as *mut usize};
let mut first:NativeManagedScope=native_managed_scope_init(ft,4);
let mut second:NativeManagedScope=native_managed_scope_init(st,4);
let a:*mut NativeManagedScope=unsafe{(&mut first) as *mut NativeManagedScope};
let b:*mut NativeManagedScope=unsafe{(&mut second) as *mut NativeManagedScope};
'''
        source = runtime+'\n'+setup+'\npub fn main_entry()->u32{'+fixture+body+'}'
        self.execute(self.compile(name, source))

    def test_suffix_transfer_preserves_order_prefix_and_refcounts(self):
        self.program('resource_suffix', '''if !native_managed_bytes_clone_into(root,copy)
|| !native_managed_scope_push(a,root) || !native_managed_scope_push(a,copy)
|| !native_managed_scope_push(b,extra){return 1;}
let weak:NativeWeakToken=native_managed_bytes_weak(root);
if !native_managed_scope_transfer_suffix(a,b,1) || first.used!=1 || second.used!=2
|| first_table[0]!=unsafe{root as usize} || first_table[1]!=0
|| second_table[0]!=unsafe{extra as usize} || second_table[1]!=unsafe{copy as usize}
|| header.strong!=2 || !native_weak_current(weak){return 2;}
if !native_managed_scope_drain(a) || header.strong!=1 || bytes[0]!=42{return 3;}
if !native_managed_scope_release_last(b) || header.live || bytes[0]!=0
|| native_weak_current(weak) || other_bytes[0]!=7{return 4;}
if !native_managed_scope_drain(b) || other_header.live || other_bytes[0]!=0{return 5;}return 42;''')

    def test_transfer_all_and_empty_suffix_do_not_retain_or_release(self):
        self.program('resource_transfer_all', '''if !native_managed_scope_push(a,root)
|| !native_managed_scope_transfer_suffix(a,b,1) || first.used!=1 || second.used!=0
|| !native_managed_scope_transfer_suffix(a,b,0) || first.used!=0 || second.used!=1
|| header.strong!=1 || bytes[0]!=42 || first_table[0]!=0{return 1;}
if !native_managed_scope_transfer_suffix(a,b,0) || second.used!=1{return 2;}
if !native_managed_scope_drain(b) || header.live || bytes[0]!=0{return 3;}return 42;''')

    def test_retained_aliases_across_both_scopes_remain_valid(self):
        self.program('resource_cross_retained', '''if !native_managed_bytes_clone_into(root,copy)
|| !native_managed_scope_push(a,root) || !native_managed_scope_push(b,copy)
|| !native_managed_scope_transfer_suffix(a,b,0) || second.used!=2
|| header.strong!=2 || bytes[0]!=42{return 1;}
if !native_managed_scope_drain(b) || header.live || header.strong!=0
|| bytes[0]!=0 || !native_managed_bytes_empty(root) || !native_managed_bytes_empty(copy){return 2;}
return 42;''')

    def test_scope_capacity_64_and_last_destination_slot(self):
        self.program('resource_batch_capacity64', '''let mut large_table:[usize;64]=0;
let mut large:NativeManagedScope=native_managed_scope_init(unsafe{large_table as *mut usize},64);
let large_scope:*mut NativeManagedScope=unsafe{(&mut large) as *mut NativeManagedScope};
if !native_managed_scope_push(a,root) || !native_managed_scope_transfer_suffix(a,large_scope,0)
|| large.used!=1 || large_table[0]!=unsafe{root as usize}
|| !native_managed_scope_drain(large_scope) || large_table[0]!=0 || bytes[0]!=0{return 1;}
second.capacity=1;if !native_managed_scope_push(a,extra)
|| !native_managed_scope_transfer_suffix(a,b,0) || second.used!=1
|| !native_managed_scope_drain(b) || other_bytes[0]!=0{return 2;}return 42;''')

    def test_insufficient_capacity_and_invalid_mark_are_transactional(self):
        self.program('resource_capacity', '''if !native_managed_scope_push(a,root)
|| !native_managed_scope_push(b,extra){return 1;}second.capacity=1;
if native_managed_scope_transfer_suffix(a,b,0) || native_managed_scope_transfer_suffix(a,b,2)
|| first.used!=1 || second.used!=1 || first_table[0]!=unsafe{root as usize}
|| second_table[0]!=unsafe{extra as usize} || header.strong!=1 || bytes[0]!=42{return 2;}
return 42;''')

    def test_same_null_and_overlapping_scopes_rejected_without_writes(self):
        self.program('resource_overlapping', '''if !native_managed_scope_push(a,root){return 1;}
if native_managed_scope_transfer_suffix(a,a,0) || native_managed_scope_transfer_suffix(null,b,0)
|| native_managed_scope_transfer_suffix(a,null,0){return 2;}
second.entries=unsafe{ft+1};second.capacity=3;
if native_managed_scope_transfer_suffix(a,b,0) || first.used!=1 || second.used!=0
|| first_table[0]!=unsafe{root as usize} || header.strong!=1{return 3;}return 42;''')

    def test_duplicate_slots_fail_before_cleanup(self):
        self.program('resource_duplicate', '''if !native_managed_scope_push(a,root){return 1;}
first_table[1]=unsafe{root as usize};first.used=2;
if native_managed_scope_claims_valid(a) || native_managed_scope_drain(a)
|| native_managed_scope_transfer_suffix(a,b,0) || first.used!=2 || second.used!=0
|| header.strong!=1 || bytes[0]!=42 || !native_managed_bytes_current(root){return 2;}return 42;''')

    def test_distinct_unretained_claims_fail_without_partial_destruction(self):
        self.program('resource_overclaimed', '''unsafe{*copy=*root;}
if !native_managed_scope_push(a,root) || !native_managed_scope_push(a,copy){return 1;}
if native_managed_scope_claims_valid(a) || native_managed_scope_rewind(a,1)
|| native_managed_scope_drain(a) || native_managed_scope_transfer_suffix(a,b,0)
|| first.used!=2 || header.strong!=1 || !header.live || bytes[0]!=42
|| !native_managed_bytes_current(root) || !native_managed_bytes_current(copy){return 2;}return 42;''')

    def test_same_control_with_inconsistent_payload_is_rejected(self):
        self.program('resource_payload_mismatch', '''if !native_managed_bytes_clone_into(root,copy){return 1;}
alias.bytes=unsafe{other_bytes as *mut u8};
if !native_managed_scope_push(a,root) || !native_managed_scope_push(a,copy){return 2;}
if native_managed_scope_claims_valid(a) || native_managed_scope_drain(a)
|| native_managed_scope_transfer_suffix(a,b,1) || header.strong!=2
|| bytes[0]!=42 || other_bytes[0]!=7 || first.used!=2{return 3;}return 42;''')

    def test_stale_suffix_cannot_partially_transfer(self):
        self.program('resource_stale_suffix', '''if !native_managed_bytes_clone_into(root,copy)
|| !native_managed_scope_push(a,root) || !native_managed_scope_push(a,copy){return 1;}
native_managed_bytes_close(copy);
if native_managed_scope_transfer_suffix(a,b,0) || first.used!=2 || second.used!=0
|| header.strong!=1 || bytes[0]!=42 || !native_managed_bytes_current(root){return 2;}return 42;''')

    def test_cross_scope_duplicate_handle_is_rejected(self):
        self.program('resource_cross_duplicate', '''if !native_managed_scope_push(a,root)
|| !native_managed_scope_push(b,root){return 1;}
if native_managed_scope_transfer_suffix(a,b,0) || first.used!=1 || second.used!=1
|| header.strong!=1 || bytes[0]!=42{return 2;}return 42;''')

    def test_cross_scope_overclaim_is_rejected(self):
        self.program('resource_cross_overclaim', '''unsafe{*copy=*root;}
if !native_managed_scope_push(a,root) || !native_managed_scope_push(b,copy)
|| !native_managed_scope_claims_valid(a) || !native_managed_scope_claims_valid(b){return 1;}
if native_managed_scope_transfer_suffix(a,b,0) || first.used!=1 || second.used!=1
|| header.strong!=1 || bytes[0]!=42{return 2;}return 42;''')

    def test_deferred_batch_cleanup_after_transfer_and_early_return(self):
        self.program('resource_deferred_batch', '''if !native_managed_scope_push(a,root)
|| !native_managed_scope_transfer_suffix(a,b,0){return 1;}
if work(b,true)!=7 || header.live || bytes[0]!=0 || second.used!=0{return 2;}
native_managed_scope_close(b);
if header.strong!=0 || !native_managed_bytes_empty(root){return 3;}return 42;''',
            '''fn work(scope:*mut NativeManagedScope,early:bool)->u32{
defer native_managed_scope_close(scope);if early{return 7;}return 9;}''')

    def test_saturated_counts_and_invalid_metadata_reject_cleanly(self):
        self.program('resource_batch_limits', '''if native_managed_scope_claims_valid(null){return 1;}
if !native_managed_scope_push(a,root){return 2;}
header.strong=18446744073709551615;
if !native_managed_scope_transfer_suffix(a,b,0) || header.strong!=18446744073709551615{return 3;}
second.used=5;
if native_managed_scope_transfer_suffix(b,a,0) || native_managed_scope_drain(b)
|| first.used!=0 || header.strong!=18446744073709551615 || bytes[0]!=42{return 4;}return 42;''')


if __name__ == '__main__':
    unittest.main()
