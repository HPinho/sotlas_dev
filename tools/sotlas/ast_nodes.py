"""Sotlas AST Nodes — Hierarquia completa de nós da Árvore Sintática Abstrata."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union
from .token_types import TK, PRIMITIVE_TOKENS, OWNERSHIP_MODS, TOPOLOGY_MODS


# ---------------------------------------------------------------------------
# Localização (para mensagens de erro semântico)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Span:
    file: str
    line: int
    col: int

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.col}"


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------


@dataclass
class TypeNode:
    """Representa um tipo completo com modificadores opcionais de posse e topologia."""
    span: Span
    ownership: Optional[TK]           # co-owned | sole | island | whisper | direct
    topology_ptr: Optional[TK]        # rawphys | virtmap | portwire | dmazone | voidzero
    topology_mut: bool                # *mut T
    primitive: Optional[TK]          # tipo primitivo (KW_INT8 … KW_VOID)
    name: Optional[str]              # identificador de tipo definido pelo usuário
    is_optional: bool                 # sufixo '?'
    is_array: bool                    # [T; N]
    array_size: Optional["ExprNode"]  # expressão do tamanho
    bounded_lo: Optional["ExprNode"]  # PrimitiveType.bound[lo..hi]
    bounded_hi: Optional["ExprNode"]
    generic_args: List["TypeNode"] = field(default_factory=list)
    is_slice: bool = False            # [T] fatia dinâmica
    inner_type: Optional["TypeNode"] = None
    tuple_elements: List["TypeNode"] = field(default_factory=list)
    is_const_generic: bool = False
    const_val: Optional[Union[int, str]] = None

    @property
    def is_topology_ptr(self) -> bool:
        return self.topology_ptr is not None

    @property
    def is_primitive(self) -> bool:
        return self.primitive is not None

    @property
    def is_bounded(self) -> bool:
        return self.bounded_lo is not None

    @property
    def is_tuple(self) -> bool:
        return len(self.tuple_elements) > 0

    def display_name(self) -> str:
        res = ""
        if self.ownership:
            res += f"{self.ownership.name.lower().replace('kw_', '')} "
        if self.topology_ptr:
            t_name = self.topology_ptr.name.lower().replace('kw_', '')
            res += f"*{t_name} " if t_name != "mut" else "*mut "
        if self.const_val is not None:
            res += str(self.const_val)
        elif self.name:
            res += self.name
        elif self.primitive:
            canon = {
                TK.KW_UINT8: "u8", TK.KW_UINT16: "u16", TK.KW_UINT32: "u32", TK.KW_UINT64: "u64",
                TK.KW_INT8: "i8", TK.KW_INT16: "i16", TK.KW_INT32: "i32", TK.KW_INT64: "i64",
                TK.KW_FLOAT32: "f32", TK.KW_FLOAT64: "f64",
                TK.KW_USIZE: "usize", TK.KW_ISIZE: "isize",
                TK.KW_BOOL: "bool", TK.KW_VOID: "void", TK.KW_CHAR: "char", TK.KW_STRING: "string",
                TK.KW_F32X4: "f32x4", TK.KW_F32X8: "f32x8",
                TK.KW_F64X2: "f64x2", TK.KW_F64X4: "f64x4",
                TK.KW_U8X16: "u8x16", TK.KW_U8X32: "u8x32",
                TK.KW_I32X4: "i32x4", TK.KW_I32X8: "i32x8",
                TK.KW_I64X2: "i64x2", TK.KW_I64X4: "i64x4",
            }
            res += canon.get(self.primitive, self.primitive.name.lower().replace('kw_', ''))
        elif self.is_tuple:
            res += f"({', '.join(e.display_name() for e in self.tuple_elements)})"
        elif self.inner_type:
            res += f"[{self.inner_type.display_name()}]"
        if self.generic_args:
            res += f"<{', '.join(g.display_name() for g in self.generic_args)}>"
        if self.is_optional:
            res += "?"
        return res.strip()


@dataclass
class FunctionTypeNode:
    span: Span
    params: List[TypeNode]
    ret: TypeNode
    is_async: bool = False


@dataclass
class TupleTypeNode:
    span: Span
    elements: List[TypeNode]


@dataclass
class SliceTypeNode:
    span: Span
    element_type: TypeNode


# ---------------------------------------------------------------------------
# Expressões
# ---------------------------------------------------------------------------

@dataclass
class LiteralNode:
    span: Span
    kind: TK       # INT_LIT | FLOAT_LIT | STR_LIT | CHAR_LIT | KW_TRUE | KW_FALSE | KW_NIL
    value: str


@dataclass
class IdentNode:
    span: Span
    name: str
    path: List[str] = field(default_factory=list)  # a::b::c → path=["a","b"], name="c"


@dataclass
class BinaryExprNode:
    span: Span
    op: TK
    left: "ExprNode"
    right: "ExprNode"


@dataclass
class UnaryExprNode:
    span: Span
    op: TK     # NOT | MINUS | TILDE | STAR | LAND | KW_AWAIT | KW_WHISPER
    operand: "ExprNode"
    is_mut: bool = False


@dataclass
class CallExprNode:
    span: Span
    callee: "ExprNode"
    args: List["ArgNode"]


@dataclass
class ArgNode:
    span: Span
    label: Optional[str]   # argumento rotulado: label: expr
    value: "ExprNode"


@dataclass
class IndexExprNode:
    span: Span
    base: "ExprNode"
    index: "ExprNode"


@dataclass
class FieldExprNode:
    span: Span
    base: "ExprNode"
    field: str


@dataclass
class BitSliceExprNode:
    """base.slit[lo..hi] — extrai campo de bits."""
    span: Span
    base: "ExprNode"
    lo: "ExprNode"
    hi: "ExprNode"


@dataclass
class BitNotchExprNode:
    """base.notch[n] — extrai bit isolado."""
    span: Span
    base: "ExprNode"
    bit: "ExprNode"


@dataclass
class BitStrandExprNode:
    """base.strand — inverte endianness dos bytes."""
    span: Span
    base: "ExprNode"


@dataclass
class CastExprNode:
    """expr as Type."""
    span: Span
    expr: "ExprNode"
    target_type: TypeNode


@dataclass
class OptionalChainExprNode:
    """expr? — encadeia opcional."""
    span: Span
    expr: "ExprNode"


@dataclass
class ForceUnwrapExprNode:
    """expr! — desempacotamento forçado."""
    span: Span
    expr: "ExprNode"


@dataclass
class ArrayLitExprNode:
    span: Span
    elements: List["ExprNode"]


@dataclass
class ClosureExprNode:
    span: Span
    params: List[str]
    body: List["StmtNode"]


@dataclass
class StructLitFieldNode:
    span: Span
    name: str
    value: "ExprNode"


@dataclass
class StructLitExprNode:
    span: Span
    struct_name: str
    prefix: List[str]
    fields: List[StructLitFieldNode]
    generic_args: List[TypeNode] = field(default_factory=list)


@dataclass
class TupleLitExprNode:
    span: Span
    elements: List["ExprNode"]


@dataclass
class TupleIndexExprNode:
    span: Span
    base: "ExprNode"
    index: int


@dataclass
class SliceExprNode:
    span: Span
    base: "ExprNode"
    lo: Optional["ExprNode"]
    hi: Optional["ExprNode"]


@dataclass
class IfExprNode:
    span: Span
    condition: "ExprNode"
    then_expr: "ExprNode"
    else_expr: "ExprNode"


@dataclass
class SpanOfNode:
    span: Span
    target_type: TypeNode


@dataclass
class StrideOfNode:
    span: Span
    target_type: TypeNode


@dataclass
class AlignOfNode:
    span: Span
    target_type: TypeNode


@dataclass
class FieldOffsetNode:
    span: Span
    struct_name: str
    field_name: str


@dataclass
class ComptimeExprNode:
    span: Span
    expr: "ExprNode"


@dataclass
class AwaitExprNode:
    span: Span
    expr: "ExprNode"


# TryExprNode é alias de OptionalChainExprNode (operador postfix '?')
TryExprNode = OptionalChainExprNode


# Union type para todas as expressões
ExprNode = Union[
    LiteralNode, IdentNode, BinaryExprNode, UnaryExprNode, CallExprNode,
    IndexExprNode, FieldExprNode, BitSliceExprNode, BitNotchExprNode,
    BitStrandExprNode, CastExprNode, OptionalChainExprNode, ForceUnwrapExprNode,
    ArrayLitExprNode, ClosureExprNode, StructLitExprNode, TupleLitExprNode,
    TupleIndexExprNode, SliceExprNode, TryExprNode, IfExprNode, ArgNode,
    SpanOfNode, StrideOfNode, AlignOfNode, FieldOffsetNode,
    ComptimeExprNode, AwaitExprNode,
]


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@dataclass
class LocalVarDeclNode:
    span: Span
    is_var: bool           # var → mutável; let → imutável
    is_shielded: bool      # shielded (não reordenável pelo compilador)
    is_nvkeep: bool        # nvkeep (persistência em memória não-volátil)
    is_seal: bool          # seal (constante em tempo de link)
    name: str
    type_ann: Optional[TypeNode]
    init: ExprNode


@dataclass
class AssignmentNode:
    span: Span
    target: ExprNode
    op: TK                 # ASSIGN | PLUS_EQ | MINUS_EQ | …
    value: ExprNode


@dataclass
class HandoverNode:
    span: Span
    expr: ExprNode         # transfere posse para o chamador


@dataclass
class QuarantineNode:
    span: Span
    expr: ExprNode         # isola recurso em região island


@dataclass
class ClinchNode:
    span: Span
    body: List["StmtNode"]
    revert: List["StmtNode"]   # bloco revert (restauração)


@dataclass
class QuenchNode:
    span: Span
    body: List["StmtNode"]     # barreira de memória persistente


@dataclass
class GateNode:
    span: Span
    condition: ExprNode
    body: List["StmtNode"]


@dataclass
class EmitNode:
    span: Span
    template: str              # string de assembly
    outputs: List[ExprNode]
    inputs: List[ExprNode]
    clobbers: List[str]


@dataclass
class GuardNode:
    span: Span
    condition: ExprNode
    else_body: List["StmtNode"]


@dataclass
class IfNode:
    span: Span
    let_bind: Optional[str]    # if let x = expr
    condition: ExprNode
    then_body: List["StmtNode"]
    else_body: Optional[Union[List["StmtNode"], "IfNode"]]
    pattern: Optional["MatchPatternNode"] = None


@dataclass
class MatchArmNode:
    span: Span
    pattern: "MatchPatternNode"
    body: Union[List["StmtNode"], ExprNode]


@dataclass
class MatchPatternNode:
    span: Span
    kind: str          # "literal" | "wildcard" | "enum_variant" | "ident"
    value: Optional[Union[str, LiteralNode]]
    sub_patterns: List["MatchPatternNode"] = field(default_factory=list)


@dataclass
class MatchNode:
    span: Span
    subject: ExprNode
    arms: List[MatchArmNode]


@dataclass
class WhileNode:
    span: Span
    condition: ExprNode
    body: List["StmtNode"]
    pattern: Optional["MatchPatternNode"] = None


@dataclass
class ForNode:
    span: Span
    var: str
    iterable: ExprNode
    body: List["StmtNode"]


@dataclass
class UnsafeBlockNode:
    span: Span
    body: List["StmtNode"]


@dataclass
class ReturnNode:
    span: Span
    value: Optional[ExprNode]


@dataclass
class ReboundNode:
    span: Span     # encadeia retorno de interrupção (iret / eret)


@dataclass
class BreakNode:
    span: Span


@dataclass
class ContinueNode:
    span: Span


@dataclass
class ExprStmtNode:
    span: Span
    expr: ExprNode


@dataclass
class DeferNode:
    span: Span
    expr: Optional[ExprNode] = None
    body: Optional[List["StmtNode"]] = None


@dataclass
class DiscernCaseNode:
    span: Span
    pattern: MatchPatternNode
    guard: Optional[ExprNode]
    body: List["StmtNode"]


@dataclass
class DiscernStmtNode:
    span: Span
    subject: ExprNode
    cases: List[DiscernCaseNode]
    default_case: Optional[List["StmtNode"]] = None


@dataclass
class ProbeStmtNode:
    span: Span
    condition: ExprNode
    message: Optional[str] = None


@dataclass
class PulseStmtNode:
    span: Span
    order: Optional[str] = None  # seq_cst, acquire, release, relaxed


class GenericParam(str):
    """Representa um parâmetro genérico com suporte a const generics e bounds formais de spec, compatível com str."""
    name: str
    is_const: bool
    const_type: Optional[str]
    bound: Optional[str]

    def __new__(cls, name: str, is_const: bool = False, const_type: Optional[str] = None, bound: Optional[str] = None):
        val = f"const {name}: {const_type}" if is_const and const_type else name
        obj = super().__new__(cls, val)
        obj.name = name
        obj.is_const = is_const
        obj.const_type = const_type
        obj.bound = bound
        return obj


@dataclass
class GenericParamNode:
    span: Span
    name: str
    bound: Optional[str] = None
    is_const: bool = False
    const_type: Optional[TypeNode] = None


@dataclass
class ComptimeBlockNode:
    span: Span
    body: List["StmtNode"]


@dataclass
class AsmOperand:
    constraint: str
    expr: "ExprNode"


@dataclass
class AsmStmtNode:
    span: Span
    template: str
    is_volatile: bool = True
    outputs: List[AsmOperand] = field(default_factory=list)
    inputs: List[AsmOperand] = field(default_factory=list)
    clobbers: List[str] = field(default_factory=list)


StmtNode = Union[
    LocalVarDeclNode, AssignmentNode, HandoverNode, QuarantineNode,
    ClinchNode, QuenchNode, GateNode, EmitNode, GuardNode,
    IfNode, MatchNode, DiscernStmtNode, WhileNode, ForNode, UnsafeBlockNode,
    ReturnNode, ReboundNode, BreakNode, ContinueNode, DeferNode, ExprStmtNode,
    ProbeStmtNode, PulseStmtNode, ComptimeBlockNode, AsmStmtNode,
]


# ---------------------------------------------------------------------------
# Declarações
# ---------------------------------------------------------------------------

@dataclass
class DirectiveNode:
    span: Span
    name: str
    args: List[tuple]   # [(key, value_str), …]


@dataclass
class FieldDeclNode:
    span: Span
    directives: List[DirectiveNode]
    visibility: Optional[TK]      # KW_PUB | KW_CAPSULE | KW_LINEAGE
    is_var: bool
    is_shielded: bool
    is_nvkeep: bool
    is_seal: bool
    name: str
    type_ann: TypeNode
    default: Optional[ExprNode]


@dataclass
class ParamNode:
    span: Span
    label: Optional[str]       # rótulo externo (Objective-C style)
    name: str
    type_ann: TypeNode
    default: Optional[ExprNode]


@dataclass
class FnDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    is_irqfree: bool
    is_async: bool
    is_moldable: bool
    is_reshape: bool
    name: str
    generics: List[str]
    params: List[ParamNode]
    ret: Optional[TypeNode]
    body: Optional[List[StmtNode]]   # None → declaração em spec


@dataclass
class TrapFnDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    params: List[ParamNode]
    ret: Optional[TypeNode]
    body: List[StmtNode]


@dataclass
class InitDeclNode:
    span: Span
    visibility: Optional[TK]
    params: List[ParamNode]
    body: List[StmtNode]


@dataclass
class DeinitDeclNode:
    span: Span
    body: List[StmtNode]


@dataclass
class StructDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    generics: List[str]
    adopts: List[str]             # nomes de specs adotados
    members: List[Union[FieldDeclNode, FnDeclNode, InitDeclNode]]
    is_sole: bool = False


@dataclass
class ClassDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    generics: List[str]
    base: Optional[str]           # herança simples
    adopts: List[str]             # specs adotados
    members: List[Union[FieldDeclNode, FnDeclNode, InitDeclNode, DeinitDeclNode]]


@dataclass
class MeshMemberNode:
    span: Span
    name: str
    type_ann: TypeNode
    align: Optional[ExprNode]


@dataclass
class MeshDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    members: List[MeshMemberNode]


@dataclass
class SpecMemberNode:
    span: Span
    is_irqfree: bool
    is_async: bool
    fn_decl: FnDeclNode


@dataclass
class SpecDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    generics: List[str]
    members: List[SpecMemberNode]


@dataclass
class EnumVariantNode:
    span: Span
    name: str
    params: List[ParamNode]
    value: Optional[ExprNode]


@dataclass
class EnumDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    backing_type: Optional[TypeNode]
    variants: List[EnumVariantNode]


@dataclass
class ConstDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    type_ann: TypeNode
    value: ExprNode


@dataclass
class StaticDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    modifier: Optional[TK]     # KW_SHIELDED | KW_NVKEEP | KW_SEAL
    is_var: bool
    name: str
    type_ann: TypeNode
    value: ExprNode


@dataclass
class TypeAliasDeclNode:
    span: Span
    is_pub: bool
    name: str
    generics: List[str]
    alias: TypeNode


@dataclass
class MouldBlockNode:
    span: Span
    is_pub: bool
    body: List[StmtNode]


@dataclass
class ImportDeclNode:
    span: Span
    is_pub: bool
    path: List[str]
    items: Optional[List[str]]   # None → wildcard *


@dataclass
class ModuleDeclNode:
    span: Span
    path: List[str]


@dataclass
class RegisterFieldNode:
    span: Span
    name: str
    lo_bit: int
    hi_bit: int


@dataclass
class RegisterDeclNode:
    span: Span
    directives: List[DirectiveNode]
    is_pub: bool
    name: str
    backing_type: TypeNode
    fields: List[RegisterFieldNode]


@dataclass
class SourceFileNode:
    span: Span
    filename: str
    is_barecore: bool
    module: ModuleDeclNode
    imports: List[ImportDeclNode]
    decls: List[Union[
        StructDeclNode, ClassDeclNode, MeshDeclNode, SpecDeclNode,
        EnumDeclNode, ConstDeclNode, StaticDeclNode, FnDeclNode,
        TrapFnDeclNode, TypeAliasDeclNode, MouldBlockNode, RegisterDeclNode,
    ]]
