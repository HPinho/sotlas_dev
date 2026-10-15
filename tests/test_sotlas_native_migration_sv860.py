"""SV8.60: native numeric syntax, match edges, managed slots and binary I/O."""
from pathlib import Path
import unittest
import test_sotlas_native_migration_sv856 as previous

ROOT = Path(__file__).resolve().parents[1]


class NativeMigrationSV860Tests(unittest.TestCase):
    setUpClass = classmethod(previous.NativeMigrationSV856Tests.setUpClass.__func__)
    tearDownClass = classmethod(previous.NativeMigrationSV856Tests.tearDownClass.__func__)
    compile = previous.NativeMigrationSV856Tests.compile
    execute = previous.NativeMigrationSV856Tests.execute
    link_image = previous.NativeMigrationSV856Tests.link_image
    runtime = previous.NativeMigrationSV856Tests.runtime
    def ir(self, name, body):
        text=(ROOT/'bootstrap/sotlas/native_compiler/backend/target_ir.sotlas').read_text(encoding='utf-8').split(';',1)[1]
        pairs='struct FunctionPair{pub first:TargetFunction;pub second:TargetFunction;}struct ParameterPair{pub first:TargetParameter;pub second:TargetParameter;}'
        self.execute(self.compile(name,text+pairs+'pub fn main_entry()->u32{'+body+'}'))

    def test_frontend_f32_positive_exponent_separators_execute(self):
        self.execute(self.compile('f32_exponent_separator', 'pub fn main_entry()->u32{let value:f32=4.2e+0_1;if value==42.0{return 42;}return 1;}'))

    def test_frontend_f64_negative_exponent_separators_execute(self):
        self.execute(self.compile('f64_exponent_separator', 'pub fn main_entry()->u32{let value:f64=420.0e-0_1;if value==42.0{return 42;}return 1;}'))

    def test_frontend_float_module_constants_accept_exponent_separators(self):
        self.execute(self.compile('const_exponent_separator', 'const VALUE:f64=42e0_0;pub fn main_entry()->u32{if VALUE==42.0{return 42;}return 1;}'))

    def test_frontend_malformed_exponent_separators_and_out_of_profile_values_fail(self):
        for index, literal in enumerate(('1e_1', '1e1_', '1e1__0', '1e+_1', '1e1_9')):
            with self.subTest(literal=literal):
                self.compile('bad_exponent_separator_'+str(index), 'fn bad()->f64{return '+literal+';}', success=False)

    def match_edges(self, name, arms):
        prefix = 'struct Token{pub value:u32;}fn consume(v:sole Token)->void{return;}pub fn main_entry()->u32{let owner:sole Token=Token{value:42};let mut count:u32=0;while count<3{count=count+1;'
        self.execute(self.compile(name, prefix+'match count{'+arms+'}}return owner.value;}'))
        moved_arms = arms.replace('let seen:u32=owner.value;', 'let seen:u32=count;')
        self.compile(name+'_moved', prefix+'consume(owner);match count{'+moved_arms+'}}return 42;}', success=False)

    def test_ownership_match_then_break_preserves_fallthrough(self):
        self.match_edges('match_then_break', '2=>{break;},_=>{let seen:u32=owner.value;}')

    def test_ownership_match_else_break_preserves_live_arm(self):
        self.match_edges('match_else_break', '1=>{let seen:u32=owner.value;},_=>{break;}')

    def test_ownership_match_then_continue_preserves_loop_entry(self):
        self.match_edges('match_then_continue', '1=>{continue;},_=>{let seen:u32=owner.value;}')

    def test_ownership_match_else_continue_preserves_live_arm(self):
        self.match_edges('match_else_continue', '2=>{let seen:u32=owner.value;},_=>{continue;}')

    def slots(self, name, body):
        self.runtime(name, '''let mut bytes:[u8;2]=[20,22];let mut header:NativeRefHeader=native_ref_init();
let hp:*mut NativeRefHeader=unsafe{(&mut header) as *mut NativeRefHeader};
let raw:*mut u8=unsafe{bytes as *mut u8};let mut source:NativeManagedBytes=native_managed_bytes_open(hp,raw,2);
let p:*mut NativeManagedBytes=unsafe{(&mut source) as *mut NativeManagedBytes};
let mut destination:NativeManagedBytes=NativeManagedBytes{control:null,bytes:null,length:0,generation:0};
let q:*mut NativeManagedBytes=unsafe{(&mut destination) as *mut NativeManagedBytes};
'''+body)

    def test_memory_managed_clone_creates_an_independently_closed_strong_slot(self):
        self.slots('managed_clone', '''if !native_managed_bytes_clone_into(p,q) || header.strong!=2{return 1;}
if native_managed_bytes_clone_into(p,q) || header.strong!=2{return 2;}
native_managed_bytes_close(p);if bytes[0]!=20 || header.strong!=1{return 3;}
native_managed_bytes_close(q);if bytes[0]!=0 || bytes[1]!=0 || header.live{return 4;}return 42;''')

    def test_memory_managed_weak_upgrade_publishes_only_a_matching_strong_slot(self):
        self.slots('managed_upgrade_into', '''let mut weak:NativeWeakToken=native_managed_bytes_weak(p);weak.generation=weak.generation+1;
if native_managed_bytes_upgrade_into(p,weak,q) || header.strong!=1 || !native_managed_bytes_empty(q){return 1;}
weak=native_managed_bytes_weak(p);if !native_managed_bytes_upgrade_into(p,weak,q) || header.strong!=2{return 2;}
native_managed_bytes_close(p);native_managed_bytes_close(q);if header.live || bytes[0]!=0{return 3;}return 42;''')

    def test_memory_managed_take_poisoned_source_does_not_change_reference_count(self):
        self.slots('managed_take', '''if !native_managed_bytes_take(p,q) || !native_managed_bytes_empty(p) || header.strong!=1{return 1;}
if native_managed_bytes_take(p,q){return 2;}native_managed_bytes_close(p);
if header.strong!=1 || bytes[0]!=20{return 3;}native_managed_bytes_close(q);if header.live || bytes[1]!=0{return 4;}return 42;''')

    def test_memory_managed_swap_preserves_claims_and_rejects_invalid_slots(self):
        self.slots('managed_swap', '''if !native_managed_bytes_swap(p,q) || !native_managed_bytes_empty(p) || header.strong!=1{return 1;}
if !native_managed_bytes_swap(q,q) || native_managed_bytes_swap(q,null){return 2;}
native_managed_bytes_close(q);if header.live || bytes[0]!=0{return 3;}return 42;''')

    def narrow(self, name, typ, valid, invalid):
        self.runtime(name, 'let mut value:'+typ+'=7;let out:*mut '+typ+'=unsafe{(&mut value) as *mut '+typ+'};if !native_contract_'+typ+'('+valid+',out) || value!=42{return 1;}if native_contract_'+typ+'('+invalid+',out) || value!=42{return 2;}return 42;')

    def test_contract_u8_narrowing_rejects_overflow_before_output(self): self.narrow('narrow_u8', 'u8', '42', '256')
    def test_contract_u16_narrowing_rejects_overflow_before_output(self): self.narrow('narrow_u16', 'u16', '42', '65536')
    def test_contract_u32_narrowing_rejects_overflow_before_output(self): self.narrow('narrow_u32', 'u32', '42', '4294967296')
    def test_contract_i32_narrowing_rejects_out_of_range_before_output(self): self.narrow('narrow_i32', 'i32', '42', '-2147483649')

    def partition(self, name, field):
        self.ir(name, '''let mut first:TargetFunction=TargetFunction::empty();let mut second:TargetFunction=TargetFunction::empty();
'''+field+'''
let mut pair:FunctionPair=FunctionPair{first:first,second:second};
let raw:*mut FunctionPair=unsafe{(&mut pair) as *mut FunctionPair};let address:usize=unsafe{raw as usize};let p:*const TargetFunction=unsafe{address as *const TargetFunction};
if target_function_partitions_valid(2,p){return 1;}return 42;''')

    def test_ir_functions_cannot_share_parameter_rows(self):
        self.partition('parameter_partitions', 'first.parameter_count=1;second.parameter_count=1;')

    def test_ir_functions_cannot_share_block_rows(self):
        self.partition('block_partitions', 'first.block_count=1;second.block_count=1;')

    def test_ir_duplicate_function_spellings_are_rejected(self):
        self.ir('duplicate_function_names', '''let mut first:TargetFunction=TargetFunction::empty();let mut second:TargetFunction=TargetFunction::empty();
first.name=TargetSourceSlice{offset:0,length:1};second.name=TargetSourceSlice{offset:1,length:1};
let mut pair:FunctionPair=FunctionPair{first:first,second:second};
let raw:*mut FunctionPair=unsafe{(&mut pair) as *mut FunctionPair};let address:usize=unsafe{raw as usize};let p:*const TargetFunction=unsafe{address as *const TargetFunction};
if target_function_names_unique("aa",2,2,p){return 1;}return 42;''')

    def test_ir_duplicate_parameter_spellings_are_rejected_within_a_function(self):
        self.ir('duplicate_parameter_names', '''let mut pair:ParameterPair=ParameterPair{first:TargetParameter{value_id:1,type_tag:TargetTypeTag::U32,name:TargetSourceSlice{offset:0,length:1}},second:TargetParameter{value_id:2,type_tag:TargetTypeTag::U32,name:TargetSourceSlice{offset:1,length:1}}};
let raw:*mut ParameterPair=unsafe{(&mut pair) as *mut ParameterPair};let address:usize=unsafe{raw as usize};let p:*const TargetParameter=unsafe{address as *const TargetParameter};
if target_parameter_names_unique("aa",2,2,p){return 1;}return 42;''')

    def binary(self, name, body):
        source = (ROOT/'runtime/native/binary.sotlas').read_text(encoding='utf-8').split(';', 1)[1]
        self.execute(self.compile(name, source+'\npub fn main_entry()->u32{'+body+'}'))

    def test_backend_unaligned_little_endian_load_checks_the_full_extent(self):
        self.binary('binary_load_le', '''let bytes:[u8;4]=[99,42,1,99];let p:*const u8=unsafe{bytes as *const u8};let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_binary_load_le(p,4,1,2,out) || value!=298{return 1;}if native_binary_load_le(p,4,3,2,out) || value!=298{return 2;}return 42;''')

    def test_backend_unaligned_big_endian_load_has_no_host_endian_dependency(self):
        self.binary('binary_load_be', '''let bytes:[u8;4]=[99,1,42,99];let p:*const u8=unsafe{bytes as *const u8};let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_binary_load_be(p,4,1,2,out) || value!=298{return 1;}if native_binary_load_be(p,4,0,3,out) || value!=298{return 2;}return 42;''')

    def test_backend_little_endian_store_rejects_truncation_before_writing(self):
        self.binary('binary_store_le', '''let mut bytes:[u8;4]=[99;4];let p:*mut u8=unsafe{bytes as *mut u8};
if !native_binary_store_le(p,4,1,2,298) || bytes[1]!=42 || bytes[2]!=1{return 1;}
if native_binary_store_le(p,4,1,1,298) || bytes[1]!=42 || bytes[0]!=99 || bytes[3]!=99{return 2;}return 42;''')

    def test_backend_big_endian_store_roundtrips_full_width_values(self):
        self.binary('binary_store_be', '''let mut bytes:[u8;10]=[99;10];let p:*mut u8=unsafe{bytes as *mut u8};let mut value:u64=0;let out:*mut u64=unsafe{(&mut value) as *mut u64};
if !native_binary_store_be(p,10,1,8,18446744073709551615) || !native_binary_load_be(p,10,1,8,out) || value!=18446744073709551615{return 1;}
if native_binary_store_be(p,10,3,8,42) || bytes[0]!=99 || bytes[9]!=99{return 2;}return 42;''')


if __name__ == '__main__': unittest.main()
