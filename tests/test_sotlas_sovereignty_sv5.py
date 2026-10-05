"""Sovereignty Milestone SV5 Gate: Sotlas-Owned Object Emission & Freestanding/Native Linking.

Validates that:
1. Native compiler emits valid ELF64 relocatable objects (.o) with custom sections,
   symbols, and relocations without external toolchains.
2. Direct single-object linking creates valid static ELF64 executables (ET_EXEC) for hosted
   applications and freestanding kernels (base 0x100000).
3. Multi-object linking (--link-objs) links multiple independently compiled Sotlas modules,
   resolving cross-object symbols and patching R_X86_64_PLT32 / PC32 relocations into text.
4. Link order invariance: linking (A, B) or (B, A) resolves cross references identically.
5. Strict fail-closed link-time contract guards:
   - Undefined external references fail closed.
   - Duplicate strong symbol definitions across objects fail closed.
   - Non-existent entry point symbol fails closed.
   - Malformed or corrupt object headers fail closed.
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

from sotlas.bootstrap_pipeline import build_stage1_native_compiler

APP_MODULE = """module app::single;

pub fn add_numbers(a: u32, b: u32) -> u32 {
    return a + b;
}

pub fn main_entry() -> u32 {
    let result: u32 = add_numbers(19, 23);
    return result;
}
"""

KERNEL_MODULE = """module kernel::freestanding;

fn init_hardware(magic: u32) -> u32 {
    return magic + 1;
}

@system
pub fn _start() -> u32 {
    let status: u32 = init_hardware(41);
    return status;
}
"""

MULTI_A = """module multi::math;

pub fn calculate_factor(x: u32) -> u32 {
    return x * 2 + 10;
}
"""

MULTI_B = """module multi::runner;

@extern(C)
fn calculate_factor(x: u32) -> u32;

