"""Owned-image bit operations, full-width shift guards and short circuit gates."""
import os
import signal
import subprocess
import unittest
from pathlib import Path

import test_sotlas_native_i32 as signed32

ROOT = Path(__file__).resolve().parents[1]
INTEGER_TYPES = (("u8", 8), ("u16", 16), ("u32", 32), ("u64", 64),
                 ("usize", 64), ("i8", 8), ("i16", 16), ("i32", 32), ("i64", 64), ("isize", 64))


class NativeBitOperationsTests(unittest.TestCase):
    setUpClass = classmethod(signed32.NativeI32Tests.setUpClass.__func__)
    tearDownClass = classmethod(signed32.NativeI32Tests.tearDownClass.__func__)
    compile = signed32.NativeI32Tests.compile
    link_image = signed32.NativeI32Tests.link_image
    execute = signed32.NativeI32Tests.execute
    windows_process_exit_code = signed32.NativeI32Tests.windows_process_exit_code
    assert_c11_reference = signed32.NativeI32Tests.assert_c11_reference

    def test_variable_shifts_and_complement_at_every_integer_width(self):
        for typ, width in INTEGER_TYPES:
            signed = typ.startswith("i")
            high = -(1 << (width - 1)) if signed else 1 << (width - 1)
            all_bits = -1 if signed else (1 << width) - 1
            source = f'''fn left(x:{typ},n:{typ})->{typ}{{return x<<n;}}
fn right(x:{typ},n:{typ})->{typ}{{return x>>n;}}
fn flip(x:{typ})->{typ}{{return ~x;}}
pub fn main_entry()->u32{{let one:{typ}=1;let high:{typ}={high};let bits:{typ}={all_bits};
if left(one,{width-1})!=high || left(one,0)!=1 || right(bits,0)!=bits{{return 1;}}
if right(high,{width-1})!={-1 if signed else 1} || right(bits,{width-1})!={-1 if signed else 1}{{return 2;}}
if flip(bits)!=0 || flip(0)!=bits || flip(flip(high))!=high{{return 3;}}return 42;}}'''
            with self.subTest(typ=typ):
                self.execute(self.compile(typ + "_bits", source))

    def test_count_calls_execute_once_and_mutable_cfg_counts_work(self):
        source = '''static mut calls:u32=0;
fn count()->u32{unsafe{calls=calls+1;}return 3;}
fn operand()->u32{unsafe{calls=calls+1;}return 7;}
pub fn main_entry()->u32{let a:u32=operand()<<count();let b:u32=~operand();
if a!=56 || b!=4294967288 || unsafe{calls}!=3{return 1;}
let mut n:u32=0;let mut sum:u32=0;while n<6{sum=sum+(1<<n);n=n+1;}
if sum!=63{return 2;}return 42;}'''
        self.execute(self.compile("count_once", source))

    def test_short_circuit_does_not_execute_invalid_dynamic_shifts(self):
        source = '''fn guard(x:u64,n:u64)->bool{return n<64 && (x>>n)==1;}
fn alternative(x:i32,n:i32)->bool{return n<0 || (x<<n)==2;}
pub fn main_entry()->u32{let x:u64=1;let bad:u64=64;
let skipped:bool=bad<64 && (x<<bad)==1;let taken:bool=bad>=64 || (x>>bad)==0;
if skipped || !taken || guard(1,64) || !guard(1,0){return 1;}
if !alternative(1,-1) || !alternative(1,1){return 2;}return 42;}'''
        self.execute(self.compile("short_circuit", source))

    def test_stack_argument_and_memory_counts_preserve_the_declared_width(self):
        source = '''pub struct Counts{pub byte:u8;pub wide:u64;}
static mut counts:[u64;2]=0;
fn stack(a:u64,b:u64,c:u64,d:u64,e:u64,f:u64,x:u64,n:u64)->u64{return x<<n;}
pub fn main_entry()->u32{let record:Counts=Counts{byte:7,wide:63};let byte:u8=1;
unsafe{counts[0]=record.wide;counts[1]=0;}
let p:*const u64=unsafe{counts as *const u64};let n:u64=unsafe{*p};
if (byte<<record.byte)!=128 || stack(0,0,0,0,0,0,1,n)!=9223372036854775808{return 1;}
let zero:u64=unsafe{*(p+1)};if (42>>zero)!=42{return 2;}return 42;}'''
        self.execute(self.compile("stored_counts", source))

    def test_computed_and_memory_counts_use_runtime_validation(self):
        sources = (
            '''fn shift(x:u64,n:u64)->u64{return x<<(n+1);}
pub fn main_entry()->u32{return shift(1,63) as u32;}''',
            '''static mut counts:[u64;1]=0;
pub fn main_entry()->u32{unsafe{counts[0]=4294967296;}
let p:*const u64=unsafe{counts as *const u64};let n:u64=unsafe{*p};return (1>>n) as u32;}''',
        )
        for index, source in enumerate(sources):
            with self.subTest(index=index):
                output = self.link_image(self.compile(f"computed_trap_{index}", source))
                self.assert_shift_trap(output)

    def test_invalid_constant_counts_and_noninteger_operands_fail_before_output(self):
        for typ, width in INTEGER_TYPES:
            cases = [f'pub fn f(x:{typ})->{typ}{{return x<<{width};}}',
                     f'pub fn f(x:{typ})->{typ}{{return x>>true;}}']
            if typ.startswith("i"):
                cases.append(f'pub fn f(x:{typ})->{typ}{{return x>>-1;}}')
            for index, source in enumerate(cases):
                with self.subTest(typ=typ, index=index):
                    self.compile(f"{typ}_invalid_{index}", source, success=False)
        for index, source in enumerate((
                'pub fn f(x:bool)->bool{return ~x;}',
                'pub fn f(x:*const u8)->*const u8{return ~x;}',
                'pub fn f(x:f64)->f64{return ~x;}')):
            self.compile(f"complement_invalid_{index}", source, success=False)

    def test_invalid_dynamic_counts_trap_before_hardware_masks_them(self):
        if os.name == "nt":
            control = self.link_image(self.compile("shift_control", "pub fn main_entry()->u32{return 42;}"))
            status, error = self.windows_process_exit_code(control)
            self.assertEqual(status, 42, error)
        for typ, width in INTEGER_TYPES:
            counts = [width, width + 1]
            if width == 64:
                counts.append(1 << 32)  # Its low dword is zero: ECX-only checks are insufficient.
            if typ.startswith("i"):
                counts.append(-1)
            for count in counts:
                for direction in ("<<", ">>"):
                    name = f"{typ}_trap_{count}_{'left' if direction == '<<' else 'right'}"
                    source = f'''fn shift(x:{typ},n:{typ})->{typ}{{return x{direction}n;}}
pub fn main_entry()->u32{{return shift(1,{count}) as u32;}}'''
                    with self.subTest(typ=typ, count=count, direction=direction):
                        output = self.link_image(self.compile(name, source))
                        self.assert_shift_trap(output)

    def assert_shift_trap(self, output):
        if os.name == "nt":
            status, error = self.windows_process_exit_code(output)
            self.assertEqual(status, 0xc000001d, error)
        else:
            import resource
            result = subprocess.run([str(output)], capture_output=True, timeout=15,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
            self.assertEqual(result.returncode, -signal.SIGILL, result.stderr)

    def test_crc32_rotation_and_byte_unpacking_match_c11(self):
        source = (ROOT / "examples/native_bit_operations.sotlas").read_text(encoding="utf-8").split("\n", 1)[1]
        obj = self.compile("bit_workload", source)
        self.execute(obj)
        self.assert_c11_reference(obj)


if __name__ == "__main__":
    unittest.main()
