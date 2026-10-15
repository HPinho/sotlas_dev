"""SV8.55 ELF identity/alignment, project manifests and artifact-set tooling."""
import struct
import platform
import unittest
import test_sotlas_native_tool_operations_sv854 as previous

@unittest.skipUnless(platform.machine().lower() in ('amd64','x86_64'),'requires x86-64')
class NativeToolOperationsSV855Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeToolOperationsSV854Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeToolOperationsSV854Tests.tearDownClass.__func__)
    run_tool=classmethod(previous.NativeToolOperationsSV854Tests.run_tool.__func__)
    native=previous.NativeToolOperationsSV854Tests.native
    object_file=previous.NativeToolOperationsSV854Tests.object_file
    image_format=previous.NativeToolOperationsSV854Tests.image_format
    file_name=staticmethod(str)
    manifest=previous.NativeToolOperationsSV854Tests.manifest
    invalid_object=previous.NativeToolOperationsSV854Tests.invalid_object

    def test_object_osabi_accepts_systemv_linux_and_rejects_uncontracted_values(self):
        obj=self.object_file('osabi object');original=obj.read_bytes()
        for value in (0,3):
            data=bytearray(original);data[7]=value;obj.write_bytes(data);self.native('--verify-object',obj)
        data[7]=255;obj.write_bytes(data);self.native('--verify-object',obj,expected=8)

    def test_object_abi_version_must_be_zero(self):
        self.invalid_object('abi version',lambda data:data.__setitem__(8,1))

    def test_object_reserved_ident_bytes_must_be_zero(self):
        for offset in (9,15):self.invalid_object('reserved ident '+str(offset),lambda data,o=offset:data.__setitem__(o,1))

    def test_object_file_sections_respect_their_declared_alignment(self):
        def mutate(data):
            headers=struct.unpack_from('<Q',data,40)[0]
            header=headers+64;offset=struct.unpack_from('<Q',data,header+24)[0]
            struct.pack_into('<Q',data,header+24,offset+1)
        self.invalid_object('section alignment',mutate)

    def project(self,name,resolved=False):
        library=self.directory/(name+' library.sotlas');app=self.directory/(name+' app.sotlas')
        library.write_text('module library;pub fn number()->u32{return 42;}',encoding='utf-8')
        app.write_text('module app;'+('import library::*;' if resolved else '')+'pub fn main_entry()->u32{return number();}',encoding='utf-8')
        return library,app

    def test_cli_check_project_list_resolves_declarations_without_output(self):
        library,app=self.project('ordered project');manifest=self.manifest('ordered project',[library,app])
        before=set(self.directory.iterdir());self.native('--check-project-list',manifest)
        self.assertEqual(before,set(self.directory.iterdir()))
        app.write_text('module app;fn bad()->u32{return missing();}',encoding='utf-8')
        self.native('--check-project-list',manifest,expected=6)

    def test_cli_check_project_list_resolve_orders_imported_modules(self):
        library,app=self.project('resolved project',True);manifest=self.manifest('resolved project',[app,library])
        self.native('--check-project-list-resolve',manifest)
        manifest=self.manifest('missing project dependency',[app])
        self.native('--check-project-list-resolve',manifest,expected=12)

    def test_cli_project_list_object_matches_direct_project_object_emission(self):
        library,app=self.project('project object');manifest=self.manifest('project object',[library,app])
        first=self.directory/'listed project.o';second=self.directory/'direct project.o'
        self.native('--project-list-object',first,manifest)
        self.native('--project-object',second,library,app)
        self.assertEqual(first.read_bytes(),second.read_bytes());self.native('--verify-object',first)

    def test_cli_build_project_list_executes_and_preserves_output_on_resolution_errors(self):
        library,app=self.project('project build',True);manifest=self.manifest('project build',[app,library])
        output=self.directory/'listed project image';self.native('--build-project-list',output,manifest)
        before=output.read_bytes()
        environment={'PATH':str(self.directory/'no-tools')}
        import os
        if os.name=='nt':environment['SystemRoot']=os.environ.get('SystemRoot','C:\\Windows')
        self.run_tool([str(output)],expected=42,env=environment)
        library.write_text('module unrelated;pub fn other()->u32{return 1;}',encoding='utf-8')
        self.native('--build-project-list',output,manifest,expected=12)
        self.assertEqual(output.read_bytes(),before)

    @staticmethod
    def fnv(data):
        result=14695981039346656037
        for byte in data:result=((result^byte)*1099511628211)&((1<<64)-1)
        return result

    def artifact_files(self,name):
        first=self.directory/(name+' first');second=self.directory/(name+' second')
        first.write_bytes(b'alpha\0source');second.write_bytes(b'beta build artifact')
        return first,second

    def test_bootstrap_artifact_set_info_matches_the_ordered_record_contract(self):
        files=self.artifact_files('artifact info');manifest=self.manifest('artifact info',files)
        numbers=[int(line,16) for line in self.native('--artifact-set-info',manifest).stdout.splitlines()]
        records=b''.join(struct.pack('<QQ',self.fnv(path.read_bytes()),path.stat().st_size) for path in files)
        self.assertEqual(numbers,[self.fnv(records),sum(path.stat().st_size for path in files),2])

    def test_bootstrap_artifact_set_stamps_accept_nonseeds_and_refuse_overwrites(self):
        files=self.artifact_files('stamped artifacts');manifest=self.manifest('stamped artifacts',files)
        stamp=self.directory/'artifact stamp';self.native('--stamp-artifact-set',manifest,stamp)
        data=stamp.read_bytes();self.assertEqual(len(data),32);self.assertEqual(data[:8],b'SOTART01')
        self.assertEqual(data[24:26],bytes((2,1)))
        self.native('--stamp-artifact-set',manifest,stamp,expected=10);self.assertEqual(stamp.read_bytes(),data)
        self.native('--verify-seed-set',manifest,stamp,expected=15)

    def test_bootstrap_artifact_verification_detects_bytes_order_and_reserved_metadata(self):
        files=self.artifact_files('verified artifacts');manifest=self.manifest('verified artifacts',files)
        stamp=self.directory/'verified artifact stamp';self.native('--stamp-artifact-set',manifest,stamp)
        self.assertEqual(self.native('--verify-artifact-set',manifest,stamp).stdout,b'artifact-set=matched\n')
        original=stamp.read_bytes();invalid=bytearray(original);invalid[31]=1;stamp.write_bytes(invalid)
        self.native('--verify-artifact-set',manifest,stamp,expected=16);stamp.write_bytes(original)
        self.manifest('verified artifacts',reversed(files));self.native('--verify-artifact-set',manifest,stamp,expected=16)
        self.manifest('verified artifacts',files);files[1].write_bytes(b'changed')
        self.assertEqual(self.native('--verify-artifact-set',manifest,stamp,expected=16).stdout,b'')

    def test_bootstrap_compare_sets_checks_corresponding_bytes_and_count(self):
        files=self.artifact_files('left comparison');other=self.artifact_files('right comparison')
        left=self.manifest('left comparison',files);right=self.manifest('right comparison',other)
        self.assertEqual(self.native('--compare-sets',left,right).stdout,b'artifact-sets=identical\n')
        other[1].write_bytes(b'changed')
        self.assertEqual(self.native('--compare-sets',left,right,expected=14).stdout,b'')
        self.manifest('right comparison',[other[0]])
        self.native('--compare-sets',left,right,expected=14)

if __name__=='__main__':unittest.main()