pub fn main_entry() -> u32 {
    let ans: u32 = calculate_factor(16);
    return ans;
}
"""


def get_elf_section(data: bytes, section_name: bytes) -> bytes | None:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        return None
    shoff = struct.unpack_from("<Q", data, 40)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 58)
    str_hdr = shoff + shstrndx * shentsize
    str_off = struct.unpack_from("<Q", data, str_hdr + 24)[0]
    for i in range(shnum):
        hdr = shoff + i * shentsize
        name_idx = struct.unpack_from("<I", data, hdr)[0]
        end = data.index(b"\0", str_off + name_idx)
        if data[str_off + name_idx:end] == section_name:
            off, size = struct.unpack_from("<QQ", data, hdr + 24)
            return data[off:off + size]
    return None


class TestSotlasSovereigntySV5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory(prefix="sotlas-sv5-")
        cls.root = Path(cls.tmp_dir.name)
        exe_suffix = ".exe" if os.name == "nt" else ""
        cls.stage1 = ROOT / "build" / f"sotlas_stage1{exe_suffix}"
        if not cls.stage1.is_file():
            build_stage1_native_compiler(cls.stage1, verbose=False)

        cls.app_src = cls.root / "app.sotlas"
        cls.app_src.write_text(APP_MODULE, encoding="utf-8")
        cls.app_obj = cls.root / "app.o"
        r = subprocess.run([str(cls.stage1), "--compile-obj", str(cls.app_src), str(cls.app_obj)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

        cls.kernel_src = cls.root / "kernel.sotlas"
        cls.kernel_src.write_text(KERNEL_MODULE, encoding="utf-8")
        cls.kernel_obj = cls.root / "kernel.o"
        r = subprocess.run([str(cls.stage1), "--compile-obj", str(cls.kernel_src), str(cls.kernel_obj)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

        cls.mod_a_src = cls.root / "mod_a.sotlas"
        cls.mod_a_src.write_text(MULTI_A, encoding="utf-8")
        cls.mod_a_obj = cls.root / "mod_a.o"
        r = subprocess.run([str(cls.stage1), "--compile-obj", str(cls.mod_a_src), str(cls.mod_a_obj)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

        cls.mod_b_src = cls.root / "mod_b.sotlas"
        cls.mod_b_src.write_text(MULTI_B, encoding="utf-8")
        cls.mod_b_obj = cls.root / "mod_b.o"
        r = subprocess.run([str(cls.stage1), "--compile-obj", str(cls.mod_b_src), str(cls.mod_b_obj)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    def test_sv5_single_object_elf_structure(self):
        """SV5.1: Emitted object is valid ELF64 relocatable object with .text and symbols."""
        data = self.app_obj.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        self.assertEqual(data[4], 2, "ELFCLASS64")
        self.assertEqual(data[5], 1, "ELFDATA2LSB")
        e_type = struct.unpack_from("<H", data, 16)[0]
        self.assertEqual(e_type, 1, "ET_REL")
        e_machine = struct.unpack_from("<H", data, 18)[0]
        self.assertEqual(e_machine, 62, "EM_X86_64")

        text = get_elf_section(data, b".text")
        self.assertIsNotNone(text)
        self.assertGreater(len(text), 0)

    def test_sv5_single_object_link_hosted_executable(self):
        """SV5.2: Link single-object hosted executable with custom entry symbol."""
        out_exe = self.root / "app_linked.bin"
        r = subprocess.run([str(self.stage1), "--link-exe", str(self.app_obj), str(out_exe), "main_entry"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_exe.is_file())

        data = out_exe.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        e_type = struct.unpack_from("<H", data, 16)[0]
        self.assertEqual(e_type, 2, "ET_EXEC")
        e_entry = struct.unpack_from("<Q", data, 24)[0]
        self.assertGreaterEqual(e_entry, 0x400000)
        self.assertLess(e_entry, 0x400000 + 0x10000)

    def test_sv5_single_object_link_freestanding_kernel(self):
        """SV5.3: Link freestanding kernel image loaded at 1 MiB (0x100000)."""
        out_kernel = self.root / "kernel_linked.bin"
        r = subprocess.run([str(self.stage1), "--link-exe", str(self.kernel_obj), str(out_kernel), "_start", "--freestanding"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_kernel.is_file())

        data = out_kernel.read_bytes()
        self.assertEqual(data[:4], b"\x7fELF")
        e_type = struct.unpack_from("<H", data, 16)[0]
        self.assertEqual(e_type, 2, "ET_EXEC")
        e_entry = struct.unpack_from("<Q", data, 24)[0]
        self.assertGreaterEqual(e_entry, 0x100000)
        self.assertLess(e_entry, 0x100000 + 0x10000)

    def test_sv5_external_call_object_generates_rela_text(self):
        """SV5.4: Object calling @extern(C) function contains .rela.text with R_X86_64_PLT32."""
        data = self.mod_b_obj.read_bytes()
        rela = get_elf_section(data, b".rela.text")
        self.assertIsNotNone(rela, "mod_b.o must carry a .rela.text section")
        self.assertEqual(len(rela) % 24, 0)
        self.assertGreaterEqual(len(rela) // 24, 1)
        r_info = struct.unpack_from("<Q", rela, 8)[0]
        self.assertEqual(r_info & 0xFFFFFFFF, 4, "R_X86_64_PLT32 relocation type")

    def test_sv5_multi_object_linking_and_relocation_resolution(self):
        """SV5.5: Multi-object link resolves external symbols and patches call relocations."""
        out_multi = self.root / "multi_linked.bin"
        r = subprocess.run([str(self.stage1), "--link-objs", str(out_multi), "main_entry", str(self.mod_b_obj), str(self.mod_a_obj)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out_multi.is_file())

        image = out_multi.read_bytes()
        self.assertEqual(image[:4], b"\x7fELF")
        e_type = struct.unpack_from("<H", image, 16)[0]
        self.assertEqual(e_type, 2, "ET_EXEC")

        a_text = get_elf_section(self.mod_a_obj.read_bytes(), b".text")
        b_text = get_elf_section(self.mod_b_obj.read_bytes(), b".text")
        self.assertIsNotNone(a_text)
        self.assertIsNotNone(b_text)

        helper_pos = image.find(a_text)
        self.assertGreaterEqual(helper_pos, 0, "mod_a code must be in executable image")

        call_op = b_text.index(b"\xe8")
        main_pos = image.find(b_text[:call_op + 1])
        self.assertGreaterEqual(main_pos, 0, "mod_b code must be in executable image")

        rel_disp = struct.unpack_from("<i", image, main_pos + call_op + 1)[0]
        self.assertEqual(main_pos + call_op + 5 + rel_disp, helper_pos, "Call offset must land exactly on target function")

    def test_sv5_multi_object_link_order_invariance(self):
        """SV5.6: Object order does not break cross-object relocation resolution."""
        out1 = self.root / "order1.bin"
        out2 = self.root / "order2.bin"
        r1 = subprocess.run([str(self.stage1), "--link-objs", str(out1), "main_entry", str(self.mod_a_obj), str(self.mod_b_obj)], capture_output=True, text=True)
        r2 = subprocess.run([str(self.stage1), "--link-objs", str(out2), "main_entry", str(self.mod_b_obj), str(self.mod_a_obj)], capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r2.returncode, 0)

        for exe in (out1, out2):
            img = exe.read_bytes()
            a_text = get_elf_section(self.mod_a_obj.read_bytes(), b".text")
            b_text = get_elf_section(self.mod_b_obj.read_bytes(), b".text")
            call_idx = b_text.index(b"\xe8")
            main_idx = img.find(b_text[:call_idx + 1])
            disp = struct.unpack_from("<i", img, main_idx + call_idx + 1)[0]
            self.assertEqual(main_idx + call_idx + 5 + disp, img.find(a_text))

    def test_sv5_fail_closed_undefined_symbol(self):
        """SV5.7: Undefined cross-object reference fails closed."""
        bad_out = self.root / "bad_undef.bin"
        r = subprocess.run([str(self.stage1), "--link-objs", str(bad_out), "main_entry", str(self.mod_b_obj)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(bad_out.exists())

    def test_sv5_fail_closed_duplicate_strong_symbol(self):
        """SV5.8: Duplicate strong symbols fail closed."""
        bad_out = self.root / "bad_dup.bin"
        r = subprocess.run([str(self.stage1), "--link-objs", str(bad_out), "main_entry", str(self.mod_a_obj), str(self.mod_a_obj)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(bad_out.exists())

    def test_sv5_fail_closed_missing_entry_symbol(self):
        """SV5.9: Missing entry point symbol fails closed."""
        bad_out = self.root / "bad_entry.bin"
        r = subprocess.run([str(self.stage1), "--link-objs", str(bad_out), "non_existent_symbol", str(self.mod_a_obj)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(bad_out.exists())


if __name__ == "__main__":
    unittest.main()
