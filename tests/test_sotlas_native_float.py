"""Native IEEE scalar execution through the owned internal bit-pattern ABI."""
import unittest
import test_sotlas_native_i32 as integer


class NativeFloatTests(unittest.TestCase):
    setUpClass = classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile = integer.NativeI32Tests.compile
    link_image = integer.NativeI32Tests.link_image
    execute = integer.NativeI32Tests.execute
    assert_c11_reference = integer.NativeI32Tests.assert_c11_reference

    def test_float_return_functions_cannot_be_linked_as_process_entries(self):
        import subprocess
        for typ in ("f32", "f64"):
            obj = self.compile(typ + "_entry", f'pub fn value()->{typ}{{return 1.0;}}')
            for mode in ("--link-exe", "--link-pe", "--link-macho"):
                output = obj.with_suffix("." + mode[2:])
                result = subprocess.run([str(self.producer), mode, str(obj), str(output), "value"], capture_output=True, timeout=60)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertFalse(output.exists())

    def test_more_than_512_data_relocations_execute_and_exhaustion_fails_closed(self):
        for functions, success in ((9, True), (65, False)):
            terms = "+".join("(unsafe{data[0]} as u32)" for _ in range(64))
            declarations = ''.join(f'fn f{i}()->u32{{return {terms};}}' for i in range(functions))
            calls = ''.join(f'if f{i}()!=0{{return 1;}}' for i in range(functions))
            source = 'static mut data:[u8;1]=0;' + declarations + 'pub fn main_entry()->u32{' + calls + 'return 42;}'
            with self.subTest(functions=functions):
                obj = self.compile(f"relocations_{functions}", source, success=success)
                if success:
                    self.execute(obj)

    def test_generated_name_arena_exhaustion_does_not_write_or_advance(self):
        source = '''import sotlas::compiler::backend::lower_scalar::*;
import sotlas::compiler::backend::target_ir::*;
static mut arena:[u8;4194304]=0;
pub fn main_entry()->u32{
let text:*const u8=unsafe{arena as *const u8};
let mut lowering:ScalarLowering=ScalarLowering::new(null,0,text,4,
null,0,null,0,null,0,null,0,null,0,null,0,null,0,null,0);
unsafe{arena[4194303]=9;g_extended_len=4194303;}
let name:TargetSourceSlice=lowering.append_mangled_name(0,1,2,1);
let symbol:TargetSourceSlice=lowering.append_synthetic_str_symbol(0);
if name.length!=0 || symbol.length!=0 || unsafe{g_extended_len}!=4194303{return 1;}
if unsafe{arena[4194303]}!=9{return 2;}return 42;}'''
        self.execute(self.compile("suffix_exhaustion", source))

    def test_arithmetic_comparisons_negation_and_mixed_register_stack_calls(self):
        for typ in ("f32", "f64"):
            source = f'''fn calc(a:{typ},b:{typ})->{typ}{{return (a+b)*b-a/b;}}
fn many(a:{typ},b:u64,c:{typ},d:{typ},e:u32,f:{typ},g:{typ},h:{typ})->{typ}{{return a+c+d+f+g+h;}}
pub fn main_entry()->u32{{let x:{typ}=calc(4.0,2.0);let neg:{typ}=-x;
if x!=10.0 || neg!=-10.0 || x<10.0 || x>10.0 || !(x<=10.0) || !(x>=10.0){{return 1;}}
if many(1.0,9,2.0,3.0,7,4.0,5.0,6.0)!=21.0{{return 2;}}return 42;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ + "_arithmetic", source))

    def test_decimal_rounding_is_to_nearest_even_at_the_declared_precision(self):
        cases = (("f32", "16777217.0", "16777216.0", "16777219.0", "16777220.0"),
                 ("f64", "9007199254740993.0", "9007199254740992.0", "9007199254740995.0", "9007199254740996.0"))
        for typ, a, rounded_a, b, rounded_b in cases:
            source = f'''pub fn main_entry()->u32{{let a:{typ}={a};let b:{typ}={b};
let fraction:{typ}=0.1;let underscored:{typ}=1_024.125;
if a!={rounded_a} || b!={rounded_b} || fraction!=0.1 || underscored!=1024.125{{return 1;}}return 42;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ + "_rounding", source))

    def test_decimal_literals_encode_independent_ieee_bit_patterns(self):
        import struct
        cases = (("f32", "0.1", 0x3dcccccd), ("f64", "0.1", 0x3fb999999999999a),
                 ("f32", "0.499999985098838806", 0x3effffff))
        for typ, literal, bits in cases:
            with self.subTest(typ=typ, literal=literal):
                obj = self.compile(typ + "_literal_bits_" + str(bits),
                    f'pub fn value()->{typ}{{return {literal};}}pub fn main_entry()->u32{{return 42;}}')
                data = obj.read_bytes()
                section_headers = struct.unpack_from("<Q", data, 40)[0]
                stride = struct.unpack_from("<H", data, 58)[0]
                text_offset, text_size = struct.unpack_from("<QQ", data, section_headers + stride + 24)
                text = data[text_offset:text_offset + text_size]
                constant = (b"\x48\xb8" + struct.pack("<Q", bits)) if typ == "f64" else (b"\xb8" + struct.pack("<I", bits))
                self.assertIn(constant, text)
        # This decimal is below a single-precision midpoint. Parsing through a
        # rounded host double first can incorrectly round it to 0.5f.
        self.execute(self.compile("direct_f32_rounding", '''pub fn main_entry()->u32{
let a:f32=0.499999985098838806;let previous:f32=0.499999970197677612;
if a==previous && a!=0.5{return 42;}return 1;}'''))

    def test_ieee_nan_infinity_negative_zero_and_ordered_predicates(self):
        for typ in ("f32", "f64"):
            source = f'''pub fn main_entry()->u32{{let zero:{typ}=0.0;let negative:{typ}=-zero;
let nan:{typ}=zero/zero;let inf:{typ}=1.0/zero;let neginf:{typ}=1.0/negative;
if nan==nan || !(nan!=nan) || nan<zero || nan<=zero || nan>zero || nan>=zero{{return 1;}}
if zero!=negative || !(inf>zero) || !(neginf<zero) || inf==neginf{{return 2;}}
let inverse:{typ}=-neginf;if inverse!=inf{{return 3;}}return 42;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ + "_ieee", source))

    def test_float_mutable_loops_and_early_returns(self):
        for typ in ("f32", "f64"):
            source = f'''fn accumulate(limit:{typ})->{typ}{{let mut x:{typ}=0.0;
let mut result:{typ}=0.0;while x<limit{{x=x+0.5;if x==1.0{{continue;}}
if x>3.0{{break;}}result=result+x;}}return result;}}
pub fn main_entry()->u32{{if accumulate(10.0)==9.5{{return 42;}}return 1;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ + "_loops", source))

    def test_defined_float_workload_matches_c11(self):
        source = '''fn calc(a:f64,b:f64)->f64{return (a+b)*b-a/b;}
pub fn main_entry()->u32{let x:f64=calc(4.0,2.0);if x==10.0{return 42;}return 1;}'''
        obj = self.compile("float_reference", source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_float_memory_arrays_fields_pointer_stride_and_precision_casts(self):
        for typ in ("f32", "f64"):
            source = f'''pub struct Record{{pub head:u8;pub value:{typ};pub tail:u8;}}
static mut data:[{typ};2]=0;static mut total:{typ}=0.0;
pub fn main_entry()->u32{{let record:Record=Record{{head:7,value:1.5,tail:9}};
let mut small:[{typ};2]=0;let mut large:[{typ};20]=0;
unsafe{{small[0]=1.5;small[1]=2.5;data[0]=1.5;data[1]=2.5;large[19]=4.0;total=4.0;}}
let p:*const {typ}=unsafe{{data as *const {typ}}};let a:{typ}=unsafe{{*p}};let b:{typ}=unsafe{{*(p+1)}};
let wide:f64=record.value as f64;let narrow:f32=wide as f32;
if record.head!=7 || record.tail!=9 || wide!=1.5 || narrow!=1.5{{return 1;}}
if a+b!=4.0 || small[0]+small[1]!=4.0 || large[0]!=0.0 || large[19]!=4.0 || unsafe{{total}}!=4.0{{return 2;}}return 42;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ + "_memory", source))

    def test_unsupported_float_forms_fail_before_output(self):
        for index, source in enumerate((
            'pub fn f(a:f32,b:f64)->f64{return a+b;}',
            'pub fn f(a:f64,b:f64)->f64{return a%b;}',
            'pub fn f(a:f64)->f64{return a<<1.0;}',
            'pub fn f(a:f64)->f64{return ~a;}',
            'pub fn f()->f64{return 1000000000000000000.0;}',
            'pub fn f()->f64{return 0.0000000000000000001;}',
            'static mut x:f64=true;pub fn main_entry()->u32{return 42;}',
            'static mut x:[f64;2]=1;pub fn main_entry()->u32{return 42;}',
            'fn external_float(x:f64)->f64;pub fn main_entry()->u32{return 42;}',
            'fn external_return()->f64;pub fn main_entry()->u32{return 42;}',
        )):
            with self.subTest(index=index):
                self.compile(f"float_invalid_{index}", source, success=False)


if __name__ == "__main__":
    unittest.main()
