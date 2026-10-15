"""Native project/object/bootstrap commands for the second 36-contract package."""
import os
import platform
from pathlib import Path
import unittest
import test_sotlas_native_tool_operations as previous

@unittest.skipUnless(platform.machine().lower() in ('amd64','x86_64'),'requires native x86-64')
class NativeToolOperationsSV851Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeToolOperationsTests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeToolOperationsTests.tearDownClass.__func__)
    run_tool=classmethod(previous.NativeToolOperationsTests.run_tool.__func__)
    native=previous.NativeToolOperationsTests.native
    image_format=previous.NativeToolOperationsTests.image_format

    def files(self,prefix):
        first=self.directory/(prefix+' library.sotlas');second=self.directory/(prefix+' app.sotlas')
        first.write_text('module library;pub fn number()->u32{return 42;}',encoding='utf-8')
        second.write_text('module app;pub fn main_entry()->u32{return number();}',encoding='utf-8')
        return first,second

    def object_file(self,name):
        source=self.directory/(name+'.sotlas');obj=source.with_suffix('.o')
        source.write_text('module app;pub fn main_entry()->u32{return 42;}',encoding='utf-8')
        self.native(source,obj,'--object')
        return obj

    def test_cli_check_project_uses_the_native_pipeline_without_output(self):
        first,second=self.files('sv851 check')
        before=set(self.directory.iterdir());self.native('--check-project',first,second)
        self.assertEqual(before,set(self.directory.iterdir()))
        self.native('--check-project',first)
        second.write_text('module app;pub fn main_entry()->u32{return missing();}',encoding='utf-8')
        result=self.native('--check-project',first,second,expected=6)
        self.assertIn(str(second).encode(),result.stderr)
        self.assertEqual(before,set(self.directory.iterdir()))

    def test_cli_check_project_resolve_orders_imports_and_rejects_missing_dependencies(self):
        first,second=self.files('sv851 resolve')
        second.write_text('module app;import library::*;pub fn main_entry()->u32{return number();}',encoding='utf-8')
        self.native('--check-project-resolve',second,first)
        second.write_text('module app;import absent::*;pub fn main_entry()->u32{return 42;}',encoding='utf-8')
        self.native('--check-project-resolve',second,first,expected=12)

    def test_cli_verify_object_checks_real_native_objects_and_bad_envelopes(self):
        obj=self.object_file('sv851 verify object')
        self.assertEqual(self.native('--verify-object',obj).stdout,b'object=ELF64-x86_64-valid\n')
        bad=self.directory/'bad object.o';data=bytearray(obj.read_bytes());data[0]=0;bad.write_bytes(data)
        self.native('--verify-object',bad,expected=8)
        self.native('--verify-object',obj,'extra',expected=1)

    def test_cli_link_object_executes_and_preserves_previous_image_on_rejection(self):
        obj=self.object_file('sv851 link object');output=self.directory/'sv851 linked image'
        self.native('--link-object',obj,output,'main_entry')
        environment={'PATH':str(self.directory/'no-host-tools')}
        if os.name=='nt':environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')
        self.run_tool([str(output)],expected=42,env=environment)
        before=output.read_bytes()
        self.native('--link-object',obj,output,'missing_entry',expected=9)
        self.assertEqual(output.read_bytes(),before)
        obj.write_bytes(b'not an object');self.native('--link-object',obj,output,'main_entry',expected=8)
        self.assertEqual(output.read_bytes(),before)

    def test_bootstrap_compare_three_reports_success_only_after_all_comparisons(self):
        files=[self.directory/('three artifact '+str(index)) for index in range(3)]
        for path in files:path.write_bytes(b'owned compiler'*1000)
        self.assertEqual(self.native('--compare-three',*files).stdout,b'three-byte-identical\n')
        files[2].write_bytes(b'changed')
        self.assertEqual(self.native('--compare-three',*files,expected=14).stdout,b'')
        self.native('--compare-three',*files[:2],expected=1)

    def test_bootstrap_stamp_creation_is_exclusive_and_cannot_overwrite_a_seed(self):
        stamp=self.directory/'exclusive seed stamp'
        if stamp.exists():stamp.unlink()
        self.native('--stamp-seed',self.seed,stamp)
        data=stamp.read_bytes();self.assertEqual(len(data),32);self.assertEqual(data[:8],b'SOTSEED1')
        self.assertEqual(data[25],1);self.assertEqual(data[26:],b'\0'*6)
        self.native('--stamp-seed',self.seed,stamp,expected=10)
        self.assertEqual(stamp.read_bytes(),data)
        seed=self.seed.read_bytes();self.native('--stamp-seed',self.seed,self.seed,expected=10)
        self.assertEqual(self.seed.read_bytes(),seed)

    def test_bootstrap_stamp_verification_detects_content_length_version_and_target_changes(self):
        seed=self.directory/'stamped seed copy';seed.write_bytes(self.seed.read_bytes())
        stamp=self.directory/'verification stamp'
        if stamp.exists():stamp.unlink()
        self.native('--stamp-seed',seed,stamp)
        data=stamp.read_bytes()
        self.assertEqual(self.native('--verify-stamp',seed,stamp).stdout,b'seed-stamp=matched\n')
        for offset in (8,16,24,25,31):
            invalid=bytearray(data);invalid[offset]^=1;stamp.write_bytes(invalid)
            self.assertEqual(self.native('--verify-stamp',seed,stamp,expected=16).stdout,b'')
        for invalid in (data[:-1],data+b'x'):
            stamp.write_bytes(invalid);self.native('--verify-stamp',seed,stamp,expected=16)
        stamp.write_bytes(data);content=bytearray(seed.read_bytes());content[-1]^=1;seed.write_bytes(content)
        self.native('--verify-stamp',seed,stamp,expected=16)

    def test_bootstrap_seed_info_reports_fingerprint_and_exact_64_bit_size(self):
        info=self.native('--seed-info',self.seed).stdout.splitlines()
        self.assertEqual(len(info),2)
        self.assertEqual(info[0],self.native('--fingerprint',self.seed).stdout.strip())
        self.assertEqual(int(info[1],16),len(self.seed.read_bytes()))
        self.native('--seed-info',self.seed,'extra',expected=1)

if __name__=='__main__':unittest.main()
