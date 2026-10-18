"""Native regular ar creation, lazy extraction, ABI checks and execution."""
import unittest
from pathlib import Path
import test_sotlas_native_multi_object_cli as previous


class NativeStaticLibraryTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeMultiObjectCliTests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeMultiObjectCliTests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeMultiObjectCliTests.run_tool.__func__)
    native = previous.NativeMultiObjectCliTests.native
    object = previous.NativeMultiObjectCliTests.object
    execute_elf = previous.NativeMultiObjectCliTests.execute_elf

    def image(self):
        return self.directory / ('static library image ' + self._testMethodName)

    def archive(self, name, *members):
        path = self.directory / (name + '.a')
        self.native('--archive-elf', path, *members)
        return path

    def link(self, *inputs, expected=0):
        self.native('--link-elf-libraries', self.image(), 'main_entry', *inputs, expected=expected)

    def reject(self, *inputs, expected=9):
        self.image().write_bytes(b'keep previous executable')
        self.link(*inputs, expected=expected)
        self.assertEqual(self.image().read_bytes(), b'keep previous executable')

    def application(self, name='number', value=''):
        return self.object('archive caller', '@extern(C) fn ' + name + '()->u32;'
            'pub fn main_entry()->u32{return unsafe{' + name + '(' + value + ')};}')

    def test_three_module_example_builds_through_a_static_library(self):
        root = Path(__file__).resolve().parents[1] / 'examples/separate_modules'
        objects = [self.object('archive example ' + name,
            (root / (name + '.sotlas')).read_text(encoding='utf-8').split(';', 1)[1])
            for name in ('app', 'left', 'right')]
        library = self.archive('math library with spaces', *objects[1:])
        self.link(objects[0], library)
        self.execute_elf(self.image())

    def test_format_determinism_and_member_order(self):
        first = self.object('archive first', 'pub fn number()->u32{return 42;}')
        second = self.object('archive second', 'pub fn other()->u32{return 1;}')
        library = self.archive('deterministic', first, second)
        original = library.read_bytes()
        self.assertEqual(original[:8], b'!<arch>\n')
        self.assertEqual(original[8:24], b'm00000000.o/    ')
        self.assertEqual(original[24:36], b'0           ')
        self.assertEqual(original[48:56], b'100644  ')
        self.assertEqual(original[66:68], b'`\n')
        size = int(original[56:66])
        self.assertEqual(original[68:68 + size], first.read_bytes())
        # Neither source names nor directory paths appear in archive headers.
        renamed = self.directory / 'different member filename.o'
        renamed.write_bytes(first.read_bytes())
        self.native('--archive-elf', library, renamed, second)
        self.assertEqual(library.read_bytes(), original)

    def test_odd_sized_object_uses_newline_padding(self):
        provider = self.object('odd object', 'pub fn number()->u32{return 42;}')
        provider.write_bytes(provider.read_bytes() + b'\0')
        library = self.archive('odd', provider)
        binary = library.read_bytes()
        self.assertEqual(binary[-1:], b'\n')
        self.assertEqual(len(binary) % 2, 0)
        self.link(self.application(), library)
        self.execute_elf(self.image())

    def test_unused_member_with_unresolved_import_is_not_linked(self):
        used = self.object('used member', 'pub fn number()->u32{return 42;}')
        unused = self.object('unused member', '@extern(C) fn missing()->u32;'
                             'pub fn unused()->u32{return unsafe{missing()};}')
        self.link(self.application(), self.archive('lazy', unused, used))
        self.execute_elf(self.image())

    def test_transitive_dependencies_work_across_archive_order(self):
        first = self.object('archive chain first', '@extern(C) fn tail()->u32;'
                            'pub fn number()->u32{return unsafe{tail()};}')
        second = self.object('archive chain second', 'pub fn tail()->u32{return 42;}')
        left, right = self.archive('left', first), self.archive('right', second)
        caller = self.application()
        for inputs in ((caller, left, right), (right, left, caller)):
            self.link(*inputs)
            self.execute_elf(self.image())

    def test_cyclic_imports_select_members_to_a_fixed_point(self):
        caller = self.object('cycle caller', '@extern(C) fn left(v:u32)->u32;'
                             'pub fn main_entry()->u32{return unsafe{left(3)};}')
        left = self.object('cycle left', '@extern(C) fn right(v:u32)->u32;'
            'pub fn left(v:u32)->u32{if v==0{return 42;}return unsafe{right(v-1)};}')
        right = self.object('cycle right', '@extern(C) fn left(v:u32)->u32;'
            'pub fn right(v:u32)->u32{if v==0{return 42;}return unsafe{left(v-1)};}')
        self.link(caller, self.archive('cycle', right, left))
        self.execute_elf(self.image())

    def test_direct_provider_prevents_conflicting_archive_member_extraction(self):
        provider = self.object('direct provider', 'pub fn number()->u32{return 42;}')
        unused = self.object('unselected duplicate', 'pub fn number()->u32{return 1;}')
        self.link(self.application(), self.archive('unused duplicate', unused), provider)
        self.execute_elf(self.image())

    def test_first_archive_provider_is_deterministic(self):
        first = self.object('first provider', 'pub fn number()->u32{return 42;}')
        second = self.object('second provider', 'pub fn number()->u32{return 7;}')
        self.link(self.application(), self.archive('ordered', first, second))
        self.execute_elf(self.image())

    def test_abi_mismatch_in_selected_member_preserves_output(self):
        wrong = self.object('wrong return', 'pub fn number()->u64{return 42;}')
        self.reject(self.application(), self.archive('wrong ABI', wrong))

    def test_selected_member_duplicate_definition_is_rejected(self):
        provider = self.object('direct clash', 'pub fn clash()->u32{return 1;}')
        member = self.object('archive clash', 'pub fn number()->u32{return 42;}'
                              'pub fn clash()->u32{return 2;}')
        self.reject(self.application(), provider, self.archive('clashing', member))

    def test_unresolved_dependency_and_archive_only_input_are_rejected(self):
        member = self.object('unresolved library', '@extern(C) fn missing()->u32;'
                              'pub fn number()->u32{return unsafe{missing()};}')
        library = self.archive('unresolved', member)
        self.reject(self.application(), library)
        self.reject(library)

    def test_direct_objects_can_be_linked_without_an_archive(self):
        self.link(self.object('self contained', 'pub fn main_entry()->u32{return 42;}'))
        self.execute_elf(self.image())

    def test_sixteen_selected_objects_and_unused_archive_members(self):
        members = [self.object('boundary member ' + str(i),
                   'pub fn n_' + str(i) + '()->u32{return 42;}') for i in range(16)]
        declarations = ''.join('@extern(C) fn n_' + str(i) + '()->u32;' for i in range(15))
        caller = self.object('boundary caller', declarations
                             + 'pub fn main_entry()->u32{return unsafe{n_14()};}')
        library = self.archive('sixteen members', *members)
        self.link(caller, library)
        self.execute_elf(self.image())
        caller = self.object('over capacity caller', declarations + '@extern(C) fn n_15()->u32;'
                             'pub fn main_entry()->u32{return unsafe{n_15()};}')
        self.reject(caller, library)

    def test_invalid_pack_input_preserves_existing_library(self):
        library = self.directory / 'preserved archive.a'
        library.write_bytes(b'previous library')
        bad = self.directory / 'not an object.o'
        bad.write_bytes(b'bad ELF')
        self.native('--archive-elf', library, bad, expected=8)
        self.assertEqual(library.read_bytes(), b'previous library')
        self.native('--archive-elf', library, self.directory / 'missing.o', expected=2)
        self.assertEqual(library.read_bytes(), b'previous library')

    def test_candidate_table_accepts_256_and_rejects_257_members_and_roots(self):
        provider = self.object('candidate table provider', 'pub fn number()->u32{return 42;}')
        library = self.archive('candidate table', provider)
        member = library.read_bytes()[8:]
        caller = self.application()
        library.write_bytes(b'!<arch>\n' + member * 255)
        self.link(caller, library)
        self.execute_elf(self.image())
        library.write_bytes(b'!<arch>\n' + member * 256)
        self.reject(caller, library, expected=8)

    def test_cli_count_and_total_input_bounds(self):
        provider = self.object('argument bound', 'pub fn number()->u32{return 42;}')
        library = self.directory / 'count.a'
        self.native('--archive-elf', library, expected=1)
        self.native('--archive-elf', library, *([provider] * 17), expected=1)
        self.link(expected=1)
        huge = self.directory / 'oversized.a'
        huge.write_bytes(b'!<arch>\n' + bytes(8388608))
        self.reject(self.application(), huge, expected=3)

    def test_corrupt_archive_headers_and_members_preserve_output(self):
        provider = self.object('corrupt library provider', 'pub fn number()->u32{return 42;}')
        library = self.archive('corrupt', provider)
        original = library.read_bytes()
        caller = self.application()
        cases = {
            'empty': b'!<arch>\n',
            'short-header': original[:30],
            'short-member': original[:-1],
            'bad-trailer': original[:66] + b'xx' + original[68:],
            'gnu-index': original[:8] + b'/               ' + original[24:],
            'bsd-name': original[:8] + b'#1/9            ' + original[24:],
            'invalid-size': original[:56] + b'9999999999' + original[66:],
            'negative-size': original[:56] + b'-1        ' + original[66:],
            'size-overflow': original[:56] + b'zzzzzzzzzz' + original[66:],
            'bad-mode': original[:48] + b'99999999' + original[56:],
            'invalid-ELF': original[:68] + b'xxxx' + original[72:],
        }
        for name, binary in cases.items():
            with self.subTest(name=name):
                library.write_bytes(binary)
                self.reject(caller, library, expected=8)

    def test_invalid_odd_padding_is_rejected(self):
        provider = self.object('odd corrupted padding', 'pub fn number()->u32{return 42;}')
        provider.write_bytes(provider.read_bytes() + b'\0')
        library = self.archive('bad padding', provider)
        original = library.read_bytes()
        for binary in (original[:-1], original[:-1] + b' '):
            library.write_bytes(binary)
            self.reject(self.application(), library, expected=8)


if __name__ == '__main__':
    unittest.main()
