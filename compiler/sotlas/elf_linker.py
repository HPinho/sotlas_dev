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
        if (
            not isinstance(page_size, int)
            or isinstance(page_size, bool)
            or page_size < 1
            or page_size & (page_size - 1)
        ):
            raise ELFLinkerError("ELF page size must be a positive power of two")
        if not isinstance(load_address, (int, type(None))) or (
            isinstance(load_address, bool)
            or (load_address is not None and load_address < 0)
        ):
            raise ELFLinkerError("ELF load address must be a non-negative integer")
        if not isinstance(entry_symbol, str) or not entry_symbol:
            raise ELFLinkerError("ELF entry symbol must be a non-empty name")
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
        self._text_vaddr = 0
        self._rodata_vaddr = 0
        self._data_vaddr = 0

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
        self._global_syms.clear()
        for obj in self._objects:
            for sym in obj.symbols:
                if sym.binding in (STB_GLOBAL, STB_WEAK) and sym.name:
                    if sym.shndx != 0:  # definido (não undef)
                        previous = self._global_syms.get(sym.name)
                        if sym.binding == STB_GLOBAL:
                            if previous is not None and previous[0].binding == STB_GLOBAL:
                                raise ELFLinkerError(
                                    f"duplicate strong symbol {sym.name!r} in "
                                    f"{previous[1].path} and {obj.path}"
                                )
                            self._global_syms[sym.name] = (sym, obj)
                        elif previous is None:
                            self._global_syms[sym.name] = (sym, obj)

    def _check_undefined(self) -> None:
        """Verifica que todos os símbolos referenciados foram definidos."""
        undefined: set[str] = set()
        for obj in self._objects:
            for sym in obj.symbols:
                if sym.binding in (STB_GLOBAL, STB_WEAK) and sym.shndx == 0 and sym.name:
                    if sym.name not in self._global_syms:
                        undefined.add(f"'{sym.name}' (referenciado em {obj.path})")
        if undefined:
            msg = "\n  ".join(sorted(undefined))
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
        self._merged_text.clear()
        self._merged_rodata.clear()
        self._merged_data.clear()
        self._merged_bss_size = 0
        self._sec_vaddr.clear()

        for obj_idx, obj in enumerate(self._objects):
            for sec in obj.sections:
                if not (sec.flags & SHF_ALLOC):
                    continue
                if (
                    not isinstance(sec.addr_align, int)
                    or sec.addr_align < 1
                    or sec.addr_align & (sec.addr_align - 1)
                ):
                    raise ELFLinkerError(
                        f"{obj.path}:{sec.name}: section alignment must be a power of two"
                    )
                if sec.flags & SHF_EXECINSTR:
                    if sec.sec_type != SHT_PROGBITS or sec.flags & SHF_WRITE:
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: executable load sections must be read-only PROGBITS"
                        )
                elif sec.flags & SHF_WRITE:
                    if sec.sec_type not in (SHT_PROGBITS, SHT_NOBITS):
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: writable load section has unsupported type {sec.sec_type}"
                        )
                elif sec.sec_type != SHT_PROGBITS:
                    raise ELFLinkerError(
                        f"{obj.path}:{sec.name}: read-only load section must be PROGBITS"
                    )

        def append_sections(predicate, buffer: bytearray, base: int, vaddr: int) -> int:
            for obj_idx, obj in enumerate(self._objects):
                for sec_idx, sec in enumerate(obj.sections):
                    if not (sec.flags & SHF_ALLOC) or not predicate(sec):
                        continue
                    aligned = self._align_up(vaddr, sec.addr_align)
                    buffer_offset = aligned - base
                    if buffer_offset < len(buffer):
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: overlapping section layout"
                        )
                    buffer.extend(bytes(buffer_offset - len(buffer)))
                    self._sec_vaddr[(obj_idx, sec_idx)] = aligned
                    buffer.extend(sec.data)
                    vaddr = aligned + len(sec.data)
            return vaddr

        self._text_vaddr = self._align_up(self.load_address, self.page_size)
        vaddr = append_sections(
            lambda sec: bool(sec.flags & SHF_EXECINSTR),
            self._merged_text,
            self._text_vaddr,
            self._text_vaddr,
        )

        self._rodata_vaddr = self._align_up(vaddr, self.page_size)
        vaddr = append_sections(
            lambda sec: not (sec.flags & SHF_EXECINSTR)
            and not (sec.flags & SHF_WRITE),
            self._merged_rodata,
            self._rodata_vaddr,
            self._rodata_vaddr,
        )

        self._data_vaddr = self._align_up(vaddr, self.page_size)
        vaddr = append_sections(
            lambda sec: bool(sec.flags & SHF_WRITE)
            and sec.sec_type == SHT_PROGBITS,
            self._merged_data,
            self._data_vaddr,
            self._data_vaddr,
        )
        bss_start = vaddr
        for obj_idx, obj in enumerate(self._objects):
            for sec_idx, sec in enumerate(obj.sections):
                if not (
                    sec.flags & SHF_ALLOC
                    and sec.flags & SHF_WRITE
                    and sec.sec_type == SHT_NOBITS
                ):
                    continue
                aligned = self._align_up(vaddr, sec.addr_align)
                self._sec_vaddr[(obj_idx, sec_idx)] = aligned
                vaddr = aligned + len(sec.data)
        self._merged_bss_size = vaddr - bss_start

    def _resolve_symbol_vaddr(self, sym: ObjSymbol, obj: ObjectFile) -> int:
        """Retorna o endereço virtual absoluto de um símbolo."""
        if sym.shndx == 0xFFF1:  # SHN_ABS
            return sym.value
        if not 0 < sym.shndx < len(obj.sections):
            raise ELFLinkerError(
                f"{obj.path}: symbol {sym.name!r} has invalid section index {sym.shndx}"
            )
        obj_idx = self._objects.index(obj)
        sec_vaddr = self._sec_vaddr.get((obj_idx, sym.shndx))
        if sec_vaddr is None:
            raise ELFLinkerError(
                f"{obj.path}: symbol {sym.name!r} refers to a non-loadable section"
            )
        if sym.value > len(obj.sections[sym.shndx].data):
            raise ELFLinkerError(
                f"{obj.path}: symbol {sym.name!r} lies outside its section"
            )
        return sec_vaddr + sym.value

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
                    if not (sec.flags & SHF_ALLOC):
                        # Debug and other non-allocated sections are discarded.
                        continue
                    raise ELFLinkerError(
                        f"{obj.path}:{sec.name}: relocation targets a non-file-backed load section"
                    )

                for rel in sec.relocations:
                    # Resolve o símbolo
                    sym_obj = obj.symbols[rel.sym_idx] if rel.sym_idx < len(obj.symbols) else None
                    if rel.rtype == R_X86_64_NONE:
                        continue
                    if (
                        sym_obj is None
                        or rel.sym_idx < 0
                        or rel.sym_idx >= len(obj.symbols)
                    ):
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: relocation references invalid symbol index {rel.sym_idx}"
                        )

                    if sym_obj.shndx == 0:
                        resolved = self._global_syms.get(sym_obj.name)
                        if resolved is None:
                            raise ELFLinkerError(
                                f"{obj.path}:{sec.name}: unresolved relocation symbol {sym_obj.name!r}"
                            )
                        sym_obj, sym_owner = resolved
                    else:
                        sym_owner = obj

                    S = self._resolve_symbol_vaddr(sym_obj, sym_owner)
                    A = rel.addend
                    P = sec_vaddr + rel.offset
                    widths = {
                        R_X86_64_64: 8,
                        R_X86_64_PC32: 4,
                        R_X86_64_PLT32: 4,
                        R_X86_64_32: 4,
                        R_X86_64_32S: 4,
                    }
                    width = widths.get(rel.rtype)
                    if width is None:
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: unsupported x86-64 relocation type {rel.rtype}"
                        )
                    if rel.offset < 0 or rel.offset + width > len(sec.data):
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: relocation at offset {rel.offset} exceeds section bounds"
                        )
                    if sec_buf is None:
                        raise ELFLinkerError(
                            f"{obj.path}:{sec.name}: relocation targets a non-file-backed section"
                        )

                    if rel.rtype == R_X86_64_64:
                        value = S + A
                        if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
                            raise ELFLinkerError(
                                f"{obj.path}:{sec.name}: R_X86_64_64 relocation overflow"
                            )
                        struct.pack_into("<Q", sec_buf, rel.offset, value)
                    elif rel.rtype in (R_X86_64_PC32, R_X86_64_PLT32):
                        value = S + A - P
                        if not -(1 << 31) <= value < (1 << 31):
                            raise ELFLinkerError(
                                f"{obj.path}:{sec.name}: PC-relative relocation overflow"
                            )
                        struct.pack_into("<i", sec_buf, rel.offset, value)
                    elif rel.rtype == R_X86_64_32:
                        value = S + A
                        if not 0 <= value <= 0xFFFFFFFF:
                            raise ELFLinkerError(
                                f"{obj.path}:{sec.name}: R_X86_64_32 relocation overflow"
                            )
                        struct.pack_into("<I", sec_buf, rel.offset, value)
                    else:  # R_X86_64_32S
                        value = S + A
                        if not -(1 << 31) <= value < (1 << 31):
                            raise ELFLinkerError(
                                f"{obj.path}:{sec.name}: R_X86_64_32S relocation overflow"
                            )
                        struct.pack_into("<i", sec_buf, rel.offset, value)

    def _get_section_output_buffer(self, obj_idx: int, sec_idx: int):
        """Return a writable view of the merged output bytes for a section."""
        obj = self._objects[obj_idx]
        sec = obj.sections[sec_idx]
        section_vaddr = self._sec_vaddr.get((obj_idx, sec_idx))
        if section_vaddr is None:
            return None
        if sec.flags & SHF_EXECINSTR:
            buffer = self._merged_text
            base = self._text_vaddr
        elif sec.flags & SHF_WRITE:
            if sec.sec_type == SHT_NOBITS:
                return None
            buffer = self._merged_data
            base = self._data_vaddr
        else:
            buffer = self._merged_rodata
            base = self._rodata_vaddr
        offset = section_vaddr - base
        end = offset + len(sec.data)
        if 0 <= offset <= end <= len(buffer):
            return memoryview(buffer)[offset:end]
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

        # Resolve the requested entry exactly; never alias it to another symbol.
        entry = self._global_syms.get(self.entry_symbol)
        if entry is None:
            raise ELFLinkerError(
                f"entry symbol {self.entry_symbol!r} is not defined"
            )
        entry_symbol, entry_obj = entry
        if not 0 < entry_symbol.shndx < len(entry_obj.sections):
            raise ELFLinkerError(
                f"entry symbol {self.entry_symbol!r} is not defined in a loadable section"
            )
        entry_section = entry_obj.sections[entry_symbol.shndx]
        if not (entry_section.flags & SHF_EXECINSTR):
            raise ELFLinkerError(
                f"entry symbol {self.entry_symbol!r} is not in an executable section"
            )
        if not 0 <= entry_symbol.value < len(entry_section.data):
            raise ELFLinkerError(
                f"entry symbol {self.entry_symbol!r} lies outside executable section"
            )
        entry_vaddr = self._resolve_symbol_vaddr(entry_symbol, entry_obj)

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

        # Use the same section bases that symbol resolution and relocation used.
        text_vaddr  = self._text_vaddr
        text_size   = len(self._merged_text)

        rodata_vaddr = self._rodata_vaddr
        rodata_size  = len(self._merged_rodata)

        data_vaddr = self._data_vaddr
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
