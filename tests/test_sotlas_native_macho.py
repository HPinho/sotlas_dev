"""Owned static Intel Mach-O output and Darwin platform rejection gates."""
from pathlib import Path
import os
import platform
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeMachOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sotlas-macho-")
        cls.directory = Path(cls.temp.name)
        cls.producer = cls.directory / ("producer.exe" if os.name == "nt" else "producer")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "compiler")
        script = (
            "import sys; from pathlib import Path; "
            "from sotlas.bootstrap_pipeline import build_stage1_native_compiler; "
            "build_stage1_native_compiler(Path(sys.argv[1]), verbose=False)"
        )
        built = subprocess.run([sys.executable, "-c", script, str(cls.producer)],
                               cwd=ROOT, env=environment, capture_output=True, timeout=180)
        if built.returncode:
            raise RuntimeError(f"Clean public Stage 1 build failed: {built.stderr!r}")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compile(self, name, body, success=True):
        path = self.directory / (name + ".sotlas")
        path.write_text("module probe;\n" + body, encoding="utf-8")
        obj = path.with_suffix(".o")
        result = subprocess.run([str(self.producer), "--compile-obj", str(path), str(obj)],
                                capture_output=True, timeout=60)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(obj.exists())
        return obj

    def link(self, obj, output, option="--link-macho", entry="main_entry"):
        return subprocess.run([str(self.producer), option, str(obj), str(output), entry],
                              capture_output=True, timeout=60)

    def validate_image(self, data):
        magic, cpu, subtype, kind, count, commands_size, flags, reserved = struct.unpack_from("<8I", data)
        self.assertEqual((magic, cpu, subtype, kind), (0xfeedfacf, 0x1000007, 3, 2))
        self.assertEqual((count, commands_size, flags, reserved), (5, 416, 1, 0))
        offset = 32
        segments = []
        entry = None
        for _ in range(count):
            command, size = struct.unpack_from("<II", data, offset)
            self.assertLessEqual(offset + size, 32 + commands_size)
            if command == 0x19:
                name = data[offset + 8:offset + 24].rstrip(b"\0")
                address, memory, raw, length, maximum, protection, sections, segment_flags = struct.unpack_from("<QQQQIIII", data, offset + 24)
                self.assertLessEqual(raw + length, len(data))
                self.assertEqual((address % 4096, memory % 4096, raw % 4096), (0, 0, 0))
                self.assertGreaterEqual(memory, length)
                self.assertEqual((maximum, sections, segment_flags), (protection, 0, 0))
                segments.append((name, address, memory, raw, length, protection))
            elif command == 5:
                self.assertEqual(size, 184)
                self.assertEqual(struct.unpack_from("<II", data, offset + 8), (4, 42))
                entry = struct.unpack_from("<Q", data, offset + 16 + 16 * 8)[0]
            elif command == 0x24:
                self.assertEqual(size, 16)
                self.assertEqual(struct.unpack_from("<I", data, offset + 8)[0], 0x0a0d00)
            else:
                self.fail(f"unexpected load command {command:#x}")
            offset += size
        self.assertEqual(offset, 32 + commands_size)
        self.assertEqual([s[0] for s in segments], [b"__PAGEZERO", b"__SOTLAS", b"__START"])
        self.assertEqual(segments[0][1:], (0, 0x400000, 0, 0, 0))
        for left, right in zip(segments, segments[1:]):
            self.assertLessEqual(left[1] + left[2], right[1])
        startup = segments[2]
        self.assertEqual((entry, startup[5]), (startup[1], 5))
        self.assertEqual(data[4096:4100], b"\x7fELF")  # private linked payload
        shim = data[startup[3]:startup[3] + 20]
        self.assertEqual(shim[:5], b"\x48\x83\xe4\xf0\xe8")
        relative = struct.unpack_from("<i", shim, 5)[0]
        target = entry + 9 + relative
        self.assertGreaterEqual(target, segments[1][1])
        self.assertLess(target, segments[1][1] + segments[1][2])
        self.assertEqual(shim[9:], b"\x89\xc7\xb8\x01\x00\x00\x02\x0f\x05\x0f\x0b")

    def execute_on_mac(self, output, code, stdout=b""):
        if sys.platform == "darwin" and platform.machine().lower() in ("x86_64", "amd64"):
            result = subprocess.run([str(output)], env={"PATH": str(self.directory / "no-host-tools")},
                                    capture_output=True, timeout=15)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(result.stdout, stdout)

    def test_static_images_layout_relocations_bss_and_execution(self):
        fixtures = (
            ("calls", "fn twice(x:u32)->u32{return x*2;} pub fn main_entry()->u32{return twice(21);}", 42),
            ("strings", 'pub fn main_entry()->u32{let p:*const u8="abc";return unsafe{*(p+1)} as u32;}', 98),
            ("bss", "static mut n:usize=0;pub fn main_entry()->u32{let mut i:usize=0;while i<2{unsafe{n=n+21;}i=i+1;}return unsafe{n} as u32;}", 42),
            ("large_bss", "static mut bytes:[u8;8192]=0;pub fn main_entry()->u32{unsafe{bytes[8191]=42;}return unsafe{bytes[8191]} as u32;}", 42),
        )
        for name, source, code in fixtures:
            with self.subTest(name=name):
                obj = self.compile(name, source)
                output = self.directory / (name + ".macho")
                linked = self.link(obj, output)
                self.assertEqual(linked.returncode, 0, linked.stderr)
                self.validate_image(output.read_bytes())
                other = output.with_suffix(".second")
                self.assertEqual(self.link(obj, other).returncode, 0)
                self.assertEqual(output.read_bytes(), other.read_bytes())
                self.execute_on_mac(output, code)

    def test_darwin_io_and_negative_errno(self):
        filename = (self.directory / "roundtrip.txt").as_posix()
        path_literal = '"' + filename.replace('\\', '\\\\').replace('"', '\\"') + '"'
        body = r"""
@extern(C) fn sotlas_darwin_open(path:*const u8,flags:u64,mode:u64)->i64;
@extern(C) fn sotlas_darwin_read(fd:u64,buffer:*mut u8,count:u64)->i64;
@extern(C) fn sotlas_darwin_write(fd:u64,buffer:*const u8,count:u64)->i64;
@extern(C) fn sotlas_darwin_close(fd:u64)->i64;
static mut buffer:[u8;4]=0;
@system pub fn main_entry()->u32{
    let bad:i64=sotlas_darwin_close(18446744073709551615);
    if bad>=0{return 1;}
    let fd:i64=sotlas_darwin_open(PATH,1537,384);
    if fd<0{return 2;}
    let written:i64=sotlas_darwin_write(fd as u64,"abc",3);
    let closed:i64=sotlas_darwin_close(fd as u64);
    if written!=3 || closed!=0{return 3;}
    let input:i64=sotlas_darwin_open(PATH,0,0);
    if input<0{return 4;}
    let count:i64=sotlas_darwin_read(input as u64,unsafe{buffer as *mut u8},4);
    let done:i64=sotlas_darwin_close(input as u64);
    if count!=3 || done!=0 || unsafe{buffer[2]}!=99{return 5;}
    let displayed:i64=sotlas_darwin_write(1,"Darwin native I/O\n",18);
    if displayed!=18{return 6;}
    return 42;
}
""".replace("PATH", path_literal)
        obj = self.compile("io", body)
        self.assertEqual(struct.unpack_from("<I", obj.read_bytes(), 48)[0], 2)
        output = self.directory / "io.macho"
        self.assertEqual(self.link(obj, output).returncode, 0)
        self.validate_image(output.read_bytes())
        self.execute_on_mac(output, 42, b"Darwin native I/O\n")
        if sys.platform == "darwin" and platform.machine().lower() == "x86_64":
            self.assertEqual((self.directory / "roundtrip.txt").read_bytes(), b"abc")
        for option in ("--link-exe", "--link-pe"):
            wrong = self.directory / (option[2:] + ".out")
            wrong.write_bytes(b"preserve")
            self.assertNotEqual(self.link(obj, wrong, option).returncode, 0)
            self.assertEqual(wrong.read_bytes(), b"preserve")

    def test_wrong_platform_unresolved_and_entry_contract_rejected(self):
        fixtures = (
            ("linux", '@extern(C) fn sotlas_linux_close(fd:u64)->i64;@system pub fn main_entry()->u32{let n:i64=sotlas_linux_close(7);return n as u32;}'),
            ("foreign", '@extern(C) fn foreign()->u32;@system pub fn main_entry()->u32{return foreign();}'),
            ("parameter", 'pub fn main_entry(x:u32)->u32{return x;}'),
        )
        for name, body in fixtures:
            with self.subTest(name=name):
                obj = self.compile(name, body)
                output = self.directory / (name + ".invalid")
                output.write_bytes(b"preserve")
                self.assertNotEqual(self.link(obj, output).returncode, 0)
                self.assertEqual(output.read_bytes(), b"preserve")
        self.compile("wrong_signature", '@extern(C) fn sotlas_darwin_close(fd:u32)->i64;@system pub fn main_entry()->u32{let n:i64=sotlas_darwin_close(7);return n as u32;}', success=False)

    def test_malformed_object_and_missing_abi_note_rejected(self):
        obj = self.compile("malformed_seed", "pub fn main_entry()->u32{return 42;}")
        original = obj.read_bytes()
        mutations = [original[:63]]
        data = bytearray(original)
        headers = struct.unpack_from("<Q", data, 40)[0]
        count = struct.unpack_from("<H", data, 60)[0]
        for index in range(count):
            header = headers + index * 64
            if struct.unpack_from("<I", data, header + 4)[0] == 7:
                struct.pack_into("<I", data, header + 4, 1)
        mutations.append(data)
        data = bytearray(original)
        struct.pack_into("<Q", data, 40, len(data) - 1)
        mutations.append(data)
        data = bytearray(original)
        struct.pack_into("<I", data, 48, 4)
        mutations.append(data)
        for index, data in enumerate(mutations):
            with self.subTest(index=index):
                broken = self.directory / f"broken{index}.o"
                broken.write_bytes(data)
                output = broken.with_suffix(".macho")
                self.assertNotEqual(self.link(broken, output).returncode, 0)
                self.assertFalse(output.exists())

    def test_darwin_process_argv_and_explicit_signature(self):
        obj = self.compile("argv", "pub fn sotlas_darwin_main(argc:u64,argv:*const *const u8)->u32{if argv==null{return 9;}return argc as u32;}")
        output = self.directory / "argv.macho"
        self.assertEqual(self.link(obj, output, entry="sotlas_darwin_main").returncode, 0)
        data = output.read_bytes()
        raw = struct.unpack_from("<Q", data, 176 + 40)[0]
        self.assertEqual(data[raw:raw+9], b"\x48\x8b\x3c\x24\x48\x8d\x74\x24\x08")
        if sys.platform == "darwin" and platform.machine().lower() in ("x86_64", "amd64"):
            result = subprocess.run([str(output), "one", "two words"], env={"PATH": "/no-host-tools"}, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 3, result.stderr)
        for name, signature in (
            ("missing_param", "()->u32{return 1;}"),
            ("wrong_arg", "(argc:u32,argv:*const u8)->u32{return argc;}"),
            ("wrong_result", "(argc:u64,argv:*const u8)->u64{return argc;}"),
        ):
            self.compile(name, "pub fn sotlas_darwin_main"+signature, success=False)
        # An ordinary two-parameter function cannot opt into process entry by
        # altering only the linker command's function name.
        ordinary = self.compile("ordinary", "pub fn main_entry(argc:u64,argv:*const u8)->u32{return argc as u32;}")
        rejected = self.directory / "ordinary.invalid"
        self.assertNotEqual(self.link(ordinary, rejected).returncode, 0)
        self.assertFalse(rejected.exists())


if __name__ == "__main__":
    unittest.main()
