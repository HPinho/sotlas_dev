"""SV8.56 ELF geometry, compiler manifests and checked source audits."""
import os
import platform
import struct
import unittest
import test_sotlas_native_tool_operations_sv855 as previous


@unittest.skipUnless(platform.machine().lower() in ('amd64', 'x86_64'), 'requires x86-64')
class NativeToolOperationsSV856Tests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeToolOperationsSV855Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeToolOperationsSV855Tests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeToolOperationsSV855Tests.run_tool.__func__)
    native = previous.NativeToolOperationsSV855Tests.native
    object_file = previous.NativeToolOperationsSV855Tests.object_file
    image_format = previous.NativeToolOperationsSV855Tests.image_format
    file_name = staticmethod(str)
    manifest = previous.NativeToolOperationsSV855Tests.manifest
    invalid_object = previous.NativeToolOperationsSV855Tests.invalid_object
    project = previous.NativeToolOperationsSV855Tests.project

    def test_object_no_program_headers_requires_zero_entry_size(self):
        self.invalid_object('program entry size', lambda data: struct.pack_into('<H', data, 54, 56))

    def test_object_section_headers_require_aligned_geometry(self):
        def mutate(data):
            offset = struct.unpack_from('<Q', data, 40)[0]
            struct.pack_into('<Q', data, 40, offset + 1)
        self.invalid_object('header geometry', mutate)

    def test_object_file_payload_cannot_overlap_elf_header(self):
        def mutate(data):
            header = struct.unpack_from('<Q', data, 40)[0] + 64
            struct.pack_into('<Q', data, header + 24, 0)
        self.invalid_object('elf header overlap', mutate)

    def test_object_file_payload_cannot_overlap_section_table(self):
        def mutate(data):
            headers = struct.unpack_from('<Q', data, 40)[0]
            header = headers + 64
            struct.pack_into('<Q', data, header + 24, headers)
            struct.pack_into('<Q', data, header + 48, 1)
        self.invalid_object('section table overlap', mutate)

    def execute_image(self, output):
        environment = {'PATH': str(self.directory / 'no-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        self.run_tool([str(output)], expected=42, env=environment)

    def compiler_project(self, name, resolved):
        library, app = self.project(name, resolved)
        entry = {'PE32+': 'main_entry', 'ELF64': 'sotlas_linux_main',
                 'Mach-O64': 'sotlas_darwin_main'}[self.image_format]
        signature = '()->u32' if self.image_format == 'PE32+' else '(argc:u64,argv:*const *const u8)->u32'
        app.write_text('module app;' + ('import library::*;' if resolved else '') +
                       'pub fn ' + entry + signature + '{return number();}',
                       encoding='utf-8')
        return library, app

    def test_cli_resolved_project_manifest_object_matches_direct_emission(self):
        library, app = self.project('resolved object', True)
        manifest = self.manifest('resolved object', [app, library])
        listed = self.directory / 'resolved listed.o'
        direct = self.directory / 'resolved direct.o'
        self.native('--project-list-resolve-object', listed, manifest)
        self.native('--project-resolve-object', direct, app, library)
        self.assertEqual(listed.read_bytes(), direct.read_bytes())
        self.native('--verify-object', listed)

    def test_cli_ordered_compiler_manifest_selects_host_entry(self):
        library, app = self.compiler_project('ordered compiler', False)
        manifest = self.manifest('ordered compiler', [library, app])
        output = self.directory / 'ordered compiler image'
        self.native('--project-list-compiler', output, manifest)
        self.execute_image(output)

    def test_cli_resolved_compiler_manifest_orders_modules_and_preserves_output(self):
        library, app = self.compiler_project('resolved compiler', True)
        manifest = self.manifest('resolved compiler', [app, library])
        output = self.directory / 'resolved compiler image'
        self.native('--project-list-resolve-compiler', output, manifest)
        self.execute_image(output)
        before = output.read_bytes()
        library.write_text('module unrelated;pub fn other()->u32{return 1;}', encoding='utf-8')
        self.native('--project-list-resolve-compiler', output, manifest, expected=12)
        self.assertEqual(before, output.read_bytes())

    def test_cli_project_manifest_cross_emits_macho_envelope(self):
        library, app = self.project('macho project')
        manifest = self.manifest('macho project', [library, app])
        output = self.directory / 'manifest macho'
        self.native('--project-list-macho', output, manifest)
        self.assertEqual(output.read_bytes()[:4], b'\xcf\xfa\xed\xfe')

    def test_bootstrap_project_info_checks_semantics_before_reporting(self):
        library, app = self.project('project info', True)
        manifest = self.manifest('project info', [app, library])
        result = self.native('--project-set-info', manifest)
        values = [int(line, 16) for line in result.stdout.splitlines()]
        self.assertEqual(values[1:], [library.stat().st_size + app.stat().st_size, 2])
        app.write_text('module app;fn bad()->u32{return missing();}', encoding='utf-8')
        self.assertEqual(self.native('--project-set-info', manifest, expected=6).stdout, b'')

    def test_bootstrap_project_stamp_requires_valid_project_and_exclusive_output(self):
        library, app = self.project('project stamp', True)
        manifest = self.manifest('project stamp', [app, library])
        stamp = self.directory / 'checked project stamp'
        self.native('--stamp-project', manifest, stamp)
        data = stamp.read_bytes()
        self.assertEqual(data[:8], b'SOTART01')
        self.native('--stamp-project', manifest, stamp, expected=10)
        self.assertEqual(data, stamp.read_bytes())
        library.write_text('module library;fn bad()->u32{return missing();}', encoding='utf-8')
        rejected = self.directory / 'rejected project stamp'
        self.native('--stamp-project', manifest, rejected, expected=6)
        self.assertFalse(rejected.exists())

    def test_bootstrap_project_stamp_verification_checks_semantics_and_content(self):
        library, app = self.project('verify project', True)
        manifest = self.manifest('verify project', [app, library])
        stamp = self.directory / 'verify project stamp'
        self.native('--stamp-project', manifest, stamp)
        self.assertEqual(self.native('--verify-project-stamp', manifest, stamp).stdout,
                         b'artifact-set=matched\n')
        library.write_text('module library;pub fn number()->u32{return 43;}', encoding='utf-8')
        self.native('--verify-project-stamp', manifest, stamp, expected=16)
        library.write_text('module library;fn bad()->u32{return missing();}', encoding='utf-8')
        self.native('--verify-project-stamp', manifest, stamp, expected=6)

    def test_bootstrap_project_comparison_validates_both_sets_before_success(self):
        first = self.project('left checked project', True)
        second = self.project('right checked project', True)
        left = self.manifest('left checked project', reversed(first))
        right = self.manifest('right checked project', reversed(second))
        self.assertEqual(self.native('--compare-projects', left, right).stdout,
                         b'artifact-sets=identical\n')
        second[0].write_text('module library;pub fn number()->u32{return 43;}', encoding='utf-8')
        self.native('--compare-projects', left, right, expected=14)
        second[1].write_text('module app;fn bad()->u32{return missing();}', encoding='utf-8')
        self.assertEqual(self.native('--compare-projects', left, right, expected=6).stdout, b'')


if __name__ == '__main__':
    unittest.main()
