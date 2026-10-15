"""SV8.59: Sotlas-native managed close through compiler-emitted defer cleanup."""
import unittest
from pathlib import Path
import test_sotlas_native_migration_sv858 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV859Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV858Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV858Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV858Tests.compile
    link_image=previous.NativeMigrationSV858Tests.link_image
    execute=previous.NativeMigrationSV858Tests.execute
    runtime=previous.NativeMigrationSV858Tests.runtime

    def execute_runtime(self,name,program):
        source=(ROOT/'runtime/native/managed.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        self.execute(self.compile(name,source+'\n'+program))

    def test_managed_defer_block_cleans_payload_once_and_poisoned_slot(self):
        self.runtime('sv859_scope_close','''let mut bytes:[u8;3]=[21,21,79];
let mut header:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
let raw:*mut u8=unsafe{bytes as *mut u8};
let mut owner:NativeManagedBytes=native_managed_bytes_open(hp,raw,2);
let p:*mut NativeManagedBytes=unsafe{(&mut owner) as *mut NativeManagedBytes};
let weak:NativeWeakToken=native_managed_bytes_weak(p);
{defer native_managed_bytes_close(p);defer native_managed_bytes_close(p);
if !native_managed_bytes_current(p) || bytes[0]!=21{return 1;}}
if header.strong!=0 || header.live || bytes[0]!=0 || bytes[1]!=0 || bytes[2]!=79{return 2;}
if owner.control!=null || owner.bytes!=null || owner.length!=0 || owner.generation!=0{return 3;}
if native_weak_upgrade(weak) || native_managed_bytes_current(p){return 4;}
native_managed_bytes_close(p);
if header.strong!=0 || bytes[2]!=79{return 5;}
return 42;''')

    def test_managed_defer_runs_before_early_return_and_preserves_return_value(self):
        self.execute_runtime('sv859_return_close','''fn finish(p:*mut NativeManagedBytes,flag:bool)->u32{
defer native_managed_bytes_close(p);
if flag{return 42;}return 42;}
pub fn main_entry()->u32{
let mut bytes:[u8;3]=[21,21,9];let mut header:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
let raw:*mut u8=unsafe{bytes as *mut u8};
let mut resource:NativeManagedBytes=native_managed_bytes_open(hp,raw,2);
let p:*mut NativeManagedBytes=unsafe{(&mut resource) as *mut NativeManagedBytes};
if finish(p,true)!=42 || bytes[0]!=0 || bytes[1]!=0 || bytes[2]!=9
    || header.strong!=0 || resource.control!=null{return 1;}
return 42;}''')

    def test_managed_nonfinal_close_preserves_bytes_and_other_strong_claim(self):
        self.runtime('sv859_nonfinal_close','''let mut bytes:[u8;2]=[20,22];
let mut hdr:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut hdr) as *mut NativeRefHeader};
let b:*mut u8=unsafe{bytes as *mut u8};
let mut managed:NativeManagedBytes=native_managed_bytes_open(hp,b,2);
let p:*mut NativeManagedBytes=unsafe{(&mut managed) as *mut NativeManagedBytes};
if !native_managed_bytes_retain(p) || hdr.strong!=2{return 1;}
{defer native_managed_bytes_close(p);}
if hdr.strong!=1 || bytes[0]!=20 || bytes[1]!=22 || managed.control!=null{return 2;}
let mut last:NativeManagedBytes=native_managed_bytes_open(hp,b,2);
let lp:*mut NativeManagedBytes=unsafe{(&mut last) as *mut NativeManagedBytes};
native_managed_bytes_close(lp);
if hdr.strong!=0 || bytes[0]!=0 || bytes[1]!=0{return 3;}
return 42;''')

    def test_managed_invalid_close_never_clears_foreign_or_stale_payload(self):
        self.runtime('sv859_invalid_close','''let mut bytes:[u8;2]=[20,22];
let mut hdr:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut hdr) as *mut NativeRefHeader};
let b:*mut u8=unsafe{bytes as *mut u8};
let mut managed:NativeManagedBytes=native_managed_bytes_open(hp,b,2);
let p:*mut NativeManagedBytes=unsafe{(&mut managed) as *mut NativeManagedBytes};
managed.generation=managed.generation+1;
native_managed_bytes_close(p);native_managed_bytes_close(null);
if hdr.strong!=1 || bytes[0]!=20 || bytes[1]!=22 || managed.control!=hp{return 1;}
managed.generation=hdr.generation;
native_managed_bytes_close(p);
if hdr.strong!=0 || managed.control!=null || bytes[0]!=0 || bytes[1]!=0{return 2;}
return 42;''')

if __name__=='__main__':unittest.main()
