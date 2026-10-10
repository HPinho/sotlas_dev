"""Owned PE32+ output, native Windows execution and platform rejection gates."""
from pathlib import Path
import os
import json
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativePETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-pe-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        # The public CLI uses compiler/, which has stricter type checking than
        # tools/. A fresh child and output path also bypass any cached Stage 1.
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        script = (
            "import sys; from pathlib import Path; "
            "from sotlas.bootstrap_pipeline import build_stage1_native_compiler; "
            "build_stage1_native_compiler(Path(sys.argv[1]), verbose=False)"
        )
        result = subprocess.run([sys.executable, "-c", script, str(cls.producer)],
                                cwd=ROOT, env=environment, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f"Public frontend clean Stage 1 build failed: {result.stderr!r}")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compile_object(self, name, source):
        path = self.directory / (name + ".sotlas")
        path.write_text("module probe;\n" + source, encoding="utf-8")
        obj = path.with_suffix(".o")
        result = subprocess.run([str(self.producer), "--compile-obj", str(path), str(obj)], capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return obj

    def link(self, obj, output, entry="main_entry"):
        return subprocess.run([str(self.producer), "--link-pe", str(obj), str(output), entry], capture_output=True, timeout=60)

    def validate_pe(self, data):
        self.assertEqual(data[:2], b"MZ")
        pe = struct.unpack_from("<I", data, 60)[0]
        self.assertEqual(data[pe:pe + 4], b"PE\0\0")
        self.assertEqual(struct.unpack_from("<H", data, pe + 4)[0], 0x8664)
        count = struct.unpack_from("<H", data, pe + 6)[0]
        optional_size = struct.unpack_from("<H", data, pe + 20)[0]
        optional = pe + 24
        self.assertEqual(struct.unpack_from("<H", data, optional)[0], 0x20b)
        self.assertFalse(struct.unpack_from("<H", data, optional + 70)[0] & 0x40)
        entry = struct.unpack_from("<I", data, optional + 16)[0]
        sections = []
        for index in range(count):
            header = optional + optional_size + index * 40
            size, rva, raw_size, raw = struct.unpack_from("<IIII", data, header + 8)
            self.assertLessEqual(raw + raw_size, len(data))
            self.assertEqual(rva % 4096, 0)
            self.assertEqual(raw % 512, 0)
            sections.append((rva, size, raw))
        def file_offset(rva):
            for base, size, raw in sections:
                if base <= rva < base + size:
                    return raw + rva - base
            self.fail(f"unmapped RVA {rva}")
        file_offset(entry)
        imports_rva, imports_size = struct.unpack_from("<II", data, optional + 120)
        self.assertEqual(imports_size, 40)
        descriptor = file_offset(imports_rva)
        lookup, _, _, dll, iat = struct.unpack_from("<IIIII", data, descriptor)
        self.assertEqual(data[descriptor + 20:descriptor + 40], bytes(20))
        dll_offset = file_offset(dll)
        self.assertEqual(data[dll_offset:data.index(b"\0", dll_offset)], b"KERNEL32.dll")
        name_rva = struct.unpack_from("<Q", data, file_offset(lookup))[0]
        self.assertEqual(name_rva, struct.unpack_from("<Q", data, file_offset(iat))[0])
        hint = file_offset(name_rva)
        self.assertEqual(data[hint + 2:data.index(b"\0", hint + 2)], b"ExitProcess")

    def test_pe_header_imports_determinism_and_native_execution(self):
        fixtures = (
            ("calls", "fn twice(x:u32)->u32{return x*2;} pub fn main_entry()->u32{return twice(21);}", 42),
            ("wide_exit", "pub fn main_entry()->u32{return 260;}", 260),
            ("syscall_shaped_constant", "pub fn main_entry()->u32{return 1295;}", 1295),
            ("strings", 'pub fn main_entry()->u32{let p:*const u8="abc"; return unsafe{*(p+1)} as u32;}', 98),
            ("pointer_array", 'static mut pointers:[*const u8;2]=0; pub fn main_entry()->u32{let p:*const u8="abc"; unsafe{pointers[0]=p;} let view:*const *const u8=unsafe{pointers as *const *const u8}; let first:*const u8=unsafe{*view}; return unsafe{*first} as u32;}', 97),
            ("bss", "pub static mut total:usize=0; pub fn main_entry()->u32{let mut i:usize=0; while i<2{unsafe{total=total+21;} i=i+1;} return unsafe{total} as u32;}", 42),
        )
        for name, source, code in fixtures:
            with self.subTest(name=name):
                obj = self.compile_object(name, source)
                exe = self.directory / (name + ".exe")
                linked = self.link(obj, exe)
                self.assertEqual(linked.returncode, 0, linked.stderr)
                self.validate_pe(exe.read_bytes())
                second = self.directory / (name + "_second.exe")
                self.assertEqual(self.link(obj, second).returncode, 0)
                self.assertEqual(exe.read_bytes(), second.read_bytes())
                if os.name == "nt":
                    environment = {"PATH": str(self.directory / "no-tools"), "SystemRoot": os.environ.get("SystemRoot", "C:\\Windows")}
                    executed = subprocess.run([str(exe)], env=environment, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(executed.returncode, code, executed.stderr)

    def test_windows_console_and_file_api_bridges(self):
        filename = self.directory / "native_file_roundtrip.txt"
        declarations = """
@extern(C) fn sotlas_windows_get_std_handle(kind:u32)->u64;
@extern(C) fn sotlas_windows_create_file(path:*const u8,access:u32,share:u32,security:*const u8,creation:u32,flags:u32,template:u64)->u64;
@extern(C) fn sotlas_windows_read_file(handle:u64,buffer:*mut u8,count:u32,read:*mut u32,overlapped:*mut u8)->u32;
@extern(C) fn sotlas_windows_write_file(handle:u64,buffer:*const u8,count:u32,written:*mut u32,overlapped:*mut u8)->u32;
@extern(C) fn sotlas_windows_close_handle(handle:u64)->u32;
@extern(C) fn sotlas_windows_get_last_error()->u32;
@extern(C) fn sotlas_windows_get_command_line()->*const u8;
"""
        body = declarations + """
@system pub fn main_entry()->u32 {
    let command:*const u8 = sotlas_windows_get_command_line();
    if command == null { return 1; }
    let handle:u64 = sotlas_windows_create_file(PATH,1073741824,1,null,2,128,0);
    if handle == 18446744073709551615 { return sotlas_windows_get_last_error(); }
    let mut written:u32=0;
    let success:u32=sotlas_windows_write_file(handle,"abc",3,unsafe{(&mut written) as *mut u32},null);
    let closed:u32=sotlas_windows_close_handle(handle);
    if success == 0 || closed == 0 || written != 3 { return 2; }
    let input:u64=sotlas_windows_create_file(PATH,2147483648,1,null,3,128,0);
    if input == 18446744073709551615 { return 3; }
    let mut bytes:[u8;4]=0;
    let mut read:u32=0;
    let loaded:u32=sotlas_windows_read_file(input,unsafe{bytes as *mut u8},3,unsafe{(&mut read) as *mut u32},null);
    let closed_input:u32=sotlas_windows_close_handle(input);
    if loaded == 0 || closed_input == 0 || read != 3 || bytes[1] != 98 { return 4; }
    let stdout:u64=sotlas_windows_get_std_handle(4294967285);
    let printed:u32=sotlas_windows_write_file(stdout,"Sotlas native Windows I/O\\n",26,unsafe{(&mut written) as *mut u32},null);
    if printed == 0 || written != 26 { return 5; }
    return 0;
}
"""
        body = body.replace("PATH", json.dumps(str(filename)))
        obj = self.compile_object("windows_io", body)
        output = self.directory / "windows_io.exe"
        result = self.link(obj, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.validate_pe(output.read_bytes())
        if os.name == "nt":
            environment = {"PATH": str(self.directory / "no-tools"), "SystemRoot": os.environ.get("SystemRoot", "C:\\Windows")}
            executed = subprocess.run([str(output)], env=environment, capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(executed.stdout, b"Sotlas native Windows I/O\n")
            self.assertEqual(filename.read_bytes(), b"abc")

    def test_windows_import_signatures_fail_closed(self):
        declarations = (
            "@extern(C) fn sotlas_windows_close_handle(handle:u32)->u32;",
            "@extern(C) fn sotlas_windows_get_last_error()->u64;",
            "@extern(C) fn sotlas_windows_write_file(handle:u64,buffer:*const u8,count:u32,written:*mut u32)->u32;",
        )
        for index, declaration in enumerate(declarations):
            with self.subTest(declaration=declaration):
                source = self.directory / f"wrong_windows_signature_{index}.sotlas"
                source.write_text("module probe; " + declaration + " pub fn main_entry()->u32{return 42;}")
                output = source.with_suffix(".o")
                result = subprocess.run([str(self.producer), "--compile-obj", str(source), str(output)], capture_output=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_public_native_cli_builds_with_empty_cache(self):
        cache_root = self.directory / "public_cli_empty_cache"
        source = self.directory / "public_cli_source.sotlas"
        source.write_text("module probe; pub fn main_entry()->u32{return 42;}")
        output = self.directory / "public_cli_output.c"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        script = (
            "import sys; from pathlib import Path; "
            "import sotlas.bootstrap_pipeline as pipeline; "
            "pipeline._ROOT = Path(sys.argv[1]); "
            "from sotlas.cli import main; "
            "raise SystemExit(main(['compile', sys.argv[2], '--backend', 'native', "
            "'--emit-c', '-o', sys.argv[3]]))"
        )
        result = subprocess.run([sys.executable, "-c", script, str(cache_root), str(source), str(output)],
                                cwd=ROOT, env=environment, capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr)
        suffix = ".exe" if os.name == "nt" else ""
        self.assertTrue((cache_root / "build" / ("sotlas_stage1" + suffix)).is_file())
        self.assertTrue(output.is_file())
        self.assertIn("main_entry", output.read_text())

    def test_pe_rejects_foreign_symbols_linux_syscalls_and_nonzero_arity(self):
        fixtures = (
            ("arity", "pub fn main_entry(x:u32)->u32{return x;}"),
            ("foreign", "@extern(C) fn unknown()->u32; pub fn main_entry()->u32{return unknown();}"),
            ("linux", "@extern(C) fn sotlas_linux_close(fd:u64)->i64; @system pub fn main_entry()->u32{return sotlas_linux_close(0) as u32;}"),
        )
        for name, source in fixtures:
            with self.subTest(name=name):
                obj = self.compile_object(name, source)
                output = self.directory / "preserved.exe"
                sentinel = b"preserve existing executable on unsupported PE input"
                output.write_bytes(sentinel)
                self.assertNotEqual(self.link(obj, output).returncode, 0)
                self.assertEqual(output.read_bytes(), sentinel)

    def test_pe_rejects_truncated_objects_missing_entry_and_abi_note(self):
        obj = self.compile_object("valid", "pub fn main_entry()->u32{return 42;}")
        data = obj.read_bytes()
        headers = struct.unpack_from("<Q", data, 40)[0]
        missing_note = bytearray(data)
        for index in range(struct.unpack_from("<H", data, 60)[0]):
            header = headers + index * 64
            if struct.unpack_from("<I", data, header + 4)[0] == 7:
                note = struct.unpack_from("<Q", data, header + 24)[0]
                missing_note[note + 12] = 0
        output = self.directory / "malformed_preserved.exe"
        for payload, entry in ((data[:48], "main_entry"), (data, "absent"), (missing_note, "main_entry")):
            with self.subTest(entry=entry, size=len(payload)):
                bad = self.directory / "malformed.o"
                bad.write_bytes(payload)
                output.write_bytes(b"sentinel")
                self.assertNotEqual(self.link(bad, output, entry).returncode, 0)
                self.assertEqual(output.read_bytes(), b"sentinel")
