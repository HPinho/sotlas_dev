"""Native static Intel macOS compiler and original-source generation gates."""
from pathlib import Path
import os
import platform
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAC_X64 = sys.platform == "darwin" and platform.machine().lower() in ("x86_64", "amd64")


class NativeDarwinDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-darwin-native-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        script = "import sys;from pathlib import Path;from sotlas.bootstrap_pipeline import build_stage1_native_compiler;build_stage1_native_compiler(Path(sys.argv[1]),verbose=False)"
        built = subprocess.run([sys.executable, "-c", script, str(cls.producer)],
                               cwd=ROOT, env=environment, capture_output=True, timeout=180)
        if built.returncode:
            raise RuntimeError(built.stderr)
        cls.obj = cls.directory / "darwin_driver.o"
        cls.seed = cls.directory / "sotlas-native"
        cls.run_tool([str(cls.producer), "--compile-obj", str(ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas"), str(cls.obj)])
        cls.run_tool([str(cls.producer), "--link-macho", str(cls.obj), str(cls.seed), "sotlas_darwin_main"])
        cls.environment = {"PATH": str(cls.directory / "no-host-tools")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_tool(cls, args, expected=0, timeout=180, env=None):
        result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
        if result.returncode != expected:
            raise AssertionError(f"{args}: exit {result.returncode}, expected {expected}: {result.stderr!r}")
        return result

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_native_diagnostics_preserve_path_position_phase_and_context(self):
        source=self.directory/'diagnostic file.sotlas'
        output=self.directory/'diagnostic.exe'
        cases=(
            ('module gate;\nfn probe()->u32{return 42;}\n',5,2,4,b'syntax error; expected identifier',b'fn probe'),
            ('module gate;\npub fn main_entry()->u32{let target:u32=0;return 42;}\n',5,2,30,b'syntax error; expected identifier',b'let target'),
            ('module gate;\n# invalid\n',4,2,1,b'lexical error',b'# invalid'),
        )
        for text,code,line,column,message,context in cases:
            with self.subTest(message=message,text=text):
                source.write_text(text,encoding='utf-8');output.write_bytes(b'preserve')
                checked=self.run_tool([str(self.seed),'--check',str(source)],expected=code,env=self.environment)
                compiled=self.run_tool([str(self.seed),str(source),str(output)],expected=code,env=self.environment)
                location=f'{source}:{line}:{column}: '.encode()
                self.assertIn(location,checked.stderr)
                self.assertIn(message,checked.stderr)
                self.assertIn(context,checked.stderr)
                self.assertIn(b'^',checked.stderr)
                self.assertEqual(checked.stderr,compiled.stderr)
                self.assertEqual(output.read_bytes(),b'preserve')

    def test_driver_macho_and_recorded_process_entry(self):
        obj = self.obj.read_bytes()
        self.assertEqual(obj[:4], b"\x7fELF")
        self.assertEqual(struct.unpack_from("<I", obj, 48)[0], 2)
        data = self.seed.read_bytes()
        self.assertEqual(data[:4], b"\xcf\xfa\xed\xfe")
        start_raw = struct.unpack_from("<Q", data, 176 + 40)[0]
        self.assertEqual(data[start_raw:start_raw + 14],
                         b"\x48\x8b\x3c\x24\x48\x8d\x74\x24\x08\x48\x83\xe4\xf0\xe8")
        second = self.directory / "second-image"
        self.run_tool([str(self.producer), "--link-macho", str(self.obj), str(second), "sotlas_darwin_main"])
        self.assertEqual(data, second.read_bytes())
        for target in ("--link-exe", "--link-pe"):
            output = self.directory / (target[2:] + ".invalid")
            output.write_bytes(b"preserve")
            result = subprocess.run([str(self.producer), target, str(self.obj), str(output), "sotlas_darwin_main"], capture_output=True, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"preserve")

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_native_file_check_compile_and_error_preservation(self):
        directory = self.directory / "path with spaces"
        directory.mkdir()
        source = directory / "program.sotlas"
        source.write_text("module probe;fn twice(x:u32)->u32{return x*2;}pub fn main_entry()->u32{return twice(21);}")
        output = directory / "native program"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)
        reference = directory / "reference.o"
        actual = directory / "actual.o"
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(reference)])
        self.run_tool([str(self.seed), str(source), str(actual), "--object"], env=self.environment)
        self.assertEqual(reference.read_bytes(), actual.read_bytes())
        previous = output.read_bytes()
        source.write_text("module probe;import missing::*;pub fn main_entry()->u32{return 42;}")
        self.run_tool([str(self.seed), str(source), str(output)], expected=12, env=self.environment)
        self.assertEqual(output.read_bytes(), previous)
        self.run_tool([str(self.seed), str(directory / "missing.sotlas"), str(output)], expected=2, env=self.environment)
        self.assertEqual(output.read_bytes(), previous)
        self.run_tool([str(self.seed)], expected=1, env=self.environment)

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_native_profile_help_and_float_workload(self):
        help_result = self.run_tool([str(self.seed), "--help"], env=self.environment)
        self.assertIn(b"Usage: sotlas-native", help_result.stdout)
        profile = self.run_tool([str(self.seed), "--capabilities"], env=self.environment)
        self.assertIn(b"floats=f32,f64", profile.stdout)
        self.assertIn(b"float_abi=internal-bits", profile.stdout)
        self.assertIn(b"ownership_runtime=unsupported", profile.stdout)
        self.assertIn(b"flow_execution=unsupported", profile.stdout)
        self.assertEqual(profile.stderr, b"")
        source = ROOT / "examples/native_float_profile.sotlas"
        output = self.directory / "float_profile"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_native_check_compile_reject_ownership_and_flow_consistently(self):
        unsupported = ["module gate;pub struct Token{pub value:u32;}fn use(x:"+domain+" Token)->u32{return x.value;}" for domain in ("sole","shared","region","device","external","island","whisper","direct")]
        unsupported.append("module gate;fn load()->u32{return 42;}flow Compute{stage seed=load;}")
        for index, text in enumerate(unsupported):
            with self.subTest(index=index):
                source = self.directory / ("unsupported_"+str(index)+".sotlas")
                source.write_text(text, encoding="utf-8")
                output = self.directory / ("unsupported_"+str(index)+"")
                output.write_bytes(b"preserve")
                code = 5 if index == 8 else 7
                self.run_tool([str(self.seed), "--check", str(source)], expected=code, env=self.environment)
                self.run_tool([str(self.seed), str(source), str(output)], expected=code, env=self.environment)
                self.assertEqual(output.read_bytes(), b"preserve")

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_bit_operations_workload_executes_without_host_tools(self):
        source = ROOT / "examples/native_bit_operations.sotlas"
        output = self.directory / "bit_operations"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_signed_integer_family_executes_without_host_tools(self):
        source = self.directory / "signed_family.sotlas"
        source.write_text("module probe;fn wide(a:i8,b:i16)->i64{let x:i64=a as i64;let y:i64=b as i64;return x/y;}pub fn main_entry()->u32{let n:i8=-17;let q:i8=n/5;let r:i8=n%5;let s:i16=-257;if wide(-127,5)==-25 && q==-3 && r==-2 && (s>>8)==-2{return 42;}return 1;}")
        output = self.directory / "signed_family"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_signed_i32_program_compiles_and_runs_without_host_tools(self):
        source = self.directory / "signed_program.sotlas"
        source.write_text("module probe;fn score(a:i32,b:i32)->i32{return a/b+a%b;}pub fn main_entry()->u32{let n:i32=score(-17,5);let wide:i64=n as i64;if wide==-5 && (n>>1)==-3{return 42;}return 1;}")
        output = self.directory / "signed_program"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(MAC_X64, "native execution requires Intel macOS")
    def test_original_modules_build_native_stage2_stage3_fixed_point(self):
        directory = ROOT / "bootstrap/sotlas/native_compiler"
        names = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir", "backend/lower_scalar", "backend/x86_64_scalar")
        sources = [directory / (name + ".sotlas") for name in names]
        sources.append(ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas")
        stage2 = self.directory / "stage2"
        stage3 = self.directory / "stage3"
        self.run_tool([str(self.seed), "--project-resolve-compiler", str(stage2), *map(str, sources)], env=self.environment, timeout=900)
        self.run_tool([str(stage2), "--project-resolve-compiler", str(stage3), *map(str, sources)], env=self.environment, timeout=900)
        self.assertEqual(stage2.read_bytes(), stage3.read_bytes())
        source = self.directory / "stage3_program.sotlas"
        source.write_bytes((ROOT / "examples/native_float_profile.sotlas").read_bytes())
        output = self.directory / "stage3_program"
        self.run_tool([str(stage3), "--check", str(source)], env=self.environment)
        self.run_tool([str(stage3), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)


if __name__ == "__main__":
    unittest.main()
