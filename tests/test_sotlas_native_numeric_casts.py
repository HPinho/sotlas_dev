"""Integer/float boundaries, native faults and defined C11 equivalence."""
import os
import signal
import subprocess
import unittest
import test_sotlas_native_i32 as integer


class NativeNumericCastTests(unittest.TestCase):
    setUpClass = classmethod(integer.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(integer.NativeI32Tests.tearDownClass.__func__)
    compile = integer.NativeI32Tests.compile
    link_image = integer.NativeI32Tests.link_image
    execute = integer.NativeI32Tests.execute
    windows_process_exit_code = integer.NativeI32Tests.windows_process_exit_code
    assert_c11_reference = integer.NativeI32Tests.assert_c11_reference

    def test_integer_float_conversions_across_widths_and_precisions(self):
        for typ in ('u8','u16','u32','u64','usize','i8','i16','i32','i64','isize'):
            for fp in ('f32','f64'):
                signed = typ.startswith('i')
                source = f'''fn encode(x:{typ})->{fp}{{return x as {fp};}}
fn decode(x:{fp})->{typ}{{return x as {typ};}}
pub fn main_entry()->u32{{let n:{typ}={-17 if signed else 42};let f:{fp}=encode(n);
if f!={"-17.0" if signed else "42.0"} || decode(f)!=n{{return 1;}}
if decode({"-17.9" if signed else "42.9"})!=n{{return 2;}}return 42;}}'''
                with self.subTest(typ=typ, fp=fp):
                    self.execute(self.compile(typ+'_'+fp,source))

    def test_fractional_lower_bounds_truncate_into_the_integer_range(self):
        for fp in ('f32','f64'):
            source = f'''fn byte(x:{fp})->i8{{return x as i8;}}
fn word(x:{fp})->i16{{return x as i16;}}
fn unsigned(x:{fp})->u64{{return x as u64;}}
pub fn main_entry()->u32{{let a:{fp}=-128.5;let b:{fp}=-32768.5;let c:{fp}=-0.75;
if byte(a)!=-128 || word(b)!=-32768 || unsigned(c)!=0{{return 1;}}
let negative:{fp}=-0.0;if unsigned(negative)!=0{{return 2;}}return 42;}}'''
            self.execute(self.compile(fp+'_lower_fractions',source))
        self.execute(self.compile('i32_lower_fraction','''pub fn main_entry()->u32{
let x:f64=-2147483648.5;let n:i32=x as i32;if n==-2147483648{return 42;}return 1;}'''))

    def test_wide_unsigned_conversion_and_signed_minimum(self):
        for fp in ('f32','f64'):
            source = f'''pub fn main_entry()->u32{{let high:u64=9223372036854775808;
let next:u64=9223372036854775809;let top:u64=18446744073709551615;
let a:{fp}=high as {fp};let b:{fp}=next as {fp};let c:{fp}=top as {fp};
let restored:u64=a as u64;let minimum:i64=-9223372036854775808;
let m:{fp}=minimum as {fp};let back:i64=m as i64;
if a!=b || restored!=high || c!=a*2.0 || back!=minimum{{return 1;}}
let half:u64=4611686018427387904;let three:u64=13835058055282163712;
let d:{fp}=three as {fp};let e:{fp}=half as {fp};if d!=e*3.0 || (d as u64)!=three{{return 2;}}return 42;}}'''
            self.execute(self.compile(fp+'_wide',source))

    def test_direct_literal_casts_and_single_evaluation(self):
        self.execute(self.compile('literal_casts','''static mut calls:u32=0;
fn value()->f64{unsafe{calls=calls+1;}return 42.75;}
pub fn main_entry()->u32{let x:f64=42 as f64;let y:f32=-17 as f32;
let a:i32=42.9 as i32;let b:i32=-17.9 as i32;let result:u32=value() as u32;
if x!=42.0 || y!=-17.0 || a!=42 || b!=-17 || result!=42 || unsafe{calls}!=1{return 1;}return 42;}'''))

    def test_short_circuit_skips_invalid_casts(self):
        self.execute(self.compile('lazy_cast','''pub fn main_entry()->u32{
let zero:f64=0.0;let nan:f64=zero/zero;
let skipped:bool=false && (nan as i32)==1;
let accepted:bool=true || (nan as u64)==1;
if skipped || !accepted{return 1;}return 42;}'''))

    def test_defined_conversions_match_c11(self):
        source = '''fn encode(x:u64)->f64{return x as f64;}
fn decode(x:f64)->i32{return x as i32;}
pub fn main_entry()->u32{let high:u64=13835058055282163712;let f:f64=encode(high);
let half:u64=4611686018427387904;let g:f64=encode(half);
if f==g*3.0 && decode(-17.9)==-17 && decode(-2147483648.5)==-2147483648{return 42;}return 1;}'''
        obj=self.compile('conversion_reference',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_bool_and_pointer_numeric_casts_fail_before_output(self):
        for index,source in enumerate((
            'pub fn f(x:bool)->f64{return x as f64;}',
            'pub fn f(x:*const u8)->f64{return x as f64;}',
            'pub fn f(x:f64)->bool{return x as bool;}',
            'pub fn f(x:f64)->*const u8{return x as *const u8;}',
        )):
            self.compile('invalid_'+str(index),source,success=False)

    def test_nonfinite_and_out_of_range_values_trap(self):
        for fp in ('f32','f64'):
            cases=(('u8','-1.0'),('u8','256.0'),('i8','-129.0'),('i8','128.0'),
                   ('u16','65536.0'),('i16','-32769.0'),('i16','32768.0'),
                   ('u32','4294967296.0'),('i32','2147483648.0'),
                   ('u64','(18446744073709551615 as '+fp+')'),
                   ('i64','(9223372036854775807 as '+fp+')'),
                   ('u64','zero/zero'),('i64','1.0/zero'),('i32','-1.0/zero'))
            for index,(typ,expression) in enumerate(cases):
                source=f'''pub fn main_entry()->u32{{let zero:{fp}=0.0;let x:{fp}={expression};
let result:{typ}=x as {typ};return result as u32;}}'''
                with self.subTest(fp=fp,typ=typ,expression=expression):
                    output=self.link_image(self.compile(fp+'_trap_'+str(index),source))
                    if os.name=='nt':
                        status,error=self.windows_process_exit_code(output)
                        self.assertEqual(status,0xc000001d,error)
                    else:
                        import resource
                        result=subprocess.run([str(output)],capture_output=True,timeout=15,
                            preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
                        self.assertEqual(result.returncode,-signal.SIGILL,result.stderr)


if __name__=='__main__':
    unittest.main()
