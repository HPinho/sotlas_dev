"""Native execution and malformed-input gates for SV8.50 boundaries."""
from pathlib import Path
import subprocess
import struct
import unittest
import test_sotlas_native_i32 as integer

ROOT = Path(__file__).resolve().parents[1]


class NativeBoundaryExpansionTests(unittest.TestCase):
    setUpClass = classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile = integer.NativeI32Tests.compile
    link_image = integer.NativeI32Tests.link_image
    execute = integer.NativeI32Tests.execute

    def test_frontend_nested_comments_preserve_code_and_reject_unclosed_inner(self):
        self.execute(self.compile('nested_comments',
            '/* first /* second */ first */pub fn main_entry()->u32{return 42;}'))
        self.compile('nested_unclosed',
            'pub fn main_entry()->u32{return 42;}/* first /* second */',success=False)

    def test_frontend_separators_require_digits_on_both_sides(self):
        self.execute(self.compile('separators_valid',
            'pub fn main_entry()->u32{let x:u32=4_2;return x;}'))
        for index,literal in enumerate(('42_','4__2','0x','0x_2a','4_.2','4.2_','4_e2')):
            self.compile('separator_invalid_'+str(index),
                'pub fn value()->f64{return '+literal+';}pub fn main_entry()->u32{return 42;}',success=False)

    def test_frontend_strings_reject_raw_or_escaped_line_breaks(self):
        for index,text in enumerate(('"x\r\ny"','"x\\\ny"','"x\\\r\ny"')):
            self.compile('string_newline_'+str(index),
                'pub fn main_entry()->u32{let s:*const u8='+text+';return 42;}',success=False)
        self.execute(self.compile('string_escape_valid',
            'pub fn main_entry()->u32{let s:*const u8="x\\ny";return 42;}'))

    def test_frontend_source_nul_is_rejected_even_in_comments_and_literals(self):
        for index,suffix in enumerate(('\x00','//x\x00','/*x\x00*/')):
            self.compile('source_nul_'+str(index),
                'pub fn main_entry()->u32{return 42;}'+suffix,success=False)
        self.compile('literal_nul',
            'pub fn main_entry()->u32{let s:*const u8="x\x00y";return 42;}',success=False)

    def test_abi_pointer_u64_roundtrip_preserves_storage_identity(self):
        self.execute(self.compile('pointer_u64', '''pub fn main_entry()->u32{
let mut buffer:[u8;8]=0;let p:*mut u8=unsafe{buffer as *mut u8};
let address:u64=unsafe{p as u64};let q:*mut u8=unsafe{address as *mut u8};
unsafe{*q=42;}return buffer[0] as u32;}'''))
        self.execute(self.compile('record_pointer_u64', '''struct Packet{pub value:u32;}
pub fn main_entry()->u32{let mut packet:Packet=Packet{value:1};
let p:*mut Packet=unsafe{(&mut packet) as *mut Packet};let address:u64=unsafe{p as u64};
let q:*mut Packet=unsafe{address as *mut Packet};unsafe{(*q).value=42;}return packet.value;}'''))

    def test_abi_pointer_usize_roundtrip_and_pointer_offsets(self):
        self.execute(self.compile('pointer_usize', '''pub fn main_entry()->u32{
let mut buffer:[u8;8]=0;let p:*mut u8=unsafe{buffer as *mut u8};
let address:usize=unsafe{p as usize};let q:*mut u8=unsafe{address as *mut u8};
let offset:usize=3;unsafe{*(q+offset)=42;}return buffer[3] as u32;}'''))

    def test_lowering_scalar_and_pointer_branch_assignments_use_structured_cfg(self):
        self.execute(self.compile('branch_assignment_cfg', '''fn choose(flag:bool)->u32{
let mut value:u32=1;if flag{value=42;}return value;}
pub fn main_entry()->u32{if choose(false)!=1{return 1;}return choose(true);}'''))
        self.execute(self.compile('pointer_branch_assignment_cfg', '''fn choose(flag:bool)->u32{
let mut text:*const u8="x";if flag{text="*";}return unsafe{*text} as u32;}
pub fn main_entry()->u32{if choose(false)!=120{return 1;}return choose(true);}'''))

    def test_abi_address_conversions_require_unsafe(self):
        cases=('let p:*const u8="x";let address:u64=p as u64;',
               'let address:u64=0;let p:*mut u8=address as *mut u8;',
               'let p:*const u8="x";let address:usize=p as usize;')
        for index,body in enumerate(cases):
            self.compile('pointer_safe_reject_'+str(index),
                'pub fn main_entry()->u32{'+body+'return 42;}',success=False)

    def test_abi_pointer_conversions_reject_narrow_signed_and_float_addresses(self):
        cases=('let p:*const u8="x";let address:u32=unsafe{p as u32};',
               'let address:u32=0;let p:*mut u8=unsafe{address as *mut u8};',
               'let address:i64=0;let p:*mut u8=unsafe{address as *mut u8};',
               'let address:f64=0.0;let p:*mut u8=unsafe{address as *mut u8};')
        for index,body in enumerate(cases):
            self.compile('pointer_width_reject_'+str(index),
                'pub fn main_entry()->u32{'+body+'return 42;}',success=False)
        for index,body in enumerate(('let packet:Packet=Packet{value:42};let address:u64=unsafe{packet as u64};',
                                     'let packet:Packet=Packet{value:42};let address:usize=unsafe{packet as usize};')):
            self.compile('aggregate_address_reject_'+str(index),
                'struct Packet{pub value:u32;}pub fn main_entry()->u32{'+body+'return 42;}',success=False)

    def run_ir(self,name,body):
        text=(ROOT/'bootstrap/sotlas/native_compiler/backend/target_ir.sotlas').read_text(encoding='utf-8')
        self.execute(self.compile(name,text.split(';',1)[1]+'\npub fn main_entry()->u32{'+body+'}'))

    def test_ir_ssa_values_cannot_have_void_or_invalid_types(self):
        self.run_ir('ir_value_types', '''let mut value:TargetValue=TargetValue::empty();value.id=1;
value.type_tag=TargetTypeTag::Void;
if !target_module_value_invalid(unsafe{(&mut value) as *mut TargetValue},0){return 1;}
value.type_tag=TargetTypeTag::U32;
if target_module_value_invalid(unsafe{(&mut value) as *mut TargetValue},0){return 2;}return 42;''')

    def test_ir_domain_metadata_rejects_out_of_contract_domain_ids(self):
        self.run_ir('ir_domain', '''let mut value:TargetValue=TargetValue::empty();value.id=1;
value.type_tag=TargetTypeTag::U32;value.flags=2304;
if !target_module_value_invalid(unsafe{(&mut value) as *mut TargetValue},0){return 1;}
value.flags=2048;if target_module_value_invalid(unsafe{(&mut value) as *mut TargetValue},0){return 2;}return 42;''')

    def test_ir_function_return_and_parameter_type_sets_are_distinct(self):
        self.run_ir('ir_return_types', '''if target_type_is_value(TargetTypeTag::Void)
|| !target_type_is_return(TargetTypeTag::Void) || target_type_is_return(TargetTypeTag::Invalid)
|| !target_type_is_value(TargetTypeTag::Aggregate){return 1;}return 42;''')

    def test_ir_source_slices_reject_range_wraparound_and_accept_empty_end(self):
        self.run_ir('ir_source_bounds', '''let end:TargetSourceSlice=TargetSourceSlice{offset:42,length:0};
let huge:TargetSourceSlice=TargetSourceSlice{offset:1,length:18446744073709551615};
let beyond:TargetSourceSlice=TargetSourceSlice{offset:43,length:0};
if !target_source_slice_valid(end,42) || target_source_slice_valid(huge,42)
|| target_source_slice_valid(beyond,42){return 1;}return 42;''')

    def reject_object(self,name,mutate):
        obj=self.compile(name,'pub fn main_entry()->u32{return 42;}')
        data=bytearray(obj.read_bytes());mutate(data);obj.write_bytes(data)
        output=obj.with_suffix('.bad-image')
        result=subprocess.run([str(self.producer),'--link-exe',str(obj),str(output),'main_entry'],
            capture_output=True,timeout=30)
        self.assertNotEqual(result.returncode,0,result.stderr)
        self.assertFalse(output.exists())

    def test_object_linker_rejects_wrong_elf_version_and_header_envelope(self):
        for name,offset,value in (('elf_ident',6,2),('elf_header_size',52,0),('elf_program_count',56,1)):
            self.reject_object(name,lambda data,o=offset,v=value:data.__setitem__(o,v))

    def test_object_linker_rejects_nonempty_undefined_section(self):
        def mutate(data):
            headers=struct.unpack_from('<Q',data,40)[0];data[headers+32]=1
        self.reject_object('elf_null_section',mutate)

    def test_object_linker_validates_section_name_table_identity_and_bounds(self):
        def mutate(data):
            count=struct.unpack_from('<H',data,60)[0];struct.pack_into('<H',data,62,count)
        self.reject_object('elf_names_index',mutate)
        def unterminated(data):
            headers=struct.unpack_from('<Q',data,40)[0]
            index=struct.unpack_from('<H',data,62)[0]
            offset,size=struct.unpack_from('<QQ',data,headers+index*64+24)
            data[offset+size-1]=1
        self.reject_object('elf_names_termination',unterminated)

    def test_object_linker_rejects_forged_null_symbol(self):
        def mutate(data):
            headers=struct.unpack_from('<Q',data,40)[0]
            count=struct.unpack_from('<H',data,60)[0]
            for index in range(1,count):
                if struct.unpack_from('<I',data,headers+index*64+4)[0]==2:
                    offset=struct.unpack_from('<Q',data,headers+index*64+24)[0]
                    data[offset+8]=42;return
            raise AssertionError('missing symbol table')
        self.reject_object('elf_null_symbol',mutate)


if __name__=='__main__':
    unittest.main()
