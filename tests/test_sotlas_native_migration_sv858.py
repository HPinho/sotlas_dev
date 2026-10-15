"""SV8.58: managed byte resources execute with the native compiler/runtime."""
import unittest
import test_sotlas_native_migration_sv857 as previous
import test_sotlas_native_migration_sv851 as runtime_base

class NativeMigrationSV858Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV857Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV857Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV857Tests.compile
    execute=previous.NativeMigrationSV857Tests.execute
    link_image=previous.NativeMigrationSV857Tests.link_image
    runtime=runtime_base.NativeMigrationSV851Tests.runtime

    def test_managed_last_release_zeros_only_payload_and_invalidates_weak(self):
        self.runtime('sv858_last_release','''let mut bytes:[u8;5]=[7,8,9,10,77];
let mut header:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
let buf:*mut u8=unsafe{bytes as *mut u8};
let mut resource:NativeManagedBytes=native_managed_bytes_open(hp,buf,4);
let rp:*const NativeManagedBytes=unsafe{(&mut resource) as *const NativeManagedBytes};
if !native_managed_bytes_current(rp){return 1;}
let weak:NativeWeakToken=native_managed_bytes_weak(rp);
if !native_managed_bytes_retain(rp) || header.strong!=2{return 2;}
if native_managed_bytes_release(rp)!=1 || bytes[0]!=7 || bytes[3]!=10{return 3;}
if !native_managed_bytes_upgrade(rp,weak) || header.strong!=2{return 4;}
if native_managed_bytes_release(rp)!=1 || bytes[2]!=9{return 5;}
if native_managed_bytes_release(rp)!=2{return 6;}
if bytes[0]!=0 || bytes[1]!=0 || bytes[2]!=0 || bytes[3]!=0 || bytes[4]!=77{return 7;}
if native_managed_bytes_current(rp) || native_managed_bytes_release(rp)!=0
 || native_weak_upgrade(weak) || native_managed_bytes_upgrade(rp,weak){return 8;}
return 42;''')

    def test_managed_binding_rejects_null_empty_nonunique_and_bad_weak_tokens(self):
        self.runtime('sv858_reject_invalid','''let mut bytes:[u8;3]=[7,8,9];
let mut h:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
let p:*mut u8=unsafe{bytes as *mut u8};
let empty:NativeManagedBytes=native_managed_bytes_open(null,p,3);
let invalid:NativeManagedBytes=native_managed_bytes_open(hp,null,3);
let zero:NativeManagedBytes=native_managed_bytes_open(hp,p,0);
if empty.control!=null || invalid.control!=null || zero.control!=null{return 1;}
if !native_ref_retain(hp) || h.strong!=2{return 2;}
let shared:NativeManagedBytes=native_managed_bytes_open(hp,p,3);
if shared.control!=null || h.strong!=2{return 3;}
if native_ref_release_checked(hp)!=1{return 4;}
let mut good:NativeManagedBytes=native_managed_bytes_open(hp,p,3);
let gp:*const NativeManagedBytes=unsafe{(&mut good) as *const NativeManagedBytes};
if !native_managed_bytes_current(gp) || native_managed_bytes_retain(null){return 5;}
let mut other:NativeRefHeader=native_ref_init();
let op:*mut NativeRefHeader=unsafe{(&mut other) as *mut NativeRefHeader};
let foreign:NativeWeakToken=native_ref_weak(op);
if native_managed_bytes_upgrade(gp,foreign) || h.strong!=1{return 6;}
if native_managed_bytes_release(gp)!=2 || bytes[2]!=0{return 7;}
return 42;''')

    def test_managed_stale_handle_rejected_after_control_block_recycled(self):
        self.runtime('sv858_stale_generation','''let mut bytes:[u8;2]=[21,21];
let mut h:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut h) as *mut NativeRefHeader};
let p:*mut u8=unsafe{bytes as *mut u8};
let mut old:NativeManagedBytes=native_managed_bytes_open(hp,p,2);
let handle:*const NativeManagedBytes=unsafe{(&mut old) as *const NativeManagedBytes};
let old_weak:NativeWeakToken=native_managed_bytes_weak(handle);
if native_managed_bytes_release(handle)!=2 || !native_ref_recycle(hp){return 1;}
if native_managed_bytes_current(handle) || native_managed_bytes_retain(handle)
 || native_managed_bytes_upgrade(handle,old_weak) || native_weak_upgrade(old_weak)
 || native_managed_bytes_release(handle)!=0{return 2;}
bytes[0]=20;bytes[1]=22;
let mut fresh:NativeManagedBytes=native_managed_bytes_open(hp,p,2);
let fp:*const NativeManagedBytes=unsafe{(&mut fresh) as *const NativeManagedBytes};
if !native_managed_bytes_current(fp) || native_managed_bytes_upgrade(fp,old_weak){return 3;}
if native_managed_bytes_release(fp)!=2 || bytes[0]!=0 || bytes[1]!=0{return 4;}
return 42;''')

    def test_managed_rejects_bogus_resource_without_touching_payload(self):
        self.runtime('sv858_bogus','''let mut bytes:[u8;2]=[20,22];
let mut hdr:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut hdr) as *mut NativeRefHeader};
let b:*mut u8=unsafe{bytes as *mut u8};
let mut managed:NativeManagedBytes=native_managed_bytes_open(hp,b,2);
managed.generation=managed.generation+1;
let ptr:*const NativeManagedBytes=unsafe{(&mut managed) as *const NativeManagedBytes};
if native_managed_bytes_current(ptr) || native_managed_bytes_retain(ptr)
 || native_managed_bytes_release(ptr)!=0 || hdr.strong!=1
 || bytes[0]!=20 || bytes[1]!=22{return 1;}
return 42;''')

if __name__=='__main__':unittest.main()
