"""Native signed 32-bit execution, memory, boundary and reference parity gates."""
from pathlib import Path
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeI32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-i32-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        script = "import sys;from pathlib import Path;from sotlas.bootstrap_pipeline import build_stage1_native_compiler;build_stage1_native_compiler(Path(sys.argv[1]),verbose=False)"
        built = subprocess.run([sys.executable, "-c", script, str(cls.producer)], cwd=ROOT,
                               env=environment, capture_output=True, timeout=180)
        if built.returncode:
            raise RuntimeError(built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compile(self, name, source, success=True):
        path = self.directory / (name + ".sotlas")
        path.write_text("module probe;\n" + source, encoding="utf-8")
        obj = path.with_suffix(".o")
        result = subprocess.run([str(self.producer), "--compile-obj", str(path), str(obj)], capture_output=True, timeout=60)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(obj.exists())
        return obj

    def link_image(self, obj):
        output = obj.with_suffix(".exe" if os.name == "nt" else ".bin")
        mode = "--link-pe" if os.name == "nt" else "--link-macho" if sys.platform == "darwin" else "--link-exe"
        linked = subprocess.run([str(self.producer), mode, str(obj), str(output), "main_entry"], capture_output=True, timeout=60)
        self.assertEqual(linked.returncode, 0, linked.stderr)
        return output

    def execute(self, obj, expected=42):
        if platform.machine().lower() not in ("amd64", "x86_64"):
            return
        output = self.link_image(obj)
        environment = {"PATH": str(self.directory / "no-host-tools")}
        if os.name == "nt":
            environment["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run([str(output)], env=environment, capture_output=True, timeout=15, **options)
        self.assertEqual(result.returncode, expected, result.stderr)

    def windows_process_exit_code(self, output):
        # Configure only the launcher, whose error mode is inherited by the
        # native child. Python never executes generated code through ctypes:
        # ctypes/libffi can translate an arithmetic trap to OSError or fail-fast
        # termination depending on the interpreter build.
        script = """
import ctypes
import json
import subprocess
import sys
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.SetErrorMode.argtypes = [ctypes.c_uint32]
kernel.SetErrorMode.restype = ctypes.c_uint32
kernel.SetErrorMode(0x0001 | 0x0002 | 0x8000)
result = subprocess.run([sys.argv[1]], capture_output=True, timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW)
print(json.dumps({'returncode': result.returncode,
                  'stderr': result.stderr.decode('utf-8', errors='replace')}))
"""
        result = subprocess.run([sys.executable, "-c", script, str(output)],
                                cwd=self.directory, capture_output=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        return report["returncode"] & 0xffffffff, report["stderr"]

    def test_arithmetic_calls_signed_comparisons_and_register_stack_arguments(self):
        cases = (
            ('fn value()->i32{return -21;}pub fn main_entry()->u32{let x:i32=value();if x<0 && x<=-21 && x!=21 && x>-22 && x>=-21{return (x+63) as u32;}return 1;}'),
            ('fn calc(a:i32,b:i32)->i32{return a*b-a+b;}pub fn main_entry()->u32{let n:i32=calc(-5,3);if n==-7{return 42;}return 1;}'),
            ('fn negate(x:i32)->i32{return -x;}pub fn main_entry()->u32{if negate(-42)==42 && negate(-2147483648)==-2147483648{return 42;}return 1;}'),
            ('pub fn main_entry()->u32{let x:i32=-1;let masked:i32=x&255;let joined:i32=x|0;let flipped:i32=x^255;if masked==255 && joined==-1 && flipped==-256{return 42;}return 1;}'),
            ('fn sum(a:i32,b:i32,c:i32,d:i32,e:i32,f:i32,g:i32,h:i32)->i32{return a+b+c+d+e+f+g+h;}pub fn main_entry()->u32{let n:i32=sum(-1,-2,-3,-4,-5,-6,-7,-8);if n==-36{return 42;}return 1;}'),
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.execute(self.compile(f"arith{index}", source))

    def test_signed_division_remainder_and_arithmetic_right_shift(self):
        cases = (
            ('fn div(a:i32,b:i32)->i32{return a/b;}fn rem(a:i32,b:i32)->i32{return a%b;}pub fn main_entry()->u32{if div(-17,5)==-3 && rem(-17,5)==-2 && div(17,-5)==-3 && rem(17,-5)==2{return 42;}return 1;}'),
            ('fn shift(a:i32)->i32{return a>>2;}pub fn main_entry()->u32{let x:i32=-17;let y:i32=x<<1;if shift(x)==-5 && y==-34{return 42;}return 1;}'),
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.execute(self.compile(f"div{index}", source))

    def test_sign_extension_narrowing_and_integer_boundaries(self):
        cases = (
            'fn low()->i32{return -2147483648;}fn high()->i32{return 2147483647;}pub fn main_entry()->u32{let lo:i32=low();let hi:i32=high();let wide:i64=lo as i64;let bits:u32=lo as u32;if wide==-2147483648 && hi==2147483647 && bits==2147483648{return 42;}return 1;}',
            'pub fn main_entry()->u32{let signed:i32=-1;let bits:u64=signed as u64;let byte:u8=signed as u8;let word:u16=signed as u16;let positive:u32=4294967295;let narrow:i32=positive as i32;if bits==18446744073709551615 && byte==255 && word==65535 && narrow==-1{return 42;}return 1;}',
            'pub fn main_entry()->u32{let wide:i64=-4294967297;let narrow:i32=wide as i32;let high:i32=2147483647;let wrapped:i32=high+1;if narrow==-1 && wrapped==-2147483648{return 42;}return 1;}',
            'pub fn main_entry()->u32{let source:u32=4294967295;let signed:i64=source as i64;let n:i32=-1;if signed==4294967295 && (n>>31)==-1{return 42;}return 1;}',
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.execute(self.compile(f"cast{index}", source))

    def test_struct_arrays_globals_pointer_stride_and_cfg_state(self):
        cases = (
            'pub struct Pair{pub left:i32;pub right:i32;}pub fn main_entry()->u32{let p:Pair=Pair{left:-21,right:63};return (p.left+p.right) as u32;}',
            'static mut data:[i32;2]=0;pub fn main_entry()->u32{unsafe{data[0]=-21;data[1]=63;}let p:*const i32=unsafe{data as *const i32};let sum:i32=unsafe{*p}+unsafe{*(p+1)};return sum as u32;}',
            'static mut total:i32=0;pub fn main_entry()->u32{let mut i:i32=-2;while i<1{unsafe{total=total+14;}i=i+1;}return unsafe{total} as u32;}',
            'pub fn main_entry()->u32{let mut data:[i32;2]=0;unsafe{data[0]=-21;data[1]=63;}let mut n:i32=-1;let mut sum:i32=0;while n<2{n=n+1;if n==0{continue;}if n==2{break;}sum=sum+data[0]+data[1];}return sum as u32;}',
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.execute(self.compile(f"memory{index}", source))

    def test_invalid_literals_shifts_indices_and_mixed_types_rejected(self):
        cases = (
            'pub fn main_entry()->i32{return 2147483648;}',
            'pub fn main_entry()->i32{return -2147483649;}',
            'pub fn main_entry()->i32{let x:i32=1;return x>>32;}',
            'pub fn shift(x:i32,y:i32)->i32{return x>>y;}pub fn main_entry()->u32{return 42;}',
            'pub fn main_entry()->i32{let x:i32=1;let y:u32=2;return x+y;}',
            'pub fn main_entry()->u32{let data:[i32;2]=0;let index:i32=-1;return data[index] as u32;}',
        )
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                self.compile(f"invalid{index}", source, success=False)

    def test_zero_division_and_minimum_overflow_trap_in_child(self):
        if os.name == "nt":
            control = self.compile("trap_control", "pub fn main_entry()->u32{return 42;}")
            status, error = self.windows_process_exit_code(self.link_image(control))
            self.assertEqual(status, 42, error)
        for index, expression in enumerate(("17/0", "-2147483648 / -1", "-2147483648 % -1")):
            with self.subTest(index=index):
                obj = self.compile(f"trap{index}", f"pub fn main_entry()->u32{{let result:i32={expression};return result as u32;}}")
                if os.name == "nt":
                    status, error = self.windows_process_exit_code(self.link_image(obj))
                    expected = 0xc0000094 if index == 0 else 0xc0000095
                    self.assertEqual(status, expected, error)
                else:
                    import resource
                    output = self.link_image(obj)
                    result = subprocess.run([str(output)], cwd=self.directory, capture_output=True, timeout=15,
                                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
                    self.assertEqual(result.returncode, -signal.SIGFPE, result.stderr)

    def test_defined_signed_arithmetic_matches_c11_reference(self):
        source = 'fn calc(a:i32,b:i32)->i32{return a/b+a%b;}pub fn main_entry()->u32{let result:i32=calc(-17,5);if result==-5{return 42;}return 1;}'
        obj = self.compile("reference", source)
        self.execute(obj)
        c_path = self.directory / "reference.c"
        ref_obj = self.directory / "reference-host.o"
        output = self.directory / ("reference-host.exe" if os.name == "nt" else "reference-host")
        script = (
            "import sys;from pathlib import Path;from sotlas_compile.bootstrap import parse,compile_module;"
            "from sotlas.llvm_toolchain import default_toolchain;"
            "path=Path(sys.argv[1]);c=compile_module(parse(path.read_text(),filename=str(path)));"
            "Path(sys.argv[2]).write_text(c+'\\nint main(void){return (int)main_entry();}\\n');"
            "default_toolchain.compile_c_to_obj(Path(sys.argv[2]),Path(sys.argv[3]));"
            "default_toolchain.link_native_binary([Path(sys.argv[3])],Path(sys.argv[4]))"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        built = subprocess.run([sys.executable, "-c", script, str(obj.with_suffix(".sotlas")), str(c_path), str(ref_obj), str(output)],
                               cwd=ROOT, env=environment, capture_output=True, timeout=120)
        self.assertEqual(built.returncode, 0, built.stderr)
        result = subprocess.run([str(output)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 42, result.stderr)


if __name__ == "__main__":
    unittest.main()
