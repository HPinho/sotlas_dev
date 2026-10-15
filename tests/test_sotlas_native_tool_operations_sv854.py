"""Four owned object, four manifest CLI and four bootstrap manifest gates."""
import struct
import unittest
import platform
import test_sotlas_native_tool_operations_sv851 as previous

@unittest.skipUnless(platform.machine().lower() in ('amd64','x86_64'),'requires x86-64')
class NativeToolOperationsSV854Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeToolOperationsSV851Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeToolOperationsSV851Tests.tearDownClass.__func__)
    run_tool=classmethod(previous.NativeToolOperationsSV851Tests.run_tool.__func__)
    native=previous.NativeToolOperationsSV851Tests.native
    object_file=previous.NativeToolOperationsSV851Tests.object_file
    image_format=previous.NativeToolOperationsSV851Tests.image_format
    file_name=staticmethod(str)

    def manifest(self,name,paths):
        path=self.directory/(name+'.list')
        content='# artifact list\r\n\r\n'+'\r\n'.join(' \t'+self.file_name(item)+'\t ' for item in paths)+'\r\n'
        path.write_bytes(content.encode('utf-8'))
        return path

    def invalid_object(self,name,mutate):
        obj=self.object_file(name);data=bytearray(obj.read_bytes());mutate(data);obj.write_bytes(data)
        self.native('--verify-object',obj,expected=8)

    def test_object_relocatable_headers_reject_nonzero_entry_addresses(self):
        self.invalid_object('object entry',lambda data:struct.pack_into('<Q',data,24,1))

    def test_object_flags_reject_unknown_bits_and_preserve_internal_os_bits(self):
        obj=self.object_file('object flags');original=obj.read_bytes()
        for bits in (0,1,2,3):
            data=bytearray(original);struct.pack_into('<I',data,48,bits);obj.write_bytes(data)
            self.native('--verify-object',obj)
        data=bytearray(original);struct.pack_into('<I',data,48,4);obj.write_bytes(data)
        self.native('--verify-object',obj,expected=8)

    def test_object_section_names_must_fit_the_section_name_table(self):
        def mutate(data):
            headers=struct.unpack_from('<Q',data,40)[0];struct.pack_into('<I',data,headers+64,0xffffffff)
        self.invalid_object('section name bounds',mutate)

    def test_object_symbol_local_boundary_must_fit_the_symbol_table(self):
        def mutate(data):
            headers=struct.unpack_from('<Q',data,40)[0];count=struct.unpack_from('<H',data,60)[0]
            for index in range(1,count):
                header=headers+index*64
                if struct.unpack_from('<I',data,header+4)[0]==2:
                    struct.pack_into('<I',data,header+44,0xffffffff);return
            self.fail('missing symbol table')
        self.invalid_object('symbol boundary',mutate)

    def test_cli_check_list_accepts_crlf_spaces_and_independent_modules(self):
        files=[self.directory/('check source '+str(index)+'.sotlas') for index in range(2)]
        for path in files:path.write_text('module same;fn number()->u32{return 42;}',encoding='utf-8')
        manifest=self.manifest('source manifest',files);before=set(self.directory.iterdir())
        self.assertEqual(self.native('--check-list',manifest).stdout,b'batch=passed\n')
        self.assertEqual(before,set(self.directory.iterdir()))
        files[1].write_text('module same;fn bad()->u32{return missing();}',encoding='utf-8')
        self.assertEqual(self.native('--check-list',manifest,expected=6).stdout,b'')

    def test_cli_verify_object_list_rejects_nul_empty_oversized_and_excess_entries(self):
        obj=self.object_file('manifest object');manifest=self.manifest('object manifest',[obj])
        self.native('--verify-object-list',manifest)
        for content,code in ((b'# empty\n',1),(b'bad\0path',1),(b'x'*65536,3),
                             ((self.file_name(obj)+'\n').encode()*17,1)):
            manifest.write_bytes(content);self.native('--verify-object-list',manifest,expected=code)

    def test_cli_check_entry_list_validates_every_object_without_output(self):
        first=self.object_file('first entry');second=self.object_file('second entry')
        manifest=self.manifest('entry manifest',[first,second]);before=set(self.directory.iterdir())
        self.assertEqual(self.native('--check-entry-list','main_entry',manifest).stdout,b'entries=passed\n')
        self.native('--check-entry-list','missing',manifest,expected=9)
        self.assertEqual(before,set(self.directory.iterdir()))

    def test_cli_link_elf_list_uses_the_owned_linker_and_preserves_rejected_output(self):
        obj=self.object_file('list link input');manifest=self.manifest('link manifest',[obj])
        output=self.directory/'manifest linked ELF'
        self.native('--link-elf-list',output,'main_entry',manifest)
        before=output.read_bytes();self.assertEqual(before[:5],b'\x7fELF\x02')
        if self.image_format=='ELF64':
            self.run_tool([str(output)],expected=42,env={'PATH':str(self.directory/'no-tools')})
        self.native('--link-elf-list',output,'missing',manifest,expected=9)
        self.assertEqual(output.read_bytes(),before)

    def test_bootstrap_compare_list_reports_success_only_after_every_comparison(self):
        first=self.directory/'first compared';second=self.directory/'second compared'
        first.write_bytes(b'seed');second.write_bytes(b'seed')
        manifest=self.manifest('compare manifest',[first,second]);self.native('--compare-list',manifest)
        second.write_bytes(b'changed')
        self.assertEqual(self.native('--compare-list',manifest,expected=14).stdout,b'')

    def test_bootstrap_verify_seed_list_rejects_a_late_invalid_seed(self):
        invalid=self.directory/'invalid list seed';invalid.write_bytes(b'invalid')
        manifest=self.manifest('seed manifest',[self.seed,self.seed]);self.native('--verify-seed-list',manifest)
        manifest=self.manifest('seed manifest',[self.seed,invalid])
        self.assertEqual(self.native('--verify-seed-list',manifest,expected=15).stdout,b'')

    def test_bootstrap_seed_set_stamps_are_exclusive_and_record_count_size_and_hash(self):
        manifest=self.manifest('stamped seed manifest',[self.seed,self.seed]);stamp=self.directory/'seed set stamp'
        self.native('--stamp-seed-set',manifest,stamp)
        data=stamp.read_bytes();self.assertEqual(len(data),32);self.assertEqual(data[:8],b'SOTSET01')
        self.assertEqual(struct.unpack_from('<Q',data,16)[0],len(self.seed.read_bytes())*2)
        self.assertEqual(data[24:26],bytes((2,1)));self.assertEqual(data[26:],b'\0'*6)
        self.native('--stamp-seed-set',manifest,stamp,expected=10);self.assertEqual(stamp.read_bytes(),data)
        self.native('--stamp-seed-set',manifest,self.seed,expected=10)

    def test_bootstrap_seed_set_verification_rejects_metadata_content_and_count_changes(self):
        copied=self.directory/'seed set copy';copied.write_bytes(self.seed.read_bytes()+b'SV854')
        manifest=self.manifest('verified seed set',[self.seed,copied]);stamp=self.directory/'verified set stamp'
        self.native('--stamp-seed-set',manifest,stamp);data=stamp.read_bytes()
        self.assertEqual(self.native('--verify-seed-set',manifest,stamp).stdout,b'seed-set=matched\n')
        self.manifest('verified seed set',[copied,self.seed])
        self.native('--verify-seed-set',manifest,stamp,expected=16)
        self.manifest('verified seed set',[self.seed,copied])
        for offset in (0,8,16,24,25,31):
            invalid=bytearray(data);invalid[offset]^=1;stamp.write_bytes(invalid)
            self.assertEqual(self.native('--verify-seed-set',manifest,stamp,expected=16).stdout,b'')
        stamp.write_bytes(data);changed=bytearray(copied.read_bytes());changed[-1]^=1;copied.write_bytes(changed)
        self.native('--verify-seed-set',manifest,stamp,expected=16)
        self.manifest('verified seed set',[self.seed]);self.native('--verify-seed-set',manifest,stamp,expected=16)

if __name__=='__main__':unittest.main()
