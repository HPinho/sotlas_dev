"""Testes unitários para o emissor direto de código objeto ELF64 de Sotlas."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.elf_emitter import (
    ElfEmitter,
    EI_MAG0, EI_MAG1, EI_MAG2, EI_MAG3,
    ELFCLASS64, ELFDATA2LSB, EV_CURRENT,
    ET_REL, EM_X86_64, EM_AARCH64
)


class TestSotlasElfEmitter(unittest.TestCase):
    def test_elf_header_magic_and_fields(self):
        emitter = ElfEmitter(target_triple="x86_64-sotlas-bakenos")
        # Emite alguns bytes de máquina simples (x86_64: nop; ret)
        text_off = emitter.emit_text(bytes([0x90, 0xC3]))
        emitter.add_symbol("kernel_entry", ".text", text_off, 2, is_global=True, is_func=True)

        raw = emitter.build_bytes()

        # Verifica Magic 0x7F 'E' 'L' 'F'
        self.assertEqual(raw[0], EI_MAG0)
        self.assertEqual(raw[1], EI_MAG1)
        self.assertEqual(raw[2], EI_MAG2)
        self.assertEqual(raw[3], EI_MAG3)
        self.assertEqual(raw[4], ELFCLASS64)
        self.assertEqual(raw[5], ELFDATA2LSB)
        self.assertEqual(raw[6], EV_CURRENT)

        # Verifica seções emitidas
        section_names = [sec.name for sec in emitter.sections]
        self.assertIn(".text", section_names)
        self.assertIn(".rodata", section_names)
        self.assertIn(".data", section_names)
        self.assertIn(".bss", section_names)
        self.assertIn(".bkn_tcb", section_names)  # Seção customizada BakenOS
        self.assertIn(".symtab", section_names)
        self.assertIn(".strtab", section_names)
        self.assertIn(".shstrtab", section_names)

    def test_elf_aarch64_target_triple(self):
        emitter = ElfEmitter(target_triple="aarch64-sotlas-bakenos")
        self.assertEqual(emitter.machine, EM_AARCH64)
        raw = emitter.build_bytes()
        self.assertGreater(len(raw), 64)

    def test_elf_write_to_file(self, tmp_path=None):
        import tempfile
        emitter = ElfEmitter(target_triple="x86_64-sotlas-bakenos")
        emitter.emit_text(b"\x90\x90\xC3")
        with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            emitter.write_to_file(tmp_path)
            content = Path(tmp_path).read_bytes()
            self.assertTrue(content.startswith(b"\x7fELF"))
            self.assertGreaterEqual(len(content), 64)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
