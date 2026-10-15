"""Owned ELF linking from independently compiled inputs on every native host."""
import platform
import sys
import unittest
import test_sotlas_native_tool_operations as previous


@unittest.skipUnless(platform.machine().lower() in ('amd64', 'x86_64'), 'requires x86-64')
class NativeMultiObjectCliTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeToolOperationsTests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeToolOperationsTests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeToolOperationsTests.run_tool.__func__)
    native = previous.NativeToolOperationsTests.native

    def object(self, name, body):
        source = self.directory / (name + '.sotlas')
        output = source.with_suffix('.o')
        source.write_text('module app;' + body, encoding='utf-8')
        self.native(source, output, '--object')
        return output

    def execute_elf(self, output):
        if sys.platform.startswith('linux'):
            self.run_tool([str(output)], expected=42,
                          env={'PATH': str(self.directory / 'no-host-tools')})

    def test_separate_function_objects_resolve_calls_in_either_order(self):
        library = self.object('separate library', 'pub fn number()->u32{return 42;}')
        app = self.object('separate app', '@extern(C) fn number()->u32;'
                          'pub fn main_entry()->u32{return unsafe{number()};}')
        images = []
        for index, objects in enumerate(((app, library), (library, app))):
            output = self.directory / ('separate image ' + str(index))
            self.native('--link-elf-objects', output, 'main_entry', *objects)
            self.assertEqual(output.read_bytes()[:5], b'\x7fELF\x02')
            images.append(output.read_bytes())
            self.execute_elf(output)
        self.assertTrue(all(images))

    def test_missing_and_malformed_later_inputs_preserve_existing_output(self):
        obj = self.object('valid input', 'pub fn main_entry()->u32{return 42;}')
        output = self.directory / 'preserved multi image'
        output.write_bytes(b'previous image')
        missing = self.directory / 'missing.o'
        self.native('--link-elf-objects', output, 'main_entry', obj, missing, expected=2)
        self.assertEqual(output.read_bytes(), b'previous image')
        malformed = self.directory / 'malformed.o'
        malformed.write_bytes(b'not ELF')
        self.native('--link-elf-objects', output, 'main_entry', obj, malformed, expected=8)
        self.assertEqual(output.read_bytes(), b'previous image')

    def test_duplicate_symbols_and_unresolved_calls_preserve_output(self):
        first = self.object('duplicate one', 'pub fn main_entry()->u32{return 42;}')
        second = self.object('duplicate two', 'pub fn main_entry()->u32{return 7;}')
        output = self.directory / 'duplicate image'
        output.write_bytes(b'previous image')
        self.native('--link-elf-objects', output, 'main_entry', first, second, expected=9)
        unresolved = self.object('unresolved input', '@extern(C) fn absent()->u32;'
                                 'pub fn main_entry()->u32{return unsafe{absent()};}')
        self.native('--link-elf-objects', output, 'main_entry', unresolved, expected=9)
        self.assertEqual(output.read_bytes(), b'previous image')

    def test_object_count_and_entry_bounds_are_checked_before_output(self):
        obj = self.object('count input', 'pub fn main_entry()->u32{return 42;}')
        output = self.directory / 'count image'
        output.write_bytes(b'previous image')
        self.native('--link-elf-objects', output, 'main_entry', expected=1)
        self.native('--link-elf-objects', output, 'main_entry', *([obj] * 17), expected=1)
        self.native('--link-elf-objects', output, '', obj, expected=1)
        self.native('--link-elf-objects', output, 'missing_entry', obj, expected=9)
        self.assertEqual(output.read_bytes(), b'previous image')

    def test_total_input_capacity_is_enforced_before_output(self):
        obj = self.object('capacity input', 'pub fn main_entry()->u32{return 42;}')
        huge = self.directory / 'oversized input.o'
        huge.write_bytes(obj.read_bytes() + b'\0' * 8388608)
        output = self.directory / 'capacity image'
        output.write_bytes(b'previous image')
        self.native('--link-elf-objects', output, 'main_entry', huge, expected=3)
        self.native('--link-elf-objects', output, 'main_entry', obj, huge, expected=3)
        self.assertEqual(output.read_bytes(), b'previous image')

    def test_sixteen_distinct_objects_link_at_the_declared_count_limit(self):
        objects = [self.object('limit library ' + str(index),
                   'pub fn leaf_' + str(index) + '()->u32{return 42;}')
                   for index in range(15)]
        objects.append(self.object('limit app', '@extern(C) fn leaf_14()->u32;'
                       'pub fn main_entry()->u32{return unsafe{leaf_14()};}'))
        output = self.directory / 'sixteen object image'
        self.native('--link-elf-objects', output, 'main_entry', *objects)
        self.assertEqual(output.read_bytes()[:5], b'\x7fELF\x02')
        self.execute_elf(output)

    def test_single_input_is_reproducible_and_can_replace_its_loaded_object(self):
        obj = self.object('single ELF input', 'pub fn main_entry()->u32{return 42;}')
        output = self.directory / 'single ELF image'
        self.native('--link-elf-objects', output, 'main_entry', obj)
        expected = output.read_bytes()
        self.native('--link-elf-objects', output, 'main_entry', obj)
        self.assertEqual(output.read_bytes(), expected)
        self.native('--link-elf-objects', obj, 'main_entry', obj)
        self.assertEqual(obj.read_bytes(), expected)
        self.execute_elf(output)


if __name__ == '__main__':
    unittest.main()
