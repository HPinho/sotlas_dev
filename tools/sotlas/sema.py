"""Sotlas Sema — Analisador Semântico e Verificador de Tipos (duas passagens)."""
from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from .token_types import TK, PRIMITIVE_TOKENS
from .ast_nodes import *


class SotlasSemaError(Exception):
    def __init__(self, msg: str, span: Span, source: Optional[str] = None) -> None:
        self.raw_msg = msg
        self.span = span
        self.source = source
        super().__init__(self.format(source))

    def format(self, source: Optional[str] = None) -> str:
        src = source or self.source
        header = f"error: {self.raw_msg}\n  --> {self.span.file}:{self.span.line}:{self.span.col}"
        if not src and self.span.file and self.span.file not in ("<stdin>", "<test>"):
            try:
                from pathlib import Path
                p = Path(self.span.file)
                if p.is_file():
                    src = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if src and self.span.line > 0:
            lines = src.splitlines()
            if 0 < self.span.line <= len(lines):
                line_str = lines[self.span.line - 1]
                line_no = str(self.span.line)
                pad = " " * len(line_no)
                col_offset = max(0, self.span.col - 1)
                caret = " " * col_offset + "^~~~"
                return (
                    f"{header}\n"
                    f"{pad} |\n"
                    f"{line_no} | {line_str}\n"
                    f"{pad} | {caret}"
                )
        return header


TOPOLOGY_NAME_MAP: Dict[TK, str] = {
    TK.KW_RAWPHYS: "*rawphys",
    TK.KW_VIRTMAP: "*virtmap",
    TK.KW_PORTWIRE: "*portwire",
    TK.KW_DMAZONE: "*dmazone",
    TK.KW_VOIDZERO: "*voidzero",
    TK.KW_MUT: "*mut",
    TK.KW_CONST_MOD: "*const",
}


# ---------------------------------------------------------------------------
# Estados de Ownership (CFG Dataflow) e Efeitos de Hardware
# ---------------------------------------------------------------------------

class VarState(Enum):
    LIVE           = "live"
    MOVED          = "moved"
    MAYBE_MOVED    = "maybe_moved"
    BORROWED_IMMUT = "borrowed_immut"
    BORROWED_MUT   = "borrowed_mut"


class Effect(Enum):
    ALLOC    = "alloc"
    BLOCKING = "blocking"
    ASYNC    = "async"
    MMIO     = "mmio"
    DMA      = "dma"
    IRQ      = "irq"
    UNSAFE   = "unsafe"


