"""Native Windows file driver and original-source compiler generation gates."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeWindowsDriverTests(unittest.TestCase):
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
        source = self.directory / "stage3_application.sotlas"
        source.write_text("module probe; pub fn main_entry()->u32{return 42;}")
        output = self.directory / "stage3_application.exe"
        self.run_tool([str(stage3), "--check", str(source)], env=self.environment)
        self.run_tool([str(stage3), str(source), str(output)], env=self.environment)
        self.run_tool([str(output)], expected=42, env=self.environment)
