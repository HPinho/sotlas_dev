"""Sotlas ELF64 Direct Object Emitter — Emissão nativa de arquivos .o sem dependência externa.

Suporta:
  - Cabeçalho canônico Elf64_Ehdr (64-bit Little Endian)
  - Target triples: x86_64-sotlas-bakenos, aarch64-sotlas-bakenos, x86_64-unknown-elf
  - Seções estruturadas: .text, .rodata, .data, .bss, .shstrtab, .symtab, .strtab
  - Tabela de símbolos ELF64 (Elf64_Sym) com visibilidade STB_LOCAL e STB_GLOBAL
  - Suporte a ABI BakenOS: convenções de contexto de kernel e seções especiais
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Constantes ELF64
EI_MAG0 = 0x7F
EI_MAG1 = ord('E')
EI_MAG2 = ord('L')
EI_MAG3 = ord('F')
ELFCLASS64 = 2
ELFDATA2LSB = 1       # Little-endian
EV_CURRENT = 1
ELFOSABI_SYSV = 0
ELFOSABI_STANDALONE = 255

ET_REL = 1            # Relocatable file (.o)
ET_EXEC = 2           # Executable file

EM_X86_64 = 62        # AMD x86-64
EM_AARCH64 = 183      # ARM 64-bit

# Tipos de Seção
SHT_NULL = 0
SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_HASH = 5
SHT_DYNAMIC = 6
SHT_NOTE = 7
SHT_NOBITS = 8
SHT_REL = 9

# Flags de Seção
SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
SHF_MERGE = 0x10
SHF_STRINGS = 0x20

# Tipos e Ligações de Símbolos
STB_LOCAL = 0
STB_GLOBAL = 1
STB_WEAK = 2

STT_NOTYPE = 0
STT_OBJECT = 1
STT_FUNC = 2
STT_SECTION = 3
STT_FILE = 4


@dataclass
class ElfSymbol:
    name: str
    sec_idx: int
    value: int
    size: int
    binding: int = STB_GLOBAL
    sym_type: int = STT_FUNC


@dataclass
class ElfSection:
    name: str
    sec_type: int
    flags: int
    data: bytearray = field(default_factory=bytearray)
    addr_align: int = 16
    link: int = 0
    info: int = 0
    ent_size: int = 0
    name_offset: int = 0
    file_offset: int = 0


class ElfEmitter:
    """Emissor direto de código objeto ELF64 de alta performance."""

    def __init__(self, target_triple: str = "x86_64-sotlas-bakenos") -> None:
        self.target_triple = target_triple
        self.machine = EM_X86_64 if "x86_64" in target_triple else EM_AARCH64
        self.osabi = ELFOSABI_STANDALONE if "bakenos" in target_triple else ELFOSABI_SYSV

        # Seções padrão
        self.sections: List[ElfSection] = []
        self.sec_map: Dict[str, int] = {}
        self.symbols: List[ElfSymbol] = []

        # 0. Seção nula obrigatória
        self._add_section("", SHT_NULL, 0, addr_align=0)

        # 1. Seções canônicas de código e dados
        self.text_idx = self._add_section(".text", SHT_PROGBITS, SHF_ALLOC | SHF_EXECINSTR, addr_align=16)
        self.rodata_idx = self._add_section(".rodata", SHT_PROGBITS, SHF_ALLOC, addr_align=8)
        self.data_idx = self._add_section(".data", SHT_PROGBITS, SHF_ALLOC | SHF_WRITE, addr_align=8)
        self.bss_idx = self._add_section(".bss", SHT_NOBITS, SHF_ALLOC | SHF_WRITE, addr_align=8)

        # 2. Seções de BakenOS para drivers e TCB
        if "bakenos" in target_triple:
            self.tcb_idx = self._add_section(".bkn_tcb", SHT_PROGBITS, SHF_ALLOC | SHF_WRITE, addr_align=64)

        # 3. Metadados e strings
        self.shstrtab_idx = self._add_section(".shstrtab", SHT_STRTAB, 0, addr_align=1)
        self.symtab_idx = self._add_section(".symtab", SHT_SYMTAB, 0, addr_align=8, ent_size=24)
        self.strtab_idx = self._add_section(".strtab", SHT_STRTAB, 0, addr_align=1)

        # Símbolo nulo
        self.symbols.append(ElfSymbol(name="", sec_idx=0, value=0, size=0, binding=STB_LOCAL, sym_type=STT_NOTYPE))

    def _add_section(self, name: str, sec_type: int, flags: int, addr_align: int = 16, ent_size: int = 0) -> int:
        idx = len(self.sections)
        sec = ElfSection(name=name, sec_type=sec_type, flags=flags, addr_align=addr_align, ent_size=ent_size)
        self.sections.append(sec)
        self.sec_map[name] = idx
        return idx

    def emit_text(self, code_bytes: bytes) -> int:
        """Adiciona bytes executáveis na seção .text e retorna o offset."""
        sec = self.sections[self.text_idx]
        offset = len(sec.data)
        sec.data.extend(code_bytes)
        return offset

    def emit_rodata(self, data_bytes: bytes) -> int:
        """Adiciona dados constantes em .rodata e retorna o offset."""
        sec = self.sections[self.rodata_idx]
        offset = len(sec.data)
        sec.data.extend(data_bytes)
        return offset

    def emit_data(self, data_bytes: bytes) -> int:
        """Adiciona dados inicializados em .data e retorna o offset."""
        sec = self.sections[self.data_idx]
        offset = len(sec.data)
        sec.data.extend(data_bytes)
        return offset

    def add_symbol(self, name: str, section_name: str, offset: int, size: int,
                   is_global: bool = True, is_func: bool = True) -> None:
        """Registra um símbolo para a tabela de exportação ELF."""
        sec_idx = self.sec_map.get(section_name, self.text_idx)
        binding = STB_GLOBAL if is_global else STB_LOCAL
        sym_type = STT_FUNC if is_func else STT_OBJECT
        self.symbols.append(ElfSymbol(
            name=name,
            sec_idx=sec_idx,
            value=offset,
            size=size,
            binding=binding,
            sym_type=sym_type
        ))

    def build_bytes(self) -> bytes:
        """Empacota a estrutura ELF64 completa em um buffer binário pronto para disco."""
        # 1. Constrói a tabela de strings dos nomes de seção (.shstrtab)
        shstrtab_data = bytearray(b"\x00")
        for sec in self.sections:
            if sec.name:
                sec.name_offset = len(shstrtab_data)
                shstrtab_data.extend(sec.name.encode("utf-8") + b"\x00")
            else:
                sec.name_offset = 0
        self.sections[self.shstrtab_idx].data = shstrtab_data

        # 2. Constrói a tabela de strings dos símbolos (.strtab)
        strtab_data = bytearray(b"\x00")
        sym_name_offsets = []
        for sym in self.symbols:
            if sym.name:
                offset = len(strtab_data)
                strtab_data.extend(sym.name.encode("utf-8") + b"\x00")
                sym_name_offsets.append(offset)
            else:
                sym_name_offsets.append(0)
        self.sections[self.strtab_idx].data = strtab_data

        # 3. Constrói a tabela de símbolos (.symtab)
        symtab_data = bytearray()
        first_global_idx = len(self.symbols)
        for i, sym in enumerate(self.symbols):
            if sym.binding == STB_GLOBAL and i < first_global_idx:
                first_global_idx = i
            name_off = sym_name_offsets[i]
            info = (sym.binding << 4) | (sym.sym_type & 0xF)
            other = 0
            # Formato Elf64_Sym (24 bytes):
            # uint32_t st_name
            # uint8_t  st_info
            # uint8_t  st_other
            # uint16_t st_shndx
            # uint64_t st_value
            # uint64_t st_size
            sym_entry = struct.pack(
                "<IBBHQQ",
                name_off,
                info,
                other,
                sym.sec_idx,
                sym.value,
                sym.size
            )
            symtab_data.extend(sym_entry)

        self.sections[self.symtab_idx].data = symtab_data
        self.sections[self.symtab_idx].link = self.strtab_idx
        self.sections[self.symtab_idx].info = first_global_idx if first_global_idx < len(self.symbols) else 1

        # 4. Calcula offsets de cada seção no arquivo
        header_size = 64  # sizeof(Elf64_Ehdr)
        current_offset = header_size

        for sec in self.sections:
            if sec.sec_type == SHT_NULL:
                sec.file_offset = 0
                continue
            # Alinhamento
            if sec.addr_align > 1:
                padding = (sec.addr_align - (current_offset % sec.addr_align)) % sec.addr_align
                current_offset += padding
            sec.file_offset = current_offset
            if sec.sec_type != SHT_NOBITS:
                current_offset += len(sec.data)

        # Alinha offset dos Section Headers (Elf64_Shdr) em 8 bytes
        sh_padding = (8 - (current_offset % 8)) % 8
        current_offset += sh_padding
        shoff = current_offset

        # 5. Emite Elf64_Ehdr (64 bytes)
        # e_ident: 16 bytes
        e_ident = bytearray(16)
        e_ident[0] = EI_MAG0
        e_ident[1] = EI_MAG1
        e_ident[2] = EI_MAG2
        e_ident[3] = EI_MAG3
        e_ident[4] = ELFCLASS64
        e_ident[5] = ELFDATA2LSB
        e_ident[6] = EV_CURRENT
        e_ident[7] = self.osabi

        ehdr = struct.pack(
            "<16sHHIQQQIHHHHHH",
            bytes(e_ident),
            ET_REL,
            self.machine,
            EV_CURRENT,
            0,            # e_entry
            0,            # e_phoff
            shoff,        # e_shoff
            0,            # e_flags
            header_size,  # e_ehsize
            0,            # e_phentsize
            0,            # e_phnum
            64,           # e_shentsize (sizeof(Elf64_Shdr))
            len(self.sections),  # e_shnum
            self.shstrtab_idx    # e_shstrndx
        )

        out = bytearray(ehdr)

        # 6. Grava os dados de cada seção
        for sec in self.sections:
            if sec.sec_type == SHT_NULL:
                continue
            # Preenche padding se necessário
            while len(out) < sec.file_offset:
                out.append(0)
            if sec.sec_type != SHT_NOBITS:
                out.extend(sec.data)

        # Preenche padding para o Section Header Table
        while len(out) < shoff:
            out.append(0)

        # 7. Grava a tabela de Section Headers (64 bytes cada)
        for sec in self.sections:
            sec_len = len(sec.data) if sec.sec_type != SHT_NOBITS else 0
            shdr = struct.pack(
                "<IIQQQQIIQQ",
                sec.name_offset,
                sec.sec_type,
                sec.flags,
                0,                # sh_addr
                sec.file_offset,  # sh_offset
                sec_len,          # sh_size
                sec.link,         # sh_link
                sec.info,         # sh_info
                sec.addr_align,   # sh_addralign
                sec.ent_size      # sh_entsize
            )
            out.extend(shdr)

        return bytes(out)

    def write_to_file(self, filename: str) -> None:
        """Grava o binário ELF diretamente no caminho especificado."""
        data = self.build_bytes()
        with open(filename, "wb") as f:
            f.write(data)
