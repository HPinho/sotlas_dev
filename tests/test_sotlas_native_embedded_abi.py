"""Production ELF manifests and native multi-module integer ABI linking."""
import struct
import unittest
from pathlib import Path
import test_sotlas_native_multi_object_cli as previous


class NativeEmbeddedAbiTests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeMultiObjectCliTests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeMultiObjectCliTests.tearDownClass.__func__)
    run_tool = classmethod(previous.NativeMultiObjectCliTests.run_tool.__func__)
    native = previous.NativeMultiObjectCliTests.native
    object = previous.NativeMultiObjectCliTests.object
    execute_elf = previous.NativeMultiObjectCliTests.execute_elf

    def image(self):
        return self.directory / ('embedded ABI image ' + self._testMethodName)

    def pair(self, declaration='fn number(v:u32)->u32;',
             definition='pub fn number(v:u32)->u32{return v;}', argument='42'):
        caller = self.object('embedded caller', '@extern(C) ' + declaration
                             + 'pub fn main_entry()->u32{return unsafe{number('
                             + argument + ')};}')
        return caller, self.object('embedded provider', definition)

    def link(self, objects, expected=0):
        self.native('--link-elf-abi-objects', self.image(), 'main_entry',
                    *objects, expected=expected)

    def reject(self, objects):
        self.image().write_bytes(b'preserve previous executable')
        self.link(objects, expected=9)
        self.assertEqual(self.image().read_bytes(), b'preserve previous executable')

    @staticmethod
    def manifest(binary):
        headers = struct.unpack_from('<Q', binary, 40)[0]
        sections = struct.unpack_from('<H', binary, 60)[0]
        for index in range(1, sections):
            header = headers + index * 64
            if struct.unpack_from('<I', binary, header + 4)[0] == 7:
                start, size = struct.unpack_from('<QQ', binary, header + 24)
                legacy = struct.unpack_from('<I', binary, start + 4)[0]
                note = start + 20 + legacy
                if note + 28 <= start + size:
                    return header, note
        raise AssertionError('production object has no embedded ABI manifest')

    def test_three_modules_resolve_multiple_imports_without_sidecars(self):
        example = Path(__file__).resolve().parents[1] / 'examples/separate_modules'
        caller, left, right = [self.object('ABI example ' + name,
            (example / (name + '.sotlas')).read_text(encoding='utf-8').split(';', 1)[1])
            for name in ('app', 'left', 'right')]
        for objects in ((caller, left, right), (right, caller, left)):
            self.link(objects)
            self.execute_elf(self.image())

    def test_integer_signedness_widths_and_bool_execute(self):
        for tag in ('u8', 'u16', 'u32', 'u64', 'usize',
                    'i8', 'i16', 'i32', 'i64', 'isize', 'bool'):
            with self.subTest(tag=tag):
                value = 'true' if tag == 'bool' else '-7' if tag.startswith('i') else '42'
                caller = self.object('ABI caller ' + tag,
                    '@extern(C) fn identity(v:' + tag + ')->' + tag + ';'
                    'pub fn main_entry()->u32{if unsafe{identity(' + value + ')}=='
                    + value + '{return 42;}return 1;}')
                provider = self.object('ABI identity ' + tag,
                    'pub fn identity(v:' + tag + ')->' + tag + '{return v;}')
                self.link((caller, provider))
                self.execute_elf(self.image())

    def test_void_return_and_stack_arguments_execute(self):
        caller = self.object('ABI stack caller',
            '@extern(C) fn observe()->void;'
            '@extern(C) fn sum(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,h:u32)->u32;'
            'pub fn main_entry()->u32{unsafe{observe();}'
            'return unsafe{sum(1,2,3,4,5,6,7,14)};}')
        provider = self.object('ABI stack provider',
            'pub fn observe()->void{return;}'
            'pub fn sum(a:u32,b:u32,c:u32,d:u32,e:u32,f:u32,g:u32,h:u32)->u32'
            '{return a+b+c+d+e+f+g+h;}')
        self.link((caller, provider))
        self.execute_elf(self.image())

    def test_plain_data_section_does_not_hide_function_signatures(self):
        objects = self.pair(definition='static mut seed:u32=42;'
                           'pub fn number(v:u32)->u32{return unsafe{seed};}')
        self.link(objects)
        self.execute_elf(self.image())

    def test_arity_mismatch_preserves_previous_image(self):
        self.reject(self.pair(definition='pub fn number()->u32{return 42;}'))

    def test_same_register_width_different_signedness_is_rejected(self):
        self.reject(self.pair(definition='pub fn number(v:i32)->u32{return 42;}'))

    def test_parameter_width_mismatch_is_rejected(self):
        self.reject(self.pair(definition='pub fn number(v:u64)->u32{return 42;}'))

    def test_return_type_mismatch_is_rejected(self):
        self.reject(self.pair(definition='pub fn number(v:u32)->u64{return 42;}'))

    def test_bool_does_not_alias_an_integer_parameter(self):
        self.reject(self.pair(definition='pub fn number(v:bool)->u32{return 42;}'))

    def test_unused_external_declaration_requires_a_matching_definition(self):
        caller = self.object('ABI unused import', '@extern(C) fn unused()->u32;'
                             'pub fn main_entry()->u32{return 42;}')
        self.reject((caller,))

    def test_duplicate_provider_is_rejected(self):
        caller, provider = self.pair()
        duplicate = self.object('ABI duplicate', 'pub fn number(v:u32)->u32{return v;}')
        self.reject((caller, provider, duplicate))

    def test_pointer_cross_module_contract_is_explicitly_rejected(self):
        caller = self.object('ABI pointer caller', '@extern(C) fn number(v:*const u8)->u32;'
                             'pub fn main_entry()->u32{return unsafe{number(null)};}')
        provider = self.object('ABI pointer provider',
                               'pub fn number(v:*const u8)->u32{return 42;}')
        self.reject((caller, provider))

    def test_manifest_is_deterministic_and_contains_actual_type_tags(self):
        caller, provider = self.pair()
        binary = provider.read_bytes()
        _, note = self.manifest(binary)
        self.assertEqual(struct.unpack_from('<III', binary, note), (7, 116, 3))
        self.assertEqual(struct.unpack_from('<II', binary, note + 20), (1, 1))
        self.assertEqual(struct.unpack_from('<IIII', binary, note + 28), (1, 4, 1, 4))
        self.assertEqual(binary[note + 44:note + 136], bytes(92))
        self.link((caller, provider))
        image = self.image().read_bytes()
        self.link((caller, provider))
        self.assertEqual(self.image().read_bytes(), image)

    def test_missing_or_malformed_manifest_never_overwrites_output(self):
        caller, provider = self.pair()
        original = provider.read_bytes()
        header, note = self.manifest(original)
        cases = {
            'legacy-only': (header + 32, 24, '<Q'),
            'version': (note + 20, 2, '<I'),
            'count': (note + 24, 1025, '<I'),
            'descriptor-length': (note + 4, 8, '<I'),
            'symbol-zero': (note + 28, 0, '<I'),
            'symbol-out-of-bounds': (note + 28, 999999, '<I'),
            'arity': (note + 36, 25, '<I'),
            'invalid-return': (note + 32, 0, '<I'),
            'invalid-parameter': (note + 40, 0, '<I'),
            'unused-parameter-slot': (note + 44, 4, '<I'),
            'note-name': (note + 12, 0, '<I'),
        }
        for name, (position, value, encoding) in cases.items():
            with self.subTest(name=name):
                changed = bytearray(original)
                struct.pack_into(encoding, changed, position, value)
                provider.write_bytes(changed)
                self.reject((caller, provider))

    def test_duplicate_manifest_symbol_record_is_rejected(self):
        caller, provider = self.pair(definition='pub fn other()->u32{return 1;}'
            'pub fn number(v:u32)->u32{return v;}')
        binary = bytearray(provider.read_bytes())
        _, note = self.manifest(binary)
        binary[note + 136:note + 140] = binary[note + 28:note + 32]
        provider.write_bytes(binary)
        self.reject((caller, provider))

    def test_omitting_a_function_record_is_rejected(self):
        caller, provider = self.pair(definition='pub fn number(v:u32)->u32{return v;}'
            'pub fn other()->u32{return 1;}')
        binary = bytearray(provider.read_bytes())
        header, note = self.manifest(binary)
        start = struct.unpack_from('<Q', binary, header + 24)[0]
        struct.pack_into('<I', binary, note + 4, 116)
        struct.pack_into('<I', binary, note + 24, 1)
        struct.pack_into('<Q', binary, header + 32, note - start + 136)
        provider.write_bytes(binary)
        self.reject((caller, provider))

    def test_sixteen_objects_and_cli_bounds(self):
        objects = [self.object('ABI leaf ' + str(i),
                   'pub fn leaf_' + str(i) + '()->u32{return 42;}') for i in range(15)]
        caller = self.object('ABI boundary caller', '@extern(C) fn leaf_14()->u32;'
                             'pub fn main_entry()->u32{return unsafe{leaf_14()};}')
        objects.append(caller)
        self.link(objects)
        self.execute_elf(self.image())
        self.link(objects + [caller], expected=1)
        self.link((), expected=1)


if __name__ == '__main__':
    unittest.main()
