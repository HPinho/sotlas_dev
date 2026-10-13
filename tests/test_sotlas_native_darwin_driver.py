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

    @unittest.skipUnless(MAC_X64, "requires native platform execution")
    def test_native_frontend_ownership_eight_advances_and_diagnostics(self):
        source = self.directory / 'native_owned_arrays.sotlas'
        output = self.directory / 'native_owned_arrays_image'
        source.write_text('module probe;struct Token{pub values:[u16;3];}\nstatic mut total:u32=0;\nimpl Token{fn read(self:direct Self)->u32{return (self.values[0] as u32)+(self.values[1] as u32)+(self.values[2] as u32);}}\nfn identity(value:u32)->u32{return value;}\nfn observe(value:whisper Token)->void{unsafe{total=value.read();}}\nfn consume(value:sole Token)->u32{return value.read();}\nfn consume_bool(value:sole Token)->bool{return true;}\npub fn main_entry()->u32{let input:[u16;3]=[10,12,20];let value:sole Token=Token{values:input};\n{defer observe(value);}let skipped:bool=false&&consume_bool(value);\nif skipped || unsafe{total}!=42{return 1;}if identity(value.read())!=42{return 2;}return consume(value);}', encoding='utf-8')
        environment = {'PATH': str(self.directory / 'no-host-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        self.run_tool([str(self.seed), '--check', str(source)], env=environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=environment)
        self.run_tool([str(output)], expected=42, env=environment)
        original = output.read_bytes()
        cases = [('module probe;struct Token{pub value:u32;}fn consume(value:sole Token)->u32{return value.value;}pub fn main_entry()->u32{let value:sole Token=Token{value:42};consume(value);return value.value;}', 'use of moved or maybe-moved value'), ('module probe;struct Token{pub value:u32;}fn wrong(mut value:direct Token)->u32{value.value=42;return 42;}pub fn main_entry()->u32{return 42;}', 'borrowed value cannot be mutated'), ('module probe;struct Token{pub value:u32;}fn wrong(value:whisper Token)->*const Token{return unsafe{value as *const Token};}pub fn main_entry()->u32{return 42;}', 'borrowed value cannot escape'), ('module probe;struct Token{pub value:u32;}fn observe(value:direct Token)->void{return;}fn consume(value:sole Token)->u32{return value.value;}pub fn main_entry()->u32{let value:sole Token=Token{value:42};defer observe(value);return consume(value);}', 'deferred borrow prevents ownership transfer')]
        for invalid, message in cases:
            source.write_text(invalid, encoding='utf-8')
            for arguments in ([str(self.seed), '--check', str(source)], [str(self.seed), str(source), str(output)]):
                result = self.run_tool(arguments, expected=6, env=environment)
                self.assertIn(message.encode(), result.stderr)
                self.assertEqual(output.read_bytes(), original)

    @unittest.skipUnless(MAC_X64, "requires native platform execution")
    def test_native_owned_array_records_check_compile_run_without_host_tools(self):
        source = self.directory / 'native_owned_arrays.sotlas'
        output = self.directory / 'native_owned_arrays_image'
        source.write_text('module probe;struct Packet{pub values:[u32;3];}\nfn read(value:direct Packet)->u32{return value.values[0]+value.values[1]+value.values[2];}\npub fn main_entry()->u32{let value:sole Packet=Packet{values:[10,12,20]};return read(value);}', encoding='utf-8')
        environment = {'PATH': str(self.directory / 'no-host-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        self.run_tool([str(self.seed), '--check', str(source)], env=environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=environment)
        self.run_tool([str(output)], expected=42, env=environment)
        original = output.read_bytes()
        source.write_text('module probe;struct Packet{pub values:[u32;3];}\npub fn main_entry()->u32{let value:sole Packet=Packet{values:[1,2]};return 42;}', encoding='utf-8')
        for arguments in ([str(self.seed), '--check', str(source)], [str(self.seed), str(source), str(output)]):
            self.run_tool(arguments, expected=7, env=environment)
            self.assertEqual(output.read_bytes(), original)

    @unittest.skipUnless(MAC_X64, "requires native platform execution")
    def test_native_direct_check_compile_run_without_host_tools(self):
        source = self.directory / 'native_direct.sotlas'
        output = self.directory / 'native_direct_image'
        source.write_text('module probe;struct Token{pub value:u32;}\nfn read(value:direct Token)->u32{return value.value;}\nfn forward(value:direct Token)->u32{return read(value);}\nfn consume(value:sole Token)->u32{return value.value;}\npub fn main_entry()->u32{let value:sole Token=Token{value:21};return forward(value)+consume(value);}', encoding='utf-8')
        environment = {'PATH': str(self.directory / 'no-host-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        profile = self.run_tool([str(self.seed), '--capabilities'], env=environment)
        self.assertIn(b'direct-internal', profile.stdout)
        self.run_tool([str(self.seed), '--check', str(source)], env=environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=environment)
        self.run_tool([str(output)], expected=42, env=environment)
        original = output.read_bytes()
        source.write_text('module probe;struct Token{pub value:u32;}\nfn read(mut value:direct Token)->u32{value.value=0;return 42;}\npub fn main_entry()->u32{return 42;}', encoding='utf-8')
        for arguments in ([str(self.seed), '--check', str(source)], [str(self.seed), str(source), str(output)]):
            self.run_tool(arguments, expected=6, env=environment)
            self.assertEqual(output.read_bytes(), original)


    @unittest.skipUnless(MAC_X64, "requires native platform execution")
    def test_native_match_check_compile_run_without_host_tools(self):
        source = self.directory / 'native_match.sotlas'
        output = self.directory / 'native_match_image'
        source.write_text('module probe;enum Code{First=1,Last=9}static mut trace:u32=0;\nfn append(value:u32)->void{unsafe{trace=trace*10+value;}}\nfn boolean(value:bool)->bool{match value{true=>return true;false=>return false;}}\nfn choose(value:Code)->u32{defer append(9);match value{\nCode::First=>{defer append(4);return 42;} Code::Last=>return 1;}}\npub fn main_entry()->u32{let value:u32=choose(Code::First);if !boolean(true) || unsafe{trace}!=49{return 2;}return value;}', encoding='utf-8')
        environment = {'PATH': str(self.directory / 'no-host-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        self.run_tool([str(self.seed), '--check', str(source)], env=environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=environment)
        self.run_tool([str(output)], expected=42, env=environment)
        original = output.read_bytes()
        source.write_text('module probe;pub fn main_entry()->u32{match 0{0=>return 42;}}', encoding='utf-8')
        for arguments in ([str(self.seed), '--check', str(source)], [str(self.seed), str(source), str(output)]):
            self.run_tool(arguments, expected=7, env=environment)
            self.assertEqual(output.read_bytes(), original)

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
        source = self.directory / "exclusive.sotlas"
        output = self.directory / "exclusive"
        source.write_text("module gate;struct Token{pub value:u32;}fn read(x:whisper Token)->u32{return x.value;}fn consume(x:sole Token)->u32{return x.value;}pub fn main_entry()->u32{let first:sole Token=Token{value:42};if read(first)!=42{return 1;}let second:exclusive Token=first;return consume(second);}",encoding="utf-8")
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)
        unsupported = ["module gate;pub struct Token{pub value:u32;}fn use(x:"+domain+(" *mut Token" if domain in ("sole","whisper","direct") else " Token")+")->u32{return 42;}" for domain in ("sole","shared","region","device","external","island","whisper","direct")]
        unsupported.append("module gate;fn load()->u32{return 42;}flow Compute{stage seed=load;}")
        for index, text in enumerate(unsupported):
            with self.subTest(index=index):
                source = self.directory / ("unsupported_"+str(index)+".sotlas")
                source.write_text(text, encoding="utf-8")
                output = self.directory / ("unsupported_"+str(index)+"")
                output.write_bytes(b"preserve")
                code = 5 if index == 8 else 6
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




    @unittest.skipUnless(MAC_X64, "requires native platform execution")
    def test_project_diagnostics_map_original_files_after_import_removal(self):
        environment=self.environment
        root=self.directory/'project diagnostics';namespace=root/'app';namespace.mkdir(parents=True)
        entry=namespace/'main.sotlas';dependency=namespace/'base.sotlas';output=root/'preserved output'
        good_dependency='module app::base;\nfn number()->u32{return 21;}\n'
        good_entry='module app::main;\nimport app::base::*;\n\npub fn main_entry()->u32{\n    return number()*2;\n}\n'
        cases=(('let target:u32=0;',5,5,9,b'expected identifier'),('return absent;',6,5,12,b'semantic error'))
        for statement,code,line,column,message in cases:
            dependency.write_text(good_dependency,encoding='utf-8')
            text='module app::main;\nimport app::base::*;\n\npub fn main_entry()->u32{\n    '+statement+'\n}\n'
            entry.write_text(text,encoding='utf-8')
            commands=(['--check-build',str(root),str(entry)],['--build',str(output),str(root),str(entry)],
                      ['--project-resolve-object',str(output),str(entry),str(dependency)])
            for arguments in commands:
                with self.subTest(statement=statement,mode=arguments[0]):
                    output.write_bytes(b'preserve')
                    result=self.run_tool([str(self.seed),*arguments],expected=code,env=environment)
                    self.assertIn(f'{entry}:{line}:{column}: '.encode(),result.stderr)
                    self.assertIn(message,result.stderr);self.assertIn(statement.encode(),result.stderr)
                    self.assertNotIn(b'<native-project>',result.stderr);self.assertEqual(output.read_bytes(),b'preserve')
            entry.write_text(text.replace('import app::base::*;',''),encoding='utf-8')
            output.write_bytes(b'preserve')
            result=self.run_tool([str(self.seed),'--project-object',str(output),str(dependency),str(entry)],expected=code,env=environment)
            self.assertIn(f'{entry}:{line}:{column}: '.encode(),result.stderr)
            self.assertEqual(output.read_bytes(),b'preserve')
        entry.write_text(good_entry,encoding='utf-8')
        dependency.write_text('module app::base;\nfn number()->u32{\n    return absent;\n}\n',encoding='utf-8')
        output.write_bytes(b'preserve')
        result=self.run_tool([str(self.seed),'--build',str(output),str(root),str(entry)],expected=6,env=environment)
        self.assertIn(f'{dependency}:3:12: '.encode().replace(bytes([92]),b'/'),result.stderr.replace(bytes([92]),b'/'))
        self.assertIn(b'return absent;',result.stderr);self.assertEqual(output.read_bytes(),b'preserve')


if __name__ == "__main__":
    unittest.main()
