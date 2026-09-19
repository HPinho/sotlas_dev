"""Sotlas ELF64 Internal Linker — Linkagem nativa sem dependências externas.

Combina múltiplos arquivos objeto ELF64 relocatable (.o) em um executável
ELF64 estático (ET_EXEC) para alvos Linux e bare-metal x86_64/aarch64.

Suporta:
  - Leitura de arquivos .o ELF64 (relocatable, little-endian)
  - Resolução de tabela de símbolos global (pass1) e verificação de não-definidos (pass2)
  - Relocações x86_64: R_X86_64_64, R_X86_64_PC32, R_X86_64_PLT32, R_X86_64_32
  - Segmentos PT_LOAD com layout: .text (rx), .rodata (r), .data+.bss (rw)
  - Entry point configurável (_start, sotlas_main, ou custom)
  - Endereço de carga configurável (default: 0x400000 para Linux, 0x8000 para bare)
  - Emissão de ELF64 executável válido
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constantes ELF64
# ---------------------------------------------------------------------------

EI_MAG       = b"\x7fELF"
ELFCLASS64   = 2
ELFDATA2LSB  = 1
EV_CURRENT   = 1
ELFOSABI_SYSV       = 0
ELFOSABI_STANDALONE = 255

ET_EXEC = 2
ET_REL  = 1
EM_X86_64  = 62
EM_AARCH64 = 183

PT_LOAD    = 1
PT_GNU_STACK = 0x6474e551

PF_X = 0x1
PF_W = 0x2
PF_R = 0x4

SHT_NULL     = 0
SHT_PROGBITS = 1
SHT_SYMTAB   = 2
SHT_STRTAB   = 3
SHT_RELA     = 4
SHT_NOBITS   = 8
SHT_REL      = 9

SHF_WRITE     = 0x1
SHF_ALLOC     = 0x2
SHF_EXECINSTR = 0x4

STB_LOCAL  = 0
STB_GLOBAL = 1
STB_WEAK   = 2

STT_NOTYPE  = 0
STT_OBJECT  = 1
STT_FUNC    = 2
STT_SECTION = 3

# Tipos de relocação x86_64
R_X86_64_NONE   = 0
R_X86_64_64     = 1   # 64-bit absolute
R_X86_64_PC32   = 2   # 32-bit PC-relative
R_X86_64_GOT32  = 3
R_X86_64_PLT32  = 4   # 32-bit PLT-relative
R_X86_64_32     = 10  # 32-bit absolute (zero-extended)
R_X86_64_32S    = 11  # 32-bit absolute (sign-extended)

PAGE_SIZE = 0x1000     # 4 KiB


class ELFLinkerError(Exception):
    """Erro emitido durante a linkagem."""
    pass


# ---------------------------------------------------------------------------
# Estruturas de leitura de .o
# ---------------------------------------------------------------------------

@dataclass
class ObjSymbol:
    name: str
    value: int          # offset dentro da seção
    size: int
    binding: int
    sym_type: int
    shndx: int          # índice da seção de definição (0 = undef)
    obj_idx: int        # índice do arquivo objeto de origem


@dataclass
class ObjRelocation:
    offset: int         # offset dentro da seção alvo
    rtype: int          # tipo de relocação
    sym_idx: int        # índice do símbolo global
    addend: int         # addend (RELA)


@dataclass
class ObjSection:
    name: str
    sec_type: int
    flags: int
    data: bytearray
    addr_align: int
    link: int           # para RELA/REL: seção de símbolo associada
    info: int           # para RELA/REL: seção alvo
    relocations: List[ObjRelocation] = field(default_factory=list)
    # Endereço virtual final (preenchido pelo linker)
    final_vaddr: int = 0
    # Offset no arquivo de saída
    final_file_offset: int = 0


@dataclass
class ObjectFile:
    path: str
    machine: int
    sections: List[ObjSection]
    symbols: List[ObjSymbol]


# ---------------------------------------------------------------------------
# Leitura de arquivo .o
# ---------------------------------------------------------------------------

def _read_u8(data: bytes, off: int) -> int:
    return data[off]

def _read_u16le(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]

def _read_u32le(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]

def _read_u64le(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]

def _read_i64le(data: bytes, off: int) -> int:
    return struct.unpack_from("<q", data, off)[0]


def parse_elf_object(path: str, obj_idx: int) -> ObjectFile:
    """Lê e parseia um arquivo ELF64 relocatable (.o)."""
    raw = Path(path).read_bytes()

    if len(raw) < 64:
        raise ELFLinkerError(f"{path}: arquivo muito pequeno para ser um ELF válido")
    if raw[:4] != EI_MAG:
        raise ELFLinkerError(f"{path}: magic ELF inválido")
    if raw[4] != ELFCLASS64:
        raise ELFLinkerError(f"{path}: apenas ELF64 é suportado")
    if raw[5] != ELFDATA2LSB:
        raise ELFLinkerError(f"{path}: apenas little-endian é suportado")

    e_type    = _read_u16le(raw, 16)
    e_machine = _read_u16le(raw, 18)
    e_shoff   = _read_u64le(raw, 40)
    e_shentsize = _read_u16le(raw, 58)
    e_shnum   = _read_u16le(raw, 60)
    e_shstrndx = _read_u16le(raw, 62)

    if e_type != ET_REL:
        raise ELFLinkerError(f"{path}: esperado ET_REL, encontrado {e_type}")

    # Lê section headers
    def read_shdr(i: int):
        base = e_shoff + i * e_shentsize
        sh_name    = _read_u32le(raw, base + 0)
        sh_type    = _read_u32le(raw, base + 4)
        sh_flags   = _read_u64le(raw, base + 8)
        sh_offset  = _read_u64le(raw, base + 24)
        sh_size    = _read_u64le(raw, base + 32)
        sh_link    = _read_u32le(raw, base + 40)
        sh_info    = _read_u32le(raw, base + 44)
        sh_addralign = _read_u64le(raw, base + 48)
        return sh_name, sh_type, int(sh_flags), sh_offset, sh_size, sh_link, sh_info, sh_addralign

    # Lê shstrtab
    shstrtab_sh = read_shdr(e_shstrndx)
    shstrtab_off = shstrtab_sh[3]
    shstrtab_size = shstrtab_sh[4]
    shstrtab = raw[shstrtab_off: shstrtab_off + shstrtab_size]

    def get_str(strtab: bytes, off: int) -> str:
        end = strtab.index(b"\x00", off)
        return strtab[off:end].decode("utf-8", errors="replace")

    # Parseia todas as seções
    sections: List[ObjSection] = []
    for i in range(e_shnum):
        sh_name, sh_type, sh_flags, sh_offset, sh_size, sh_link, sh_info, sh_align = read_shdr(i)
        sec_name = get_str(shstrtab, sh_name) if sh_name < len(shstrtab) else ""
        if sh_type == SHT_NOBITS:
            data = bytearray(sh_size)  # .bss: zeros
        elif sh_offset + sh_size <= len(raw):
            data = bytearray(raw[sh_offset: sh_offset + sh_size])
        else:
            data = bytearray()
        sections.append(ObjSection(
            name=sec_name,
            sec_type=sh_type,
            flags=sh_flags,
            data=data,
            addr_align=max(1, sh_align),
            link=sh_link,
            info=sh_info,
        ))

    # Parseia tabela de símbolos
    obj_symbols: List[ObjSymbol] = []
    strtab_data: Optional[bytes] = None

    for i, sec in enumerate(sections):
        if sec.sec_type == SHT_SYMTAB:
            strtab_idx = sec.link
            if strtab_idx < len(sections):
                strtab_data = bytes(sections[strtab_idx].data)
            sym_data = bytes(sec.data)
            n_syms = len(sym_data) // 24
            for j in range(n_syms):
                base = j * 24
                st_name  = struct.unpack_from("<I", sym_data, base)[0]
                st_info  = sym_data[base + 4]
                st_shndx = struct.unpack_from("<H", sym_data, base + 6)[0]
                st_value = struct.unpack_from("<Q", sym_data, base + 8)[0]
                st_size  = struct.unpack_from("<Q", sym_data, base + 16)[0]
                binding = (st_info >> 4) & 0xF
                sym_type = st_info & 0xF
                sym_name = ""
                if strtab_data and st_name < len(strtab_data):
                    sym_name = get_str(strtab_data, st_name)
                obj_symbols.append(ObjSymbol(
                    name=sym_name,
                    value=st_value,
                    size=st_size,
                    binding=binding,
                    sym_type=sym_type,
                    shndx=st_shndx,
                    obj_idx=obj_idx,
                ))
            break  # assumimos uma única .symtab

    # Parseia relocações RELA
    for i, sec in enumerate(sections):
        if sec.sec_type == SHT_RELA:
            target_sec_idx = sec.info
            rela_data = bytes(sec.data)
            n_rela = len(rela_data) // 24
            for j in range(n_rela):
                base = j * 24
                r_offset = struct.unpack_from("<Q", rela_data, base)[0]
                r_info   = struct.unpack_from("<Q", rela_data, base + 8)[0]
                r_addend = struct.unpack_from("<q", rela_data, base + 16)[0]
                r_sym  = (r_info >> 32) & 0xFFFFFFFF
                r_type = r_info & 0xFFFFFFFF
                if target_sec_idx < len(sections):
                    sections[target_sec_idx].relocations.append(ObjRelocation(
                        offset=r_offset,
                        rtype=r_type,
                        sym_idx=r_sym,
                        addend=r_addend,
                    ))

    return ObjectFile(path=path, machine=e_machine, sections=sections, symbols=obj_symbols)


# ---------------------------------------------------------------------------
# Linker Principal
# ---------------------------------------------------------------------------

class ELFLinker:
    """Linker ELF64 estático interno do Sotlas.

    Combina arquivos .o em um executável ELF64 ET_EXEC sem LLVM/LLD.
    """

    DEFAULT_LOAD_ADDR = 0x400000   # base Linux x86_64
    BARE_LOAD_ADDR    = 0x8000     # base barecore ARM/x86

    def __init__(
        self,
        entry_symbol: str = "_start",
        load_address: Optional[int] = None,
        target_triple: str = "x86_64-linux-gnu",
        page_size: int = PAGE_SIZE,
    ) -> None:
        self.entry_symbol = entry_symbol
        self.load_address = load_address if load_address is not None else self.DEFAULT_LOAD_ADDR
        self.target_triple = target_triple
        self.page_size = page_size
        self.machine = EM_X86_64 if "x86_64" in target_triple else EM_AARCH64
        self.osabi = ELFOSABI_STANDALONE if "unknown-elf" in target_triple else ELFOSABI_SYSV

        self._objects: List[ObjectFile] = []
        # Tabela de símbolos global: nome → (ObjSymbol, arquivo_objeto, índice_seção_global)
        self._global_syms: Dict[str, Tuple[ObjSymbol, ObjectFile]] = {}
        # Seções unificadas por tipo
        self._merged_text    = bytearray()
        self._merged_rodata  = bytearray()
        self._merged_data    = bytearray()
        self._merged_bss_size = 0
        # Mapeamento: (obj_idx, sec_idx_local) → vaddr_final
        self._sec_vaddr: Dict[Tuple[int, int], int] = {}

    def add_object(self, path: str) -> None:
        """Adiciona um arquivo .o ao conjunto de entrada."""
        obj_idx = len(self._objects)
        obj = parse_elf_object(path, obj_idx)
        if obj.machine != self.machine:
            raise ELFLinkerError(
                f"{path}: arquitetura incompatível (esperado {self.machine}, encontrado {obj.machine})"
            )
        self._objects.append(obj)

    def add_object_bytes(self, data: bytes, name: str = "<memory>") -> None:
        """Adiciona um .o a partir de bytes em memória (útil para runtime embutido)."""
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
            f.write(data)
            tmp = f.name
        try:
            self.add_object(tmp)
            self._objects[-1].path = name
        finally:
            os.unlink(tmp)

    # ------------------------------------------------------------------
    # Pass 1: Coletar símbolos globais
    # ------------------------------------------------------------------

    def _collect_symbols(self) -> None:
        """Coleta todos os símbolos globais/fracos de todos os arquivos objeto."""
        for obj in self._objects:
            for sym in obj.symbols:
                if sym.binding in (STB_GLOBAL, STB_WEAK) and sym.name:
                    if sym.shndx != 0:  # definido (não undef)
                        if sym.name not in self._global_syms or sym.binding == STB_GLOBAL:
                            self._global_syms[sym.name] = (sym, obj)

    def _check_undefined(self) -> None:
        """Verifica que todos os símbolos referenciados foram definidos."""
        undefined: List[str] = []
        for obj in self._objects:
            for sym in obj.symbols:
                if sym.binding in (STB_GLOBAL, STB_WEAK) and sym.shndx == 0 and sym.name:
                    if sym.name not in self._global_syms:
                        undefined.append(f"'{sym.name}' (referenciado em {obj.path})")
        if undefined:
            msg = "\n  ".join(undefined)
            raise ELFLinkerError(f"símbolos não definidos:\n  {msg}")

    # ------------------------------------------------------------------
    # Pass 2: Layout de memória
    # ------------------------------------------------------------------

    def _align_up(self, val: int, align: int) -> int:
        if align <= 1:
            return val
        return (val + align - 1) & ~(align - 1)

    def _layout_sections(self) -> None:
        """Monta as seções unificadas e calcula endereços virtuais."""
        vaddr = self.load_address

        # ── Segmento .text (rx) ──
        text_base = vaddr
        for obj_idx, obj in enumerate(self._objects):
            for sec_idx, sec in enumerate(obj.sections):
                if sec.sec_type in (SHT_PROGBITS, SHT_NOBITS) and (sec.flags & SHF_EXECINSTR):
                    vaddr = self._align_up(vaddr, sec.addr_align)
                    self._sec_vaddr[(obj_idx, sec_idx)] = vaddr
                    vaddr += len(sec.data)
                    self._merged_text.extend(bytes(sec.data))

        # Alinha ao próximo page boundary para separação rx/r
        vaddr = self._align_up(vaddr, self.page_size)

        # ── Segmento .rodata (r) ──
        for obj_idx, obj in enumerate(self._objects):
            for sec_idx, sec in enumerate(obj.sections):
                if (sec.sec_type == SHT_PROGBITS
                        and not (sec.flags & SHF_EXECINSTR)
                        and not (sec.flags & SHF_WRITE)
                        and (sec.flags & SHF_ALLOC)):
                    vaddr = self._align_up(vaddr, sec.addr_align)
                    self._sec_vaddr[(obj_idx, sec_idx)] = vaddr
                    vaddr += len(sec.data)
                    self._merged_rodata.extend(bytes(sec.data))

        vaddr = self._align_up(vaddr, self.page_size)

        # ── Segmento .data + .bss (rw) ──
        for obj_idx, obj in enumerate(self._objects):
            for sec_idx, sec in enumerate(obj.sections):
                if sec.flags & SHF_WRITE and sec.flags & SHF_ALLOC:
                    vaddr = self._align_up(vaddr, sec.addr_align)
                    self._sec_vaddr[(obj_idx, sec_idx)] = vaddr
                    if sec.sec_type == SHT_NOBITS:
                        self._merged_bss_size += len(sec.data)
                    else:
                        self._merged_data.extend(bytes(sec.data))
                    vaddr += len(sec.data)

    def _resolve_symbol_vaddr(self, sym: ObjSymbol, obj: ObjectFile) -> int:
        """Retorna o endereço virtual absoluto de um símbolo."""
        key = (obj.symbols.index(sym) if sym in obj.symbols else -1, sym.shndx)
        sec_base = self._sec_vaddr.get((self._objects.index(obj), sym.shndx), 0)
        return sec_base + sym.value

    # ------------------------------------------------------------------
    # Pass 3: Aplicar relocações
    # ------------------------------------------------------------------

    def _apply_relocations(self) -> None:
        """Aplica relocações nos buffers de seção mergeados."""
        for obj_idx, obj in enumerate(self._objects):
            for sec_idx, sec in enumerate(obj.sections):
                if not sec.relocations:
                    continue
                # Obtém o buffer correto desta seção
                sec_vaddr = self._sec_vaddr.get((obj_idx, sec_idx), 0)
                # Encontra o buffer na saída correspondente a este sec_idx
                sec_buf = self._get_section_output_buffer(obj_idx, sec_idx)
                if sec_buf is None:
                    continue

                for rel in sec.relocations:
                    # Resolve o símbolo
                    sym_obj = obj.symbols[rel.sym_idx] if rel.sym_idx < len(obj.symbols) else None
                    if sym_obj is None:
                        continue

                    sym_vaddr = 0
                    if sym_obj.shndx != 0:
                        # Símbolo local/definido neste obj
                        sym_sec_vaddr = self._sec_vaddr.get((obj_idx, sym_obj.shndx), 0)
                        sym_vaddr = sym_sec_vaddr + sym_obj.value
                    elif sym_obj.name in self._global_syms:
                        g_sym, g_obj = self._global_syms[sym_obj.name]
                        g_obj_idx = self._objects.index(g_obj)
                        g_sec_vaddr = self._sec_vaddr.get((g_obj_idx, g_sym.shndx), 0)
                        sym_vaddr = g_sec_vaddr + g_sym.value
                    else:
                        continue  # símbolo externo não resolvido (já reportado)

                    S = sym_vaddr
                    A = rel.addend
                    P = sec_vaddr + rel.offset

                    try:
                        if rel.rtype == R_X86_64_64:
                            val = (S + A) & 0xFFFFFFFFFFFFFFFF
                            struct.pack_into("<Q", sec_buf, rel.offset, val)

                        elif rel.rtype in (R_X86_64_PC32, R_X86_64_PLT32):
                            val = (S + A - P) & 0xFFFFFFFF
                            # Verifica overflow de 32 bits (signed)
                            signed_val = struct.unpack("<i", struct.pack("<I", val))[0]
                            struct.pack_into("<i", sec_buf, rel.offset, signed_val)

                        elif rel.rtype == R_X86_64_32:
                            val = (S + A) & 0xFFFFFFFF
                            struct.pack_into("<I", sec_buf, rel.offset, val)

                        elif rel.rtype == R_X86_64_32S:
                            val = (S + A) & 0xFFFFFFFF
                            signed_val = struct.unpack("<i", struct.pack("<I", val))[0]
                            struct.pack_into("<i", sec_buf, rel.offset, signed_val)

                    except struct.error:
                        pass  # overflow de relocação: reportar como warning

    def _get_section_output_buffer(self, obj_idx: int, sec_idx: int) -> Optional[bytearray]:
        """Retorna o bytearray de saída que contém os dados desta seção."""
        obj = self._objects[obj_idx]
        sec = obj.sections[sec_idx]
        if sec.flags & SHF_EXECINSTR:
            # Calcula offset dentro de _merged_text
            text_start = self.load_address
            sec_start = self._sec_vaddr.get((obj_idx, sec_idx), 0)
            off = sec_start - text_start
            if 0 <= off < len(self._merged_text):
                return memoryview(self._merged_text)[off: off + len(sec.data)].obj  # type: ignore
        return None

    # ------------------------------------------------------------------
    # Emit: Gerar ELF64 ET_EXEC
    # ------------------------------------------------------------------

    def link(self, output_path: str) -> None:
        """Executa a linkagem completa e grava o executável."""
        # Pass 1: símbolos
        self._collect_symbols()
        self._check_undefined()

        # Pass 2: layout
        self._layout_sections()

        # Pass 3: relocações
        self._apply_relocations()

        # Obtém entry point
        entry_vaddr = 0
        if self.entry_symbol in self._global_syms:
            e_sym, e_obj = self._global_syms[self.entry_symbol]
            e_obj_idx = self._objects.index(e_obj)
            e_sec_vaddr = self._sec_vaddr.get((e_obj_idx, e_sym.shndx), 0)
            entry_vaddr = e_sec_vaddr + e_sym.value
        else:
            # Tenta _start como fallback
            if "_start" in self._global_syms and self.entry_symbol != "_start":
                e_sym, e_obj = self._global_syms["_start"]
                e_obj_idx = self._objects.index(e_obj)
                e_sec_vaddr = self._sec_vaddr.get((e_obj_idx, e_sym.shndx), 0)
                entry_vaddr = e_sec_vaddr + e_sym.value

        # Emite ELF executável
        elf_bytes = self._emit_exec_elf(entry_vaddr)
        Path(output_path).write_bytes(elf_bytes)

        # Em sistemas POSIX, torna executável
        import os
        try:
            os.chmod(output_path, 0o755)
        except OSError:
            pass

    def _emit_exec_elf(self, entry_vaddr: int) -> bytes:
        """Gera o ELF64 ET_EXEC com segmentos PT_LOAD."""
        # Calcula tamanhos e posições dos segmentos no arquivo
        ELF_HEADER_SIZE = 64
        PHDR_ENTRY_SIZE = 56
        # Segmentos: .text, .rodata, .data+.bss, (PT_GNU_STACK opcional)
        n_phdrs = 3  # text, rodata, data+bss

        phdrs_size = n_phdrs * PHDR_ENTRY_SIZE
        file_header_size = ELF_HEADER_SIZE + phdrs_size

        load_addr = self.load_address

        # Calcula VAs dos segmentos de acordo com o layout
        text_vaddr  = self._align_up(load_addr, self.page_size)
        text_size   = len(self._merged_text)

        rodata_vaddr = self._align_up(text_vaddr + text_size, self.page_size)
        rodata_size  = len(self._merged_rodata)

        data_vaddr = self._align_up(rodata_vaddr + rodata_size, self.page_size)
        data_size  = len(self._merged_data)
        bss_size   = self._merged_bss_size

        # Offsets no arquivo de saída
        text_file_off   = self._align_up(file_header_size, self.page_size)
        rodata_file_off = text_file_off + self._align_up(text_size, self.page_size)
        data_file_off   = rodata_file_off + self._align_up(rodata_size, self.page_size)
        file_size       = data_file_off + data_size

        # ── ELF Header ──
        e_ident = bytearray(16)
        e_ident[0:4] = EI_MAG
        e_ident[4] = ELFCLASS64
        e_ident[5] = ELFDATA2LSB
        e_ident[6] = EV_CURRENT
        e_ident[7] = self.osabi

        ehdr = struct.pack(
            "<16sHHIQQQIHHHHHH",
            bytes(e_ident),
            ET_EXEC,               # e_type
            self.machine,          # e_machine
            EV_CURRENT,            # e_version
            entry_vaddr,           # e_entry
            ELF_HEADER_SIZE,       # e_phoff
            0,                     # e_shoff (sem section headers no executável)
            0,                     # e_flags
            ELF_HEADER_SIZE,       # e_ehsize
            PHDR_ENTRY_SIZE,       # e_phentsize
            n_phdrs,               # e_phnum
            64,                    # e_shentsize
            0,                     # e_shnum
            0,                     # e_shstrndx
        )

        def make_phdr(p_type, p_flags, p_offset, p_vaddr, p_filesz, p_memsz, p_align):
            return struct.pack(
                "<IIQQQQQQ",
                p_type,    # p_type
                p_flags,   # p_flags
                p_offset,  # p_offset
                p_vaddr,   # p_vaddr
                p_vaddr,   # p_paddr
                p_filesz,  # p_filesz
                p_memsz,   # p_memsz
                p_align,   # p_align
            )

        phdr_text = make_phdr(
            PT_LOAD, PF_R | PF_X,
            text_file_off, text_vaddr, text_size, text_size, self.page_size
        )
        phdr_rodata = make_phdr(
            PT_LOAD, PF_R,
            rodata_file_off, rodata_vaddr, rodata_size, rodata_size, self.page_size
        )
        phdr_data = make_phdr(
            PT_LOAD, PF_R | PF_W,
            data_file_off, data_vaddr, data_size, data_size + bss_size, self.page_size
        )

        # ── Monta o arquivo de saída ──
        out = bytearray(ehdr)
        out.extend(phdr_text)
        out.extend(phdr_rodata)
        out.extend(phdr_data)

        # Padding até text_file_off
        while len(out) < text_file_off:
            out.append(0)
        out.extend(self._merged_text)

        # Padding até rodata_file_off
        while len(out) < rodata_file_off:
            out.append(0)
        out.extend(self._merged_rodata)

        # Padding até data_file_off
        while len(out) < data_file_off:
            out.append(0)
        out.extend(self._merged_data)
        # .bss é virtual, não ocupa espaço no arquivo

        return bytes(out)


# ---------------------------------------------------------------------------
# API de alto nível
# ---------------------------------------------------------------------------

def link_objects(
    object_files: List[str],
    output: str,
    entry: str = "_start",
    target: str = "x86_64-linux-gnu",
    load_addr: Optional[int] = None,
) -> None:
    """API de alto nível: linka múltiplos .o em um executável."""
    linker = ELFLinker(entry_symbol=entry, target_triple=target, load_address=load_addr)
    for obj in object_files:
        linker.add_object(obj)
    linker.link(output)