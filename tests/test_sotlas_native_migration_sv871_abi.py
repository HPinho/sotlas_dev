"""SV8.71: native typed-interface ABI derived from compiler-owned Target IR.

Positive and negative inputs execute in Sotlas-produced machine code; Python
orchestrates the same native compiler, object writer and linker as SV8.69.
"""
import unittest
import test_sotlas_native_migration_sv869 as previous

class NativeMigrationSV871AbiTests(unittest.TestCase):
    setUpClass=classmethod(previous.NativeMigrationSV869Tests.setUpClass.__func__)
    tearDownClass=classmethod(previous.NativeMigrationSV869Tests.tearDownClass.__func__)
    compile=previous.NativeMigrationSV869Tests.compile
    link_image=previous.NativeMigrationSV869Tests.link_image
    execute=previous.NativeMigrationSV869Tests.execute
    wire=previous.NativeMigrationSV869Tests.wire

    def ir(self,name,body):
        fixture='''let mut abi_parameter:TargetParameter=TargetParameter{
value_id:1,type_tag:TargetTypeTag::U32,
name:TargetSourceSlice{offset:0,length:3}};
let abi_ptr:*const TargetParameter=unsafe{
 (&mut abi_parameter) as *const TargetParameter};
let mut function_ir:TargetFunction=TargetFunction{
name:TargetSourceSlice{offset:0,length:3},
return_type:TargetTypeTag::U32,first_parameter:0,
parameter_count:1,first_block:0,block_count:0,flags:TARGET_FUNCTION_EXTERNAL};
'''
        self.wire(name,fixture+body)

    def test_native_ir_generates_import_soti_from_real_parameter_types(self):
        self.ir('sv871_ir_import','''if !target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=56 || !target_interface_wire_valid(ib,ni,names,12)
 || (in_bytes[8] as u32)!=TARGET_INTERFACE_IMPORT
 || in_bytes[12]!=4 || in_bytes[16]!=0
 || in_bytes[20]!=3 || in_bytes[24]!=1
 || in_bytes[48]!=4 || in_bytes[52]!=0
 || in_bytes[32]!=3 || in_bytes[40]!=7{return 1;}
return 42;''')

    def test_native_ir_generates_export_and_checks_wire_compatibility(self):
        self.ir('sv871_ir_compatible','''if !target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip){return 1;}
function_ir.flags=0;function_ir.name.offset=9;
if !target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,1,3,eb,256,ep)
 || ne!=56 || (ex_bytes[8] as u32)!=TARGET_INTERFACE_EXPORT
 || !target_interface_wire_compatible(ib,ni,eb,ne,names,12){return 2;}
return 42;''')

    def test_native_ir_copies_return_and_parameter_scalar_widths(self):
        self.ir('sv871_ir_width','''function_ir.return_type=TargetTypeTag::U64;
abi_parameter.type_tag=TargetTypeTag::I32;
if !target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,0,0,ib,256,ip)
 || in_bytes[12]!=5 || in_bytes[48]!=9
 || in_bytes[52]!=0{return 1;}
return 42;''')

    def test_native_ir_zero_parameter_void_signature(self):
        self.ir('sv871_ir_void','''function_ir.parameter_count=0;
function_ir.return_type=TargetTypeTag::Void;
if !target_interface_wire_encode_from_function_abi(
 names,12,function_ir,null,0,0,0,ib,256,ip)
 || ni!=48 || in_bytes[12]!=16
 || in_bytes[24]!=0{return 1;}
return 42;''')

    def test_native_ir_rejects_bad_parameter_range_transactionally(self):
        self.ir('sv871_ir_range','''function_ir.first_parameter=1;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 1;}
function_ir.first_parameter=0;function_ir.parameter_count=25;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 2;}
return 42;''')

    def test_native_ir_rejects_aggregate_and_void_parameter_abi(self):
        self.ir('sv871_ir_aggregate','''abi_parameter.type_tag=TargetTypeTag::Aggregate;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 1;}
abi_parameter.type_tag=TargetTypeTag::Void;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 2;}
return 42;''')

    def test_native_ir_rejects_nonzero_unsupported_flags_and_aggregate_return(self):
        self.ir('sv871_ir_bad_kind','''function_ir.flags=16;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 1;}
function_ir.flags=0;function_ir.return_type=TargetTypeTag::Aggregate;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 2;}
return 42;''')

    def test_native_ir_capacity_and_source_bounds_do_not_modify_artifact(self):
        self.ir('sv871_ir_size','''if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,55,ip)
 || ni!=777 || in_bytes[0]!=170{return 1;}
function_ir.name.offset=11;
if target_interface_wire_encode_from_function_abi(
 names,12,function_ir,abi_ptr,1,3,7,ib,256,ip)
 || ni!=777 || in_bytes[0]!=170{return 2;}
return 42;''')

if __name__=='__main__':unittest.main()
