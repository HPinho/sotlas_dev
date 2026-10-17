"""SV8.69 owned native Target IR wire ABI: success, corruption and rollback."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv868 as previous

ROOT=Path(__file__).resolve().parents[1]

class NativeMigrationSV869Tests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV868Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV868Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV868Tests.compile
    link_image=previous.NativeMigrationSV868Tests.link_image
    execute=previous.NativeMigrationSV868Tests.execute

    def wire(self,name,body):
        source=(ROOT/'bootstrap/sotlas/native_compiler/backend/target_ir.sotlas').read_text(
            encoding='utf-8').split(';',1)[1]
        fixture='''struct WireParamPair {
pub first:TargetInterfaceParameter;pub second:TargetInterfaceParameter;}
pub fn main_entry()->u32{
let names:*const u8="foobarbazfoo";
let mut pair:WireParamPair=WireParamPair{
first:TargetInterfaceParameter{type_tag:TargetTypeTag::U32,role:0},
second:TargetInterfaceParameter{type_tag:TargetTypeTag::U32,role:0}};
let raw:*mut WireParamPair=unsafe{(&mut pair) as *mut WireParamPair};
let parameters:*const TargetInterfaceParameter=unsafe{
 (raw as usize) as *const TargetInterfaceParameter};
let mut imported:TargetInterface=TargetInterface{
name:TargetSourceSlice{offset:0,length:3},return_type:TargetTypeTag::U32,
first_parameter:0,parameter_count:1,effects:3,
required_capabilities:7,flags:TARGET_INTERFACE_IMPORT};
let mut exported:TargetInterface=TargetInterface{
name:TargetSourceSlice{offset:9,length:3},return_type:TargetTypeTag::U32,
first_parameter:1,parameter_count:1,effects:1,
required_capabilities:3,flags:TARGET_INTERFACE_EXPORT};
let mut in_bytes:[u8;256]=[170;256];
let mut ex_bytes:[u8;256]=[170;256];
let ib:*mut u8=unsafe{in_bytes as *mut u8};
let eb:*mut u8=unsafe{ex_bytes as *mut u8};
let mut ni:usize=777;let mut ne:usize=888;
let ip:*mut usize=unsafe{(&mut ni) as *mut usize};
let ep:*mut usize=unsafe{(&mut ne) as *mut usize};
'''
        self.execute(self.compile(name,source+fixture+body+'}'))

    def test_wire_fixed_width_sizes_and_limit(self):
        self.wire('sv869_sizes','''if target_interface_wire_size(0)!=48
 || target_interface_wire_size(1)!=56
 || target_interface_wire_size(24)!=240
 || target_interface_wire_size(25)!=0{return 1;}return 42;''')

    def test_wire_import_roundtrip_preserves_fields_and_role(self):
        self.wire('sv869_roundtrip','''pair.first.role=1;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || ni!=56{return 1;}
let mut decoded:TargetInterface=exported;
let dp:*mut TargetInterface=unsafe{(&mut decoded) as *mut TargetInterface};
let mut value:TargetInterfaceParameter=TargetInterfaceParameter{
type_tag:TargetTypeTag::U8,role:0};
let vp:*mut TargetInterfaceParameter=unsafe{
 (&mut value) as *mut TargetInterfaceParameter};
if !target_interface_wire_decode(ib,ni,names,12,dp,vp,1)
 || decoded.flags!=TARGET_INTERFACE_IMPORT || decoded.name.offset!=0
 || decoded.name.length!=3 || decoded.parameter_count!=1
 || decoded.first_parameter!=0 || decoded.effects!=3
 || decoded.required_capabilities!=7
 || value.type_tag!=TargetTypeTag::U32 || value.role!=1{return 2;}
return 42;''')

    def test_wire_little_endian_header_does_not_copy_host_padding(self):
        self.wire('sv869_header','''if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || in_bytes[0]!=83 || in_bytes[1]!=79
 || in_bytes[2]!=84 || in_bytes[3]!=73
 || in_bytes[4]!=1 || in_bytes[8]!=2 || in_bytes[12]!=4
 || in_bytes[20]!=3 || in_bytes[24]!=1
 || in_bytes[28]!=0 || in_bytes[32]!=3 || in_bytes[40]!=7
 || in_bytes[48]!=4 || in_bytes[52]!=0
 || in_bytes[55]!=0{return 1;}return 42;''')

    def test_wire_unaligned_byte_buffer(self):
        self.wire('sv869_unaligned','''let shifted:*mut u8=unsafe{ib+1};
if !target_interface_wire_encode(names,12,imported,parameters,2,shifted,255,ip)
 || !target_interface_wire_valid(shifted,56,names,12)
 || in_bytes[0]!=170 || in_bytes[1]!=83{return 1;}return 42;''')

    def test_wire_bad_magic_version_reserved_fields_and_extent(self):
        self.wire('sv869_corrupt_header','''if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip){
return 1;}
in_bytes[0]=0;
if target_interface_wire_valid(ib,56,names,12){return 2;}
in_bytes[0]=83;in_bytes[4]=2;
if target_interface_wire_valid(ib,56,names,12){return 3;}
in_bytes[4]=1;in_bytes[28]=1;
if target_interface_wire_valid(ib,56,names,12){return 4;}
in_bytes[28]=0;
if target_interface_wire_valid(ib,55,names,12)
 || target_interface_wire_valid(ib,57,names,12)
 || target_interface_wire_valid(null,56,names,12)
 || !target_interface_wire_valid(ib,56,names,12){return 5;}
return 42;''')

    def test_wire_encode_rejects_overflow_without_writing(self):
        self.wire('sv869_small','''if target_interface_wire_encode(names,12,imported,parameters,2,ib,55,ip)
 || ni!=777 || in_bytes[0]!=170 || in_bytes[55]!=170{return 1;}
return 42;''')

    def test_wire_invalid_name_before_publication(self):
        self.wire('sv869_name_bounds','''imported.name.offset=11;
if target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 1;}
return 42;''')

    def test_wire_bad_param_role_and_type_preserve_decode_destinations(self):
        self.wire('sv869_invalid_param','''if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip){
return 1;}
let mut decoded:TargetInterface=exported;
let dp:*mut TargetInterface=unsafe{(&mut decoded) as *mut TargetInterface};
let mut slot:TargetInterfaceParameter=TargetInterfaceParameter{
type_tag:TargetTypeTag::U8,role:3};
let sp:*mut TargetInterfaceParameter=unsafe{
 (&mut slot) as *mut TargetInterfaceParameter};
in_bytes[52]=4;
if target_interface_wire_decode(ib,56,names,12,dp,sp,1)
 || decoded.flags!=TARGET_INTERFACE_EXPORT
 || slot.role!=3 || slot.type_tag!=TargetTypeTag::U8{return 2;}
in_bytes[52]=0;in_bytes[48]=15;
if target_interface_wire_valid(ib,56,names,12){return 3;}
return 42;''')

    def test_wire_decode_rejects_insufficient_destination_capacity(self):
        self.wire('sv869_decode_capacity','''if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip){
return 1;}
let mut decoded:TargetInterface=exported;
let dp:*mut TargetInterface=unsafe{(&mut decoded) as *mut TargetInterface};
if target_interface_wire_decode(ib,56,names,12,dp,null,0)
 || decoded.flags!=TARGET_INTERFACE_EXPORT{return 2;}
return 42;''')

    def test_wire_compatible_exact_sole_direct_whisper_roles(self):
        self.wire('sv869_ownership_roles','''let mut role:u32=0;
while role<=3{
pair.first.role=role;pair.second.role=role;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || !target_interface_wire_compatible(ib,56,eb,56,names,12){return 1;}
role=role+1;}
return 42;''')

    def test_wire_compatible_rejects_role_mismatch_and_abi_change(self):
        self.wire('sv869_mismatch','''pair.first.role=1;pair.second.role=2;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || target_interface_wire_compatible(ib,56,eb,56,names,12){return 1;}
pair.second.role=1;pair.second.type_tag=TargetTypeTag::U64;
if !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || target_interface_wire_compatible(ib,56,eb,56,names,12){return 2;}
return 42;''')

    def test_wire_compatible_rejects_effect_capability_escalation(self):
        self.wire('sv869_privilege','''exported.effects=4;exported.required_capabilities=8;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || target_interface_wire_compatible(ib,56,eb,56,names,12){return 1;}
exported.effects=1;
if !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || target_interface_wire_compatible(ib,56,eb,56,names,12){return 2;}
return 42;''')

    def test_wire_compatible_rejects_symbol_and_return_abi_mismatch(self):
        self.wire('sv869_symbol','''exported.name.offset=3;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || target_interface_wire_compatible(ib,56,eb,56,names,12){return 1;}
exported.name.offset=9;exported.return_type=TargetTypeTag::I32;
if !target_interface_wire_encode(names,12,exported,parameters,2,eb,256,ep)
 || target_interface_wire_compatible(ib,56,eb,56,names,12){return 2;}
return 42;''')

    def test_wire_zero_parameter_void_result(self):
        self.wire('sv869_void','''imported.parameter_count=0;
imported.return_type=TargetTypeTag::Void;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip)
 || ni!=48 || !target_interface_wire_valid(ib,48,names,12){return 1;}
let mut decoded:TargetInterface=exported;
let dp:*mut TargetInterface=unsafe{(&mut decoded) as *mut TargetInterface};
if !target_interface_wire_decode(ib,48,names,12,dp,null,0)
 || decoded.return_type!=TargetTypeTag::Void
 || decoded.parameter_count!=0{return 2;}
return 42;''')

    def test_wire_max_u64_capabilities_round_trip(self):
        self.wire('sv869_max_u64','''imported.effects=18446744073709551615;
imported.required_capabilities=18446744073709551615;
if !target_interface_wire_encode(names,12,imported,parameters,2,ib,256,ip){return 1;}
let mut decoded:TargetInterface=exported;
let dp:*mut TargetInterface=unsafe{(&mut decoded) as *mut TargetInterface};
let mut slot:TargetInterfaceParameter=TargetInterfaceParameter{
type_tag:TargetTypeTag::U8,role:0};
let sp:*mut TargetInterfaceParameter=unsafe{
 (&mut slot) as *mut TargetInterfaceParameter};
if !target_interface_wire_decode(ib,56,names,12,dp,sp,1)
 || decoded.effects!=18446744073709551615
 || decoded.required_capabilities!=18446744073709551615{return 2;}
return 42;''')

if __name__=='__main__':unittest.main()
