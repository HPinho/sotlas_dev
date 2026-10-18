"""ABI-checked native libraries producing Windows PE and Intel Mach-O images."""
import os
import struct
import sys
import unittest
from pathlib import Path
import test_sotlas_native_static_libraries as previous


class NativeLibraryTargetsTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeStaticLibraryTests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeStaticLibraryTests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeStaticLibraryTests.run_tool.__func__)
    native = previous.NativeStaticLibraryTests.native
    object = previous.NativeStaticLibraryTests.object
    archive = previous.NativeStaticLibraryTests.archive
    application = previous.NativeStaticLibraryTests.application

    def image(self, target):
        return self.directory / (self._testMethodName + ('.exe' if target == 'pe' else '.macho'))

    def link(self, target, *inputs, expected=0, entry='main_entry'):
        self.native('--link-' + target + '-libraries', self.image(target), entry,
                    *inputs, expected=expected)

    def reject(self, target, *inputs, entry='main_entry'):
        path = self.image(target)
        path.write_bytes(b'previous certified image')
        self.link(target, *inputs, expected=9, entry=entry)
        self.assertEqual(path.read_bytes(), b'previous certified image')

    def verify_image(self, target):
        path = self.image(target)
        data = path.read_bytes()
        if target == 'pe':
            self.assertEqual(data[:2], b'MZ')
            pe = struct.unpack_from('<I', data, 60)[0]
            self.assertEqual(data[pe:pe + 4], b'PE\0\0')
            self.assertEqual(struct.unpack_from('<HH', data, pe + 4), (0x8664, 2))
            self.assertEqual(struct.unpack_from('<H', data, pe + 24)[0], 0x20b)
        else:
            self.assertEqual(struct.unpack_from('<4I', data), (0xfeedfacf, 0x1000007, 3, 2))
            self.assertEqual(struct.unpack_from('<I', data, 16)[0], 5)
            self.assertEqual(struct.unpack_from('<II', data, 248), (5, 184))
        if (target == 'pe' and os.name == 'nt') or (target == 'macho' and sys.platform == 'darwin'):
            environment = {'PATH': str(self.directory / 'no-host-tools')}
            if os.name == 'nt':
                environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
            self.run_tool([str(path)], expected=42, env=environment)

    def test_three_module_library_generates_both_platform_images(self):
        root = Path(__file__).resolve().parents[1] / 'examples/separate_modules'
        app, left, right = [self.object('target example ' + name,
            (root / (name + '.sotlas')).read_text(encoding='utf-8').split(';', 1)[1])
            for name in ('app', 'left', 'right')]
        library = self.archive('portable integer library', left, right)
        for target in ('pe', 'macho'):
            with self.subTest(target=target):
                self.link(target, app, library)
                self.verify_image(target)

    def test_entry_object_can_follow_providers(self):
        provider = self.object('entry provider', 'pub fn number()->u32{return 42;}')
        app = self.application()
        for target in ('pe', 'macho'):
            self.link(target, provider, app)
            self.verify_image(target)

    def test_entry_can_be_extracted_with_a_required_library_member(self):
        root = self.object('entry root', '@extern(C) fn number()->u32;'
                           'pub fn root()->u32{return unsafe{number()};}')
        member = self.object('entry member', 'pub fn number()->u32{return 42;}'
                             'pub fn main_entry()->u32{return number();}')
        library = self.archive('entry inside library', member)
        for target in ('pe', 'macho'):
            self.link(target, root, library)
            self.verify_image(target)

    def test_bool_signed_calls_and_stack_arguments_execute(self):
        caller = self.object('platform ABI caller',
            '@extern(C) fn choose(v:bool,n:i32)->u32;'
            '@extern(C) fn total(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,h:u32)->u32;'
            'pub fn main_entry()->u32{if unsafe{choose(true,-7)}!=42{return 1;}'
            'return unsafe{total(1,2,3,4,5,6,7,14)};}')
        provider = self.object('platform ABI provider',
            'pub fn choose(v:bool,n:i32)->u32{if v&&n<0{return 42;}return 1;}'
            'pub fn total(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,h:u32)->u32'
            '{return a+b+c+d+e+f+g+h;}')
        library = self.archive('platform stack library', provider)
        for target in ('pe', 'macho'):
            self.link(target, caller, library)
            self.verify_image(target)

    def test_initialized_and_zeroed_module_data_execute(self):
        provider = self.object('platform state', 'static mut value:u32=40;static mut zero:u32=0;'
            'pub fn number()->u32{unsafe{value=value+2;}return unsafe{value+zero};}')
        library = self.archive('state library', provider)
        for target in ('pe', 'macho'):
            self.link(target, self.application(), library)
            self.verify_image(target)

    def test_unused_library_member_with_wrong_platform_is_not_emitted(self):
        used = self.object('platform used', 'pub fn number()->u32{return 42;}')
        unused = self.object('platform unused', 'pub fn other()->u32{return 1;}')
        data = bytearray(unused.read_bytes())
        struct.pack_into('<I', data, 48, 1)
        unused.write_bytes(data)
        library = self.archive('unused Linux member', unused, used)
        for target in ('pe', 'macho'):
            self.link(target, self.application(), library)
            self.verify_image(target)

    def test_return_and_parameter_mismatches_preserve_both_outputs(self):
        caller = self.application()
        for definition in ('pub fn number()->u64{return 42;}',
                           'pub fn number(v:u32)->u32{return v;}'):
            provider = self.object('target mismatched provider', definition)
            library = self.archive('mismatched target library', provider)
            for target in ('pe', 'macho'):
                self.reject(target, caller, library)

    def test_non_u32_or_argument_entry_is_rejected(self):
        for body in ('pub fn main_entry()->void{return;}',
                     'pub fn main_entry()->u64{return 42;}',
                     'pub fn main_entry(v:u32)->u32{return v;}'):
            app = self.object('invalid platform entry', body)
            for target in ('pe', 'macho'):
                self.reject(target, app)

    def test_missing_entry_and_duplicate_definition_are_rejected(self):
        provider = self.object('missing platform entry', 'pub fn number()->u32{return 42;}')
        for target in ('pe', 'macho'):
            self.reject(target, provider)
            self.reject(target, self.application(), provider, provider)

    def test_wrong_selected_platform_flags_are_rejected(self):
        app = self.object('flagged entry', 'pub fn main_entry()->u32{return 42;}')
        original = app.read_bytes()
        for target, flag in (('pe', 1), ('pe', 2), ('macho', 1)):
            changed = bytearray(original)
            struct.pack_into('<I', changed, 48, flag)
            app.write_bytes(changed)
            self.reject(target, app)

    def test_machine_abi_compatible_but_unresolved_os_import_is_rejected(self):
        app = self.object('foreign library entry', '@extern(C) fn GetLastError()->u32;'
            'pub fn main_entry()->u32{return unsafe{GetLastError()};}')
        for target in ('pe', 'macho'):
            self.reject(target, app)

    def test_deterministic_relink_and_explicit_target_bounds(self):
        app = self.object('deterministic platform entry', 'pub fn main_entry()->u32{return 42;}')
        for target in ('pe', 'macho'):
            self.link(target, app)
            expected = self.image(target).read_bytes()
            self.link(target, app)
            self.assertEqual(self.image(target).read_bytes(), expected)
            self.verify_image(target)
            self.link(target, expected=1)

    def test_fifteen_pe_objects_and_sixteen_macho_objects(self):
        helpers = [self.object('platform capacity ' + str(i),
                   'pub fn helper_' + str(i) + '()->u32{return 1;}') for i in range(15)]
        app = self.object('platform capacity entry', 'pub fn main_entry()->u32{return 42;}')
        self.link('pe', app, *helpers[:14])
        self.verify_image('pe')
        self.reject('pe', app, *helpers)
        self.link('macho', app, *helpers)
        self.verify_image('macho')


if __name__ == '__main__':
    unittest.main()
