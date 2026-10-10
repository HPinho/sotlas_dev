"""Owned PE32+ output, native Windows execution and platform rejection gates."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))
from sotlas.bootstrap_pipeline import build_stage1_native_compiler


class NativePETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-pe-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        build_stage1_native_compiler(cls.producer, verbose=False)

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
            ("strings", 'pub fn main_entry()->u32{let p:*const u8="abc"; return unsafe{*(p+1)} as u32;}', 98),
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
