"""SV8.71: exhaustive imported symbol coverage and ELF ABI-note proof.

These add new real two-object native-link tests to the unchanged SV8.70
suite. All negative checks protect a previously written executable.
"""
import unittest
import test_sotlas_native_typed_elf_pair as previous

class NativeTypedElfSV871Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeTypedObjectPairTests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeTypedObjectPairTests.tearDownClass.__func__)
    run_tool=classmethod(previous.NativeTypedObjectPairTests.run_tool.__func__)
    native=previous.NativeTypedObjectPairTests.native
    object=previous.NativeTypedObjectPairTests.object
    execute_elf=previous.NativeTypedObjectPairTests.execute_elf
    wire=previous.NativeTypedObjectPairTests.wire
    setup_pair=previous.NativeTypedObjectPairTests.setup_pair
    link=previous.NativeTypedObjectPairTests.link

    @staticmethod
    def reject_with_previous_image(case, exit_code=9):
        case[-1].write_bytes(b'certified image')
        return exit_code

    def test_exact_one_external_import_still_links_and_executes(self):
        case=self.setup_pair()
        self.link(case)
        self.execute_elf(case[-1])

    def test_second_used_external_import_without_soti_is_rejected(self):
        case=self.setup_pair()
        case[1]=self.object('sv871 used extra import',
            '@extern(C) fn number()->u32;'
            '@extern(C) fn unseen()->u32;'
            'pub fn main_entry()->u32{return unsafe{number()}+unsafe{unseen()};}')
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_second_unused_external_declaration_also_requires_contract(self):
        case=self.setup_pair()
        case[1]=self.object('sv871 unused extra import',
            '@extern(C) fn number()->u32;'
            '@extern(C) fn unseen()->u32;'
            'pub fn main_entry()->u32{return unsafe{number()};}')
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_forged_agreeing_sidecars_cannot_hide_real_arity(self):
        case=self.setup_pair()
        case[2].write_bytes(self.wire(kind=2,params=1,role=0))
        case[4].write_bytes(self.wire(kind=1,params=1,role=0,effect=1,cap=3))
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_real_u32_parameter_agrees_with_elf_note(self):
        case=self.setup_pair()
        case[1]=self.object('sv871 caller u32',
            '@extern(C) fn number(v:u32)->u32;'
            'pub fn main_entry()->u32{return unsafe{number(42)};}')
        case[3]=self.object('sv871 provider u32',
            'pub fn number(v:u32)->u32{return v;}')
        case[2].write_bytes(self.wire(kind=2,params=1,role=0))
        case[4].write_bytes(self.wire(kind=1,params=1,role=0,effect=1,cap=3))
        self.link(case)
        self.execute_elf(case[-1])

    def test_real_bool_parameter_agrees_with_elf_note(self):
        case=self.setup_pair()
        case[1]=self.object('sv871 caller bool',
            '@extern(C) fn number(v:bool)->u32;'
            'pub fn main_entry()->u32{return unsafe{number(true)};}')
        case[3]=self.object('sv871 provider bool',
            'pub fn number(v:bool)->u32{if v{return 42;}return 1;}')
        case[2].write_bytes(self.wire(kind=2,params=1,role=0)[:48]
                            +b'\x01\x00\x00\x00\x00\x00\x00\x00')
        case[4].write_bytes(self.wire(kind=1,params=1,role=0,effect=1,cap=3)[:48]
                            +b'\x01\x00\x00\x00\x00\x00\x00\x00')
        self.link(case)
        self.execute_elf(case[-1])

    def test_forged_bool_parameter_mask_rejected_even_if_sidecars_match(self):
        case=self.setup_pair()
        case[1]=self.object('sv871 caller fake bool',
            '@extern(C) fn number(v:u32)->u32;'
            'pub fn main_entry()->u32{return unsafe{number(42)};}')
        case[3]=self.object('sv871 provider fake bool',
            'pub fn number(v:u32)->u32{return v;}')
        imported=self.wire(kind=2,params=1,role=0)
        exported=self.wire(kind=1,params=1,role=0,effect=1,cap=3)
        case[2].write_bytes(imported[:48]+b'\x01\x00\x00\x00\x00\x00\x00\x00')
        case[4].write_bytes(exported[:48]+b'\x01\x00\x00\x00\x00\x00\x00\x00')
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_forged_float_return_abi_rejected_by_compiler_elf_note(self):
        case=self.setup_pair()
        case[2].write_bytes(self.wire(kind=2,result=12))
        case[4].write_bytes(self.wire(kind=1,result=12,effect=1,cap=3))
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_nonplain_ownership_requires_metadata_not_present_in_elf_note(self):
        case=self.setup_pair()
        case[1]=self.object('sv871 caller nonplain',
            '@extern(C) fn number(v:u32)->u32;'
            'pub fn main_entry()->u32{return unsafe{number(42)};}')
        case[3]=self.object('sv871 provider nonplain',
            'pub fn number(v:u32)->u32{return v;}')
        case[2].write_bytes(self.wire(kind=2,params=1,role=1))
        case[4].write_bytes(self.wire(kind=1,params=1,role=1,effect=1,cap=3))
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_corrupt_emitted_sotlas_abi_note_is_rejected(self):
        case=self.setup_pair()
        binary=bytearray(case[3].read_bytes())
        marker=b'SOTLAS'
        start=binary.find(marker)
        self.assertGreater(start,0)
        binary[start]=0
        case[3].write_bytes(binary)
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

    def test_incorrect_note_arity_rejected_before_output_publish(self):
        case=self.setup_pair()
        binary=bytearray(case[3].read_bytes())
        start=binary.find(b'SOTLAS')
        self.assertGreater(start,0)
        # ELF SOTLAS note descriptor immediately follows its padded name.
        binary[start+8]=2
        case[3].write_bytes(binary)
        self.reject_with_previous_image(case)
        self.link(case,expected=9)
        self.assertEqual(case[-1].read_bytes(),b'certified image')

if __name__=='__main__':unittest.main()
