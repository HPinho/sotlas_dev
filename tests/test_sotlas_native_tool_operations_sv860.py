"""SV8.60: strict ELF sections, JSON reports and native object rebuild audits."""
import json
import platform
import struct
import unittest
import test_sotlas_native_tool_operations_sv856 as previous


@unittest.skipUnless(platform.machine().lower() in ('amd64', 'x86_64'), 'requires x86-64')
class NativeToolOperationsSV860Tests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeToolOperationsSV856Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeToolOperationsSV856Tests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeToolOperationsSV856Tests.run_tool.__func__)
    native = previous.NativeToolOperationsSV856Tests.native
    object_file = previous.NativeToolOperationsSV856Tests.object_file
    image_format = previous.NativeToolOperationsSV856Tests.image_format
    file_name = staticmethod(str)
    manifest = previous.NativeToolOperationsSV856Tests.manifest
    invalid_object = previous.NativeToolOperationsSV856Tests.invalid_object
    project = previous.NativeToolOperationsSV856Tests.project

    def test_object_file_sections_cannot_share_payload_bytes(self):
        def mutate(data):
            headers = struct.unpack_from('<Q', data, 40)[0]
            first_offset = struct.unpack_from('<Q', data, headers+64+24)[0]
            count = struct.unpack_from('<H', data, 60)[0]
            for index in range(2, count):
                row = headers+index*64
                if struct.unpack_from('<I', data, row+4)[0] == 3:
                    struct.pack_into('<Q', data, row+24, first_offset)
                    return
            self.fail('missing string table')
        self.invalid_object('overlapping payloads', mutate)

    def test_object_string_tables_reject_uncontracted_entry_metadata(self):
        def mutate(data):
            headers = struct.unpack_from('<Q', data, 40)[0]
            names = struct.unpack_from('<H', data, 62)[0]
            struct.pack_into('<Q', data, headers+names*64+56, 1)
        self.invalid_object('string table entry metadata', mutate)

    def test_object_relocations_cannot_target_metadata_sections(self):
        def mutate(data):
            headers = struct.unpack_from('<Q', data, 40)[0]
            names = struct.unpack_from('<H', data, 62)[0]
            count = struct.unpack_from('<H', data, 60)[0]
            for index in range(1, count):
                row = headers+index*64
                if struct.unpack_from('<I', data, row+4)[0] == 4:
                    struct.pack_into('<I', data, row+44, names)
                    return
            self.fail('missing relocation section')
        self.invalid_object('relocation metadata destination', mutate)

    def test_object_relocatable_sections_require_zero_virtual_addresses(self):
        def mutate(data):
            headers = struct.unpack_from('<Q', data, 40)[0]
            struct.pack_into('<Q', data, headers+64+16, 4096)
        self.invalid_object('relocatable section address', mutate)

    def report(self, command, legacy, path, keys):
        expected = self.native(legacy, path).stdout.splitlines()
        actual = json.loads(self.native(command, path).stdout)
        self.assertEqual(actual, dict(zip(keys, (value.decode('ascii') for value in expected))))
        self.assertTrue(all(len(value) == 16 for value in actual.values()))

    def test_cli_object_json_reports_validated_native_object_counts(self):
        obj = self.object_file('json object')
        self.report('--object-info-json', '--object-info', obj, ('sections_hex', 'symbols_hex', 'relocations_hex'))
        obj.write_bytes(b'invalid')
        self.assertEqual(self.native('--object-info-json', obj, expected=8).stdout, b'')

    def test_cli_seed_json_reports_the_verified_executable_envelope(self):
        self.report('--seed-info-json', '--seed-info', self.seed, ('fingerprint_hex', 'bytes_hex'))
        bad = self.directory/'bad json seed'
        bad.write_bytes(b'not executable')
        self.assertEqual(self.native('--seed-info-json', bad, expected=15).stdout, b'')

    def test_cli_artifact_json_reports_ordered_fingerprint_size_and_count(self):
        files = self.project('json artifact set', True)
        manifest = self.manifest('json artifact set', files)
        self.report('--artifact-set-info-json', '--artifact-set-info', manifest, ('fingerprint_hex', 'bytes_hex', 'files_hex'))

    def test_cli_project_json_requires_successful_native_semantics(self):
        files = self.project('json checked project', True)
        manifest = self.manifest('json checked project', reversed(files))
        self.report('--project-set-info-json', '--project-set-info', manifest, ('fingerprint_hex', 'bytes_hex', 'files_hex'))
        files[1].write_text('module app;fn bad()->u32{return missing();}', encoding='utf-8')
        self.assertEqual(self.native('--project-set-info-json', manifest, expected=6).stdout, b'')

    def checked_project(self, name):
        files = self.project(name, True)
        return files, self.manifest(name, reversed(files))

    def test_bootstrap_rebuild_verifies_object_bytes_and_refuses_valid_mismatches(self):
        files, manifest = self.checked_project('verify rebuilt object')
        obj = self.directory/'rebuilt expected.o'
        self.native('--project-list-resolve-object', obj, manifest)
        before = obj.read_bytes()
        self.assertEqual(self.native('--verify-project-object', manifest, obj).stdout, b'project-object=matched\n')
        files[0].write_text('module library;pub fn number()->u32{return 43;}', encoding='utf-8')
        self.assertEqual(self.native('--verify-project-object', manifest, obj, expected=14).stdout, b'')
        self.assertEqual(obj.read_bytes(), before)

    def test_bootstrap_compares_rebuilt_objects_instead_of_source_formatting(self):
        first, left = self.checked_project('left rebuilt project')
        second, right = self.checked_project('right rebuilt project')
        self.assertEqual(self.native('--compare-project-objects', left, right).stdout, b'project-objects=identical\n')
        second[0].write_text('module library;pub fn number()->u32{return 43;}', encoding='utf-8')
        self.assertEqual(self.native('--compare-project-objects', left, right, expected=14).stdout, b'')
        second[0].write_text('module library;fn bad()->u32{return missing();}', encoding='utf-8')
        self.native('--compare-project-objects', left, right, expected=6)

    def test_bootstrap_rebuilt_object_stamps_record_object_identity_exclusively(self):
        files, manifest = self.checked_project('stamp rebuilt project')
        stamp = self.directory/'rebuilt object stamp'
        self.native('--stamp-project-object', manifest, stamp)
        data = stamp.read_bytes()
        self.assertEqual(data[:8], b'SOTOBJ01')
        self.assertEqual(len(data), 32)
        self.assertEqual(data[24:], bytes((1, 3, 0, 0, 0, 0, 0, 0)))
        self.native('--stamp-project-object', manifest, stamp, expected=10)
        self.assertEqual(stamp.read_bytes(), data)

    def test_bootstrap_object_stamp_verification_rebuilds_and_checks_metadata(self):
        files, manifest = self.checked_project('verify rebuilt stamp')
        stamp = self.directory/'verified rebuilt object stamp'
        self.native('--stamp-project-object', manifest, stamp)
        self.assertEqual(self.native('--verify-project-object-stamp', manifest, stamp).stdout, b'project-object-stamp=matched\n')
        data = stamp.read_bytes()
        damaged = bytearray(data)
        damaged[31] = 1
        stamp.write_bytes(damaged)
        self.native('--verify-project-object-stamp', manifest, stamp, expected=16)
        stamp.write_bytes(data)
        files[0].write_text('module library;pub fn number()->u32{return 43;}', encoding='utf-8')
        self.assertEqual(self.native('--verify-project-object-stamp', manifest, stamp, expected=16).stdout, b'')


if __name__ == '__main__': unittest.main()
