"""Native reporting and bootstrap audit commands with host tools absent."""
import os
import platform
import sys
import unittest
from pathlib import Path

if os.name == 'nt':
    from test_sotlas_native_windows_driver import NativeWindowsDriverTests as Driver
elif sys.platform == 'darwin':
    from test_sotlas_native_darwin_driver import NativeDarwinDriverTests as Driver
else:
    from test_sotlas_native_linux_driver import NativeLinuxDriverTests as Driver


@unittest.skipUnless(platform.machine().lower() in ('amd64','x86_64'), 'requires native x86-64')
class NativeToolOperationsTests(unittest.TestCase):
    setUpClass=classmethod(Driver.setUpClass.__func__)
    tearDownClass=classmethod(Driver.tearDownClass.__func__)
    run_tool=classmethod(Driver.run_tool.__func__)
    image_format='PE32+' if os.name=='nt' else 'Mach-O64' if sys.platform=='darwin' else 'ELF64'

    def native(self,*arguments,expected=0):
        environment={'PATH':str(self.directory/'no-host-tools')}
        if os.name=='nt':
            environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')
        return self.run_tool([str(self.seed),*map(str,arguments)],expected=expected,env=environment)

    def test_cli_version_reports_contract_versions(self):
        self.assertEqual(self.native('--version').stdout,b'native-driver-contract=1\ntarget-ir=1\n')
        self.native('--version','unexpected',expected=1)

    def test_cli_limits_are_machine_readable(self):
        output=self.native('--limits').stdout
        self.assertIn(b'functions<=512\n',output)
        self.assertIn(b'parameters_per_function<=24\n',output)
        self.assertIn(b'project_modules<=64\n',output)
        self.native('--limits','unexpected',expected=1)

    def test_cli_target_reports_actual_image_and_foreign_float_limit(self):
        output=self.native('--target').stdout
        image=self.image_format
        self.assertIn(('image='+image+'\n').encode(),output)
        self.assertIn(b'foreign_float_abi=unsupported\n',output)
        self.native('--target','unexpected',expected=1)

    def test_cli_exit_code_contract_includes_audit_failures(self):
        output=self.native('--exit-codes').stdout
        self.assertIn(b'14=artifacts-differ\n',output)
        self.assertIn(b'15=seed-envelope\n',output)
        self.assertIn(b'6=semantic\n',output)
        self.native('--exit-codes','unexpected',expected=1)

    def test_bootstrap_compare_proves_identity_and_detects_byte_or_length_changes(self):
        left=self.directory/'left artifact';right=self.directory/'right artifact'
        for size in (0,1,4095,4096,4097,8193):
            data=bytes(index%251 for index in range(size))
            left.write_bytes(data);right.write_bytes(data)
            self.assertEqual(self.native('--compare',left,right).stdout,b'byte-identical\n')
        right.write_bytes(left.read_bytes()[:-1]+b'\xff')
        self.native('--compare',left,right,expected=14)
        right.write_bytes(left.read_bytes()+b'\0')
        self.native('--compare',left,right,expected=14)
        self.native('--compare',left,self.directory/'missing',expected=2)
        self.native('--compare',left,expected=1)

    def test_bootstrap_fingerprint_is_streaming_and_matches_known_fnv1a(self):
        path=self.directory/'fingerprint artifact'
        for data in (b'',b'hello',bytes(range(256))*33):
            path.write_bytes(data)
            hash_value=14695981039346656037
            for byte in data:
                hash_value=((hash_value^byte)*1099511628211)&((1<<64)-1)
            self.assertEqual(self.native('--fingerprint',path).stdout,f'{hash_value:016x}\n'.encode())
        self.native('--fingerprint',self.directory/'missing',expected=2)
        self.native('--fingerprint',path,'extra',expected=1)

    def test_bootstrap_seed_envelope_accepts_native_seed_and_rejects_truncation(self):
        report=self.native('--verify-seed',self.seed)
        self.assertIn(b'seed-envelope=x86_64-',report.stdout)
        path=self.directory/'invalid seed'
        for data in (b'',b'MZ',b'\x7fELF',b'\xcf\xfa\xed\xfe',b'not executable'):
            path.write_bytes(data);self.native('--verify-seed',path,expected=15)
        data=bytearray(self.seed.read_bytes())
        if self.image_format=='PE32+':
            pe=int.from_bytes(data[60:64],'little');data[pe+4]=0
        elif self.image_format=='Mach-O64':
            data[4]=0
        else:
            data[18]=0
        path.write_bytes(data);self.native('--verify-seed',path,expected=15)
        self.native('--verify-seed',self.directory/'missing',expected=2)

    def test_bootstrap_self_test_exercises_frontend_ir_and_object_writer(self):
        self.assertEqual(self.native('--self-test').stdout,b'self-test=frontend,typed-ir,owned-object\n')
        self.native('--self-test','unexpected',expected=1)

    def test_native_runtime_project_build_and_execution_without_host_tools(self):
        root=Path(__file__).resolve().parents[1]
        source=self.directory/'managed application.sotlas'
        output=self.directory/('managed application.exe' if os.name=='nt' else 'managed application')
        source.write_text('''module application;
pub fn main_entry()->u32{let mut bytes:[u8;64]=0;
let mut arena:NativeArena=native_arena_init(unsafe{bytes as *mut u8},64);
let p:*mut u8=native_arena_alloc(unsafe{(&mut arena) as *mut NativeArena},8,8);
if p==null || !native_authority_allows(3,1){return 1;}
let mut header:NativeRefHeader=native_ref_init();
let h:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
if !native_ref_upgrade(h,1) || native_ref_release(h) || !native_ref_release(h){return 2;}
if native_ref_upgrade(h,1){return 3;}unsafe{*p=42;}return unsafe{*p} as u32;}
''',encoding='utf-8')
        self.native('--project',output,root/'runtime/native/managed.sotlas',source)
        environment={'PATH':str(self.directory/'no-host-tools')}
        if os.name=='nt':environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')
        self.run_tool([str(output)],expected=42,env=environment)


# unittest discovery must not collect the imported platform fixture itself.
del Driver

if __name__=='__main__':
    unittest.main()
