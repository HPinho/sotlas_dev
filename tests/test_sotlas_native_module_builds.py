"""Whole native source-list builds, independent compilation and artifact safety."""
import os
import sys
import unittest
from pathlib import Path
import test_sotlas_native_library_targets as previous


class NativeModuleBuildTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeLibraryTargetsTests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeLibraryTargetsTests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeLibraryTargetsTests.run_tool.__func__)
    native = previous.NativeLibraryTargetsTests.native
    object = previous.NativeLibraryTargetsTests.object
    archive = previous.NativeLibraryTargetsTests.archive
    image = previous.NativeLibraryTargetsTests.image
    verify_image = previous.NativeLibraryTargetsTests.verify_image

    def source(self, name, body):
        path = self.directory / (name + '.sotlas')
        path.write_text('module app;\n' + body, encoding='utf-8')
        return path

    def manifest(self, name, entries):
        path = self.directory / (name + '.list')
        path.write_bytes(('# modules\r\n\r\n' + '\r\n'.join(
            ' \t' + str(entry) + '\t ' for entry in entries) + '\r\n').encode('utf-8'))
        return path

    def output(self, target):
        if target == 'elf':
            return self.directory / (self._testMethodName + '.elf')
        return self.image(target)

    def build(self, target, sources, libraries=None, expected=0):
        args = ['--build-' + target + '-modules', self.output(target), 'main_entry', sources]
        if libraries is not None:
            args.append(libraries)
        return self.native(*args, expected=expected)

    def verify(self, target):
        if target != 'elf':
            self.verify_image(target)
        else:
            self.assertEqual(self.output(target).read_bytes()[:5], b'\x7fELF\x02')
            if sys.platform.startswith('linux'):
                self.run_tool([str(self.output(target))], expected=42,
                              env={'PATH': str(self.directory / 'no-host-tools')})

    def test_example_sources_build_three_formats_without_intermediate_files(self):
        example = Path(__file__).resolve().parents[1] / 'examples/separate_modules'
        root = example.parents[1]
        entries = [root / line for line in (example / 'modules.list').read_text(encoding='utf-8').splitlines()
                   if line and not line.startswith('#')]
        manifest = self.manifest('all example modules', entries)
        for target in ('elf', 'pe', 'macho'):
            before = set(self.directory.iterdir())
            self.build(target, manifest)
            self.verify(target)
            self.assertEqual(set(self.directory.iterdir()) - before, {self.output(target)})

    def test_source_library_and_application_build_use_the_same_pipeline(self):
        example = Path(__file__).resolve().parents[1] / 'examples/separate_modules'
        providers = self.manifest('provider sources', [example / 'left.sotlas', example / 'right.sotlas'])
        app = self.manifest('app source', [example / 'app.sotlas'])
        library = self.directory / 'source built library.a'
        before = set(self.directory.iterdir())
        self.native('--build-library', library, providers)
        self.assertEqual(set(self.directory.iterdir()) - before, {library})
        libraries = self.manifest('dependent libraries', [library])
        for target in ('elf', 'pe', 'macho'):
            self.build(target, app, libraries)
            self.verify(target)

    def test_archive_bytes_equal_individual_compilation(self):
        first = self.source('archive source one', 'pub fn left()->u32{return 20;}')
        second = self.source('archive source two', 'pub fn right()->u32{return 22;}')
        manifest = self.manifest('archive sources', [first, second])
        library = self.directory / 'direct source archive.a'
        self.native('--build-library', library, manifest)
        objects = []
        for source in (first, second):
            obj = source.with_suffix('.o')
            self.native(source, obj, '--object')
            objects.append(obj)
        reference = self.archive('reference archive', *objects)
        self.assertEqual(library.read_bytes(), reference.read_bytes())
        self.native('--build-library', library, manifest)
        self.assertEqual(library.read_bytes(), reference.read_bytes())

    def test_units_do_not_inherit_another_modules_symbols(self):
        provider = self.source('independent provider', 'pub fn number()->u32{return 42;}')
        caller = self.source('independent caller', 'pub fn main_entry()->u32{return number();}')
        manifest = self.manifest('independent units', [provider, caller])
        self.output('pe').write_bytes(b'previous image')
        result = self.build('pe', manifest, expected=6)
        self.assertIn(str(caller).encode(), result.stderr)
        self.assertIn(b':2:', result.stderr)
        self.assertEqual(self.output('pe').read_bytes(), b'previous image')

    def test_duplicate_public_symbols_are_not_silently_concatenated(self):
        first = self.source('duplicate unit one', 'pub fn main_entry()->u32{return 42;}')
        second = self.source('duplicate unit two', 'pub fn main_entry()->u32{return 1;}')
        manifest = self.manifest('duplicate sources', [first, second])
        for target in ('elf', 'pe', 'macho'):
            self.build(target, manifest, expected=9)
            self.assertFalse(self.output(target).exists())

    def test_late_source_failure_preserves_library_and_has_original_location(self):
        first = self.source('good source', 'pub fn good()->u32{return 42;}')
        second = self.source('bad source', 'pub fn bad()->u32{return absent();}')
        manifest = self.manifest('late failure', [first, second])
        library = self.directory / 'preserved source archive.a'
        library.write_bytes(b'keep library')
        before = set(self.directory.iterdir())
        result = self.native('--build-library', library, manifest, expected=6)
        self.assertIn(str(second).encode(), result.stderr)
        self.assertEqual(library.read_bytes(), b'keep library')
        self.assertEqual(set(self.directory.iterdir()), before)

    def test_late_parse_error_preserves_executable(self):
        first = self.source('good entry', 'pub fn main_entry()->u32{return 42;}')
        second = self.source('syntax error', 'pub fn broken( {')
        manifest = self.manifest('syntax failure', [first, second])
        self.output('pe').write_bytes(b'keep executable')
        result = self.build('pe', manifest, expected=5)
        self.assertIn(str(second).encode(), result.stderr)
        self.assertEqual(self.output('pe').read_bytes(), b'keep executable')

    def test_module_data_and_types_reset_between_units(self):
        first = self.source('isolated state one', 'struct Local{pub value:u32;}'
            'static mut counter:u32=20;'
            'pub fn left()->u32{let v:Local=Local{value:2};return unsafe{counter}+v.value;}')
        second = self.source('isolated state two', 'struct Local{pub x:u64;pub y:u64;}'
            'pub fn right()->u32{let v:Local=Local{x:8,y:12};return (v.x+v.y) as u32;}')
        app = self.source('state application', '@extern(C) fn left()->u32;'
            '@extern(C) fn right()->u32;pub fn main_entry()->u32{return unsafe{left()+right()};}')
        manifest = self.manifest('isolated source state', [first, second, app])
        for target in ('elf', 'pe', 'macho'):
            self.build(target, manifest)
            self.verify(target)

    def test_unresolved_library_dependency_can_be_packaged_then_resolved(self):
        left = self.source('source dependency left', '@extern(C) fn tail()->u32;'
                           'pub fn number()->u32{return unsafe{tail()};}')
        right = self.source('source dependency right', 'pub fn tail()->u32{return 42;}')
        libraries = []
        for name, source in (('left', left), ('right', right)):
            path = self.directory / (name + '.a')
            self.native('--build-library', path, self.manifest(name + ' source list', [source]))
            libraries.append(path)
        app = self.source('source dependent app', '@extern(C) fn number()->u32;'
                          'pub fn main_entry()->u32{return unsafe{number()};}')
        source_list = self.manifest('dependent app', [app])
        library_list = self.manifest('dependency lists', list(reversed(libraries)))
        for target in ('elf', 'pe', 'macho'):
            self.build(target, source_list, library_list)
            self.verify(target)

    def test_invalid_library_list_preserves_executable(self):
        app = self.source('valid source entry', 'pub fn main_entry()->u32{return 42;}')
        sources = self.manifest('entry sources', [app])
        bad = self.directory / 'bad library.a'
        bad.write_bytes(b'not an archive')
        libraries = self.manifest('bad library list', [bad])
        self.output('pe').write_bytes(b'keep image')
        self.build('pe', sources, libraries, expected=8)
        self.assertEqual(self.output('pe').read_bytes(), b'keep image')

    def test_invalid_and_missing_manifests_or_sources_preserve_output(self):
        source = self.source('manifest test entry', 'pub fn main_entry()->u32{return 42;}')
        sources = self.manifest('malformed source manifest', [source])
        library = self.directory / 'keep manifest failure.a'
        library.write_bytes(b'old library')
        for data, status in ((b'# no entries\n', 1), (b'bad\0source', 1),
                             (b'x' * 65536, 3), ((str(source) + '\n').encode() * 17, 1)):
            sources.write_bytes(data)
            self.native('--build-library', library, sources, expected=status)
            self.assertEqual(library.read_bytes(), b'old library')
        sources = self.manifest('missing source', [self.directory / 'absent.sotlas'])
        self.native('--build-library', library, sources, expected=2)
        self.native('--build-library', library, self.directory / 'absent.list', expected=2)
        self.assertEqual(library.read_bytes(), b'old library')

    def test_sixteen_sources_and_target_selected_limits(self):
        paths = [self.source('source limit ' + str(i), 'pub fn helper_' + str(i) + '()->u32{return 1;}')
                 for i in range(15)]
        app = self.source('source limit entry', 'pub fn main_entry()->u32{return 42;}')
        all_sources = self.manifest('sixteen sources', [app, *paths])
        self.build('elf', all_sources)
        self.verify('elf')
        self.build('macho', all_sources)
        self.verify('macho')
        self.build('pe', all_sources, expected=9)
        fifteen = self.manifest('fifteen sources', [app, *paths[:14]])
        self.build('pe', fifteen)
        self.verify('pe')

    def test_duplicate_source_paths_fail_before_writing_any_artifact(self):
        source = self.source('repeat module source', 'pub fn main_entry()->u32{return 42;}')
        manifest = self.manifest('repeated source roots', [source, source])
        library = self.directory / 'preserved repeated input.a'
        library.write_bytes(b'preserve original library')
        self.native('--build-library', library, manifest, expected=1)
        self.assertEqual(library.read_bytes(), b'preserve original library')
        for target in ('elf', 'pe', 'macho'):
            self.build(target, manifest, expected=1)
            self.assertFalse(self.output(target).exists())

    def test_duplicate_library_paths_fail_without_changing_executable(self):
        source = self.source('duplicate library entry', 'pub fn main_entry()->u32{return 42;}')
        sources = self.manifest('library duplicates source list', [source])
        library = self.directory / 'same library twice.a'
        library.write_bytes(b'not a valid archive')
        libraries = self.manifest('library duplicates', [library, library])
        for target in ('elf', 'pe', 'macho'):
            self.output(target).write_bytes(b'previous executable')
            self.build(target, sources, libraries, expected=1)
            self.assertEqual(self.output(target).read_bytes(), b'previous executable')

    def test_native_module_destination_cannot_overwrite_source_or_manifest(self):
        source = self.source('protected input source', 'pub fn main_entry()->u32{return 42;}')
        original_source = source.read_bytes()
        sources = self.manifest('protected source manifest', [source])
        original_manifest = sources.read_bytes()
        self.native('--build-library', source, sources, expected=1)
        self.assertEqual(source.read_bytes(), original_source)
        self.native('--build-library', sources, sources, expected=1)
        self.assertEqual(sources.read_bytes(), original_manifest)
        for target in ('elf', 'pe', 'macho'):
            self.native('--build-' + target + '-modules',
                        source, 'main_entry', sources, expected=1)
            self.assertEqual(source.read_bytes(), original_source)
            self.native('--build-' + target + '-modules',
                        sources, 'main_entry', sources, expected=1)
            self.assertEqual(sources.read_bytes(), original_manifest)

    def test_native_module_destination_cannot_overwrite_library_inputs(self):
        source = self.source('protected library source', 'pub fn main_entry()->u32{return 42;}')
        sources = self.manifest('protected library app sources', [source])
        library = self.directory / 'protected input library.a'
        library.write_bytes(b'original bytes')
        libraries = self.manifest('protected library manifest', [library])
        original_list = libraries.read_bytes()
        for target in ('elf', 'pe', 'macho'):
            self.native('--build-' + target + '-modules',
                        library, 'main_entry', sources, libraries, expected=1)
            self.assertEqual(library.read_bytes(), b'original bytes')
            self.native('--build-' + target + '-modules',
                        libraries, 'main_entry', sources, libraries, expected=1)
            self.assertEqual(libraries.read_bytes(), original_list)

    def test_dot_and_repeated_separator_source_aliases_are_rejected(self):
        source = self.source('alias source', 'pub fn main_entry()->u32{return 42;}')
        alias = str(source.parent) + os.sep + '.' + os.sep + source.name
        self.assertEqual(Path(alias).read_bytes(), source.read_bytes())
        manifest = self.manifest('alias source entries', [source, alias])
        original = self.directory / 'protected alias archive.a'
        original.write_bytes(b'preserve source output')
        self.native('--build-library', original, manifest, expected=1)
        self.assertEqual(original.read_bytes(), b'preserve source output')
        for target in ('elf', 'pe', 'macho'):
            self.build(target, manifest, expected=1)
            self.assertFalse(self.output(target).exists())

    def test_parent_component_aliases_and_output_collisions(self):
        source = self.source('parent alias', 'pub fn main_entry()->u32{return 42;}')
        sibling = source.parent / 'existing alias folder'
        sibling.mkdir(exist_ok=True)
        alias = str(sibling) + os.sep + '..' + os.sep + source.name
        self.assertEqual(Path(alias).read_bytes(), source.read_bytes())
        sources = self.manifest('parent alias sources', [source])
        original_source = source.read_bytes()
        self.native('--build-library', alias, sources, expected=1)
        self.assertEqual(source.read_bytes(), original_source)
        for target in ('elf', 'pe', 'macho'):
            self.native('--build-' + target + '-modules',
                        alias, 'main_entry', sources, expected=1)
            self.assertEqual(source.read_bytes(), original_source)
        duplicates = self.manifest('parent alias duplicates', [source, alias])
        self.native('--build-library', self.directory / 'no alias archive.a',
                    duplicates, expected=1)

    def test_manifest_and_library_lexical_alias_collisions(self):
        source = self.source('manifest alias application', 'pub fn main_entry()->u32{return 42;}')
        sources = self.manifest('source manifest aliases', [source])
        source_list_alias = str(sources.parent) + os.sep + '.' + os.sep + sources.name
        before = sources.read_bytes()
        self.native('--build-library', source_list_alias, sources, expected=1)
        self.assertEqual(sources.read_bytes(), before)
        library = self.directory / 'alias protected input.a'
        library.write_bytes(b'not a valid archive')
        library_alias = str(library.parent) + os.sep + '.' + os.sep + library.name
        lists = self.manifest('aliases for archives', [library, library_alias])
        for target in ('elf', 'pe', 'macho'):
            self.build(target, sources, lists, expected=1)
            self.assertFalse(self.output(target).exists())
            self.native('--build-' + target + '-modules',
                        library_alias, 'main_entry', sources,
                        self.manifest('one archive for alias', [library]),
                        expected=1)
            self.assertEqual(library.read_bytes(), b'not a valid archive')

    @unittest.skipUnless(os.name == 'nt', 'Windows ASCII case and separator profile')
    def test_windows_ascii_case_and_separator_alias(self):
        source = self.source('Windows Alias', 'pub fn main_entry()->u32{return 42;}')
        alias = str(source).upper().replace('\\', '/')
        manifest = self.manifest('Windows source case aliases', [source, alias])
        self.native('--build-library', self.directory / 'no windows alias.a',
                    manifest, expected=1)

    def test_import_syntax_is_not_replaced_by_hidden_concatenation(self):
        source = self.source('unresolved native import', 'import missing::*;'
                             'pub fn main_entry()->u32{return 42;}')
        self.build('elf', self.manifest('unsupported import source', [source]), expected=12)


if __name__ == '__main__':
    unittest.main()
