"""Four ELF, four CLI and four bootstrap contracts in the native drivers."""
import platform
import struct
import unittest
import test_sotlas_native_tool_operations_sv851 as previous


@unittest.skipUnless(platform.machine().lower() in ('amd64', 'x86_64'), 'requires x86-64')
class NativeToolOperationsSV853Tests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeToolOperationsSV851Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeToolOperationsSV851Tests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeToolOperationsSV851Tests.run_tool.__func__)
    native = previous.NativeToolOperationsSV851Tests.native
    object_file = previous.NativeToolOperationsSV851Tests.object_file

    def relocation(self, name):
        source = self.directory / (name + '.sotlas')
        obj = source.with_suffix('.o')
        source.write_text('module app;@extern(C) fn other()->u32;'
                          'pub fn main_entry()->u32{return unsafe{other()};}', encoding='utf-8')
        self.native(source, obj, '--object')
        self.native('--verify-object', obj)
        data = bytearray(obj.read_bytes())
        headers = struct.unpack_from('<Q', data, 40)[0]
        count = struct.unpack_from('<H', data, 60)[0]
        for index in range(1, count):
            header = headers + index * 64
            if struct.unpack_from('<I', data, header + 4)[0] == 4:
                first = struct.unpack_from('<Q', data, header + 24)[0]
                return obj, data, headers, header, first
        self.fail('missing relocation table')

    def test_object_preflight_rejects_unknown_relocation_kinds(self):
        obj, data, _, _, first = self.relocation('unknown relocation')
        struct.pack_into('<I', data, first + 8, 99)
        obj.write_bytes(data)
        self.native('--verify-object', obj, expected=8)

    def test_object_preflight_rejects_relocation_symbol_indices_outside_the_table(self):
        obj, data, _, _, first = self.relocation('relocation symbol')
        struct.pack_into('<I', data, first + 12, 0xffffffff)
        obj.write_bytes(data)
        self.native('--verify-object', obj, expected=8)

    def test_object_preflight_checks_the_whole_patch_width_inside_its_section(self):
        obj, data, headers, header, first = self.relocation('relocation width')
        destination = struct.unpack_from('<I', data, header + 44)[0]
        size = struct.unpack_from('<Q', data, headers + destination * 64 + 32)[0]
        struct.pack_into('<Q', data, first, size - 3)
        obj.write_bytes(data)
        self.native('--verify-object', obj, expected=8)

    def test_object_preflight_rejects_relocations_into_string_tables(self):
        obj, data, headers, header, _ = self.relocation('relocation destination')
        count = struct.unpack_from('<H', data, 60)[0]
        for index in range(1, count):
            if struct.unpack_from('<I', data, headers + index * 64 + 4)[0] == 3:
                struct.pack_into('<I', data, header + 44, index)
                break
        else:
            self.fail('missing string table')
        obj.write_bytes(data)
        self.native('--verify-object', obj, expected=8)

    def test_cli_verify_objects_reports_success_only_after_all_inputs_pass(self):
        first = self.object_file('batch object first')
        second = self.object_file('batch object second')
        self.assertEqual(self.native('--verify-objects', first, second).stdout, b'batch=passed\n')
        self.native('--verify-objects', *([first] * 16))
        second.write_bytes(b'invalid')
        self.assertEqual(self.native('--verify-objects', first, second, expected=8).stdout, b'')
        self.native('--verify-objects', expected=1)
        self.native('--verify-objects', *([first] * 17), expected=1)

    def test_cli_check_many_keeps_independent_modules_separate_and_writes_nothing(self):
        files = [self.directory / ('independent ' + str(index) + '.sotlas') for index in range(2)]
        for file in files:
            file.write_text('module same;pub fn number()->u32{return 42;}', encoding='utf-8')
        before = set(self.directory.iterdir())
        self.assertEqual(self.native('--check-many', *files).stdout, b'batch=passed\n')
        self.assertEqual(before, set(self.directory.iterdir()))
        files[1].write_text('module same;fn bad()->u32{return missing();}', encoding='utf-8')
        result = self.native('--check-many', *files, expected=6)
        self.assertEqual(result.stdout, b'')
        self.assertIn(str(files[1]).encode(), result.stderr)
        self.assertEqual(before, set(self.directory.iterdir()))

    def test_cli_object_info_reports_validated_section_symbol_and_relocation_counts(self):
        obj, data, headers, _, _ = self.relocation('object info')
        sections = struct.unpack_from('<H', data, 60)[0]
        symbols = relocations = 0
        for index in range(1, sections):
            header = headers + index * 64
            kind = struct.unpack_from('<I', data, header + 4)[0]
            size = struct.unpack_from('<Q', data, header + 32)[0]
            if kind == 2:
                symbols = size // 24
            if kind == 4:
                relocations += size // 24
        numbers = [int(line, 16) for line in self.native('--object-info', obj).stdout.splitlines()]
        self.assertEqual(numbers, [sections, symbols, relocations])
        obj.write_bytes(b'invalid')
        self.assertEqual(self.native('--object-info', obj, expected=8).stdout, b'')

    def test_cli_check_object_entry_resolves_without_creating_an_image(self):
        obj = self.object_file('check entry object')
        before = set(self.directory.iterdir())
        self.native('--check-object-entry', obj, 'main_entry')
        self.native('--check-object-entry', obj, 'missing', expected=9)
        self.native('--check-object-entry', obj, '', expected=1)
        self.assertEqual(before, set(self.directory.iterdir()))

    def test_bootstrap_compare_many_detects_a_late_mismatch_without_success_output(self):
        paths = [self.directory / ('comparison ' + str(index)) for index in range(3)]
        for path in paths:
            path.write_bytes(b'compiler artifact')
        self.assertEqual(self.native('--compare-many', *paths).stdout, b'batch=passed\n')
        paths[-1].write_bytes(b'changed artifact')
        self.assertEqual(self.native('--compare-many', *paths, expected=14).stdout, b'')
        self.native('--compare-many', paths[0], expected=1)

    def test_bootstrap_verify_seeds_checks_every_platform_envelope_before_success(self):
        invalid = self.directory / 'invalid batch seed'
        invalid.write_bytes(b'invalid')
        self.assertEqual(self.native('--verify-seeds', self.seed, self.seed).stdout, b'batch=passed\n')
        self.assertEqual(self.native('--verify-seeds', self.seed, invalid, expected=15).stdout, b'')
        self.native('--verify-seeds', *([self.seed] * 17), expected=1)

    def test_bootstrap_verify_stamps_detects_a_late_changed_pair(self):
        stamp = self.directory / 'batch verification stamp'
        self.native('--stamp-seed', self.seed, stamp)
        invalid = self.directory / 'invalid batch stamp'
        data = bytearray(stamp.read_bytes())
        data[8] ^= 1
        invalid.write_bytes(data)
        self.assertEqual(self.native('--verify-stamps', self.seed, stamp, self.seed, stamp).stdout,
                         b'seed-stamps=matched\n')
        self.assertEqual(self.native('--verify-stamps', self.seed, stamp, self.seed, invalid, expected=16).stdout, b'')
        self.native('--verify-stamps', self.seed, expected=1)

    def test_bootstrap_copy_seed_is_exclusive_byte_exact_and_executable(self):
        output = self.directory / 'exclusive seed copy'
        self.native('--copy-seed', self.seed, output)
        self.assertEqual(output.read_bytes(), self.seed.read_bytes())
        self.assertEqual(self.native('--copy-seed', self.seed, output, expected=10).stdout, b'')
        self.native('--copy-seed', self.seed, self.seed, expected=10)
        self.assertEqual(output.read_bytes(), self.seed.read_bytes())
        self.assertEqual(self.native('--compare', self.seed, output).stdout, b'byte-identical\n')
        self.run_tool([str(output), '--version'], env=self.execution_environment())

    def execution_environment(self):
        import os
        environment = {'PATH': str(self.directory / 'no-host-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        return environment


if __name__ == '__main__':
    unittest.main()
