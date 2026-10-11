"""Native signed byte, word and wide-integer execution and fault contracts."""
import os
import signal
import subprocess
import unittest
import test_sotlas_native_i32 as signed32


class NativeSignedFamilyTests(unittest.TestCase):
    setUpClass = classmethod(signed32.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(signed32.NativeI32Tests.tearDownClass.__func__)
    compile = signed32.NativeI32Tests.compile
    link_image = signed32.NativeI32Tests.link_image
    execute = signed32.NativeI32Tests.execute
    windows_process_exit_code = signed32.NativeI32Tests.windows_process_exit_code
    assert_c11_reference = signed32.NativeI32Tests.assert_c11_reference

    def test_defined_signed_family_matches_c11_reference(self):
        source = '''fn tiny(a:i8,b:i8)->i8{return a/b+a%b;}
fn word(a:i16,b:i16)->i16{return a/b+a%b;}
fn wide(a:i64,b:i64)->i64{return a/b+a%b;}
pub fn main_entry()->u32{if tiny(-17,5)==-5 && word(-17,5)==-5 && wide(-17,5)==-5{return 42;}return 1;}'''
        obj=self.compile('family_reference',source)
        self.execute(obj)
        self.assert_c11_reference(obj)

    def test_narrow_signed_calls_comparisons_arithmetic_and_bitwise(self):
        for typ, minimum, maximum in (("i8", -128, 127), ("i16", -32768, 32767)):
            source = f'''fn calc(a:{typ},b:{typ})->{typ}{{return a*b+a;}}
fn neg(a:{typ})->{typ}{{return -a;}}
pub fn main_entry()->u32{{
let low:{typ}={minimum};let high:{typ}={maximum};let n:{typ}=-17;
let wrapped:{typ}=high+1;let bits:{typ}=n&15;
if low<0 && high>low && low<high && wrapped==low && calc(-3,2)==-9
    && neg(-42)==42 && neg(low)==low && bits==15{{return 42;}}return 1;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ+"_arithmetic", source))

    def test_signed_family_division_remainder_and_checked_shifts(self):
        for typ, width in (("i8",8),("i16",16),("i64",64)):
            source = f'''fn div(a:{typ},b:{typ})->{typ}{{return a/b;}}
fn rem(a:{typ},b:{typ})->{typ}{{return a%b;}}
fn shift(a:{typ})->{typ}{{return a>>2;}}
fn sign(a:{typ})->{typ}{{return a>>{width-1};}}
pub fn main_entry()->u32{{let n:{typ}=-17;let left:{typ}=n<<1;
if div(n,5)==-3 && rem(n,5)==-2 && div(17,-5)==-3 && rem(17,-5)==2
    && shift(n)==-5 && sign(n)==-1 && sign(17)==0 && left==-34{{return 42;}}return 1;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ+"_division", source))

    def test_narrow_signed_casts_and_register_stack_argument_canonicalization(self):
        for typ, unsigned, bits, minimum in (("i8","u8",255,-128),("i16","u16",65535,-32768)):
            narrowed_expected = 1 if typ == 'i8' else 257
            source = f'''fn sum(a:{typ},b:{typ},c:{typ},d:{typ},e:{typ},f:{typ},g:{typ},h:{typ})->{typ}{{return a+b+c+d+e+f+g+h;}}
pub fn main_entry()->u32{{let n:{typ}=-1;let wide:i64=n as i64;let raw:u64=n as u64;
let unsigned:{unsigned}=n as {unsigned};let again:{typ}=unsigned as {typ};
let bigger:i32=257;let narrowed:{typ}=bigger as {typ};
let low:{typ}={minimum};let low32:i32=low as i32;
if wide==-1 && raw==18446744073709551615 && unsigned=={bits} && again==-1
    && narrowed=={narrowed_expected} && low32=={minimum}
    && sum(-1,-2,-3,-4,-5,-6,-7,-8)==-36{{return 42;}}return 1;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ+"_casts", source))

    def test_signed_memory_widths_adjacent_fields_globals_arrays_and_pointer_stride(self):
        for typ in ("i8","i16","i64"):
            source = f'''pub struct Record{{pub head:u8;pub value:{typ};pub tail:u8;}}
static mut data:[{typ};2]=0;static mut count:{typ}=0;
pub fn main_entry()->u32{{let r:Record=Record{{head:7,value:-21,tail:9}};
let mut local:[{typ};2]=0;unsafe{{local[0]=-21;local[1]=63;data[0]=-21;data[1]=63;}}
let p:*const {typ}=unsafe{{data as *const {typ}}};let a:{typ}=unsafe{{*p}};let b:{typ}=unsafe{{*(p+1)}};
let mut i:{typ}=-2;while i<1{{unsafe{{count=count+14;}}i=i+1;}}
if r.head==7 && r.tail==9 && r.value==-21 && local[0]+local[1]==42
    && a+b==42 && unsafe{{count}}==42{{return 42;}}return 1;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ+"_memory", source))

    def test_signed_family_literal_shift_and_pointer_type_rejections(self):
        for typ, minimum, maximum, width in (("i8",-128,127,8),("i16",-32768,32767,16),("i64",-9223372036854775808,9223372036854775807,64)):
            cases = (
                f'pub fn f()->{typ}{{return {maximum+1};}}',
                f'pub fn f()->{typ}{{return {minimum-1};}}',
                f'pub fn f(x:{typ})->{typ}{{return x>>{width};}}',
                f'pub fn f(x:{typ},n:bool)->{typ}{{return x>>n;}}',
                f'pub fn f()->u32{{let values:[{typ};2]=0;let index:{typ}=-1;return values[index] as u32;}}',
                f'static mut data:[{typ};2]=0;pub fn f()->*const u32{{return unsafe{{data as *const u32}};}}',
            )
            for index, source in enumerate(cases):
                with self.subTest(typ=typ,index=index):
                    self.compile(f'{typ}_bad{index}', source, success=False)

    def test_signed_family_division_faults_use_declared_width(self):
        if os.name == 'nt':
            control=self.link_image(self.compile('family_control','pub fn main_entry()->u32{return 42;}'))
            status,error=self.windows_process_exit_code(control)
            self.assertEqual(status,42,error)
        for typ, minimum in (("i8",-128),("i16",-32768),("i64",-9223372036854775808)):
            for index, expression in enumerate(("17/0",f"{minimum}/-1",f"{minimum}%-1")):
                with self.subTest(typ=typ,index=index):
                    output=self.link_image(self.compile(f'{typ}_fault{index}',f'pub fn main_entry()->u32{{let n:{typ}={expression};return n as u32;}}'))
                    if os.name=='nt':
                        status,error=self.windows_process_exit_code(output)
                        self.assertEqual(status,0xc0000094 if index==0 else 0xc0000095,error)
                    else:
                        import resource
                        result=subprocess.run([str(output)],cwd=self.directory,capture_output=True,timeout=15,
                                              preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
                        self.assertEqual(result.returncode,-signal.SIGFPE,result.stderr)


if __name__ == '__main__':
    unittest.main()