class FlowContext:
    """Rastreia estados de variáveis e empréstimos em fluxos com ramificação (CFG)."""
    def __init__(self, parent: Optional["FlowContext"] = None) -> None:
        self.parent = parent
        self.var_states: Dict[str, VarState] = {}
        self.symbols: Dict[str, Symbol] = {}

    def define(self, sym: Symbol, initial_state: VarState = VarState.LIVE) -> None:
        self.symbols[sym.name] = sym
        self.var_states[sym.name] = initial_state

    def get_state(self, name: str) -> Optional[VarState]:
        if name in self.var_states:
            return self.var_states[name]
        if self.parent:
            return self.parent.get_state(name)
        return None

    def get_symbol(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.get_symbol(name)
        return None

    def set_state(self, name: str, state: VarState) -> None:
        curr: Optional["FlowContext"] = self
        while curr:
            if name in curr.var_states or name in curr.symbols:
                curr.var_states[name] = state
                sym = curr.symbols.get(name)
                if sym:
                    sym.is_moved = (state in (VarState.MOVED, VarState.MAYBE_MOVED))
                return
            curr = curr.parent
        self.var_states[name] = state

    def snapshot(self) -> Dict[str, VarState]:
        res: Dict[str, VarState] = {}
        if self.parent:
            res.update(self.parent.snapshot())
        res.update(self.var_states)
        return res

    def restore_and_merge(self, before: Dict[str, VarState], branch_snapshots: List[Dict[str, VarState]]) -> None:
        all_vars = set(before.keys())
        for snap in branch_snapshots:
            all_vars.update(snap.keys())

        for var in all_vars:
            initial = before.get(var, VarState.LIVE)
            branch_states = [snap.get(var, initial) for snap in branch_snapshots]

            if all(s == VarState.MOVED for s in branch_states):
                self.set_state(var, VarState.MOVED)
            elif any(s in (VarState.MOVED, VarState.MAYBE_MOVED) for s in branch_states):
                if initial not in (VarState.MOVED, VarState.MAYBE_MOVED):
                    self.set_state(var, VarState.MAYBE_MOVED)
                else:
                    self.set_state(var, VarState.MOVED)
            else:
                self.set_state(var, initial)


# ---------------------------------------------------------------------------
# Tabela de Símbolos
# ---------------------------------------------------------------------------

class Symbol:
    __slots__ = ("name", "kind", "type_node", "span", "is_island", "is_moved", "is_sole", "stack_origin", "bound")

    def __init__(self, name: str, kind: str, type_node: Optional[TypeNode],
                 span: Span, is_island: bool = False, is_moved: bool = False,
                 is_sole: bool = False, stack_origin: Optional[str] = None,
                 bound: Optional[str] = None) -> None:
        self.name = name
        self.kind = kind          # "var" | "let" | "fn" | "type" | "param"
        self.type_node = type_node
        self.span = span
        self.is_island = is_island
        self.is_moved = is_moved
        self.is_sole = is_sole
        self.stack_origin = stack_origin
        self.bound = bound


class Scope:
    def __init__(self, parent: Optional["Scope"] = None) -> None:
        self._parent = parent
        self._syms: Dict[str, Symbol] = {}

    def define(self, sym: Symbol) -> None:
        self._syms[sym.name] = sym

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self._syms:
            return self._syms[name]
        if self._parent:
            return self._parent.lookup(name)
        return None

    def child(self) -> "Scope":
        return Scope(self)


# ---------------------------------------------------------------------------
# Sema Principal
# ---------------------------------------------------------------------------

class Sema:
    """Verificador semântico de duas passagens.

    Passagem 1: coleta todas as declarações de topo (structs, classes, fns...).
    Passagem 2: verifica corpos de funções, tipos, SRG e regras barecore.
    """

    def __init__(self, ast: SourceFileNode, filename: str = "<stdin>", source: Optional[str] = None) -> None:
        self._ast = ast
        self._fn = filename
        self._source = source
        self._global = Scope()
        self._is_barecore = ast.is_barecore
        # Rastreamento SRG: nomes de variáveis 'island' atualmente activas
        self._island_vars: Set[str] = set()
        self._unsafe_depth: int = 0
        self._errors: List[SotlasSemaError] = []
        self._warnings: List[str] = []
        # Quando True, identificadores não resolvidos são aceitos (campo de self implícito)
        self._in_method: bool = False
        self._enums: Dict[str, EnumDeclNode] = {}
        self._structs: Dict[str, StructDeclNode] = {}
        self._specs: Dict[str, SpecDeclNode] = {}
        self._registers: Dict[str, RegisterDeclNode] = {}
        self._flow: FlowContext = FlowContext()
        self._current_effects: Set[Effect] = set()
        self._fn_effect_map: Dict[str, Set[Effect]] = {}
        self._is_system_fn: bool = False
        self._is_trapfn: bool = False
        self._is_irqfree_fn: bool = False
        self._is_async_fn: bool = False
        self._in_clinch: bool = False
        self._in_mould: bool = False
        self._functions: Dict[str, Union[FnDeclNode, TrapFnDeclNode]] = {}

    def _define_generic_param_in_scope(self, g: Any, scope: Scope, span: Span) -> None:
        if isinstance(g, GenericParam):
            if g.is_const:
                scope.define(Symbol(g.name, "const_generic", None, span))
            else:
                sym = Symbol(g.name, "type", None, span)
                sym.bound = getattr(g, "bound", None)
                scope.define(sym)
        elif isinstance(g, str):
            if g.startswith("const "):
                parts = g.split()
                p_name = parts[1].rstrip(":")
                scope.define(Symbol(p_name, "const_generic", None, span))
            else:
                scope.define(Symbol(g, "type", None, span))

    def _is_type_sole(self, type_node: Optional[TypeNode]) -> bool:
        if not type_node:
            return False
        if getattr(type_node, "ownership", None) == TK.KW_SOLE:
            return True
        if type_node.name and type_node.name in self._structs:
            return getattr(self._structs[type_node.name], "is_sole", False)
        return False

    @property
    def errors(self) -> List[SotlasSemaError]:
        return self._errors

    def check(self) -> None:
        self._pass1_collect()
        self._pass2_verify()
        if self._errors:
            raise self._errors[0]

    def _err(self, msg: str, span: Span) -> None:
        self._errors.append(SotlasSemaError(msg, span, self._source))

    # ------------------------------------------------------------------
    # Passagem 1: Coleta de Símbolos Globais
    # ------------------------------------------------------------------

    def _collect_imported_symbols(self) -> None:
        if not self._ast.imports:
            return
        from pathlib import Path
        from .lexer import Lexer
        from .parser import Parser

        cur_file = Path(self._fn).resolve() if self._fn and self._fn != "<stdin>" else Path.cwd()
        search_dirs = [cur_file.parent]
        for parent in cur_file.parents:
            search_dirs.append(parent)
            search_dirs.append(parent / "src")
            search_dirs.append(parent / "kernel" / "src")
            search_dirs.append(parent / "libbkn" / "src")
            search_dirs.append(parent / "boot")

        visited_files = set()
        for imp in self._ast.imports:
            mod_name = imp.path[-1]
            mod_path_str = "/".join(imp.path)
            target_file = None
            for d in search_dirs:
                if not d.is_dir():
                    continue
                candidates = [
                    d / f"{mod_name}.sotlas",
                    d / f"{mod_name}.st",
                    d / f"{mod_path_str}.sotlas",
                    d / f"{mod_path_str}.st",
                ]
                for c in candidates:
                    if c.is_file():
                        target_file = c
                        break
                if target_file:
                    break

            if target_file and target_file not in visited_files:
                visited_files.add(target_file)
                try:
                    text = target_file.read_text(encoding="utf-8")
                    imported_ast = Parser(Lexer(text, str(target_file)).tokenize(), str(target_file)).parse()
                    for decl in imported_ast.decls:
                        if isinstance(decl, (StructDeclNode, ClassDeclNode, MeshDeclNode,
                                             SpecDeclNode, EnumDeclNode)):
                            self._global.define(Symbol(decl.name, "type", None, decl.span))
                            if isinstance(decl, StructDeclNode):
                                self._structs[decl.name] = decl
                        elif isinstance(decl, (FnDeclNode, TrapFnDeclNode)):
                            self._global.define(Symbol(decl.name, "fn", None, decl.span))
                            self._functions[decl.name] = decl
                        elif isinstance(decl, ConstDeclNode):
                            self._global.define(Symbol(decl.name, "let", decl.type_ann, decl.span))
                        elif isinstance(decl, StaticDeclNode):
                            self._global.define(Symbol(decl.name, "var" if decl.is_var else "let",
                                                       decl.type_ann, decl.span))
                        elif isinstance(decl, RegisterDeclNode):
                            self._global.define(Symbol(decl.name, "type", None, decl.span))
                            self._registers[decl.name] = decl
                        elif isinstance(decl, TypeAliasDeclNode):
                            self._global.define(Symbol(decl.name, "type", decl.alias, decl.span))
                except Exception:
                    pass

    def _pass1_collect(self) -> None:
        self._collect_imported_symbols()
        for builtin_t in ("Enclave", "SpinLock", "ShieldClinch", "ShieldGuard", "SpinLockGuard", "Vec", "String", "Option", "Result", "Self"):
            self._global.define(Symbol(builtin_t, "type", None, Span(self._fn, 0, 0)))
        for builtin_fn in (
            "dma_fence", "dma_barrier",
            "__dma_fence", "__sfence", "__lfence", "__cpu_pause",
            "__atomic_exchange_u32", "__atomic_exchange_u64",
            "__atomic_add_u64", "__atomic_add_u32", "__atomic_sub_u64", "__atomic_sub_u32",
            "__atomic_load_u32", "__atomic_load_u64", "__atomic_store_u32", "__atomic_store_u64",
            "__atomic_cmpxchg_u64", "__atomic_cmpxchg_u32",
            "__irq_save_disable", "__irq_restore", "__interrupts_enabled",
            "__outb", "__inb", "__outw", "__inw", "__outl", "__inl",
            "__cli", "__sti", "__hlt", "__rdmsr", "__wrmsr",
            "__read_cr0", "__write_cr0", "__read_cr2", "__read_cr3", "__write_cr3", "__read_cr4", "__write_cr4",
            "__swapgs", "__read_gs_base", "__current_rsp", "__invlpg"
        ):
            self._global.define(Symbol(builtin_fn, "fn", None, Span(self._fn, 0, 0)))
        for decl in self._ast.decls:
            if isinstance(decl, (StructDeclNode, ClassDeclNode, MeshDeclNode,
                                 SpecDeclNode, EnumDeclNode)):
                sym = Symbol(decl.name, "type", None, decl.span)
                self._global.define(sym)
                if isinstance(decl, EnumDeclNode):
                    self._enums[decl.name] = decl
                elif isinstance(decl, StructDeclNode):
                    self._structs[decl.name] = decl
                elif isinstance(decl, SpecDeclNode):
                    self._specs[decl.name] = decl
                    for m in decl.members:
                        if isinstance(m, FnDeclNode):
                            self._functions[f"{decl.name}::{m.name}"] = m
                            if m.name not in self._functions:
                                self._functions[m.name] = m
            elif isinstance(decl, FnDeclNode):
                sym = Symbol(decl.name, "fn", None, decl.span)
                self._global.define(sym)
                self._functions[decl.name] = decl
            elif isinstance(decl, TrapFnDeclNode):
                sym = Symbol(decl.name, "fn", None, decl.span)
                self._global.define(sym)
                self._functions[decl.name] = decl
            elif isinstance(decl, ConstDeclNode):
                sym = Symbol(decl.name, "let", decl.type_ann, decl.span)
                self._global.define(sym)
            elif isinstance(decl, StaticDeclNode):
                sym = Symbol(decl.name, "var" if decl.is_var else "let",
                             decl.type_ann, decl.span)
                self._global.define(sym)
            elif isinstance(decl, RegisterDeclNode):
                sym = Symbol(decl.name, "type", None, decl.span)
                self._global.define(sym)
                self._registers[decl.name] = decl
            elif isinstance(decl, TypeAliasDeclNode):
                sym = Symbol(decl.name, "type", decl.alias, decl.span)
                self._global.define(sym)

    # ------------------------------------------------------------------
    # Passagem 2: Verificação
    # ------------------------------------------------------------------

    def _pass2_verify(self) -> None:
        for decl in self._ast.decls:
            if isinstance(decl, FnDeclNode):
                self._check_fn(decl, self._global)
            elif isinstance(decl, TrapFnDeclNode):
                self._check_trapfn(decl)
            elif isinstance(decl, StructDeclNode):
                self._check_struct(decl)
            elif isinstance(decl, ClassDeclNode):
                self._check_class(decl)
            elif isinstance(decl, StaticDeclNode):
                self._check_static(decl)
            elif isinstance(decl, RegisterDeclNode):
                self._check_register(decl)
            elif isinstance(decl, ConstDeclNode):
                self._check_expr(decl.value, self._global)
            elif isinstance(decl, MouldBlockNode):
                scope = self._global.child()
                prev_in_mould = self._in_mould
                self._in_mould = True
                try:
                    for stmt in decl.body:
                        self._check_stmt(stmt, scope)
                finally:
                    self._in_mould = prev_in_mould

    # ------------------------------------------------------------------
    # Declarações
    # ------------------------------------------------------------------

    def _check_struct(self, decl: StructDeclNode) -> None:
        for spec_name in getattr(decl, "adopts", []):
            if not self._global.lookup(spec_name):
                self._err(f"spec '{spec_name}' não declarado", decl.span)
        scope = self._global.child()
        for g in getattr(decl, "generics", []):
            if isinstance(g, GenericParam) and getattr(g, "bound", None):
                if not self._global.lookup(g.bound):
                    self._err(f"spec bound '{g.bound}' não declarado", decl.span)
            self._define_generic_param_in_scope(g, scope, decl.span)
        prev_in_method = self._in_method
        for member in decl.members:
            if isinstance(member, FieldDeclNode):
                self._check_type(member.type_ann, member.span, scope)
                if self._is_barecore:
                    self._assert_no_dynamic_alloc(member.type_ann, member.span)
                if member.default:
                    self._check_expr(member.default, scope)
            elif isinstance(member, FnDeclNode):
                self._in_method = True
                self._check_fn(member, scope)
                self._in_method = prev_in_method
            elif isinstance(member, InitDeclNode):
                self._in_method = True
                self._check_init(member, scope)
                self._in_method = prev_in_method

    def _check_register(self, decl: RegisterDeclNode) -> None:
        width_map = {
            TK.KW_UINT8: 8, TK.KW_UINT16: 16, TK.KW_UINT32: 32, TK.KW_UINT64: 64,
            "u8": 8, "u16": 16, "u32": 32, "u64": 64,
            "UInt8": 8, "UInt16": 16, "UInt32": 32, "UInt64": 64,
        }
        b_type = decl.backing_type
        bit_width = None
        if b_type.primitive and b_type.primitive in width_map:
            bit_width = width_map[b_type.primitive]
        elif b_type.name and b_type.name in width_map:
            bit_width = width_map[b_type.name]

        if bit_width is None:
            self._err(
                f"register '{decl.name}' backing type must be an unsigned integer (u8, u16, u32, u64), got '{b_type.display_name()}'",
                decl.span
            )
            return

        used_bits: Dict[int, str] = {}
        for f in decl.fields:
            if f.lo_bit < 0 or f.hi_bit >= bit_width:
                self._err(
                    f"register '{decl.name}' field '{f.name}' bit range {f.lo_bit}..{f.hi_bit} exceeds {bit_width}-bit backing type",
                    f.span
                )
            if f.hi_bit < f.lo_bit:
                self._err(
                    f"register '{decl.name}' field '{f.name}' invalid bit range: hi_bit ({f.hi_bit}) < lo_bit ({f.lo_bit})",
                    f.span
                )
            for bit in range(f.lo_bit, f.hi_bit + 1):
                if bit in used_bits:
                    self._err(
                        f"register '{decl.name}' field '{f.name}' overlaps bit {bit} with field '{used_bits[bit]}'",
                        f.span
                    )
                    break
                used_bits[bit] = f.name

    def _is_simd_type(self, t: Optional[TypeNode]) -> bool:
        if not t:
            return False
        simd_primitives = {
            TK.KW_F32X4, TK.KW_F32X8, TK.KW_F64X2, TK.KW_F64X4,
            TK.KW_U8X16, TK.KW_U8X32, TK.KW_I32X4, TK.KW_I32X8,
            TK.KW_I64X2, TK.KW_I64X4,
        }
        if t.primitive in simd_primitives:
            return True
        if t.name in {
            "f32x4", "f32x8", "f64x2", "f64x4",
            "u8x16", "u8x32", "i32x4", "i32x8", "i64x2", "i64x4",
        }:
            return True
        return False

    def _check_class(self, decl: ClassDeclNode) -> None:
        # Verificar herança
        if decl.base and not self._global.lookup(decl.base):
            self._err(f"classe base '{decl.base}' não declarada", decl.span)
        # Verificar specs adotados
        for spec_name in decl.adopts:
            if not self._global.lookup(spec_name):
                self._err(f"spec '{spec_name}' não declarado", decl.span)
        if self._is_barecore:
            self._err(
                "classes com herança dinâmica não são permitidas em módulos barecore",
                decl.span
            )
        scope = self._global.child()
        for g in getattr(decl, "generics", []):
            self._define_generic_param_in_scope(g, scope, decl.span)
        prev_in_method = self._in_method
        for member in decl.members:
            if isinstance(member, FieldDeclNode):
                self._check_type(member.type_ann, member.span, scope)
                if member.default:
                    self._check_expr(member.default, scope)
            elif isinstance(member, FnDeclNode):
                self._in_method = True
                self._check_fn(member, scope)
                self._in_method = prev_in_method
            elif isinstance(member, InitDeclNode):
                self._in_method = True
                self._check_init(member, scope)
                self._in_method = prev_in_method
            elif isinstance(member, DeinitDeclNode):
                self._in_method = True
                s = scope.child()
                for stmt in member.body:
                    self._check_stmt(stmt, s)
                self._in_method = prev_in_method

    def _check_fn(self, decl: FnDeclNode, outer: Scope) -> None:
        if decl.body is None:
            return
        scope = outer.child()
        prev_flow = self._flow
        prev_effects = self._current_effects
        prev_is_sys = self._is_system_fn
        prev_is_trap = self._is_trapfn
        prev_is_irqfree = self._is_irqfree_fn
        prev_is_async = self._is_async_fn

        self._flow = FlowContext()
        self._current_effects = set()

        dir_names = [getattr(d, "name", "") for d in getattr(decl, "directives", []) or []]
        self._is_system_fn = "system" in dir_names or getattr(decl, "is_system", False) or "unsafe" in dir_names
        self._is_trapfn = False
        self._is_irqfree_fn = "irqfree" in dir_names or "irq" in dir_names
        self._is_async_fn = getattr(decl, "is_async", False) or "async" in dir_names

        try:
            for g in getattr(decl, "generics", []):
                if isinstance(g, GenericParam) and getattr(g, "bound", None):
                    if not self._global.lookup(g.bound):
                        self._err(f"spec bound '{g.bound}' não declarado", decl.span)
                self._define_generic_param_in_scope(g, scope, decl.span)
            for param in decl.params:
                self._check_type(param.type_ann, param.span, scope)
                if self._is_barecore:
                    self._assert_no_dynamic_alloc(param.type_ann, param.span)
                is_sole = self._is_type_sole(param.type_ann)
                sym = Symbol(param.name, "param", param.type_ann, param.span,
                             is_island=self._type_is_island(param.type_ann),
                             is_sole=is_sole)
                scope.define(sym)
                self._flow.define(sym, VarState.LIVE)
                if sym.is_island:
                    self._island_vars.add(param.name)
            if decl.ret:
                self._check_type(decl.ret, decl.span, scope)
                if self._is_barecore:
                    self._assert_no_dynamic_alloc(decl.ret, decl.span)
            for stmt in decl.body:
                self._check_stmt(stmt, scope)

            self._fn_effect_map[decl.name] = set(self._current_effects)

            if self._is_irqfree_fn:
                if Effect.ALLOC in self._current_effects:
                    self._err("error[E0712]: alocação dinâmica (efeito 'alloc') é proibida em contexto irqfree", decl.span)
                if Effect.BLOCKING in self._current_effects:
                    self._err("error[E0713]: operação bloqueante (efeito 'blocking') é proibida em contexto irqfree", decl.span)
                if Effect.ASYNC in self._current_effects:
                    self._err("error[E0714]: suspensão assíncrona (efeito 'async') é proibida em contexto irqfree", decl.span)
        finally:
            for param in decl.params:
                self._island_vars.discard(param.name)
            self._flow = prev_flow
            prev_effects.update(self._current_effects)
            self._current_effects = prev_effects
            self._is_system_fn = prev_is_sys
            self._is_trapfn = prev_is_trap
            self._is_irqfree_fn = prev_is_irqfree
            self._is_async_fn = prev_is_async

    def _check_trapfn(self, decl: TrapFnDeclNode) -> None:
        scope = self._global.child()
        prev_flow = self._flow
        prev_effects = self._current_effects
        prev_is_sys = self._is_system_fn
        prev_is_trap = self._is_trapfn
        prev_is_irqfree = self._is_irqfree_fn

        self._flow = FlowContext()
        self._current_effects = set([Effect.IRQ])
        self._is_system_fn = True
        self._is_trapfn = True
        self._is_irqfree_fn = True

        try:
            for param in decl.params:
                self._check_type(param.type_ann, param.span, scope)
                is_sole = self._is_type_sole(param.type_ann)
                sym = Symbol(param.name, "param", param.type_ann, param.span, is_sole=is_sole)
                scope.define(sym)
                self._flow.define(sym, VarState.LIVE)
            for stmt in decl.body:
                self._check_stmt(stmt, scope)

            self._fn_effect_map[decl.name] = set(self._current_effects)

            if Effect.ALLOC in self._current_effects:
                self._err("error[E0712]: alocação dinâmica (efeito 'alloc') é terminantemente proibida em contexto de interrupção (trapfn)", decl.span)
            if Effect.BLOCKING in self._current_effects:
                self._err("error[E0713]: operação bloqueante (efeito 'blocking') é terminantemente proibida em contexto de interrupção (trapfn)", decl.span)
            if Effect.ASYNC in self._current_effects:
                self._err("error[E0714]: suspensão assíncrona (efeito 'async') é terminantemente proibida em contexto de interrupção (trapfn)", decl.span)
        finally:
            self._flow = prev_flow
            self._current_effects = prev_effects
            self._is_system_fn = prev_is_sys
            self._is_trapfn = prev_is_trap
            self._is_irqfree_fn = prev_is_irqfree

    def _check_init(self, decl: InitDeclNode, outer: Scope) -> None:
        scope = outer.child()
        for param in decl.params:
            self._check_type(param.type_ann, param.span, scope)
            scope.define(Symbol(param.name, "param", param.type_ann, param.span))
        for stmt in decl.body:
            self._check_stmt(stmt, scope)

    def _check_static(self, decl: StaticDeclNode) -> None:
        self._check_type(decl.type_ann, decl.span, self._global)
        if self._is_barecore:
            self._assert_no_dynamic_alloc(decl.type_ann, decl.span)
        self._check_expr(decl.value, self._global)

    # ------------------------------------------------------------------
    # Verificação de Tipos
    # ------------------------------------------------------------------

    def _check_type(self, t: Optional[TypeNode], span: Span, scope: Optional[Scope] = None) -> None:
        if t is None:
            return
        if getattr(t, "is_const_generic", False) or getattr(t, "const_val", None) is not None or (t.name and (t.name.isdigit() or t.name.startswith("0x") or t.name.startswith("0b"))):
            return
        lookup_scope = scope if scope is not None else self._global
        if t.is_topology_ptr:
            self._check_topology_ptr(t, span)
        if t.is_tuple:
            for elem in t.tuple_elements:
                self._check_type(elem, span, lookup_scope)
        if t.is_slice and t.inner_type:
            self._check_type(t.inner_type, span, lookup_scope)
        if hasattr(t, "generic_args") and t.generic_args:
            for g_arg in t.generic_args:
                self._check_type(g_arg, span, lookup_scope)
        if t.name and not t.is_primitive and t.name != "()" and t.name != "!":
            if not lookup_scope.lookup(t.name):
                self._err(f"tipo '{t.name}' não declarado", span)
            else:
                if t.name in self._structs and hasattr(t, "generic_args") and t.generic_args:
                    s_decl = self._structs[t.name]
                    s_generics = getattr(s_decl, "generics", [])
                    for param, arg in zip(s_generics, t.generic_args):
                        bound = getattr(param, "bound", None)
                        if bound:
                            arg_name = getattr(arg, "name", None)
                            satisfies = False
                            if arg_name and arg_name in self._structs:
                                satisfies = bound in getattr(self._structs[arg_name], "adopts", [])
                            elif arg_name and hasattr(self, "_classes") and arg_name in self._classes:
                                satisfies = bound in getattr(self._classes[arg_name], "adopts", [])
                            elif arg_name:
                                sym = lookup_scope.lookup(arg_name)
                                if sym and getattr(sym, "bound", None) == bound:
                                    satisfies = True
                            if not satisfies:
                                disp = arg.display_name() if hasattr(arg, "display_name") else (arg.name or str(arg))
                                self._err(
                                    f"tipo '{disp}' não satisfaz o bound de spec '{bound}' exigido pelo parâmetro '{getattr(param, 'name', str(param))}' em '{t.name}'",
                                    span
                                )

    def _check_topology_ptr(self, t: TypeNode, span: Span) -> None:
        """Verifica regras de segurança de ponteiros de topologia."""
        # rawphys e virtmap não podem ser atribuídos implicitamente entre si (verificado no sema de assign)
        pass  # A verificação concreta é feita em _check_assignment_topology

    def _assert_no_dynamic_alloc(self, t: TypeNode, span: Span) -> None:
        """Em módulos barecore, tipos que implicam alocação dinâmica são proibidos."""
        if t.name in ("String", "Vec", "Box", "Rc", "Arc"):
            self._err(
                f"tipo '{t.name}' implica alocação dinâmica e não é permitido em barecore",
                span
            )
        if t.ownership in (TK.KW_CO_OWNED,):
            self._err(
                "modificador 'co-owned' usa ARC e não é permitido em barecore — use 'sole' ou 'direct'",
                span
            )

    def _type_is_island(self, t: TypeNode) -> bool:
        return t.ownership == TK.KW_ISLAND

    # ------------------------------------------------------------------
    # Verificação de Statements
    # ------------------------------------------------------------------

    def _check_stmt(self, stmt: StmtNode, scope: Scope) -> None:
        if isinstance(stmt, LocalVarDeclNode):
            self._check_local_var(stmt, scope)
        elif isinstance(stmt, AssignmentNode):
            self._check_assignment(stmt, scope)
        elif isinstance(stmt, HandoverNode):
            self._check_handover(stmt, scope)
        elif isinstance(stmt, QuarantineNode):
            self._check_quarantine(stmt, scope)
        elif isinstance(stmt, ClinchNode):
            self._check_clinch(stmt, scope)
        elif isinstance(stmt, QuenchNode):
            s = scope.child()
            for st in stmt.body:
                self._check_stmt(st, s)
        elif isinstance(stmt, GateNode):
            self._check_expr(stmt.condition, scope)
            s = scope.child()
            for st in stmt.body:
                self._check_stmt(st, s)
        elif isinstance(stmt, EmitNode):
            if self._unsafe_depth <= 0 and not self._is_system_fn:
                self._err(
                    "instruções de assembly inline (asm / emit) requerem contexto '@system' ou bloco 'unsafe'",
                    stmt.span
                )
            for e in stmt.outputs + stmt.inputs:
                self._check_expr(e, scope)
        elif isinstance(stmt, ComptimeBlockNode):
            s = scope.child()
            for st in stmt.body:
                self._check_stmt(st, s)
        elif isinstance(stmt, GuardNode):
            self._check_expr(stmt.condition, scope)
            s = scope.child()
            for st in stmt.else_body:
                self._check_stmt(st, s)
        elif isinstance(stmt, IfNode):
            self._check_if(stmt, scope)
        elif isinstance(stmt, MatchNode):
            self._check_expr(stmt.subject, scope)
            for arm in stmt.arms:
                s = scope.child()
                if isinstance(arm.body, list):
                    for st in arm.body:
                        self._check_stmt(st, s)
        elif isinstance(stmt, DiscernStmtNode):
            self._check_discern(stmt, scope)
        elif isinstance(stmt, ProbeStmtNode):
            self._check_probe(stmt, scope)
        elif isinstance(stmt, PulseStmtNode):
            pass
        elif isinstance(stmt, WhileNode):
            self._check_expr(stmt.condition, scope)
            s = scope.child()
            if getattr(stmt, "pattern", None):
                pat = stmt.pattern
                if pat.sub_patterns:
                    for sub in pat.sub_patterns:
                        if sub.kind == "ident" and isinstance(sub.value, str):
                            sub_sym = Symbol(sub.value, "let", None, stmt.span)
                            s.define(sub_sym)
                            self._flow.define(sub_sym, VarState.LIVE)
            self._check_loop(stmt.body, s, stmt.span)
        elif isinstance(stmt, ForNode):
            self._check_expr(stmt.iterable, scope)
            s = scope.child()
            s.define(Symbol(stmt.var, "let", None, stmt.span))
            self._check_loop(stmt.body, s, stmt.span)
        elif isinstance(stmt, UnsafeBlockNode):
            s = scope.child()
            self._unsafe_depth += 1
            try:
                for st in stmt.body:
                    self._check_stmt(st, s)
            finally:
                self._unsafe_depth -= 1
        elif isinstance(stmt, ReturnNode):
            if stmt.value:
                self._check_expr(stmt.value, scope)
                self._check_return_escape(stmt.value, scope, stmt.span)
        elif isinstance(stmt, DeferNode):
            if stmt.expr:
                self._check_expr(stmt.expr, scope)
            if stmt.body:
                s = scope.child()
                for st in stmt.body:
                    self._check_stmt(st, s)
        elif isinstance(stmt, ExprStmtNode):
            self._check_expr(stmt.expr, scope)

    def _check_return_escape(self, expr: ExprNode, scope: Scope, span: Span) -> None:
        if isinstance(expr, UnaryExprNode) and expr.op in (TK.LAND, TK.KW_WHISPER):
            if isinstance(expr.operand, IdentNode):
                sym = scope.lookup(expr.operand.name)
                if sym and sym.kind in ("let", "var") and not self._global.lookup(expr.operand.name):
                    self._err(
                        f"referência a variável local de pilha '{expr.operand.name}' não pode escapar do escopo da função",
                        span
                    )
        elif isinstance(expr, IdentNode):
            sym = scope.lookup(expr.name)
            if sym and getattr(sym, "stack_origin", None):
                self._err(
                    f"referência a variável local de pilha '{sym.stack_origin}' não pode escapar do escopo da função",
                    span
                )

    def _check_discern(self, stmt: DiscernStmtNode, scope: Scope) -> None:
        self._check_expr(stmt.subject, scope)
        enum_decl = None
        if isinstance(stmt.subject, IdentNode):
            sym = scope.lookup(stmt.subject.name)
            if sym and sym.type_node and sym.type_node.name in self._enums:
                enum_decl = self._enums[sym.type_node.name]

        covered_variants: Set[str] = set()
        has_wildcard = stmt.default_case is not None

        before = self._flow.snapshot()
        case_snaps: List[Dict[str, VarState]] = []

        for case in stmt.cases:
            self._flow.restore_and_merge(before, [before])
            s = scope.child()
            if case.pattern.kind == "enum_variant":
                covered_variants.add(str(case.pattern.value))
            elif case.pattern.kind == "wildcard":
                has_wildcard = True
            if case.guard:
                self._check_expr(case.guard, s)
            for st in case.body:
                self._check_stmt(st, s)
            case_snaps.append(self._flow.snapshot())

        if stmt.default_case:
            self._flow.restore_and_merge(before, [before])
            s = scope.child()
            for st in stmt.default_case:
                self._check_stmt(st, s)
            case_snaps.append(self._flow.snapshot())

        if case_snaps:
            self._flow.restore_and_merge(before, case_snaps)

        if enum_decl and not has_wildcard:
            all_variants = {v.name for v in enum_decl.variants}
            missing = all_variants - covered_variants
            if missing:
                missing_str = ", ".join(sorted(missing))
                self._err(f"discern não exaustivo: variantes ausentes: {missing_str}", stmt.span)

    def _check_loop(self, body: List[StmtNode], scope: Scope, span: Span) -> None:
        before = self._flow.snapshot()
        s = scope.child()
        for st in body:
            self._check_stmt(st, s)
        after = self._flow.snapshot()
        for var, prev_st in before.items():
            if prev_st == VarState.LIVE and after.get(var) in (VarState.MOVED, VarState.MAYBE_MOVED):
                self._err(
                    f"recurso 'sole' '{var}' não pode ser transferido dentro de laço sem ser reinicializado a cada iteração",
                    span
                )
        self._flow.restore_and_merge(before, [after, before])

    def _check_local_var(self, stmt: LocalVarDeclNode, scope: Scope) -> None:
        if stmt.type_ann:
            self._check_type(stmt.type_ann, stmt.span, scope)
            if self._is_barecore:
                self._assert_no_dynamic_alloc(stmt.type_ann, stmt.span)
        self._check_expr(stmt.init, scope)

        is_sole = self._is_type_sole(stmt.type_ann)
        if isinstance(stmt.init, IdentNode):
            src_sym = scope.lookup(stmt.init.name)
            if src_sym:
                if stmt.type_ann and src_sym.type_node:
                    self._check_assignment_topology(stmt.type_ann, src_sym.type_node, stmt.span)
                if self._is_type_sole(src_sym.type_node) or getattr(src_sym, "is_sole", False):
                    var_st = self._flow.get_state(src_sym.name)
                    if var_st == VarState.MOVED:
                        self._err(f"uso inválido de recurso 'sole' '{src_sym.name}' após transferência (handover)", stmt.span)
                    elif var_st == VarState.MAYBE_MOVED:
                        self._err(f"uso inválido de recurso 'sole' '{src_sym.name}': recurso pode ter sido transferido em ramo condicional anterior", stmt.span)
                    elif var_st in (VarState.BORROWED_IMMUT, VarState.BORROWED_MUT):
                        self._err(f"não é permitido transferir recurso 'sole' '{src_sym.name}' enquanto estiver sob empréstimo ativo (whisper)", stmt.span)
                    self._flow.set_state(src_sym.name, VarState.MOVED)
                    src_sym.is_moved = True
                    is_sole = True
                    if not stmt.type_ann and src_sym.type_node:
                        stmt.type_ann = src_sym.type_node
        elif isinstance(stmt.init, StructLitExprNode):
            if stmt.init.struct_name in self._structs and self._structs[stmt.init.struct_name].is_sole:
                is_sole = True
            if not stmt.type_ann:
                stmt.type_ann = TypeNode(
                    span=stmt.span,
                    ownership=TK.KW_SOLE if is_sole else None,
                    topology_ptr=None,
                    topology_mut=False,
                    primitive=None,
                    name=stmt.init.struct_name,
                    is_optional=False,
                    is_array=False,
                    array_size=None,
                    bounded_lo=None,
                    bounded_hi=None,
                    generic_args=list(getattr(stmt.init, "generic_args", []) or []),
                )
        elif isinstance(stmt.init, CallExprNode):
            callee_str = ""
            if isinstance(stmt.init.callee, IdentNode):
                callee_str = stmt.init.callee.name
                if stmt.init.callee.path:
                    callee_str = "::".join(stmt.init.callee.path)
            for sname, sdecl in self._structs.items():
                if sdecl.is_sole and (callee_str.startswith(sname) or callee_str.endswith(sname)):
                    is_sole = True
                    break
            if not stmt.type_ann and callee_str in self._functions:
                fn_decl = self._functions[callee_str]
                if getattr(fn_decl, "ret", None):
                    stmt.type_ann = fn_decl.ret
                    if self._is_type_sole(stmt.type_ann):
                        is_sole = True

        is_island = stmt.type_ann is not None and self._type_is_island(stmt.type_ann)
        stack_orig = None
        if isinstance(stmt.init, UnaryExprNode) and stmt.init.op in (TK.LAND, TK.KW_WHISPER):
            if isinstance(stmt.init.operand, IdentNode):
                sym_orig = scope.lookup(stmt.init.operand.name)
                if sym_orig and sym_orig.kind in ("let", "var") and not self._global.lookup(stmt.init.operand.name):
                    stack_orig = stmt.init.operand.name
        elif isinstance(stmt.init, IdentNode):
            src_sym = scope.lookup(stmt.init.name)
            if src_sym and getattr(src_sym, "stack_origin", None):
                stack_orig = src_sym.stack_origin

        sym = Symbol(stmt.name, "var" if stmt.is_var else "let",
                     stmt.type_ann, stmt.span, is_island=is_island, is_sole=is_sole,
                     stack_origin=stack_orig)
        if is_sole and sym.type_node:
            sym.type_node.ownership = TK.KW_SOLE
        scope.define(sym)
        self._flow.define(sym, VarState.LIVE)
        if is_island:
            self._island_vars.add(stmt.name)

    def _check_assignment(self, stmt: AssignmentNode, scope: Scope) -> None:
        self._check_expr(stmt.target, scope)
        self._check_expr(stmt.value, scope)
        if isinstance(stmt.target, UnaryExprNode) and stmt.target.op == TK.STAR:
            if self._unsafe_depth <= 0 and not self._is_system_fn:
                self._err("desreferenciamento de ponteiro cru exige bloco unsafe explícito", stmt.span)
        if isinstance(stmt.target, IdentNode):
            dest_sym = scope.lookup(stmt.target.name)
            if dest_sym:
                if self._is_type_sole(dest_sym.type_node) or getattr(dest_sym, "is_sole", False):
                    self._flow.set_state(dest_sym.name, VarState.LIVE)
                    dest_sym.is_moved = False

                src_type = None
                if isinstance(stmt.value, IdentNode):
                    src_sym = scope.lookup(stmt.value.name)
                    if src_sym:
                        src_type = src_sym.type_node
                        if self._is_type_sole(src_sym.type_node) or getattr(src_sym, "is_sole", False):
                            var_st = self._flow.get_state(src_sym.name)
                            if var_st == VarState.MOVED:
                                self._err(f"uso inválido de recurso 'sole' '{src_sym.name}' após transferência (handover)", stmt.span)
                            elif var_st == VarState.MAYBE_MOVED:
                                self._err(f"uso inválido de recurso 'sole' '{src_sym.name}': recurso pode ter sido transferido em ramo condicional anterior", stmt.span)
                            elif var_st in (VarState.BORROWED_IMMUT, VarState.BORROWED_MUT):
                                self._err(f"não é permitido transferir recurso 'sole' '{src_sym.name}' enquanto estiver sob empréstimo ativo (whisper)", stmt.span)
                            self._flow.set_state(src_sym.name, VarState.MOVED)
                            src_sym.is_moved = True
                if dest_sym.type_node:
                    self._check_assignment_topology(dest_sym.type_node, src_type, stmt.span)
        elif isinstance(stmt.target, FieldExprNode):
            base_t = self._infer_expr_type(stmt.target.base, scope)
            if base_t:
                reg_name = base_t.name
                if reg_name and reg_name in self._registers:
                    reg_decl = self._registers[reg_name]
                    field_names = {f.name for f in reg_decl.fields}
                    if stmt.target.field not in field_names:
                        self._err(f"register '{reg_name}' has no field '{stmt.target.field}'", stmt.target.span)
                    if base_t.topology_ptr and self._unsafe_depth <= 0 and not self._is_system_fn:
                        self._err("acesso a registrador via ponteiro de hardware exige bloco unsafe explícito", stmt.span)

    def _check_assignment_topology(self, dest_type: TypeNode, src_type: Optional[TypeNode], span: Span) -> None:
        """Bloqueia atribuição implícita entre *rawphys, *virtmap, *portwire e *dmazone."""
        if not dest_type or not src_type:
            return
        dest_topo = dest_type.topology_ptr
        src_topo = src_type.topology_ptr
        if dest_topo and src_topo:
            if dest_topo != src_topo:
                src_name = TOPOLOGY_NAME_MAP.get(src_topo, getattr(src_topo, "name", str(src_topo)))
                dest_name = TOPOLOGY_NAME_MAP.get(dest_topo, getattr(dest_topo, "name", str(dest_topo)))
                self._err(
                    f"atribuição de topologia incompatível: tentativa de atribuir "
                    f"'{src_name}' para '{dest_name}' sem conversão explícita",
                    span
                )
        elif dest_topo in (TK.KW_RAWPHYS, TK.KW_VIRTMAP, TK.KW_PORTWIRE, TK.KW_DMAZONE) and not src_topo:
            dest_name = TOPOLOGY_NAME_MAP.get(dest_topo, getattr(dest_topo, "name", str(dest_topo)))
            self._err(
                f"atribuição de topologia incompatível: conversão implícita para '{dest_name}' exige cast explícito",
                span
            )
        elif src_topo in (TK.KW_RAWPHYS, TK.KW_VIRTMAP, TK.KW_PORTWIRE, TK.KW_DMAZONE) and not dest_topo:
            src_name = TOPOLOGY_NAME_MAP.get(src_topo, getattr(src_topo, "name", str(src_topo)))
            self._err(
                f"atribuição de topologia incompatível: escape de '{src_name}' para ponteiro comum exige cast explícito",
                span
            )

    def _check_handover(self, stmt: HandoverNode, scope: Scope) -> None:
        """Verifica que handover é aplicado a uma variável 'sole' e a marca como transferida (moved)."""
        self._check_expr(stmt.expr, scope)
        if isinstance(stmt.expr, IdentNode):
            sym = scope.lookup(stmt.expr.name)
            if sym:
                if not (self._is_type_sole(sym.type_node) or getattr(sym, "is_sole", False)):
                    ownership_str = getattr(sym.type_node.ownership, "name", str(sym.type_node.ownership)) if sym.type_node else "copyable"
                    self._err(
                        f"'handover' só pode ser aplicado a variáveis 'sole', "
                        f"mas '{stmt.expr.name}' é '{ownership_str}'",
                        stmt.span
                    )
                var_st = self._flow.get_state(stmt.expr.name)
                if var_st == VarState.MOVED:
                    self._err(f"uso inválido de recurso 'sole' '{stmt.expr.name}' após transferência (handover)", stmt.span)
                elif var_st == VarState.MAYBE_MOVED:
                    self._err(f"uso inválido de recurso 'sole' '{stmt.expr.name}': recurso pode ter sido transferido em ramo condicional anterior", stmt.span)
                elif var_st in (VarState.BORROWED_IMMUT, VarState.BORROWED_MUT):
                    self._err(f"não é permitido transferir recurso 'sole' '{stmt.expr.name}' enquanto estiver sob empréstimo ativo (whisper)", stmt.span)
                self._flow.set_state(stmt.expr.name, VarState.MOVED)
                sym.is_moved = True

    def _check_quarantine(self, stmt: QuarantineNode, scope: Scope) -> None:
        """Marca o recurso como island após quarantine."""
        self._check_expr(stmt.expr, scope)
        if isinstance(stmt.expr, IdentNode):
            sym = scope.lookup(stmt.expr.name)
            if sym:
                self._island_vars.add(stmt.expr.name)

    def _check_clinch(self, stmt: ClinchNode, scope: Scope) -> None:
        """Bloco clínico (seção crítica de hardware) — corpo e revert."""
        prev_clinch = self._in_clinch
        self._in_clinch = True
        try:
            s = scope.child()
            for st in stmt.body:
                self._check_stmt(st, s)
            if stmt.revert:
                r = scope.child()
                for st in stmt.revert:
                    self._check_stmt(st, r)
        finally:
            self._in_clinch = prev_clinch

    def _check_if(self, stmt: IfNode, scope: Scope) -> None:
        self._check_expr(stmt.condition, scope)
        before = self._flow.snapshot()

        s = scope.child()
        if stmt.let_bind:
            sym = Symbol(stmt.let_bind, "let", None, stmt.span)
            s.define(sym)
            self._flow.define(sym, VarState.LIVE)
        elif getattr(stmt, "pattern", None):
            pat = stmt.pattern
            if pat.sub_patterns:
                for sub in pat.sub_patterns:
                    if sub.kind == "ident" and isinstance(sub.value, str):
                        sub_sym = Symbol(sub.value, "let", None, stmt.span)
                        s.define(sub_sym)
                        self._flow.define(sub_sym, VarState.LIVE)
        for st in stmt.then_body:
            self._check_stmt(st, s)
        snap_then = self._flow.snapshot()

        if stmt.else_body:
            self._flow.restore_and_merge(before, [before])
            if isinstance(stmt.else_body, IfNode):
                self._check_if(stmt.else_body, scope)
                snap_else = self._flow.snapshot()
            elif isinstance(stmt.else_body, list):
                es = scope.child()
                for st in stmt.else_body:
                    self._check_stmt(st, es)
                snap_else = self._flow.snapshot()
            else:
                snap_else = before
            self._flow.restore_and_merge(before, [snap_then, snap_else])
        else:
            self._flow.restore_and_merge(before, [snap_then, before])

    # ------------------------------------------------------------------
    # Verificação de Expressões
    # ------------------------------------------------------------------

    def _check_expr(self, expr: ExprNode, scope: Scope) -> None:
        if isinstance(expr, IdentNode):
            if expr.name in self._island_vars or expr.name.startswith("__") or expr.name.startswith("baken_"):
                pass  # Acesso a island ou intrínseco de sistema/hardware
            elif not expr.path and not scope.lookup(expr.name):
                if not self._in_method:
                    self._err(f"símbolo não declarado: '{expr.name}'", expr.span)
            else:
                sym = scope.lookup(expr.name)
                if sym and (self._is_type_sole(sym.type_node) or getattr(sym, "is_sole", False)):
                    var_st = self._flow.get_state(expr.name)
                    if var_st == VarState.MOVED:
                        self._err(
                            f"uso inválido de recurso 'sole' '{expr.name}' após transferência (handover)",
                            expr.span
                        )
                    elif var_st == VarState.MAYBE_MOVED:
                        self._err(
                            f"uso inválido de recurso 'sole' '{expr.name}': recurso pode ter sido transferido em ramo condicional anterior",
                            expr.span
                        )
                    elif var_st == VarState.BORROWED_MUT:
                        self._err(
                            f"acesso inválido a '{expr.name}': variável sob empréstimo mutável exclusivo (whisper mut)",
                            expr.span
                        )
        elif isinstance(expr, BinaryExprNode):
            self._check_expr(expr.left, scope)
            self._check_expr(expr.right, scope)
            lt = self._infer_expr_type(expr.left, scope)
            rt = self._infer_expr_type(expr.right, scope)
            if lt and rt and self._is_simd_type(lt) and self._is_simd_type(rt):
                if lt.display_name() != rt.display_name():
                    self._err(f"type mismatch in vector operation: '{lt.display_name()}' and '{rt.display_name()}'", expr.span)
        elif (isinstance(expr, UnaryExprNode) and expr.op == TK.KW_AWAIT) or isinstance(expr, AwaitExprNode):
            self._current_effects.add(Effect.ASYNC)
            if self._in_clinch:
                self._err("suspensão ('await') é terminantemente proibida dentro de seção crítica de hardware ('clinch')", expr.span)
            elif self._is_trapfn or self._is_irqfree_fn:
                self._err("error[E0714]: suspensão assíncrona (efeito 'async') é terminantemente proibida em contexto de interrupção (trapfn/irq)", expr.span)
            elif not self._is_async_fn:
                self._err("expressão 'await' só é permitida dentro de funções assíncronas ('async fn')", expr.span)
            target = expr.expr if isinstance(expr, AwaitExprNode) else expr.operand
            self._check_expr(target, scope)
        elif isinstance(expr, ComptimeExprNode):
            self._check_expr(expr.expr, scope)
            val = self._eval_comptime_expr(expr.expr, scope)
            if val is None:
                self._err("expressão 'comptime' não pôde ser avaliada em tempo de compilação: depende de valor dinâmico em tempo de execução", expr.span)
            else:
                if isinstance(val, bool):
                    expr.folded = LiteralNode(expr.span, TK.KW_TRUE if val else TK.KW_FALSE, "true" if val else "false")
                elif isinstance(val, int):
                    expr.folded = LiteralNode(expr.span, TK.INT_LIT, str(val))
                elif isinstance(val, float):
                    expr.folded = LiteralNode(expr.span, TK.FLOAT_LIT, str(val))
                elif isinstance(val, str):
                    expr.folded = LiteralNode(expr.span, TK.STR_LIT, val)
        elif isinstance(expr, UnaryExprNode):
            self._check_expr(expr.operand, scope)
            if expr.op == TK.STAR:
                if self._unsafe_depth <= 0 and not self._is_system_fn:
                    self._err("desreferenciamento de ponteiro cru exige bloco unsafe explícito", expr.span)
            elif expr.op == TK.KW_WHISPER:
                if isinstance(expr.operand, IdentNode):
                    var_name = expr.operand.name
                    cur_st = self._flow.get_state(var_name)
                    if cur_st == VarState.MOVED:
                        self._err(f"uso inválido de recurso 'sole' '{var_name}' após transferência (handover)", expr.span)
                    elif cur_st == VarState.MAYBE_MOVED:
                        self._err(f"uso inválido de recurso 'sole' '{var_name}': recurso pode ter sido transferido em ramo condicional anterior", expr.span)

                    if getattr(expr, "is_mut", False):
                        if cur_st == VarState.BORROWED_IMMUT:
                            self._err(f"não é permitido criar empréstimo mutável (whisper mut) enquanto houver outros empréstimos ativos (whisper) em '{var_name}'", expr.span)
                        elif cur_st == VarState.BORROWED_MUT:
                            self._err(f"conflito de empréstimo: empréstimo mutável exclusivo já ativo em '{var_name}'", expr.span)
                        self._flow.set_state(var_name, VarState.BORROWED_MUT)
                    else:
                        if cur_st == VarState.BORROWED_MUT:
                            self._err(f"não é permitido criar empréstimo imutável (whisper) enquanto houver empréstimo mutável ativo (whisper mut) em '{var_name}'", expr.span)
                        self._flow.set_state(var_name, VarState.BORROWED_IMMUT)
        elif isinstance(expr, CallExprNode):
            callee_name = ""
            if isinstance(expr.callee, IdentNode):
                callee_name = expr.callee.name
                if expr.callee.path:
                    callee_name = "::".join(expr.callee.path)

            ALLOCATING_NAMES = {
                "malloc", "calloc", "realloc", "heap_allocate", "heap_alloc",
                "alloc", "kalloc", "kmalloc", "allocate"
            }
            BLOCKING_NAMES = {
                "sleep", "msleep", "usleep", "yield", "thread_yield",
                "block_on", "wait_for_event", "mutex_lock", "semaphore_wait"
            }

            if any(callee_name == a or callee_name.endswith("::" + a) for a in ALLOCATING_NAMES):
                self._current_effects.add(Effect.ALLOC)
                if self._is_trapfn or self._is_irqfree_fn:
                    self._err("error[E0712]: alocação dinâmica (efeito 'alloc') é terminantemente proibida em contexto de interrupção (trapfn/irq)", expr.span)
            if any(callee_name == b or callee_name.endswith("::" + b) for b in BLOCKING_NAMES):
                self._current_effects.add(Effect.BLOCKING)
                if self._is_trapfn or self._is_irqfree_fn:
                    self._err("error[E0713]: operação bloqueante (efeito 'blocking') é terminantemente proibida em contexto de interrupção (trapfn/irq)", expr.span)
                if self._in_clinch:
                    self._err("operação bloqueante é terminantemente proibida dentro de seção crítica de hardware ('clinch')", expr.span)
            if callee_name in self._fn_effect_map:
                callee_effects = self._fn_effect_map[callee_name]
                self._current_effects.update(callee_effects)
                if Effect.ALLOC in callee_effects and (self._is_trapfn or self._is_irqfree_fn):
                    self._err("error[E0712]: alocação dinâmica (efeito 'alloc') é terminantemente proibida em contexto de interrupção (trapfn/irq)", expr.span)
                if Effect.BLOCKING in callee_effects:
                    if self._is_trapfn or self._is_irqfree_fn:
                        self._err("error[E0713]: operação bloqueante (efeito 'blocking') é terminantemente proibida em contexto de interrupção (trapfn/irq)", expr.span)
                    if self._in_clinch:
                        self._err("operação bloqueante é terminantemente proibida dentro de seção crítica de hardware ('clinch')", expr.span)

            self._check_expr(expr.callee, scope)

            # Type, Typestate and Island validation for function parameters
            target_fn = self._functions.get(callee_name)
            if target_fn and getattr(target_fn, "params", None):
                for param, arg in zip(target_fn.params, expr.args):
                    act_type = self._infer_expr_type(arg.value, scope)
                    exp_type = param.type_ann
                    if exp_type and act_type:
                        # 1. Confinamento de island
                        if getattr(act_type, "ownership", None) == TK.KW_ISLAND or (isinstance(arg.value, IdentNode) and arg.value.name in self._island_vars):
                            if getattr(exp_type, "ownership", None) != TK.KW_ISLAND:
                                self._err(f"confinamento de 'island' violado: '{getattr(arg.value, 'name', 'valor')}' não pode escapar do domínio de execução sem 'handover'", arg.value.span)

                        # 2. Verificação de typestate e const generics
                        exp_name = exp_type.name
                        act_name = act_type.name
                        if exp_name and act_name and exp_name == act_name:
                            exp_g = getattr(exp_type, "generic_args", []) or []
                            act_g = getattr(act_type, "generic_args", []) or []
                            for eg, ag in zip(exp_g, act_g):
                                if getattr(eg, "is_const_generic", False) or getattr(ag, "is_const_generic", False) or getattr(eg, "const_val", None) is not None or getattr(ag, "const_val", None) is not None:
                                    ev = eg.const_val if getattr(eg, "const_val", None) is not None else eg.name
                                    av = ag.const_val if getattr(ag, "const_val", None) is not None else ag.name
                                    if str(ev) != str(av):
                                        self._err(f"type mismatch: expected '{exp_type.display_name()}', found '{act_type.display_name()}'", arg.value.span)
                                elif eg.name and ag.name and eg.name != ag.name:
                                    self._err(f"mismatched typestate: expected '{eg.name}', found '{ag.name}'", arg.value.span)

            for arg in expr.args:
                self._check_expr(arg.value, scope)
                if isinstance(arg.value, IdentNode):
                    arg_sym = scope.lookup(arg.value.name)
                    if arg_sym and (self._is_type_sole(arg_sym.type_node) or getattr(arg_sym, "is_sole", False)):
                        var_st = self._flow.get_state(arg.value.name)
                        if var_st == VarState.MOVED:
                            self._err(f"uso inválido de recurso 'sole' '{arg.value.name}' após transferência (handover)", expr.span)
                        elif var_st == VarState.MAYBE_MOVED:
                            self._err(f"uso inválido de recurso 'sole' '{arg.value.name}': recurso pode ter sido transferido em ramo condicional anterior", expr.span)
                        elif var_st in (VarState.BORROWED_IMMUT, VarState.BORROWED_MUT):
                            self._err(f"não é permitido transferir recurso 'sole' '{arg.value.name}' enquanto estiver sob empréstimo ativo (whisper)", expr.span)
                        self._flow.set_state(arg.value.name, VarState.MOVED)
                        arg_sym.is_moved = True
        elif isinstance(expr, (SpanOfNode, StrideOfNode, AlignOfNode)):
            self._check_type(expr.target_type, expr.span, scope)
        elif isinstance(expr, FieldOffsetNode):
            pass
        elif isinstance(expr, (IndexExprNode,)):
            self._check_expr(expr.base, scope)
            self._check_expr(expr.index, scope)
        elif isinstance(expr, FieldExprNode):
            self._check_expr(expr.base, scope)
            base_t = self._infer_expr_type(expr.base, scope)
            if base_t:
                reg_name = base_t.name
                if reg_name and reg_name in self._registers:
                    reg_decl = self._registers[reg_name]
                    field_names = {f.name for f in reg_decl.fields}
                    if expr.field not in field_names:
                        self._err(f"register '{reg_name}' has no field '{expr.field}'", expr.span)
                    if base_t.topology_ptr and self._unsafe_depth <= 0 and not self._is_system_fn:
                        self._err("acesso a registrador via ponteiro de hardware exige bloco unsafe explícito", expr.span)
        elif isinstance(expr, BitSliceExprNode):
            self._check_expr(expr.base, scope)
            self._check_expr(expr.lo, scope)
            self._check_expr(expr.hi, scope)
        elif isinstance(expr, BitNotchExprNode):
            self._check_expr(expr.base, scope)
            self._check_expr(expr.bit, scope)
        elif isinstance(expr, BitStrandExprNode):
            self._check_expr(expr.base, scope)
        elif isinstance(expr, CastExprNode):
            self._check_expr(expr.expr, scope)
            self._check_type(expr.target_type, expr.span, scope)
            if expr.target_type and (expr.target_type.is_topology_ptr or expr.target_type.topology_ptr):
                if self._unsafe_depth <= 0:
                    self._err("criação/conversão para ponteiro cru exige bloco unsafe explícito", expr.span)
        elif isinstance(expr, (OptionalChainExprNode, ForceUnwrapExprNode)):
            self._check_expr(expr.expr, scope)
        elif isinstance(expr, ArrayLitExprNode):
            for el in expr.elements:
                self._check_expr(el, scope)
        elif isinstance(expr, TupleLitExprNode):
            for el in expr.elements:
                self._check_expr(el, scope)
        elif isinstance(expr, TupleIndexExprNode):
            self._check_expr(expr.base, scope)
        elif isinstance(expr, SliceExprNode):
            self._check_expr(expr.base, scope)
            if expr.lo:
                self._check_expr(expr.lo, scope)
            if expr.hi:
                self._check_expr(expr.hi, scope)
        elif isinstance(expr, TryExprNode):
            self._check_expr(expr.expr, scope)
        elif isinstance(expr, IfExprNode):
            self._check_expr(expr.condition, scope)
            self._check_expr(expr.then_expr, scope)
            self._check_expr(expr.else_expr, scope)
        elif isinstance(expr, StructLitExprNode):
            for f in expr.fields:
                self._check_expr(f.value, scope)
        elif isinstance(expr, ClosureExprNode):
            s = scope.child()
            for p in expr.params:
                s.define(Symbol(p, "param", None, Span(self._fn, 0, 0)))
            for st in expr.body:
                self._check_stmt(st, s)

    def _check_probe(self, stmt: ProbeStmtNode, scope: Scope) -> None:
        self._check_expr(stmt.condition, scope)
        val = self._eval_comptime_expr(stmt.condition, scope)
        if val is not None and not val:
            msg = stmt.message if stmt.message else "invariante de sistema violada"
            self._err(f"static probe assertion failed: {msg}", stmt.span)

    def _eval_comptime_expr(self, expr: ExprNode, scope: Scope) -> Optional[Any]:
        if isinstance(expr, ComptimeExprNode):
            return self._eval_comptime_expr(expr.expr, scope)
        if isinstance(expr, LiteralNode):
            if expr.kind == TK.INT_LIT:
                try:
                    return int(expr.value, 0)
                except ValueError:
                    return None
            elif expr.kind == TK.FLOAT_LIT:
                try:
                    return float(expr.value)
                except ValueError:
                    return None
            elif expr.kind == TK.STR_LIT:
                return expr.value
            elif expr.kind == TK.KW_TRUE:
                return True
            elif expr.kind == TK.KW_FALSE:
                return False
            elif expr.kind == TK.KW_NIL:
                return None
        elif isinstance(expr, (SpanOfNode, StrideOfNode, AlignOfNode)):
            p = getattr(expr.target_type, "primitive", None)
            sizes = {
                TK.KW_UINT8: 1, TK.KW_INT8: 1, TK.KW_BOOL: 1,
                TK.KW_UINT16: 2, TK.KW_INT16: 2,
                TK.KW_UINT32: 4, TK.KW_INT32: 4, TK.KW_FLOAT32: 4,
                TK.KW_UINT64: 8, TK.KW_INT64: 8, TK.KW_FLOAT64: 8,
                TK.KW_USIZE: 8, TK.KW_ISIZE: 8,
            }
            if p in sizes:
                return sizes[p]
            return None
        elif isinstance(expr, BinaryExprNode):
            l = self._eval_comptime_expr(expr.left, scope)
            r = self._eval_comptime_expr(expr.right, scope)
            if l is not None and r is not None:
                op = expr.op
                try:
                    if op == TK.EQ:
                        return l == r
                    elif op == TK.NEQ:
                        return l != r
                    elif op == TK.LT:
                        return l < r
                    elif op == TK.LTE:
                        return l <= r
                    elif op == TK.GT:
                        return l > r
                    elif op == TK.GTE:
                        return l >= r
                    elif op == TK.PLUS:
                        return l + r
                    elif op == TK.MINUS:
                        return l - r
                    elif op == TK.STAR:
                        return l * r
                    elif op == TK.SLASH:
                        return l // r if r != 0 else None
                    elif op == TK.PERCENT:
                        return l % r if r != 0 else None
                    elif op == TK.LAND:
                        return l & r
                    elif op == TK.LOR:
                        return l | r
                    elif op == TK.XOR:
                        return l ^ r
                    elif op == TK.SHL:
                        return l << r
                    elif op == TK.SHR:
                        return l >> r
                    elif op == TK.AND:
                        return bool(l and r)
                    elif op == TK.OR:
                        return bool(l or r)
                except Exception:
                    return None
        elif isinstance(expr, UnaryExprNode):
            v = self._eval_comptime_expr(expr.operand, scope)
            if v is not None:
                if expr.op in (TK.NOT, TK.BANG):
                    return not v
                elif expr.op == TK.MINUS:
                    return -v
                elif expr.op == TK.TILDE:
                    return ~v
        elif isinstance(expr, IdentNode):
            sym = scope.lookup(expr.name)
            if sym and getattr(sym, "const_value", None) is not None:
                return sym.const_value
        return None

    def _infer_expr_type(self, expr: ExprNode, scope: Scope) -> Optional[TypeNode]:
        if isinstance(expr, IdentNode):
            sym = scope.lookup(expr.name)
            return sym.type_node if sym else None
        elif isinstance(expr, StructLitExprNode):
            return TypeNode(
                span=expr.span,
                ownership=None,
                topology_ptr=None,
                topology_mut=False,
                primitive=None,
                name=expr.struct_name,
                is_optional=False,
                is_array=False,
                array_size=None,
                bounded_lo=None,
                bounded_hi=None,
                generic_args=list(getattr(expr, "generic_args", []) or []),
            )
        elif isinstance(expr, CallExprNode):
            callee_name = ""
            if isinstance(expr.callee, IdentNode):
                callee_name = expr.callee.name
                if expr.callee.path:
                    callee_name = "::".join(expr.callee.path)
            elif isinstance(expr.callee, FieldExprNode):
                base_t = self._infer_expr_type(expr.callee.base, scope)
                if base_t and base_t.name:
                    callee_name = f"{base_t.name}::{expr.callee.field}"
                else:
                    callee_name = expr.callee.field
            if callee_name in self._functions:
                return getattr(self._functions[callee_name], "ret", None)
        elif isinstance(expr, UnaryExprNode):
            if expr.op in (TK.LAND, TK.KW_WHISPER):
                inner_t = self._infer_expr_type(expr.operand, scope)
                if inner_t:
                    import copy
                    t = copy.copy(inner_t)
                    t.topology_ptr = TK.KW_MUT if getattr(expr, "is_mut", False) else TK.KW_CONST_MOD
                    return t
        elif isinstance(expr, FieldExprNode):
            base_t = self._infer_expr_type(expr.base, scope)
            if base_t and base_t.name in self._registers:
                reg_decl = self._registers[base_t.name]
                for f in reg_decl.fields:
                    if f.name == expr.field:
                        return reg_decl.backing_type
        elif isinstance(expr, BinaryExprNode):
            lt = self._infer_expr_type(expr.left, scope)
            rt = self._infer_expr_type(expr.right, scope)
            if lt and self._is_simd_type(lt):
                return lt
            if rt and self._is_simd_type(rt):
                return rt
        elif isinstance(expr, ComptimeExprNode):
            if hasattr(expr, "folded") and expr.folded:
                return self._infer_expr_type(expr.folded, scope)
            return self._infer_expr_type(expr.expr, scope)
        elif isinstance(expr, AwaitExprNode):
            return self._infer_expr_type(expr.expr, scope)
        return None
