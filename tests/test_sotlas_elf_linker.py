"""Safety and layout tests for the internal freestanding ELF linker."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.elf_emitter import ElfEmitter
from sotlas.elf_linker import (
    EM_X86_64,
    ELFLinker,
    ELFLinkerError,
    ObjRelocation,
    ObjSection,
    ObjSymbol,
    ObjectFile,
    R_X86_64_32S,
    R_X86_64_64,
    R_X86_64_PC32,
    SHF_ALLOC,
    SHF_EXECINSTR,
    SHT_NULL,
    SHT_PROGBITS,
    STB_GLOBAL,
    STB_LOCAL,
    STT_FUNC,
    STT_OBJECT,
)


class SotlasELFLinkerTests(unittest.TestCase):
    def _object_path(self, directory: str, filename: str, emitter: ElfEmitter) -> Path:
        path = Path(directory) / filename
        emitter.write_to_file(str(path))
        return path

    def _linked_text(self, path: Path) -> tuple[int, bytes]:
        raw = path.read_bytes()
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", raw, 0)
        program_offset = header[5]
        entry_size = struct.unpack_from("<H", raw, 54)[0]
        program_count = struct.unpack_from("<H", raw, 56)[0]
        for index in range(program_count):
            at = program_offset + index * entry_size
            p_type, p_flags, p_offset, p_vaddr, _, p_filesz, _, _ = (
                struct.unpack_from("<IIQQQQQQ", raw, at)
            )
            if p_type == 1 and p_flags & 1:
                return p_vaddr, raw[p_offset:p_offset + p_filesz]
        self.fail("linked ELF has no executable PT_LOAD segment")

    def _load_segments(self, path: Path) -> list[tuple[int, int, int, int, int]]:
        raw = path.read_bytes()
        header = struct.unpack_from("<16sHHIQQQIHHHHHH", raw, 0)
        program_offset = header[5]
        entry_size = struct.unpack_from("<H", raw, 54)[0]
        program_count = struct.unpack_from("<H", raw, 56)[0]
        result = []
        for index in range(program_count):
            at = program_offset + index * entry_size
            p_type, p_flags, p_offset, p_vaddr, _, p_filesz, p_memsz, p_align = (
                struct.unpack_from("<IIQQQQQQ", raw, at)
            )
            if p_type == 1:
                result.append((p_flags, p_offset, p_vaddr, p_filesz, p_memsz, p_align))
        return result

    def _synthetic_object(
        self,
        name: str,
        text: bytes,
        *,
        relocations: list[ObjRelocation] | None = None,
        rodata: bytes = b"",
        absolute_address: int | None = None,
        entry_binding: int = STB_GLOBAL,
    ) -> ObjectFile:
        sections = [
            ObjSection("", SHT_NULL, 0, bytearray(), 1, 0, 0),
            ObjSection(
                ".text",
                SHT_PROGBITS,
                SHF_ALLOC | SHF_EXECINSTR,
                bytearray(text),
                16,
                0,
                0,
                relocations=relocations or [],
            ),
            ObjSection(
                ".rodata",
                SHT_PROGBITS,
                SHF_ALLOC,
                bytearray(rodata),
                16,
                0,
                0,
            ),
        ]
        symbols = [
            ObjSymbol("", 0, 0, STB_LOCAL, 0, 0, 0),
            ObjSymbol("entry", 0, len(text), entry_binding, STT_FUNC, 1, 0),
        ]
        if rodata:
            symbols.append(
                ObjSymbol("local_data", 0, len(rodata), STB_LOCAL, STT_OBJECT, 2, 0)
            )
        if absolute_address is not None:
            symbols.append(
                ObjSymbol("absolute_data", absolute_address, 1, STB_LOCAL, STT_OBJECT, 0xFFF1, 0)
            )
        return ObjectFile(name, EM_X86_64, sections, symbols)

    def test_links_exact_requested_entry_and_emits_loadable_text(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_link_") as directory:
            emitter = ElfEmitter(target_triple="x86_64-unknown-elf")
            text_offset = emitter.emit_text(b"\x90\xc3")
            emitter.add_symbol(
                "kernel_entry", ".text", text_offset, 2,
                is_global=True, is_func=True,
            )
            object_path = self._object_path(directory, "kernel.o", emitter)
            output = Path(directory) / "kernel.elf"

            linker = ELFLinker(
                entry_symbol="kernel_entry",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            linker.add_object(str(object_path))
            linker.link(str(output))

            raw = output.read_bytes()
            entry = struct.unpack_from("<Q", raw, 24)[0]
            text_vaddr, text = self._linked_text(output)
            self.assertEqual(entry, text_vaddr)
            self.assertEqual(text[:2], b"\x90\xc3")

    def test_missing_requested_entry_does_not_fall_back_to_start(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_entry_") as directory:
            emitter = ElfEmitter(target_triple="x86_64-unknown-elf")
            offset = emitter.emit_text(b"\x90\xc3")
            emitter.add_symbol("_start", ".text", offset, 2)
            object_path = self._object_path(directory, "start.o", emitter)
            output = Path(directory) / "bad.elf"
            linker = ELFLinker(
                entry_symbol="kernel_main",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            linker.add_object(str(object_path))

            with self.assertRaisesRegex(
                ELFLinkerError,
                "entry symbol 'kernel_main' is not defined",
            ):
                linker.link(str(output))
            self.assertFalse(output.exists())

    def test_section_alignment_is_reflected_in_text_bytes_and_addresses(self):
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_align_") as directory:
            first = ElfEmitter(target_triple="x86_64-unknown-elf")
            first_offset = first.emit_text(b"\x90\xc3")
            first.add_symbol("entry", ".text", first_offset, 2)
            second = ElfEmitter(target_triple="x86_64-unknown-elf")
            second.emit_text(b"\xaa")
            paths = [
                self._object_path(directory, "first.o", first),
                self._object_path(directory, "second.o", second),
            ]
            linker = ELFLinker(
                entry_symbol="entry",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            for path in paths:
                linker.add_object(str(path))
            output = Path(directory) / "aligned.elf"
            linker.link(str(output))

            text_vaddr, text = self._linked_text(output)
            self.assertEqual(text[:2], b"\x90\xc3")
            self.assertEqual(text[2:16], bytes(14))
            self.assertEqual(text[16], 0xAA)
            self.assertEqual(struct.unpack_from("<Q", output.read_bytes(), 24)[0], text_vaddr)
            text_segment = self._load_segments(output)[0]
            self.assertEqual(text_segment[2], text_vaddr)
            self.assertEqual(text_segment[3], len(text))

    def test_entry_in_non_executable_section_is_rejected(self):
        obj = self._synthetic_object("data_entry.o", b"\xc3", rodata=b"data")
        obj.symbols[1] = ObjSymbol("entry", 0, 1, STB_GLOBAL, STT_OBJECT, 2, 0)
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_badentry_") as directory:
            linker = ELFLinker(
                entry_symbol="entry",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            linker._objects.append(obj)
            with self.assertRaisesRegex(ELFLinkerError, "not in an executable section"):
                linker.link(str(Path(directory) / "bad_entry.elf"))

    def test_relocation_updates_the_aligned_section_slice_not_text_prefix(self):
        first = self._synthetic_object("entry.o", b"\x90\xc3")
        second = self._synthetic_object(
            "ref.o",
            bytes(8),
            relocations=[ObjRelocation(0, R_X86_64_64, 2, 0)],
            rodata=b"data",
            entry_binding=STB_LOCAL,
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_reloc_") as directory:
            linker = ELFLinker(
                entry_symbol="entry",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            linker._objects.extend([first, second])
            output = Path(directory) / "relocated.elf"
            linker.link(str(output))

            _, text = self._linked_text(output)
            self.assertEqual(text[:2], b"\x90\xc3")
            self.assertEqual(
                struct.unpack_from("<Q", text, 16)[0],
                linker._sec_vaddr[(1, 2)],
            )

    def test_unsupported_and_out_of_bounds_relocations_fail_closed(self):
        cases = (
            (
                ObjRelocation(0, 999, 1, 0),
                "unsupported x86-64 relocation type 999",
            ),
            (
                ObjRelocation(5, R_X86_64_64, 1, 0),
                "relocation at offset 5 exceeds section bounds",
            ),
            (
                ObjRelocation(0, R_X86_64_64, -1, 0),
                "relocation references invalid symbol index -1",
            ),
        )
        for relocation, message in cases:
            with self.subTest(message=message):
                obj = self._synthetic_object(
                    "bad.o", bytes(8), relocations=[relocation]
                )
                with tempfile.TemporaryDirectory(prefix="sotlas_elf_badrel_") as directory:
                    linker = ELFLinker(
                        entry_symbol="entry",
                        target_triple="x86_64-unknown-elf",
                        load_address=0x8000,
                    )
                    linker._objects.append(obj)
                    with self.assertRaisesRegex(ELFLinkerError, message):
                        linker.link(str(Path(directory) / "bad.elf"))

    def test_relocations_in_discarded_non_alloc_sections_are_ignored(self):
        obj = self._synthetic_object("debug.o", b"\xc3")
        obj.sections.append(
            ObjSection(
                ".debug_info",
                SHT_PROGBITS,
                0,
                bytearray(8),
                1,
                0,
                0,
                relocations=[ObjRelocation(0, 999, 999, 0)],
            )
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_debugrel_") as directory:
            linker = ELFLinker(
                entry_symbol="entry",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            linker._objects.append(obj)
            output = Path(directory) / "debug.elf"
            linker.link(str(output))
            self.assertTrue(output.is_file())

    def test_pc_relative_relocation_overflow_is_an_error(self):
        obj = self._synthetic_object(
            "overflow.o",
            bytes(8),
            relocations=[ObjRelocation(0, R_X86_64_PC32, 2, 0)],
            absolute_address=0x90000000,
        )
        with tempfile.TemporaryDirectory(prefix="sotlas_elf_overflow_") as directory:
            linker = ELFLinker(
                entry_symbol="entry",
                target_triple="x86_64-unknown-elf",
                load_address=0x8000,
            )
            linker._objects.append(obj)
            with self.assertRaisesRegex(ELFLinkerError, "PC-relative relocation overflow"):
                linker.link(str(Path(directory) / "overflow.elf"))

    def test_duplicate_strong_entry_symbols_are_rejected(self):
        first = self._synthetic_object("first.o", b"\xc3")
        second = self._synthetic_object("second.o", b"\xc3")
        linker = ELFLinker(target_triple="x86_64-unknown-elf")
        linker._objects.extend([first, second])
        with self.assertRaisesRegex(ELFLinkerError, "duplicate strong symbol 'entry'"):
            linker._collect_symbols()

    def test_invalid_page_size_is_rejected(self):
        for value in (0, -1, 3, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ELFLinkerError, "page size"):
                    ELFLinker(page_size=value)


if __name__ == "__main__":
    unittest.main()
