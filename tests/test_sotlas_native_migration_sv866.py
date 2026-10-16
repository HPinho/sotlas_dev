"""SV8.66 production-native bounded resource scopes: execution and rejection."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv860 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV866Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV860Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV860Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV860Tests.compile
    link_image=previous.NativeMigrationSV860Tests.link_image
    execute=previous.NativeMigrationSV860Tests.execute
    runtime=previous.NativeMigrationSV860Tests.runtime

    def scope(self,name,body):
        fixture='''let mut a:[u8;3]=[20,22,91];let mut b:[u8;3]=[12,30,92];
let mut c:[u8;3]=[19,23,93];
let mut ah:NativeRefHeader=native_ref_init();
let mut bh:NativeRefHeader=native_ref_init();
let mut ch:NativeRefHeader=native_ref_init();
let ap:*mut NativeRefHeader=unsafe{(&mut ah) as *mut NativeRefHeader};
let bp:*mut NativeRefHeader=unsafe{(&mut bh) as *mut NativeRefHeader};
let cp:*mut NativeRefHeader=unsafe{(&mut ch) as *mut NativeRefHeader};
let mut ra:NativeManagedBytes=native_managed_bytes_open(ap,unsafe{a as *mut u8},2);
let mut rb:NativeManagedBytes=native_managed_bytes_open(bp,unsafe{b as *mut u8},2);
let mut rc:NativeManagedBytes=native_managed_bytes_open(cp,unsafe{c as *mut u8},2);
let pa:*mut NativeManagedBytes=unsafe{(&mut ra) as *mut NativeManagedBytes};
let pb:*mut NativeManagedBytes=unsafe{(&mut rb) as *mut NativeManagedBytes};
let pc:*mut NativeManagedBytes=unsafe{(&mut rc) as *mut NativeManagedBytes};
let mut slots:[usize;4]=[0;4];
let table:*mut usize=unsafe{slots as *mut usize};
let mut manager:NativeManagedScope=native_managed_scope_init(table,4);
let m:*mut NativeManagedScope=unsafe{(&mut manager) as *mut NativeManagedScope};
'''
        self.runtime(name,fixture+body)

    def test_native_scope_initializes_and_rejects_bad_capacity(self):
        self.scope('sv866_init','''let invalid:NativeManagedScope=native_managed_scope_init(null,4);
let over:NativeManagedScope=native_managed_scope_init(table,65);
let ip:*const NativeManagedScope=unsafe{(&invalid) as *const NativeManagedScope};
let op:*const NativeManagedScope=unsafe{(&over) as *const NativeManagedScope};
if !native_managed_scope_valid(m) || native_managed_scope_valid(ip)
 || native_managed_scope_valid(op) || native_managed_scope_valid(null)
 || native_managed_scope_depth(m)!=0 || manager.used!=0{return 1;}
return 42;''')

    def test_native_scope_registers_and_blocks_duplicate(self):
        self.scope('sv866_duplicates','''if !native_managed_scope_push(m,pa)
 || !native_managed_scope_push(m,pb) || !native_managed_scope_push(m,pc)
 || native_managed_scope_push(m,pa){return 1;}
if !native_managed_scope_contains(m,pa) || native_managed_scope_contains(m,null)
 || native_managed_scope_depth(m)!=3{return 2;}
if !native_managed_scope_drain(m) || a[0]!=0 || b[0]!=0 || c[0]!=0
 || a[2]!=91 || b[2]!=92 || c[2]!=93{return 3;}
return 42;''')

    def test_native_scope_release_last_is_lifo(self):
        self.scope('sv866_lifo','''native_managed_scope_push(m,pa);
native_managed_scope_push(m,pb);native_managed_scope_push(m,pc);
if !native_managed_scope_release_last(m) || c[0]!=0
 || b[0]!=12 || a[0]!=20 || manager.used!=2{return 1;}
if !native_managed_scope_release_last(m) || b[0]!=0
 || a[0]!=20 || manager.used!=1{return 2;}
if !native_managed_scope_release_last(m) || a[0]!=0
 || native_managed_scope_release_last(m) || manager.used!=0{return 3;}
return 42;''')

    def test_native_scope_mark_rewinds_only_nested_resources(self):
        self.scope('sv866_marks','''native_managed_scope_push(m,pa);
let mark:usize=native_managed_scope_depth(m);
native_managed_scope_push(m,pb);native_managed_scope_push(m,pc);
if !native_managed_scope_rewind(m,mark) || manager.used!=1
 || a[0]!=20 || b[0]!=0 || c[0]!=0{return 1;}
if !native_managed_scope_rewind(m,0) || a[0]!=0
 || a[2]!=91 || b[2]!=92 || c[2]!=93{return 2;}
return 42;''')

    def test_native_scope_invalid_mark_does_not_close_any_owner(self):
        self.scope('sv866_bad_mark','''native_managed_scope_push(m,pa);
native_managed_scope_push(m,pb);
if native_managed_scope_rewind(m,3) || manager.used!=2
 || a[0]!=20 || b[0]!=12 || ah.strong!=1{return 1;}
if !native_managed_scope_drain(m) || a[0]!=0 || b[0]!=0{return 2;}
return 42;''')

    def test_native_scope_stale_entry_preflight_prevents_partial_cleanup(self):
        self.scope('sv866_stale','''native_managed_scope_push(m,pa);
native_managed_scope_push(m,pb);native_managed_bytes_close(pb);
if native_managed_scope_rewind(m,0) || manager.used!=2
 || a[0]!=20 || ah.strong!=1{return 1;}
if !native_managed_scope_detach(m,pb)
 || !native_managed_scope_drain(m) || a[0]!=0{return 2;}
return 42;''')

    def test_native_scope_detach_preserves_independent_strong_claim(self):
        self.scope('sv866_detach','''native_managed_scope_push(m,pa);
native_managed_scope_push(m,pb);
if !native_managed_scope_detach(m,pa) || manager.used!=1
 || native_managed_scope_contains(m,pa){return 1;}
if !native_managed_scope_drain(m) || a[0]!=20 || b[0]!=0
 || ah.strong!=1{return 2;}
native_managed_bytes_close(pa);
if a[0]!=0 || a[2]!=91 || ah.strong!=0{return 3;}
return 42;''')

    def test_native_scope_transfer_promotes_resource_without_refcount_change(self):
        self.scope('sv866_transfer','''let mut more:[usize;2]=[0;2];
let mut dest:NativeManagedScope=native_managed_scope_init(
 unsafe{more as *mut usize},2);
let dp:*mut NativeManagedScope=unsafe{(&mut dest) as *mut NativeManagedScope};
native_managed_scope_push(m,pa);native_managed_scope_push(m,pb);
if !native_managed_scope_transfer(m,dp,pa) || manager.used!=1
 || dest.used!=1 || ah.strong!=1{return 1;}
if native_managed_scope_transfer(m,dp,pa)
 || !native_managed_scope_drain(m) || a[0]!=20 || b[0]!=0{return 2;}
if !native_managed_scope_drain(dp) || a[0]!=0 || ah.strong!=0{return 3;}
return 42;''')

    def test_native_scope_transfer_full_target_is_atomic(self):
        self.scope('sv866_full_target','''let mut more:[usize;1]=[0;1];
let mut dest:NativeManagedScope=native_managed_scope_init(
 unsafe{more as *mut usize},1);
let dp:*mut NativeManagedScope=unsafe{(&mut dest) as *mut NativeManagedScope};
native_managed_scope_push(m,pa);native_managed_scope_push(dp,pb);
if native_managed_scope_transfer(m,dp,pa)
 || native_managed_scope_transfer(m,m,pa)
 || manager.used!=1 || dest.used!=1 || ah.strong!=1{return 1;}
if !native_managed_scope_drain(dp) || !native_managed_scope_drain(m)
 || a[0]!=0 || b[0]!=0{return 2;}
return 42;''')

    def test_native_scope_full_capacity_rejects_without_affecting_claims(self):
        self.scope('sv866_capacity','''let mut extra:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let mut outside:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let q:*mut NativeManagedBytes=unsafe{(&mut extra) as *mut NativeManagedBytes};
let r:*mut NativeManagedBytes=unsafe{(&mut outside) as *mut NativeManagedBytes};
if !native_managed_bytes_clone_into(pa,q)
 || !native_managed_bytes_clone_into(pa,r){return 1;}
native_managed_scope_push(m,pa);native_managed_scope_push(m,pb);
native_managed_scope_push(m,pc);native_managed_scope_push(m,q);
if native_managed_scope_push(m,r) || manager.used!=4
 || ah.strong!=3 || a[0]!=20{return 2;}
native_managed_bytes_close(r);
if !native_managed_scope_drain(m) || ah.strong!=0 || a[0]!=0
 || b[0]!=0 || c[0]!=0{return 3;}
return 42;''')

    def test_native_scope_clone_nonfinal_release_and_weak_invalidation(self):
        self.scope('sv866_weak','''let mut copy:NativeManagedBytes=NativeManagedBytes{
control:null,bytes:null,length:0,generation:0};
let q:*mut NativeManagedBytes=unsafe{(&mut copy) as *mut NativeManagedBytes};
let weak:NativeWeakToken=native_managed_bytes_weak(pa);
if !native_managed_bytes_clone_into(pa,q){return 1;}
native_managed_scope_push(m,pa);native_managed_scope_push(m,q);
if !native_managed_scope_release_last(m) || a[0]!=20
 || ah.strong!=1 || !native_weak_current(weak){return 2;}
if !native_managed_scope_release_last(m) || a[0]!=0
 || ah.strong!=0 || native_weak_upgrade(weak){return 3;}
return 42;''')

    def test_native_scope_early_return_defer_closes_registered_resource(self):
        runtime=(ROOT/'runtime/native/managed.sotlas').read_text(
            encoding='utf-8').split(';',1)[1]
        program='''fn leave(sc:*mut NativeManagedScope)->u32{
defer native_managed_scope_close(sc);
if true{return 42;}return 1;}
pub fn main_entry()->u32{
let mut a:[u8;3]=[20,22,91];let mut h:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
let mut r:NativeManagedBytes=native_managed_bytes_open(hp,unsafe{a as *mut u8},2);
let rp:*mut NativeManagedBytes=unsafe{(&mut r) as *mut NativeManagedBytes};
let mut slots:[usize;1]=[0;1];
let mut scope:NativeManagedScope=native_managed_scope_init(
 unsafe{slots as *mut usize},1);
let sc:*mut NativeManagedScope=unsafe{(&mut scope) as *mut NativeManagedScope};
if !native_managed_scope_push(sc,rp) || leave(sc)!=42{return 1;}
if a[0]!=0 || a[1]!=0 || a[2]!=91 || h.strong!=0
 || r.control!=null{return 2;}return 42;}'''
        self.execute(self.compile('sv866_defer_return',runtime+program))

    def test_native_scope_defer_runs_on_continue_and_break(self):
        self.scope('sv866_defer_loops','''let mut turn:u32=0;
while turn<3{turn=turn+1;
if turn==1{
if !native_managed_scope_push(m,pa){return 1;}
defer native_managed_scope_close(m);continue;
}else{
if !native_managed_scope_push(m,pb){return 2;}
defer native_managed_scope_close(m);break;
}}
if a[0]!=0 || b[0]!=0 || a[2]!=91 || b[2]!=92
 || manager.used!=0{return 3;}
return 42;''')

    def test_native_scope_rejects_stale_handle_without_mutation(self):
        self.scope('sv866_stale_push','''ra.generation=ra.generation+1;
if native_managed_scope_push(m,pa) || manager.used!=0
 || ah.strong!=1 || a[0]!=20{return 1;}
ra.generation=ah.generation;
if !native_managed_scope_push(m,pa)
 || !native_managed_scope_drain(m) || a[0]!=0{return 2;}
if native_managed_scope_push(m,pa) || manager.used!=0{return 3;}
return 42;''')

    def test_native_frontend_still_rejects_move_after_use_and_defer_consume(self):
        cases=(
            '''struct Token{pub value:u32;}
fn take(x:sole Token)->u32{return x.value;}
pub fn main_entry()->u32{
let x:sole Token=Token{value:42};let v:u32=take(x);return v+x.value;}''',
            '''struct Token{pub value:u32;}
fn take(x:sole Token)->void{return;}
pub fn main_entry()->u32{
let x:sole Token=Token{value:42};defer take(x);return 42;}''',
        )
        for i,source in enumerate(cases):
            with self.subTest(case=i):
                self.compile('sv866_owner_reject_'+str(i),source,success=False)

if __name__=='__main__':unittest.main()
