"""SV8.68: Sotlas-owned typed pre-link ABI and capability interface contract.

Python only launches native compiler-produced executables. All interface
validation and import resolution executes as Sotlas-generated machine code.
"""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv860 as previous

ROOT = Path(__file__).resolve().parents[1]

class NativeMigrationSV868Tests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeMigrationSV860Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeMigrationSV860Tests.tearDownClass.__func__)
    compile = previous.NativeMigrationSV860Tests.compile
    link_image = previous.NativeMigrationSV860Tests.link_image
    execute = previous.NativeMigrationSV860Tests.execute

    def interface(self, name, body):
        source = (ROOT / "bootstrap/sotlas/native_compiler/backend/target_ir.sotlas").read_text(
            encoding="utf-8").split(";", 1)[1]
        pairs = """struct InterfaceParamPair{
pub first:TargetInterfaceParameter;pub second:TargetInterfaceParameter;}
struct InterfacePair{pub first:TargetInterface;pub second:TargetInterface;}
"""
        fixture = """pub fn main_entry()->u32{
let names:*const u8="foofoobarbar";
let mut parameter_pair:InterfaceParamPair=InterfaceParamPair{
 first:TargetInterfaceParameter{type_tag:TargetTypeTag::U32,role:0},
 second:TargetInterfaceParameter{type_tag:TargetTypeTag::U32,role:0}};
let parameter_raw:*mut InterfaceParamPair=unsafe{
 (&mut parameter_pair) as *mut InterfaceParamPair};
let parameters:*const TargetInterfaceParameter=unsafe{
 (parameter_raw as usize) as *const TargetInterfaceParameter};
let mut imported:TargetInterface=TargetInterface{
 name:TargetSourceSlice{offset:0,length:3},return_type:TargetTypeTag::U32,
 first_parameter:0,parameter_count:1,effects:3,
 required_capabilities:7,flags:TARGET_INTERFACE_IMPORT};
let mut exported:TargetInterface=TargetInterface{
 name:TargetSourceSlice{offset:3,length:3},return_type:TargetTypeTag::U32,
 first_parameter:1,parameter_count:1,effects:1,
 required_capabilities:3,flags:TARGET_INTERFACE_EXPORT};
let imports:*const TargetInterface=unsafe{(&mut imported) as *const TargetInterface};
let exports:*const TargetInterface=unsafe{(&mut exported) as *const TargetInterface};
let mut matched:u32=99;
let result:*mut u32=unsafe{(&mut matched) as *mut u32};
"""
        self.execute(self.compile(name, source + pairs + fixture + body + "}"))

    def test_native_prelink_interface_accepts_exact_scalar_signature(self):
        self.interface("sv868_exact", """if !target_interface_valid(names,12,imported,parameters,2)
 || !target_interface_valid(names,12,exported,parameters,2)
 || !target_interface_compatible(names,12,imported,exported,parameters,2)
 || !target_interface_bind_manifest(names,12,imports,1,exports,1,parameters,2,result,1)
 || matched!=0{return 1;}return 42;""")

    def test_native_prelink_accepts_effect_and_authority_narrowing(self):
        self.interface("sv868_narrow", """if !target_interface_compatible(
 names,12,imported,exported,parameters,2){return 1;}
exported.effects=0;exported.required_capabilities=0;
if !target_interface_compatible(
 names,12,imported,exported,parameters,2){return 2;}
return 42;""")

    def test_native_prelink_rejects_effect_escalation_preserving_output(self):
        self.interface("sv868_effect", """exported.effects=4;
if target_interface_compatible(names,12,imported,exported,parameters,2)
 || target_interface_bind_manifest(names,12,imports,1,exports,1,
 parameters,2,result,1) || matched!=99{return 1;}return 42;""")

    def test_native_prelink_rejects_capability_escalation_preserving_output(self):
        self.interface("sv868_capability", """exported.required_capabilities=8;
if target_interface_compatible(names,12,imported,exported,parameters,2)
 || target_interface_resolve(names,12,imported,exports,1,
 parameters,2,result) || matched!=99{return 1;}return 42;""")

    def test_native_prelink_rejects_ownership_role_mismatch(self):
        self.interface("sv868_role", """parameter_pair.second.role=1;
if target_interface_compatible(names,12,imported,exported,parameters,2)
 || target_interface_bind_manifest(names,12,imports,1,exports,1,
 parameters,2,result,1) || matched!=99{return 1;}return 42;""")

    def test_native_prelink_accepts_exact_sole_direct_and_whisper_roles(self):
        self.interface("sv868_roles", """let mut role:u32=1;
while role<=3{
 parameter_pair.first.role=role;parameter_pair.second.role=role;
 if !target_interface_compatible(names,12,imported,exported,parameters,2){
 return 1;}role=role+1;}
return 42;""")

    def test_native_prelink_rejects_parameter_type_mismatch(self):
        self.interface("sv868_type", """parameter_pair.second.type_tag=TargetTypeTag::U64;
if target_interface_compatible(names,12,imported,exported,parameters,2)
 || target_interface_bind_manifest(names,12,imports,1,exports,1,
 parameters,2,result,1) || matched!=99{return 1;}return 42;""")

    def test_native_prelink_rejects_return_abi_mismatch(self):
        self.interface("sv868_return", """exported.return_type=TargetTypeTag::I32;
if target_interface_compatible(names,12,imported,exported,parameters,2)
 || target_interface_resolve(names,12,imported,exports,1,
 parameters,2,result) || matched!=99{return 1;}return 42;""")

    def test_native_prelink_rejects_parameter_arity_mismatch(self):
        self.interface("sv868_arity", """exported.parameter_count=0;
if target_interface_compatible(names,12,imported,exported,parameters,2)
 || target_interface_bind_manifest(names,12,imports,1,exports,1,
 parameters,2,result,1) || matched!=99{return 1;}return 42;""")

    def test_native_prelink_rejects_aggregate_abi_and_illegal_roles(self):
        self.interface("sv868_invalid_shape", """exported.return_type=TargetTypeTag::Aggregate;
if target_interface_valid(names,12,exported,parameters,2){return 1;}
exported.return_type=TargetTypeTag::U32;
parameter_pair.second.type_tag=TargetTypeTag::Aggregate;
if target_interface_valid(names,12,exported,parameters,2){return 2;}
parameter_pair.second.type_tag=TargetTypeTag::U32;
parameter_pair.second.role=4;
if target_interface_valid(names,12,exported,parameters,2){return 3;}
return 42;""")

    def test_native_prelink_rejects_bad_parameter_range_and_flags(self):
        self.interface("sv868_bad_range", """exported.first_parameter=2;
if target_interface_valid(names,12,exported,parameters,2){return 1;}
exported.first_parameter=1;exported.parameter_count=25;
if target_interface_valid(names,12,exported,parameters,2){return 2;}
exported.parameter_count=1;exported.flags=3;
if target_interface_valid(names,12,exported,parameters,2){return 3;}
return 42;""")

    def test_native_prelink_rejects_empty_outside_source_names(self):
        self.interface("sv868_names", """exported.name.length=0;
if target_interface_valid(names,12,exported,parameters,2){return 1;}
exported.name.length=3;exported.name.offset=11;
if target_interface_valid(names,12,exported,parameters,2){return 2;}
exported.name.offset=6;
if target_interface_compatible(names,12,imported,exported,parameters,2){return 3;}
return 42;""")

    def test_native_prelink_missing_symbol_does_not_publish_binding(self):
        self.interface("sv868_missing", """exported.name.offset=6;
if target_interface_resolve(names,12,imported,exports,1,
 parameters,2,result) || matched!=99{return 1;}
if target_interface_bind_manifest(names,12,imports,1,exports,1,
 parameters,2,result,1) || matched!=99{return 2;}return 42;""")

    def test_native_prelink_rejects_duplicate_export_symbol_spellings(self):
        self.interface("sv868_duplicate_exports", """let mut records:InterfacePair=
 InterfacePair{first:exported,second:exported};
let raw:*mut InterfacePair=unsafe{(&mut records) as *mut InterfacePair};
let entries:*const TargetInterface=unsafe{
 (raw as usize) as *const TargetInterface};
if target_interfaces_unique(names,12,entries,2,parameters,2,
 TARGET_INTERFACE_EXPORT)
 || target_interface_bind_manifest(names,12,imports,1,entries,2,
 parameters,2,result,1) || matched!=99{return 1;}
return 42;""")

    def test_native_prelink_rejects_duplicate_import_names_without_output_write(self):
        self.interface("sv868_duplicate_imports", """let mut records:InterfacePair=
 InterfacePair{first:imported,second:imported};
let raw:*mut InterfacePair=unsafe{(&mut records) as *mut InterfacePair};
let entries:*const TargetInterface=unsafe{
 (raw as usize) as *const TargetInterface};
if target_interfaces_unique(names,12,entries,2,parameters,2,
 TARGET_INTERFACE_IMPORT)
 || target_interface_bind_manifest(names,12,entries,2,exports,1,
 parameters,2,result,2) || matched!=99{return 1;}
return 42;""")

    def test_native_prelink_rejects_output_capacity_before_publishing(self):
        self.interface("sv868_small_output", """if target_interface_bind_manifest(
 names,12,imports,1,exports,1,parameters,2,result,0)
 || matched!=99{return 1;}return 42;""")

    def test_native_prelink_empty_imports_accepts_no_output_buffer(self):
        self.interface("sv868_no_imports", """if !target_interface_bind_manifest(
 names,12,null,0,exports,1,parameters,2,null,0){return 1;}
return 42;""")

    def test_native_prelink_two_imports_bind_transactionally_in_order(self):
        self.interface("sv868_two", """let mut pair_i:InterfacePair=
 InterfacePair{first:imported,second:imported};
pair_i.second.name=TargetSourceSlice{offset:6,length:3};
let mut pair_e:InterfacePair=
 InterfacePair{first:exported,second:exported};
pair_e.second.name=TargetSourceSlice{offset:9,length:3};
let raw_i:*mut InterfacePair=unsafe{(&mut pair_i) as *mut InterfacePair};
let raw_e:*mut InterfacePair=unsafe{(&mut pair_e) as *mut InterfacePair};
let in_ptr:*const TargetInterface=unsafe{
 (raw_i as usize) as *const TargetInterface};
let ex_ptr:*const TargetInterface=unsafe{
 (raw_e as usize) as *const TargetInterface};
let mut mappings:[u32;2]=[99;2];
let out_ptr:*mut u32=unsafe{mappings as *mut u32};
if !target_interface_bind_manifest(names,12,in_ptr,2,ex_ptr,2,
 parameters,2,out_ptr,2) || mappings[0]!=0 || mappings[1]!=1{return 1;}
return 42;""")

    def test_native_prelink_second_import_failure_leaves_all_indices_unmodified(self):
        self.interface("sv868_atomic", """let mut pair_i:InterfacePair=
 InterfacePair{first:imported,second:imported};
pair_i.second.name=TargetSourceSlice{offset:6,length:3};
let mut pair_e:InterfacePair=
 InterfacePair{first:exported,second:exported};
pair_e.second.name=TargetSourceSlice{offset:9,length:3};
pair_e.second.required_capabilities=8;
let raw_i:*mut InterfacePair=unsafe{(&mut pair_i) as *mut InterfacePair};
let raw_e:*mut InterfacePair=unsafe{(&mut pair_e) as *mut InterfacePair};
let in_ptr:*const TargetInterface=unsafe{
 (raw_i as usize) as *const TargetInterface};
let ex_ptr:*const TargetInterface=unsafe{
 (raw_e as usize) as *const TargetInterface};
let mut mappings:[u32;2]=[77,88];
let out_ptr:*mut u32=unsafe{mappings as *mut u32};
if target_interface_bind_manifest(names,12,in_ptr,2,ex_ptr,2,
 parameters,2,out_ptr,2) || mappings[0]!=77 || mappings[1]!=88{return 1;}
return 42;""")

if __name__=="__main__": unittest.main()
