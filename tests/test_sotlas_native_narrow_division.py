"""Native unsigned byte/word division, expression widths and machine faults."""
import os
import signal
import subprocess
import unittest
import test_sotlas_native_i32 as harness


class NativeNarrowDivisionTests(unittest.TestCase):
    setUpClass = classmethod(harness.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(harness.NativeI32Tests.tearDownClass.__func__)
    compile = harness.NativeI32Tests.compile
    link_image = harness.NativeI32Tests.link_image
    execute = harness.NativeI32Tests.execute
    windows_process_exit_code = harness.NativeI32Tests.windows_process_exit_code

    def test_all_u8_operands_match_wide_reference_and_division_identity(self):
        source = '''fn quotient(a:u8,b:u8)->u8{return a/b;}
fn remainder(a:u8,b:u8)->u8{return a%b;}
pub fn main_entry()->u32{let mut a:u32=0;while a<256{let mut b:u32=1;while b<256{
let x:u8=a as u8;let y:u8=b as u8;
let q:u32=quotient(x,y) as u32;let r:u32=remainder(x,y) as u32;
if q!=a/b || r!=a%b || q*b+r!=a || r>=b{return 1;}b+=1;}a+=1;}return 42;}'''
        self.execute(self.compile('narrow_div_u8_exhaustive', source))

    def test_u16_boundary_pairs_preserve_unsigned_width(self):
        source = '''pub fn main_entry()->u32{
let values:[u16;9]=[0,1,2,255,256,32767,32768,65534,65535];
let divisors:[u16;8]=[1,2,3,255,256,32767,32768,65535];
let mut i:u32=0;while i<9{let mut j:u32=0;while j<8{
let a:u16=values[i];let b:u16=divisors[j];let wide_a:u32=a as u32;let wide_b:u32=b as u32;
let q:u32=(a/b) as u32;let r:u32=(a%b) as u32;
if q!=wide_a/wide_b || r!=wide_a%wide_b || q*wide_b+r!=wide_a{return 1;}j+=1;}i+=1;}return 42;}'''
        self.execute(self.compile('narrow_div_u16_boundaries', source))

    def test_fields_indexed_places_and_single_evaluation(self):
        source = '''struct Values{pub byte:u8;pub word:u16;pub items:[u16;2];}
static mut trace:u32=0;
fn index()->u32{unsafe{trace=trace*10+1;}return 1;}
fn divisor()->u16{unsafe{trace=trace*10+2;}return 7;}
pub fn main_entry()->u32{let items:[u16;2]=[9,65535];
let mut values:Values=Values{byte:255,word:65535,items:items};
values.byte/=16;values.word%=256;values.items[index()]/=divisor();
if values.byte!=15 || values.word!=255 || values.items[1]!=9362 || unsafe{trace}!=12{return 1;}
let mut bytes:[u8;2]=[255,254];bytes[0]%=16;
let p:*mut u8=unsafe{bytes as *mut u8};unsafe{*(p+1)/=2;}
if bytes[0]!=15 || bytes[1]!=127{return 2;}return 42;}'''
        self.execute(self.compile('narrow_div_places', source))

    def test_nested_arithmetic_casts_calls_and_conditional_values(self):
        source = '''fn byte()->u8{return 255;}
fn word()->u16{return 65535;}
pub fn main_entry()->u32{let b:u8=byte();let w:u16=word();
let high:usize=(b/16) as usize;let low:usize=(b%16) as usize;
let quotient:f32=(w/256) as f32;let remainder:f64=(w%256) as f64;
let selected:u8=if high==15{byte()/17}else{byte()%2};
if high!=15 || low!=15 || quotient!=255.0 || remainder!=255.0 || selected!=15{return 1;}
let wrapped:u8=(b+1)/2;if wrapped!=0{return 2;}return 42;}'''
        self.execute(self.compile('narrow_div_expressions', source))

    def test_mixed_widths_boolean_divisors_and_readonly_places_are_rejected(self):
        cases = (
            'fn bad(a:u8,b:u16)->u8{return a/b;}',
            'fn bad(a:u16,b:u8)->u16{return a%b;}',
            'fn bad(a:u8,b:bool)->u8{return a/b;}',
            'fn bad(a:u8,b:i8)->u8{return a%b;}',
            'fn bad(p:*const u8)->void{unsafe{*p/=2;}return;}',
            'const VALUE:u8=255;fn bad()->u8{VALUE%=16;return VALUE;}',
            'fn bad(a:u8)->u8{return a/256;}',
            'fn bad(a:u16)->u16{return a%65536;}',
        )
        for index, source in enumerate(cases):
            with self.subTest(source=source):
                self.compile('narrow_div_invalid_' + str(index), source +
                             'pub fn main_entry()->u32{return 42;}', False)

    def test_module_constants_keep_the_declared_byte_and_word_types(self):
        source = '''const HIGH:u8=255/16;const LOW:u16=65535%4096;
pub fn main_entry()->u32{let byte:u8=HIGH;let word:u16=LOW;
if byte!=15 || word!=4095{return 1;}return 42;}'''
        self.execute(self.compile('narrow_div_constants', source))
        for index, declaration in enumerate(('const BAD:u8=255/0;', 'const BAD:u16=65535%0;')):
            self.compile('narrow_div_bad_const_' + str(index), declaration +
                         'pub fn main_entry()->u32{return 42;}', False)

    def test_dynamic_zero_divisors_trap_for_both_widths_and_operations(self):
        for typ in ('u8', 'u16'):
            for op in ('/', '%'):
                source = f'''fn calculate(a:{typ},b:{typ})->{typ}{{return a{op}b;}}
pub fn main_entry()->u32{{let result:{typ}=calculate(42,0);return result as u32;}}'''
                output = self.link_image(self.compile('narrow_div_zero_' + typ + ('q' if op=='/' else 'r'), source))
                if os.name == 'nt':
                    status, error = self.windows_process_exit_code(output)
                    self.assertEqual(status, 0xc0000094, error)
                else:
                    import resource
                    result = subprocess.run([str(output)], capture_output=True, timeout=15,
                        preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
                    self.assertEqual(result.returncode, -signal.SIGFPE, result.stderr)
