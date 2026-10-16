"""SV8.67: verified strong/weak scoped enrollment and fail-closed tables."""
import unittest
import test_sotlas_native_migration_sv866 as previous

class NativeMigrationSV867Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV866Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV866Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV866Tests.compile
    link_image=previous.NativeMigrationSV866Tests.link_image
    execute=previous.NativeMigrationSV866Tests.execute
    runtime=previous.NativeMigrationSV866Tests.runtime
    scope=previous.NativeMigrationSV866Tests.scope

    def test_scope_registers_cloned_claim_and_final_release_zeroes_only_payload(self):
        self.scope('sv867_clone','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
if !native_managed_scope_push(m,pa)
 || !native_managed_scope_clone_into(m,pa,sp)
 || manager.used!=2 || ah.strong!=2{return 1;}
if !native_managed_scope_release_last(m) || ah.strong!=1
 || a[0]!=20 || !native_managed_bytes_empty(sp){return 2;}
if !native_managed_scope_drain(m) || ah.strong!=0
 || a[0]!=0 || a[1]!=0 || a[2]!=91{return 3;}
return 42;''')

    def test_scope_clone_rejects_full_table_without_retain_or_slot_mutation(self):
        self.scope('sv867_full','''let mut cell:[usize;1]=[0;1];
let mut only:NativeManagedScope=native_managed_scope_init(
 unsafe{cell as *mut usize},1);
let op:*mut NativeManagedScope=unsafe{(&mut only) as *mut NativeManagedScope};
let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
if !native_managed_scope_push(op,pa){return 1;}
if native_managed_scope_clone_into(op,pa,sp) || ah.strong!=1
 || only.used!=1 || !native_managed_bytes_empty(sp){return 2;}
if !native_managed_scope_drain(op) || a[0]!=0{return 3;}
return 42;''')

    def test_scope_clone_rejects_nonempty_slot_without_retain(self):
        self.scope('sv867_occupied','''native_managed_scope_push(m,pa);
if native_managed_scope_clone_into(m,pa,pa) || ah.strong!=1
 || manager.used!=1 || !native_managed_bytes_current(pa){return 1;}
if !native_managed_scope_drain(m) || a[0]!=0{return 2;}
return 42;''')

    def test_scope_clone_rejects_stale_source_without_touching_destination(self):
        self.scope('sv867_stale_clone','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
ra.generation=ra.generation+1;
if native_managed_scope_clone_into(m,pa,sp) || ah.strong!=1
 || manager.used!=0 || !native_managed_bytes_empty(sp){return 1;}
ra.generation=ah.generation;
native_managed_bytes_close(pa);
if a[0]!=0{return 2;}
return 42;''')

    def test_scope_matching_weak_upgrade_creates_tracked_strong_claim(self):
        self.scope('sv867_weak','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
let weak:NativeWeakToken=native_managed_bytes_weak(pa);
native_managed_scope_push(m,pa);
if !native_managed_scope_upgrade_into(m,pa,weak,sp)
 || ah.strong!=2 || manager.used!=2{return 1;}
if !native_managed_scope_drain(m) || ah.strong!=0 || a[0]!=0
 || native_weak_upgrade(weak){return 2;}
return 42;''')

    def test_scope_rejects_stale_weak_generation_atomically(self):
        self.scope('sv867_stale_weak','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
let mut weak:NativeWeakToken=native_managed_bytes_weak(pa);
weak.generation=weak.generation+1;
if native_managed_scope_upgrade_into(m,pa,weak,sp)
 || ah.strong!=1 || manager.used!=0
 || !native_managed_bytes_empty(sp) || a[0]!=20{return 1;}
native_managed_bytes_close(pa);
if a[0]!=0{return 2;}
return 42;''')

    def test_scope_rejects_foreign_weak_token_atomically(self):
        self.scope('sv867_foreign_weak','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
let token:NativeWeakToken=native_managed_bytes_weak(pb);
if native_managed_scope_upgrade_into(m,pa,token,sp)
 || ah.strong!=1 || bh.strong!=1 || manager.used!=0
 || !native_managed_bytes_empty(sp){return 1;}
native_managed_bytes_close(pa);native_managed_bytes_close(pb);
if a[0]!=0 || b[0]!=0{return 2;}
return 42;''')

    def test_scope_weak_upgrade_rejects_full_destination_table(self):
        self.scope('sv867_weak_full','''let mut cell:[usize;1]=[0;1];
let mut only:NativeManagedScope=native_managed_scope_init(
 unsafe{cell as *mut usize},1);
let op:*mut NativeManagedScope=unsafe{(&mut only) as *mut NativeManagedScope};
let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
let weak:NativeWeakToken=native_managed_bytes_weak(pa);
native_managed_scope_push(op,pa);
if native_managed_scope_upgrade_into(op,pa,weak,sp)
 || ah.strong!=1 || only.used!=1 || !native_managed_bytes_empty(sp){return 1;}
if !native_managed_scope_drain(op) || a[0]!=0{return 2;}
return 42;''')

    def test_scope_take_registers_a_caller_strong_claim_without_retain(self):
        self.scope('sv867_take','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
if !native_managed_scope_take_into(m,pa,sp)
 || !native_managed_bytes_empty(pa) || ah.strong!=1
 || manager.used!=1 || !native_managed_scope_contains(m,sp){return 1;}
if !native_managed_scope_drain(m) || ah.strong!=0
 || a[0]!=0 || a[2]!=91{return 2;}
return 42;''')

    def test_scope_take_rejects_an_already_registered_source_without_poison(self):
        self.scope('sv867_take_registered','''let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
native_managed_scope_push(m,pa);
if native_managed_scope_take_into(m,pa,sp) || !native_managed_bytes_current(pa)
 || !native_managed_bytes_empty(sp) || ah.strong!=1 || manager.used!=1{return 1;}
if !native_managed_scope_drain(m) || a[0]!=0{return 2;}
return 42;''')

    def test_scope_take_rejects_full_table_without_poison(self):
        self.scope('sv867_take_full','''let mut cell:[usize;1]=[0;1];
let mut only:NativeManagedScope=native_managed_scope_init(
 unsafe{cell as *mut usize},1);
let op:*mut NativeManagedScope=unsafe{(&mut only) as *mut NativeManagedScope};
let mut slot:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let sp:*mut NativeManagedBytes=unsafe{(&mut slot) as *mut NativeManagedBytes};
native_managed_scope_push(op,pb);
if native_managed_scope_take_into(op,pa,sp)
 || !native_managed_bytes_current(pa) || !native_managed_bytes_empty(sp)
 || ah.strong!=1 || only.used!=1{return 1;}
if !native_managed_scope_drain(op) || b[0]!=0{return 2;}
native_managed_bytes_close(pa);
if a[0]!=0{return 3;}
return 42;''')

    def test_scope_aliasing_tables_never_transfer_a_strong_claim(self):
        self.scope('sv867_alias','''let mut alias:NativeManagedScope=NativeManagedScope{
entries:manager.entries,capacity:manager.capacity,used:0};
let other:*mut NativeManagedScope=unsafe{(&mut alias) as *mut NativeManagedScope};
native_managed_scope_push(m,pa);
if native_managed_scope_tables_disjoint(m,other)
 || native_managed_scope_transfer(m,other,pa) || manager.used!=1
 || alias.used!=0 || ah.strong!=1 || a[0]!=20{return 1;}
if !native_managed_scope_drain(m) || a[0]!=0{return 2;}
return 42;''')

    def test_scope_distinct_rejects_corrupt_duplicate_and_keeps_claim_live(self):
        self.scope('sv867_corrupted','''native_managed_scope_push(m,pa);
native_managed_scope_push(m,pb);
slots[1]=slots[0];
if native_managed_scope_entries_distinct(m)
 || native_managed_scope_rewind(m,0)
 || manager.used!=2 || ah.strong!=1 || bh.strong!=1
 || a[0]!=20 || b[0]!=12{return 1;}
slots[1]=unsafe{pb as usize};
if !native_managed_scope_entries_distinct(m)
 || !native_managed_scope_drain(m) || a[0]!=0 || b[0]!=0{return 2;}
return 42;''')

    def test_scope_disjoint_tables_accept_adjacent_nonoverlapping_storage(self):
        self.scope('sv867_adjacent','''let mut table:[usize;2]=[0;2];
let base:*mut usize=unsafe{table as *mut usize};
let second:*mut usize=unsafe{base+1};
let mut one:NativeManagedScope=native_managed_scope_init(base,1);
let mut two:NativeManagedScope=native_managed_scope_init(second,1);
let op:*mut NativeManagedScope=unsafe{(&one) as *mut NativeManagedScope};
let tp:*mut NativeManagedScope=unsafe{(&two) as *mut NativeManagedScope};
if !native_managed_scope_tables_disjoint(op,tp){return 1;}
native_managed_scope_push(op,pa);
if !native_managed_scope_transfer(op,tp,pa) || one.used!=0
 || two.used!=1 || ah.strong!=1{return 2;}
if !native_managed_scope_drain(tp) || a[0]!=0{return 3;}
return 42;''')

    def test_scope_combined_weak_upgrade_take_and_defer_cleanup(self):
        self.scope('sv867_combo','''let mut cloned:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let mut moved:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let cp:*mut NativeManagedBytes=unsafe{(&cloned) as *mut NativeManagedBytes};
let mp:*mut NativeManagedBytes=unsafe{(&moved) as *mut NativeManagedBytes};
let weak:NativeWeakToken=native_managed_bytes_weak(pa);
{defer native_managed_scope_close(m);
if !native_managed_scope_push(m,pa)
 || !native_managed_scope_upgrade_into(m,pa,weak,cp)
 || !native_managed_scope_take_into(m,pb,mp){return 1;}
if ah.strong!=2 || bh.strong!=1 || manager.used!=3{return 2;}}
if ah.strong!=0 || bh.strong!=0 || a[0]!=0 || b[0]!=0
 || a[2]!=91 || b[2]!=92 || manager.used!=0
 || native_weak_upgrade(weak){return 3;}
return 42;''')

    def test_scope_rejects_ownership_use_after_move_in_frontend(self):
        source='''struct Token{pub value:u32;}
fn consume(v:sole Token)->u32{return v.value;}
pub fn main_entry()->u32{
let token:sole Token=Token{value:42};
let first:u32=consume(token);return first+token.value;}'''
        self.compile('sv867_owner_reject',source,success=False)

if __name__=='__main__':unittest.main()
