"""Native Windows file driver and original-source compiler generation gates."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeWindowsDriverTests(unittest.TestCase):

    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
    def test_native_sv849c_loop_exit_states_and_cleanup(self):
        source = self.directory / 'loop_edge_states.sotlas'
        output = self.directory / 'loop_edge_states_image'
        source.write_text('module probe;struct Token{pub value:u32;}static mut trace:u32=0;\nfn observe(value:direct Token)->void{unsafe{trace=trace*10+value.value;}}\nfn consume(value:sole Token)->void{return;}\npub fn main_entry()->u32{let owner:sole Token=Token{value:42};let witness:sole Token=Token{value:2};\nlet mut count:u32=0;while count<3{count=count+1;match count{\n1=>{defer observe(witness);continue;},_=>{defer observe(witness);consume(owner);break;}}}\nif unsafe{trace}!=22{return 1;}return 42;}', encoding='utf-8')
        environment = {'PATH': str(self.directory / 'no-host-tools')}
        if os.name == 'nt':
            environment['SystemRoot'] = os.environ.get('SystemRoot', 'C:\\Windows')
        self.run_tool([str(self.seed), '--check', str(source)], env=environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=environment)
        self.run_tool([str(output)], expected=42, env=environment)
        original = output.read_bytes()
        source.write_text('module probe;struct Token{pub value:u32;}static mut trace:u32=0;\nfn observe(value:direct Token)->void{unsafe{trace=trace*10+value.value;}}\nfn consume(value:sole Token)->void{return;}\npub fn main_entry()->u32{let owner:sole Token=Token{value:42};let witness:sole Token=Token{value:2};\nlet mut count:u32=0;while count<3{count=count+1;match count{\n1=>{defer observe(witness);continue;},_=>{defer observe(witness);consume(owner);break;}}}\nif unsafe{trace}!=22{return 1;}return owner.value;}', encoding='utf-8')
        for arguments in ([str(self.seed), '--check', str(source)], [str(self.seed), str(source), str(output)]):
            result = self.run_tool(arguments, expected=6, env=environment)
            self.assertIn(b'moved or maybe-moved', result.stderr)
            self.assertEqual(output.read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
    def test_sv847_native_deferred_effect_specific_diagnostic(self):
        source = self.directory / "sv847_effect_diagnostic.sotlas"
        output = self.directory / "sv847_preserved_image"
        source.write_text(
            "module probe;struct Packet{pub value:u32;}static mut hits:u32=0;"
            "fn observe(v:direct Packet,x:u32)->void{return;}"
            "fn impure()->u32{unsafe{hits=hits+1;}return 2;}"
            "pub fn main_entry()->u32{let owner:sole Packet=Packet{value:42};"
            "defer observe(owner,impure());return 42;}", encoding="utf-8")
        output.write_bytes(b"keep existing output")
        env = {"PATH": str(self.directory / "no-host-tools")}
        if os.name == "nt":
            env["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")
        for args in ([str(self.seed), "--check", str(source)],
                     [str(self.seed), str(source), str(output)]):
            result = self.run_tool(args, expected=6, env=env)
            self.assertIn(b"deferred argument has unproven effects", result.stderr)
            self.assertEqual(output.read_bytes(), b"keep existing output")

    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
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

    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
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

    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
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


    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
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
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-windows-native-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        script = "import sys; from pathlib import Path; from sotlas.bootstrap_pipeline import build_stage1_native_compiler; build_stage1_native_compiler(Path(sys.argv[1]),verbose=False)"
        result = subprocess.run([sys.executable, "-c", script, str(cls.producer)], cwd=ROOT,
                                env=environment, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        cls.seed = cls.directory / "sotlas-native.exe"
        cls.obj = cls.directory / "windows_driver.o"
        cls.run_tool([str(cls.producer), "--compile-obj", str(ROOT / "bootstrap/sotlas/native_driver/windows.sotlas"), str(cls.obj)])
        cls.run_tool([str(cls.producer), "--link-pe", str(cls.obj), str(cls.seed), "main_entry"])
        cls.environment = {"PATH": str(cls.directory / "no-tools"),
                           "SystemRoot": os.environ.get("SystemRoot", "C:\\Windows")}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_tool(cls, args, expected=0, timeout=180, env=None):
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=timeout, **options)
        if result.returncode != expected:
            raise AssertionError(f"{args}: exit {result.returncode}, expected {expected}: {result.stderr!r}")
        return result

    def test_driver_cross_object_and_pe_image(self):
        self.assertEqual(self.obj.read_bytes()[:4], b"\x7fELF")
        self.assertEqual(self.seed.read_bytes()[:2], b"MZ")
        self.assertIn(b"GetCommandLineA\0", self.seed.read_bytes())
        self.assertIn(b"CreateFileA\0", self.seed.read_bytes())

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_file_compile_check_and_quoted_argument_paths_without_host_tools(self):
        directory = self.directory / "space in path"
        directory.mkdir()
        source = directory / "source with spaces.sotlas"
        source.write_text("module probe; fn twice(x:u32)->u32{return x*2;} pub fn main_entry()->u32{return twice(21);}")
        output = directory / "application with spaces.exe"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)
        first = directory / "first.sotlas"
        second = directory / "second.sotlas"
        first.write_text("module probe::first; fn answer()->u32{return 42;}")
        second.write_text("module probe::second; pub fn main_entry()->u32{return answer();}")
        self.run_tool([str(self.seed), "--project", str(output), str(first), str(second)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)
        previous = output.read_bytes()
        source.write_text("module probe; import absent::*; pub fn main_entry()->u32{return 42;}")
        self.run_tool([str(self.seed), str(source), str(output)], expected=12, env=self.environment)
        self.assertEqual(output.read_bytes(), previous)
        self.run_tool([str(self.seed), str(directory / "missing.sotlas"), str(output)], expected=2, env=self.environment)
        self.assertEqual(output.read_bytes(), previous)
        self.run_tool([str(self.seed)], expected=1, env=self.environment)

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
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
        output = self.directory / "float_profile.exe"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
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

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_native_check_compile_reject_ownership_and_flow_consistently(self):
        source = self.directory / "exclusive.sotlas"
        output = self.directory / "exclusive.exe"
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
                output = self.directory / ("unsupported_"+str(index)+".exe")
                output.write_bytes(b"preserve")
                code = 5 if index == 8 else 6
                self.run_tool([str(self.seed), "--check", str(source)], expected=code, env=self.environment)
                self.run_tool([str(self.seed), str(source), str(output)], expected=code, env=self.environment)
                self.assertEqual(output.read_bytes(), b"preserve")

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_bit_operations_workload_executes_without_host_tools(self):
        source = ROOT / "examples/native_bit_operations.sotlas"
        output = self.directory / "bit_operations.exe"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_signed_integer_family_executes_without_host_tools(self):
        source = self.directory / "signed_family.sotlas"
        source.write_text("module probe;fn wide(a:i8,b:i16)->i64{let x:i64=a as i64;let y:i64=b as i64;return x/y;}pub fn main_entry()->u32{let n:i8=-17;let q:i8=n/5;let r:i8=n%5;let s:i16=-257;if wide(-127,5)==-25 && q==-3 && r==-2 && (s>>8)==-2{return 42;}return 1;}")
        output = self.directory / "signed_family.exe"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_signed_i32_program_compiles_and_runs_without_host_tools(self):
        source = self.directory / "signed_program.sotlas"
        source.write_text("module probe;fn score(a:i32,b:i32)->i32{return a/b+a%b;}pub fn main_entry()->u32{let n:i32=score(-17,5);let wide:i64=n as i64;if wide==-5 && (n>>1)==-3{return 42;}return 1;}")
        output = self.directory / "signed_program.exe"
        self.run_tool([str(self.seed), "--check", str(source)], env=self.environment)
        self.run_tool([str(self.seed), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_cross_builds_complete_darwin_compiler_without_host_tools(self):
        root = self.directory / "darwin-source-tree"
        namespace = root / "sotlas/compiler"
        core = ROOT / "bootstrap/sotlas/native_compiler"
        names = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir", "backend/lower_scalar", "backend/x86_64_scalar")
        for name in names:
            destination = namespace / (name + ".sotlas")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((core / (name + ".sotlas")).read_bytes())
        entry = namespace / "darwin_driver.sotlas"
        entry.write_bytes((ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas").read_bytes())
        actual = self.directory / "darwin-compiler"
        obj = actual.with_suffix(".o")
        reference = self.directory / "darwin-reference"
        # Use the original source tree for the hosted oracle, whose fallback
        # import search otherwise mixes copied modules with repository paths.
        original = ROOT / "bootstrap/sotlas/native_driver/darwin.sotlas"
        self.run_tool([str(self.producer), "--compile-obj", str(original), str(obj)])
        self.run_tool([str(self.producer), "--link-macho", str(obj), str(reference), "sotlas_darwin_main"])
        # This compiles the whole compiler; use the self-hosting workload budget.
        self.run_tool([str(self.seed), "--build-mac-cc", str(actual), str(root), str(entry)], env=self.environment, timeout=900)
        self.assertEqual(actual.read_bytes(), reference.read_bytes())
        self.assertEqual(actual.read_bytes()[:4], b"\xcf\xfa\xed\xfe")

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_cross_compiles_macho_without_host_tools(self):
        source = self.directory / "mac_app.sotlas"
        source.write_text("module probe; fn twice(x:u32)->u32{return x*2;} pub fn main_entry()->u32{return twice(21);}")
        obj = source.with_suffix(".o")
        expected = self.directory / "mac_reference"
        actual = self.directory / "mac_actual"
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(obj)])
        self.run_tool([str(self.producer), "--link-macho", str(obj), str(expected), "main_entry"])
        self.run_tool([str(self.seed), "--build-mac", str(actual), str(self.directory), str(source)], env=self.environment)
        self.assertEqual(actual.read_bytes(), expected.read_bytes())
        self.assertEqual(actual.read_bytes()[:4], b"\xcf\xfa\xed\xfe")
        source.write_text("module probe; @extern(C) fn sotlas_darwin_close(fd:u64)->i64; @system pub fn main_entry()->u32{let n:i64=sotlas_darwin_close(18446744073709551615);if n<0{return 42;}return 1;}")
        self.run_tool([str(self.producer), "--compile-obj", str(source), str(obj)])
        self.run_tool([str(self.producer), "--link-macho", str(obj), str(expected), "main_entry"])
        self.run_tool([str(self.seed), "--build-mac", str(actual), str(self.directory), str(source)], env=self.environment)
        self.assertEqual(actual.read_bytes(), expected.read_bytes())
        source.write_text("module probe; @extern(C) fn sotlas_windows_get_last_error()->u32; @system pub fn main_entry()->u32{return sotlas_windows_get_last_error();}")
        previous = actual.read_bytes()
        self.run_tool([str(self.seed), "--build-mac", str(actual), str(self.directory), str(source)], expected=9, env=self.environment)
        self.assertEqual(actual.read_bytes(), previous)

    @unittest.skipUnless(os.name == "nt", "native execution requires Windows x64")
    def test_original_modules_build_native_stage2_stage3_fixed_point(self):
        directory = ROOT / "bootstrap/sotlas/native_compiler"
        names = ("token", "ast", "lexer", "parser", "sema", "backend/target_ir", "backend/lower_scalar", "backend/x86_64_scalar")
        sources = [directory / (name + ".sotlas") for name in names]
        sources.append(ROOT / "bootstrap/sotlas/native_driver/windows.sotlas")
        stage2 = self.directory / "stage2.exe"
        stage3 = self.directory / "stage3.exe"
        self.run_tool([str(self.seed), "--project-resolve-compiler", str(stage2), *map(str, sources)], env=self.environment, timeout=900)
        self.run_tool([str(stage2), "--project-resolve-compiler", str(stage3), *map(str, sources)], env=self.environment, timeout=900)
        self.assertEqual(stage2.read_bytes(), stage3.read_bytes())
        self.assertEqual(self.run_tool([str(stage3), "--compare", str(stage2), str(stage3)], env=self.environment).stdout, b"byte-identical\n")
        self.assertEqual(self.run_tool([str(stage2), "--fingerprint", str(stage2)], env=self.environment).stdout,
                         self.run_tool([str(stage3), "--fingerprint", str(stage3)], env=self.environment).stdout)
        self.run_tool([str(stage3), "--verify-seed", str(stage3)], env=self.environment)
        self.run_tool([str(stage3), "--self-test"], env=self.environment)
        powershell = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.run_tool([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(ROOT / "tests/native/match_ranges/verify.ps1"), str(stage3),
                       str(self.directory / "match range cases")], timeout=120)
        self.run_tool([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(ROOT / "tests/native/large_modules/verify.ps1"), str(stage3),
                       str(self.directory / "large module cases")], timeout=120)
        from native_calculator_gate import verify_calculator
        verify_calculator(stage3, self.directory / "calculator cases")
        from native_numeric_gate import verify_numeric_pipeline
        verify_numeric_pipeline(stage3, self.directory / "numeric pipeline cases")
        from native_numeric_gate import verify_text_pipeline
        verify_text_pipeline(stage3, self.directory / "text pipeline cases")
        from native_numeric_gate import verify_text_buffer
        verify_text_buffer(stage3, self.directory / "text buffer cases")
        from native_numeric_gate import verify_arena_text
        verify_arena_text(stage3, self.directory / "arena text cases")
        from native_numeric_gate import verify_pool_text
        verify_pool_text(stage3, self.directory / "pool text cases")
        from native_numeric_gate import verify_config_map
        verify_config_map(stage3, self.directory / "config map cases")
        from native_numeric_gate import verify_record_storage
        verify_record_storage(stage3, self.directory / "record storage cases")
        from native_window_gate import verify_window
        verify_window(stage3, self.directory / "window cases")
        from native_ui_gate import verify_ui
        verify_ui(stage3, self.directory / "ui cases")
        source = self.directory / "stage3_application.sotlas"
        source.write_bytes((ROOT / "examples/native_float_profile.sotlas").read_bytes())
        output = self.directory / "stage3_application.exe"
        self.run_tool([str(stage3), "--check", str(source)], env=self.environment)
        self.run_tool([str(stage3), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)

    @unittest.skipUnless(os.name == "nt", "requires native platform execution")
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
            commands=(['--check-build',str(root),str(entry)],['--build-win',str(output),str(root),str(entry)],
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
        result=self.run_tool([str(self.seed),'--build-win',str(output),str(root),str(entry)],expected=6,env=environment)
        self.assertIn(f'{dependency}:3:12: '.encode().replace(bytes([92]),b'/'),result.stderr.replace(bytes([92]),b'/'))
        self.assertIn(b'return absent;',result.stderr);self.assertEqual(output.read_bytes(),b'preserve')
