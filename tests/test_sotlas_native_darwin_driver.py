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
        source.write_text("module probe;pub fn main_entry()->u32{return 42;}")
        output = self.directory / "stage3_program"
        self.run_tool([str(stage3), "--check", str(source)], env=self.environment)
        self.run_tool([str(stage3), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)


if __name__ == "__main__":
    unittest.main()
