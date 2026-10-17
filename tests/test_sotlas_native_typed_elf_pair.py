"""SV8.70: real owned ELF two-object link with SOTI v1 ABI gates.

The native link driver reads two *independently emitted* ELF objects and
two serialized interface contracts. Before the existing ELF linker can
publish output, it checks real undefined/defined ELF symbol identities,
typed roles, return ABI and non-escalating effect/capability constraints.
"""
import struct
import unittest
import test_sotlas_native_multi_object_cli as previous

class NativeTypedObjectPairTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMultiObjectCliTests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMultiObjectCliTests.tearDownClass.__func__)
    run_tool=classmethod(previous.NativeMultiObjectCliTests.run_tool.__func__)
    native=previous.NativeMultiObjectCliTests.native
    object=previous.NativeMultiObjectCliTests.object
    execute_elf=previous.NativeMultiObjectCliTests.execute_elf

    @staticmethod
    def wire(kind=2, name_offset=0, name_len=6, result=4,
             effect=3, cap=7, role=0, params=0, version=1):
        # These are independent *test oracle* bytes, not the Sotlas
        # implementation: canonical SOTI header and optional parameters.
        head=struct.pack('<8I2Q',0x49544f53,version,kind,result,
                         name_offset,name_len,params,0,effect,cap)
        return head + (struct.pack('<II',4,role)*params)

    def setup_pair(self):
        imported=self.object('typed caller',
            '@extern(C) fn number()->u32;'
            'pub fn main_entry()->u32{return unsafe{number()};}')
        exported=self.object('typed provider','pub fn number()->u32{return 42;}')
        names=self.directory/'typed names'
        names.write_bytes(b'number')
        imp=self.directory/'typed importer.soti'
        exp=self.directory/'typed exporter.soti'
        imp.write_bytes(self.wire(kind=2))
        exp.write_bytes(self.wire(kind=1,effect=1,cap=3))
        image=self.directory/'typed linked executable'
        return [names,imported,imp,exported,exp,image]

    def link(self,items,expected=0):
        names,imported,imp,exported,exp,image=items
        self.native('--link-elf-typed-pair',image,'main_entry',names,
                    imported,imp,exported,exp,expected=expected)

    def test_link_real_elf_objects_with_compatible_typed_contracts(self):
        parts=self.setup_pair()
        self.link(parts)
        self.assertEqual(parts[-1].read_bytes()[:5],b'\x7fELF\x02')
        self.execute_elf(parts[-1])

    def test_typed_link_is_byte_for_byte_reproducible(self):
        parts=self.setup_pair()
        self.link(parts)
        initial=parts[-1].read_bytes()
        self.link(parts)
        self.assertEqual(parts[-1].read_bytes(),initial)

    def test_reject_exported_effect_escalation_without_touching_image(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[4].write_bytes(self.wire(kind=1,effect=4,cap=3))
        self.link(parts,expected=9)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_exported_capability_escalation_without_touching_image(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[4].write_bytes(self.wire(kind=1,effect=1,cap=8))
        self.link(parts,expected=9)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_return_abi_mismatch_without_touching_image(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[4].write_bytes(self.wire(kind=1,result=9,effect=1,cap=3))
        self.link(parts,expected=9)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_role_mismatch_with_real_symbol_objects(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[2].write_bytes(self.wire(kind=2,role=1,params=1))
        parts[4].write_bytes(self.wire(kind=1,effect=1,cap=3,role=2,params=1))
        self.link(parts,expected=9)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_parameter_count_mismatch(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[2].write_bytes(self.wire(kind=2,role=1,params=1))
        self.link(parts,expected=9)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_forged_signature_for_symbol_absent_from_actual_elf(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[0].write_bytes(b'absent')
        self.link(parts,expected=9)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_reversed_defined_and_undefined_object_identity(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        names,caller,imp,provider,exp,image=parts
        self.native('--link-elf-typed-pair',image,'main_entry',
                    names,provider,imp,caller,exp,expected=9)
        self.assertEqual(image.read_bytes(),b'certified image')

    def test_reject_corrupted_signature_magic_and_unknown_version(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        for wire in (b'BAD!' + self.wire()[4:],self.wire(version=2)):
            parts[2].write_bytes(wire)
            self.link(parts,expected=9)
            self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_truncated_and_oversized_wire_sidecars(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        for wire in (self.wire()[:47],self.wire()+b'\x00'):
            parts[2].write_bytes(wire)
            self.link(parts,expected=9)
            self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_reject_non_elf_and_preserve_output(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        parts[1].write_bytes(b'not ELF')
        self.link(parts,expected=8)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_missing_second_object_and_sidecar_leave_output_unchanged(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        missing=self.directory/'absent object'
        original=parts[3]
        parts[3]=missing
        self.link(parts,expected=2)
        parts[3]=original
        parts[4]=missing
        self.link(parts,expected=2)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

    def test_wrong_entry_symbol_fails_in_real_linker(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        names,caller,imp,provider,exp,image=parts
        self.native('--link-elf-typed-pair',image,'not_main',
                    names,caller,imp,provider,exp,expected=9)
        self.assertEqual(image.read_bytes(),b'certified image')

    def test_invalid_argument_count_never_publishes_output(self):
        parts=self.setup_pair()
        parts[-1].write_bytes(b'certified image')
        self.native('--link-elf-typed-pair',parts[-1],'main_entry',
                    expected=1)
        self.assertEqual(parts[-1].read_bytes(),b'certified image')

if __name__=='__main__':unittest.main()
