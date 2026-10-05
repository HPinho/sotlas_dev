"""SV5a: multi-object ELF64 linking with cross-object relocations.

Two independently compiled Sotlas modules are linked by the Sotlas-owned linker.
`main_entry` in module B calls `helper` defined in module A through an
`@extern(C)` declaration, which the object writer emits as an undefined symbol
plus a PLT32 relocation. The test verifies the relocation bytes in the linked
image (not only headers) and, on Linux hosts, executes the result.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.bootstrap_pipeline import build_stage1_native_compiler  # noqa: E402

MODULE_A = """module m::a;
pub fn helper(x: u32) -> u32 { return x + 1; }
"""

MODULE_B = """module m::b;
@extern(C)
fn helper(x: u32) -> u32;
pub fn main_entry() -> u32 { return helper(41); }
"""


def elf_section(data: bytes, name: bytes):
    shoff = struct.unpack_from("<Q", data, 40)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 58)
    str_hdr = shoff + shstrndx * shentsize
    str_off = struct.unpack_from("<Q", data, str_hdr + 24)[0]
    for i in range(shnum):
        hdr = shoff + i * shentsize
        n = struct.unpack_from("<I", data, hdr)[0]
        end = data.index(b"\0", str_off + n)
        if data[str_off + n:end] == name:
            off, size = struct.unpack_from("<QQ", data, hdr + 24)
            return data[off:off + size]
    return None


class TestSV5MultiObjectLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="sotlas-sv5a-")
        cls.root = Path(cls.tmp.name)
        suffix = ".exe" if os.name == "nt" else ""
        cls.stage1 = cls.root / f"stage1{suffix}"
        build_stage1_native_compiler(cls.stage1, verbose=False)
        for name, src in (("a", MODULE_A), ("b", MODULE_B)):
            (cls.root / f"{name}.sotlas").write_text(src, encoding="utf-8")
            r = subprocess.run(
                [str(cls.stage1), "--compile-obj", str(cls.root / f"{name}.sotlas"),
                 str(cls.root / f"{name}.o")],
                capture_output=True, text=True)
            assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def link(self, out, *objs, entry="main_entry", extra=()):
        return subprocess.run(
            [str(self.stage1), "--link-objs", str(out), entry,
             *[str(self.root / o) for o in objs], *extra],
            capture_output=True, text=True)

    def test_module_b_object_has_relocation_and_undefined_symbol(self):
        data = (self.root / "b.o").read_bytes()
        rela = elf_section(data, b".rela.text")
        self.assertIsNotNone(rela, "b.o must carry a .rela.text section")
        self.assertEqual(len(rela) % 24, 0)
        self.assertGreaterEqual(len(rela) // 24, 1)
        r_info = struct.unpack_from("<Q", rela, 8)[0]
        self.assertEqual(r_info & 0xFFFFFFFF, 4, "expected R_X86_64_PLT32")

    def test_cross_object_call_is_relocated_to_helper_code(self):
        out = self.root / "ab.elf"
        r = self.link(out, "b.o", "a.o")
        self.assertEqual(r.returncode, 0, r.stderr)
        image = out.read_bytes()
        a_text = elf_section((self.root / "a.o").read_bytes(), b".text")
        b_text = elf_section((self.root / "b.o").read_bytes(), b".text")
        helper_at = image.find(a_text)
        self.assertGreaterEqual(helper_at, 0, "helper code missing from image")
        call = b_text.index(b"\xe8")
        main_at = image.find(b_text[:call + 1])
        self.assertGreaterEqual(main_at, 0, "main_entry code missing from image")
        rel = struct.unpack_from("<i", image, main_at + call + 1)[0]
        self.assertEqual(main_at + call + 5 + rel, helper_at,
                         "call rel32 must land on helper")

    def test_link_order_does_not_change_resolution(self):
        o1, o2 = self.root / "ab1.elf", self.root / "ab2.elf"
        self.assertEqual(self.link(o1, "a.o", "b.o").returncode, 0)
        self.assertEqual(self.link(o2, "b.o", "a.o").returncode, 0)
        for exe in (o1, o2):
            image = exe.read_bytes()
            a_text = elf_section((self.root / "a.o").read_bytes(), b".text")
            b_text = elf_section((self.root / "b.o").read_bytes(), b".text")
            call = b_text.index(b"\xe8")
            main_at = image.find(b_text[:call + 1])
            rel = struct.unpack_from("<i", image, main_at + call + 1)[0]
            self.assertEqual(main_at + call + 5 + rel, image.find(a_text))

    def test_undefined_reference_fails_closed(self):
        r = self.link(self.root / "only_b.elf", "b.o")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root / "only_b.elf").exists())

    def test_duplicate_strong_symbol_fails_closed(self):
        r = self.link(self.root / "dup.elf", "a.o", "a.o", "b.o")
        self.assertNotEqual(r.returncode, 0)

    def test_missing_object_and_entry_fail_closed(self):
        self.assertNotEqual(self.link(self.root / "x.elf", "nope.o").returncode, 0)
        r = self.link(self.root / "y.elf", "a.o", "b.o", entry="no_such_entry")
        self.assertNotEqual(r.returncode, 0)

    @unittest.skipUnless(sys.platform.startswith("linux"), "needs a Linux host to execute ELF")
    def test_linked_program_executes_and_exits_with_42(self):
        out = self.root / "run.elf"
        self.assertEqual(self.link(out, "b.o", "a.o").returncode, 0)
        out.chmod(0o755)
        self.assertEqual(subprocess.run([str(out)]).returncode, 42)


if __name__ == "__main__":
    unittest.main()
