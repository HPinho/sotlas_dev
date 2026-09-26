"""Frontend Sotlas Bootstrap: lexer, parser recursivo, tipagem, verificação unsafe e emissor C11.

Este módulo define o contrato executável do subconjunto procedural da linguagem Sotlas:
módulos, structs com atributos, enums, globais/constantes, funções, tipos fixos,
arrays fixos [T; N], ponteiros unsafe, casts ('as'), expressões, fluxo e mangling.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import importlib
import importlib.util
from pathlib import Path
import re
import sys


class SotlasBootstrapError(Exception):
    def __init__(self, message: str, line: int = 1, column: int = 1, file: str | None = None, source: str | None = None):
        self.message = message
        self.line = line
        self.column = column
        self.file = file
        self.source = source
        loc = f"{file}:{line}:{column}" if file else f"{line}:{column}"
        snippet = ""
        if source:
            lines = source.splitlines()
            if 1 <= line <= len(lines):
                src_line = lines[line - 1]
                pointer = " " * (max(0, column - 1)) + "^"
                snippet = f"\n  {src_line}\n  {pointer}"
        super().__init__(f"{loc}: {message}{snippet}")



@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    column: int


KEYWORDS = {"module", "import", "pub", "struct", "class", "enum", "fn", "let", "mut",
            "const", "static", "return", "break", "continue", "if", "else", "while", "for", "in",
            "unsafe", "true", "false", "as", "null", "defer", "loop", "register", "sole", "move", "share", "handover", "impl"}
MULTI = ("::", "->", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "&=", "|=", "^=", "<<=", ">>=", "&&", "||", "<<", ">>", "..")
SINGLE = set(";,:{}()[]=+-*/%!<>&|^~.?")
PRIMITIVES = {"void", "bool", "u8", "u16", "u32", "u64", "usize",
              "i8", "i16", "i32", "i64", "isize", "f32", "f64", "str"}
UNSUPPORTED_OWNERSHIP_DOMAINS = {
    "exclusive", "shared",
    "whisper", "direct", "quarantine",
}
C_TYPES = {"void": "void", "bool": "_Bool", "u8": "uint8_t", "u16": "uint16_t",
           "u32": "uint32_t", "u64": "uint64_t", "usize": "size_t",
           "i8": "int8_t", "i16": "int16_t", "i32": "int32_t", "i64": "int64_t",
           "isize": "intptr_t", "f32": "float", "f64": "double", "str": "char"}


def get_c_type(name: str) -> str:
    if name in C_TYPES:
        return C_TYPES[name]
    if (name.startswith("u") or name.startswith("i")) and name[1:].isdigit():
        width = int(name[1:])
        prefix = "uint" if name.startswith("u") else "int"
        if width <= 8: return f"{prefix}8_t"
        if width <= 16: return f"{prefix}16_t"
        if width <= 32: return f"{prefix}32_t"
        return f"{prefix}64_t"
    return name

# Literais com sufixo mantêm a intenção de tipo na AST, mas o backend C emite
# um cast explícito, pois `1u32` não é sintaxe válida em C. O formato segue a
# linguagem Sotlas, não os sufixos do C/C++.
INTEGER_LITERAL_SUFFIXES = ("usize", "isize", "u64", "i64", "u32", "i32", "u16", "i16", "u8", "i8")
FLOAT_LITERAL_SUFFIXES = ("f32", "f64")
NUMBER_LITERAL_RE = re.compile(
    r"(?:[0-9]+\.[0-9]+(?:usize|isize|u64|i64|u32|i32|u16|i16|u8|i8|f32|f64)?|(?:0x[0-9A-Fa-f]+|0b[01]+|[0-9]+)(?:usize|isize|u64|i64|u32|i32|u16|i16|u8|i8)?)"
)


def numeric_literal_parts(text: str) -> tuple[str, str | None]:
    for suffix in INTEGER_LITERAL_SUFFIXES + FLOAT_LITERAL_SUFFIXES:
        if text.endswith(suffix):
            return text[:-len(suffix)], suffix
    return text, None


def numeric_literal_type(text: str) -> str:
    base, suffix = numeric_literal_parts(text)
    if suffix:
        if "." in base and suffix not in FLOAT_LITERAL_SUFFIXES:
            raise ValueError("sufixo inteiro não pode ser aplicado a literal decimal")
        return suffix
    return "f64" if "." in base else "i64"


def integer_literal_value(text: str) -> int:
    base, suffix = numeric_literal_parts(text)
    if suffix in FLOAT_LITERAL_SUFFIXES or "." in base:
        raise ValueError("literal inteiro esperado")
    return int(base, 0)


def lex(source: str, filename: str | None = None) -> list[Token]:
    tokens: list[Token] = []
    i = line = 0
    column = 1
    while i < len(source):
        ch = source[i]
        if ch in " \t\r":
            i += 1; column += 1; continue
        if ch == "\n":
            i += 1; line += 1; column = 1; continue
        if source.startswith("//", i):
            end = source.find("\n", i)
            if end < 0: break
            column = 1; line += 1; i = end + 1; continue
        if source.startswith("/*", i):
            end = source.find("*/", i)
            if end < 0:
                raise SotlasBootstrapError("comentário de bloco não finalizado", line + 1, column, filename, source)
            block_text = source[i:end + 2]
            nl_count = block_text.count("\n")
            if nl_count > 0:
                line += nl_count
                column = len(block_text) - block_text.rfind("\n")
            else:
                column += len(block_text)
            i = end + 2
            continue
        start_col = column
        # Atributos: @ident ou @ident(args)
        if ch == "@":
            match = re.match(r"@[A-Za-z_][A-Za-z0-9_]*(?:\([^\)]*\))?", source[i:])
            if match:
                text = match.group(0)
                tokens.append(Token("ATTR", text, line + 1, start_col))
                i += len(text); column += len(text); continue
        # Strings literais com escape (\", \\)
        if ch == '"':
            j = i + 1
            while j < len(source):
                if source[j] == '\\':
                    j += 2
                    continue
                if source[j] == '"':
                    break
                j += 1
            if j >= len(source):
                raise SotlasBootstrapError("string literal não terminada", line + 1, start_col, filename, source)
            text = source[i:j + 1]
            tokens.append(Token("STRING", text, line + 1, start_col))
            i = j + 1; column += len(text); continue
        # Char literais
        if ch == "'":
            j = i + 1
            while j < len(source):
                if source[j] == '\\':
                    j += 2
                    continue
                if source[j] == "'":
                    break
                j += 1
            if j >= len(source):
                raise SotlasBootstrapError("caractere literal não terminado", line + 1, start_col, filename, source)
            text = source[i:j + 1]
            tokens.append(Token("CHAR", text, line + 1, start_col))
            i = j + 1; column += len(text); continue
        pair = next((item for item in MULTI if source.startswith(item, i)), None)
        if pair:
            tokens.append(Token(pair, pair, line + 1, start_col)); i += len(pair); column += len(pair); continue
        if ch in SINGLE:
            tokens.append(Token(ch, ch, line + 1, start_col)); i += 1; column += 1; continue
        if ch.isdigit():
            match = NUMBER_LITERAL_RE.match(source[i:])
            assert match
            text = match.group(0); tokens.append(Token("NUMBER", text, line + 1, start_col)); i += len(text); column += len(text); continue
        if ch.isalpha() or ch == "_":
            match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[i:])
            assert match
            text = match.group(0); tokens.append(Token(text if text in KEYWORDS else "IDENT", text, line + 1, start_col)); i += len(text); column += len(text); continue
        raise SotlasBootstrapError(f"caractere léxico inválido: {ch!r}", line + 1, column, filename, source)
    tokens.append(Token("EOF", "", line + 1, column))
    return tokens


@dataclass(frozen=True)
class Type:
    name: str
    pointer: bool = False
    mutable: bool = False
    is_array: bool = False
    array_size: int | str = 0
    elem_type: Type | None = None
    # Suporte a ponteiros de funcao: fn(T1, T2) -> R
    is_fn_ptr: bool = False
    fn_params: tuple = ()  # tuple[Type, ...]
    fn_ret: Type | None = None
    is_reference: bool = False
    ownership_domain: str | None = None
    state_space: str | None = None
    state_name: str | None = None

    def base_c(self) -> str:
        if self.is_fn_ptr:
            return self._fn_ptr_c("")
        if self.is_array and self.elem_type:
            return self.elem_type.base_c()
        base = get_c_type(self.name)
        if self.pointer:
            prefix = "" if self.mutable else "const "
            return f"{prefix}{base} *"
        return base

    def _fn_ptr_c(self, var_name: str) -> str:
        """Emite o typedef correto para ponteiro de funcao: ret_t (*var_name)(p1, p2)."""
        ret = self.fn_ret.c() if self.fn_ret else "void"
        params = ", ".join(p.c() for p in self.fn_params) if self.fn_params else "void"
        if var_name:
            return f"{ret} (*{var_name})({params})"
        return f"{ret}(*)({params})"

    def array_dims(self) -> str:
        if not self.is_array:
            return ""
        child_dims = self.elem_type.array_dims() if self.elem_type else ""
        return f"[{self.array_size}]{child_dims}"

    def c(self) -> str:
        if self.is_fn_ptr:
            return self._fn_ptr_c("")
        if self.is_array:
            return f"{self.base_c()} *"
        base = get_c_type(self.name)
        if self.pointer:
            prefix = "" if self.mutable else "const "
            return f"{prefix}{base} *"
        return base

    def display(self) -> str:
        if self.state_space is not None and self.state_name is not None:
            return f"{self.name}<{self.state_name}>"
        return self.name

    def c_decl(self, var_name: str) -> str:
        if self.is_fn_ptr:
            return self._fn_ptr_c(var_name)
        if self.is_array:
            return f"{self.base_c()} {var_name}{self.array_dims()}"
        return f"{self.c()} {var_name}"


@dataclass
class Expr: token: Token
@dataclass
class Number(Expr): value: str
@dataclass
class Boolean(Expr): value: bool
@dataclass
class StringLit(Expr): value: str
@dataclass
class CharLit(Expr): value: str
@dataclass
class NullLit(Expr): pass
@dataclass
class UnsafeExpr(Expr): value: Expr
@dataclass
class MoveExpr(Expr): value: Expr
@dataclass
class ShareExpr(Expr): value: Expr
@dataclass
class Name(Expr): value: str
@dataclass
class EnumAccess(Expr): enum_name: str; variant: str
@dataclass
class Unary(Expr):
    op: str
    value: Expr
    mutable: bool = False
@dataclass
class Binary(Expr): left: Expr; op: str; right: Expr
@dataclass
class Call(Expr): callee: str; args: list[Expr]
@dataclass
class Index(Expr): target: Expr; index: Expr
@dataclass
class Member(Expr): target: Expr; field: str; is_pointer_target: bool = False
@dataclass
class MethodCall(Expr):
    target: Expr
    method: str
    args: list[Expr]
    target_type: Type | None = None
    pass_by_ref: bool = False
    is_vtable_call: bool = False
    is_arrow: bool = False
@dataclass
class Cast(Expr): expr: Expr; target_type: Type
@dataclass
class ArrayLit(Expr):
    elements: list[Expr]
    is_repeat: bool = False
    repeat_size: int | str = 0
@dataclass
class StructLit(Expr):
    struct_name: str
    fields: list[tuple[str, Expr]]
@dataclass
class IfExpr(Expr):
    condition: Expr
    then_expr: Expr
    else_expr: Expr
@dataclass
class TryExpr(Expr):
    expr: Expr

@dataclass
class Stmt: token: Token
@dataclass
class Let(Stmt):
    name: str
    type: Type | None
    value: Expr
    is_mut: bool = False
    is_const: bool = False
    is_static: bool = False
@dataclass
class Assign(Stmt): target: Expr; value: Expr
@dataclass
class Return(Stmt): value: Expr | None
@dataclass
class Break(Stmt): pass
@dataclass
class Continue(Stmt): pass
@dataclass
class Handover(Stmt):
    value: Expr
    destination: Expr | None = None
@dataclass
class Quarantine(Stmt): value: Expr
@dataclass
class Loop(Stmt): body: list[Stmt]
@dataclass
class If(Stmt): condition: Expr; then_body: list[Stmt]; else_body: list[Stmt]
@dataclass
class StateCase:
    token: Token
    state_name: str
    body: list[Stmt]
@dataclass
class Discern(Stmt): subject: Expr; cases: list[StateCase]
@dataclass(frozen=True)
class FlowStageDecl:
    token: Token
    name: str
    function: str
    dependencies: tuple[str, ...]
@dataclass(frozen=True)
class FlowDecl:
    token: Token
    name: str
    stages: tuple[FlowStageDecl, ...]
    public: bool = False
@dataclass
class While(Stmt): condition: Expr; body: list[Stmt]
@dataclass
class For(Stmt):
    var_name: str
    start: Expr
    end: Expr
    body: list[Stmt]
    is_mut: bool = False
@dataclass
class Unsafe(Stmt): body: list[Stmt]
@dataclass
class Expression(Stmt): value: Expr
@dataclass
class Defer(Stmt):
    value: Expr | None = None
    body: list[Stmt] | None = None
    auto_cleanup_name: str | None = None

    def __post_init__(self):
        if self.value is None and self.body is None:
            raise ValueError("Defer must have either value or body")
        if self.value is not None and self.body is not None:
            raise ValueError("Defer cannot have both value and body")
@dataclass
class Asm(Stmt):
    code: str
    outputs: list[Expr] = field(default_factory=list)
    inputs: list[Expr] = field(default_factory=list)
    clobbers: list[str] = field(default_factory=list)

@dataclass
class FieldDef:
    name: str
    type: Type
    bit_width: int | None = None

@dataclass
class Struct:
    name: str
    fields: list[FieldDef]
    public: bool = False
    attributes: list[str] = field(default_factory=list)
    methods: list[Function] = field(default_factory=list)
    is_register: bool = False
    backing_type: Type | None = None
    is_sole: bool = False

@dataclass
class Class:
    name: str
    fields: list[FieldDef]
    methods: list[Function]
    public: bool = False
    attributes: list[str] = field(default_factory=list)

@dataclass
class EnumVariant:
    name: str
    value: int | None = None
    payload_type: Type | None = None

@dataclass
class Enum:
    name: str
    variants: list[EnumVariant]
    public: bool = False

@dataclass
class Global:
    name: str
    type: Type
    value: Expr
    is_const: bool = False
    is_mut: bool = False
    public: bool = False

@dataclass
class Function:
    name: str
    params: list[tuple[str, Type]]
    result: Type
    body: list[Stmt]
    public: bool = False
    attributes: list[str] = field(default_factory=list)

@dataclass
class Module:
    name: str
    imports: list[str] = field(default_factory=list)
    structs: list[Struct] = field(default_factory=list)
    classes: list[Class] = field(default_factory=list)
    enums: list[Enum] = field(default_factory=list)
    globals: list[Global] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)
    filename: str | None = None
    source: str | None = None
    flows: list[FlowDecl] = field(default_factory=list)


class Parser:
    def __init__(self, tokens: list[Token], filename: str | None = None, source: str | None = None):
        self.tokens = tokens
        self.at = 0
        self.filename = filename
        self.source = source

    @property
    def current(self) -> Token: return self.tokens[self.at]

    def accept(self, kind: str) -> Token | None:
        if self.current.kind == kind:
            token = self.current; self.at += 1; return token
        return None

    def expect(self, kind: str) -> Token:
        token = self.accept(kind)
        if token: return token
        raise SotlasBootstrapError(f"esperado {kind}, encontrado {self.current.kind}",
                        self.current.line, self.current.column, self.filename, self.source)

    def _accept_ident_or_contextual(self) -> bool:
        if self.current.kind == "IDENT" or self.current.kind in ("pulse", "probe", "forge", "enclave", "discern"):
            self.at += 1
            return True
        return False

    def ident(self) -> str:
        if self._accept_ident_or_contextual():
            return self.tokens[self.at - 1].text
        return self.expect("IDENT").text

    def path(self) -> str:
        parts = [self.ident()]
        while self.current.kind == "::" and (self.tokens[self.at + 1].kind == "IDENT" or self.tokens[self.at + 1].kind in ("pulse", "probe", "forge", "enclave", "discern")):
            self.at += 1; parts.append(self.ident())
        return "::".join(parts)

    def _fn_ptr_type(self) -> Type:
        """Parseia fn(T1, T2, ...) -> R como tipo ponteiro de funcao."""
        self.expect("(")
        params: list[Type] = []
        if not self.accept(")"):
            while True:
                params.append(self.type())
                if self.accept(")"):
                    break
                self.expect(",")
        ret = self.type() if self.accept("->") else Type("void")
        return Type(name="__fn_ptr", is_fn_ptr=True, fn_params=tuple(params), fn_ret=ret)

    def _field_type(self) -> Type:
        """Tipo de campo de struct: 'nome: tipo' ou 'nome: fn(...)->R'."""
        self.expect(":")
        if self.current.kind == "fn":
            self.at += 1
            return self._fn_ptr_type()
        return self.type()

    def type(self) -> Type:
        if (
            self.current.kind == "IDENT"
            and self.current.text in (
                "island", "whisper", "direct", "region", "device", "external"
            )
        ):
            token = self.current
            domain = self.current.text
            self.at += 1
            inner = self.type()
            if getattr(inner, "ownership_domain", None) is not None:
                raise SotlasBootstrapError(
                    "ownership modifier duplicado",
                    token.line, token.column, self.filename, self.source,
                )
            if domain in ("whisper", "direct"):
                if (
                    inner.is_array
                    or inner.is_fn_ptr
                    or inner.pointer
                    or inner.is_reference
                    or inner.mutable
                ):
                    raise SotlasBootstrapError(
                        f"{domain} currently requires an unqualified, direct "
                        "non-array value type",
                        token.line, token.column, self.filename, self.source,
                    )
                return replace(
                    inner,
                    pointer=True,
                    mutable=False,
                    is_reference=True,
                    ownership_domain=domain,
                )
            if domain in ("region", "device", "external") and (
                inner.is_array or inner.is_fn_ptr or inner.pointer or inner.is_reference
            ):
                raise SotlasBootstrapError(
                    f"{domain} ownership requires a direct by-value type",
                    token.line, token.column, self.filename, self.source,
                )
            return replace(inner, ownership_domain=domain)
        if self.accept("!"):
            return Type("void")
        if self.accept("fn"):
            return self._fn_ptr_type()
        # Array fixo: [T; N]
        if self.accept("["):
            elem_type = self.type()
            self.expect(";")
            if self.current.kind == "NUMBER":
                size_tok = self.expect("NUMBER")
                size = integer_literal_value(size_tok.text)
            else:
                size_tok = self.expect("IDENT")
                size = size_tok.text
            self.expect("]")
            return Type(
                name=elem_type.name,
                pointer=elem_type.pointer,
                mutable=elem_type.mutable,
                is_array=True,
                array_size=size,
                elem_type=elem_type,
                state_space=elem_type.state_space,
                state_name=elem_type.state_name,
            )
        if self.accept("&"):
            is_mut = bool(self.accept("mut"))
            inner = self.type()
            return replace(
                inner,
                pointer=True,
                mutable=is_mut,
                is_reference=True,
            )
        pointer = False; mutable = False
        if self.accept("*"):
            pointer = True
            if self.accept("mut"): mutable = True
            elif self.accept("const"): mutable = False
            elif self.current.kind == "IDENT" and self.current.text in ("const", "mut"):
                mutable = (self.current.text == "mut")
                self.at += 1
            inner = self.type()
            return replace(
                inner,
                pointer=True,
                mutable=mutable,
                is_reference=False,
            )
        base_name = self.ident()
        if base_name in UNSUPPORTED_OWNERSHIP_DOMAINS:
            token = self.tokens[self.at - 1]
            raise SotlasBootstrapError(
                f"ownership domain {base_name!r} is reserved but not supported",
                token.line, token.column, self.filename, self.source,
            )
        # Generics monomorfizados: forge<...> ou <...>
        _PRIMITIVES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64", "bool", "usize", "isize", "void", "char"}
        if base_name not in _PRIMITIVES and ((self.current.kind in ("forge", "IDENT") and self.current.text == "forge") or self.current.kind == "<"):
            is_generic = True
            if self.current.kind == "<":
                pos = self.at + 1
                depth = 1
                found_closing = False
                while pos < len(self.tokens) and self.tokens[pos].kind not in (";", "{", "}", "EOF", "||", "&&"):
                    if self.tokens[pos].kind == "<":
                        depth += 1
                    elif self.tokens[pos].kind == ">":
                        depth -= 1
                        if depth == 0:
                            found_closing = True
                            break
                    pos += 1
                if not found_closing:
                    is_generic = False
            if is_generic:
                if self.current.text == "forge": self.at += 1
                if self.accept("<"):
                    depth = 1
                    while depth > 0 and self.current.kind != "EOF":
                        if self.current.kind == "<": depth += 1
                        elif self.current.kind == ">": depth -= 1
                        self.at += 1
        return Type(base_name, pointer, mutable)

    def _parse_method(self, parent_name: str, member_pub: bool, member_attrs: list[str]) -> Function:
        mname = self.ident()
        self.expect("(")
        mparams = []
        if not self.accept(")"):
            while True:
                is_ref = False
                is_mut = False
                if self.accept("&"):
                    is_ref = True
                    if self.accept("mut"):
                        is_mut = True
                elif self.accept("mut"):
                    is_mut = True

                if self.current.kind == "IDENT" and self.current.text == "self":
                    self.at += 1
                    if self.accept(":"):
                        ptype = self.type()
                        if ptype.name == "Self":
                            ptype = replace(ptype, name=parent_name)
                    else:
                        ptype = Type(parent_name, pointer=is_ref, mutable=is_mut, is_reference=is_ref)
                    mparams.append(("self", ptype))
                else:
                    pname = self.ident()
                    self.expect(":")
                    ptype = self.type()
                    if ptype.name == "Self":
                        ptype = replace(ptype, name=parent_name)
                    mparams.append((pname, ptype))
                if self.accept(")"):
                    break
                self.expect(",")
        mresult = self.type() if self.accept("->") else Type("void")
        if mresult.name == "Self":
            mresult = replace(mresult, name=parent_name)
        mbody = self.block()
        fn_name = f"{parent_name}_{mname}"
        return Function(fn_name, mparams, mresult, mbody, member_pub, member_attrs)

    def parse(self) -> Module:
        self.expect("module")
        module = Module(self.path(), filename=self.filename, source=self.source)
        self.expect(";")
        while self.current.kind != "EOF":
            if self.accept("import"):
                module.imports.append(self.path())
                self.expect("::"); self.expect("*"); self.expect(";")
                continue

            # Coleta atributos opcionais antes de declarações
            attributes: list[str] = []
            while self.current.kind == "ATTR":
                attributes.append(self.accept("ATTR").text)

            public = bool(self.accept("pub"))
            is_sole = bool(self.accept("sole"))
            if not public and not is_sole:
                public = bool(self.accept("pub"))
            if not is_sole and public:
                is_sole = bool(self.accept("sole"))

            if self.current.kind == "IDENT" and self.current.text == "flow":
                flow_token = self.current
                self.at += 1
                flow_name = self.ident()
                self.expect("{")
                stages = []
                while self.current.kind != "}":
                    stage_token = self.current
                    if stage_token.kind != "IDENT" or stage_token.text != "stage":
                        raise SotlasBootstrapError(
                            "flow declarations require 'stage name = function' entries",
                            stage_token.line, stage_token.column,
                            self.filename, self.source,
                        )
                    self.at += 1
                    stage_name = self.ident()
                    self.expect("=")
                    function_name = self.ident()
                    dependencies = []
                    if self.current.kind == "IDENT" and self.current.text == "after":
                        self.at += 1
                        dependencies.append(self.ident())
                        while self.accept(","):
                            dependencies.append(self.ident())
                    self.expect(";")
                    stages.append(FlowStageDecl(
                        stage_token, stage_name, function_name,
                        tuple(dependencies),
                    ))
                self.expect("}")
                module.flows.append(FlowDecl(
                    flow_token, flow_name, tuple(stages), public
                ))
                continue

            if self.accept("struct"):
                name = self.ident()
                if (self.current.kind in ("forge", "IDENT") and self.current.text == "forge") or self.current.kind == "<":
                    if self.current.text == "forge": self.at += 1
                    if self.accept("<"):
                        depth = 1
                        while depth > 0 and self.current.kind != "EOF":
                            if self.current.kind == "<": depth += 1
                            elif self.current.kind == ">": depth -= 1
                            self.at += 1
                self.expect("{")
                fields = []
                methods = []
                while not self.accept("}"):
                    member_attrs: list[str] = []
                    while self.current.kind == "ATTR":
                        member_attrs.append(self.accept("ATTR").text)
                    member_pub = bool(self.accept("pub"))
                    if self.accept("fn"):
                        methods.append(self._parse_method(name, member_pub, member_attrs))
                    else:
                        fname = self.ident()
                        ftype = self._field_type()
                        bw = None
                        if self.accept(":"):
                            bw = integer_literal_value(self.expect("NUMBER").text)
                        fields.append(FieldDef(fname, ftype, bit_width=bw))
                        self.expect(";")
                module.structs.append(Struct(name, fields, public, attributes, methods=methods, is_sole=is_sole))
                for m in methods:
                    module.functions.append(m)
                continue

            if self.accept("register"):
                name = self.ident()
                backing = Type("u32")
                if self.accept(":"):
                    backing = self.type()
                self.expect("{")
                fields = []
                while not self.accept("}"):
                    fname = self.ident()
                    self.expect(":")
                    ftype = self.type()
                    bw = None
                    if self.accept(":"):
                        bw = integer_literal_value(self.expect("NUMBER").text)
                    elif self.accept("["):
                        lo = integer_literal_value(self.expect("NUMBER").text)
                        if self.accept(".."):
                            hi = integer_literal_value(self.expect("NUMBER").text)
                            bw = (hi - lo) + 1
                        else:
                            bw = 1
                        self.expect("]")
                    elif (ftype.name.startswith("u") or ftype.name.startswith("i")) and ftype.name[1:].isdigit():
                        w = int(ftype.name[1:])
                        if w < 64:
                            bw = w
                    fields.append(FieldDef(fname, ftype, bit_width=bw))
                    if not self.accept(","):
                        if self.current.kind != "}":
                            self.accept(";")
                module.structs.append(Struct(name, fields, public, attributes, is_register=True, backing_type=backing))
                continue

            if self.accept("class"):
                name = self.ident()
                if (self.current.kind in ("forge", "IDENT") and self.current.text == "forge") or self.current.kind == "<":
                    if self.current.text == "forge": self.at += 1
                    if self.accept("<"):
                        depth = 1
                        while depth > 0 and self.current.kind != "EOF":
                            if self.current.kind == "<": depth += 1
                            elif self.current.kind == ">": depth -= 1
                            self.at += 1
                self.expect("{")
                fields = []
                methods = []
                while not self.accept("}"):
                    member_attrs: list[str] = []
                    while self.current.kind == "ATTR":
                        member_attrs.append(self.accept("ATTR").text)
                    member_pub = bool(self.accept("pub"))
                    if self.accept("fn"):
                        methods.append(self._parse_method(name, member_pub, member_attrs))
                    else:
                        fields.append(FieldDef(self.ident(), self._field_type()))
                        self.expect(";")
                cls = Class(name, fields, methods, public, attributes)
                module.classes.append(cls)
                module.structs.append(Struct(name, fields, public, attributes, methods=methods))
                for m in methods:
                    module.functions.append(m)
                continue

            if self.accept("enum"):
                name = self.ident(); self.expect("{"); variants = []
                while not self.accept("}"):
                    vname = self.ident()
                    vval = None
                    payload_type = None
                    if self.accept("("):
                        payload_type = self.type()
                        self.expect(")")
                    if self.accept("="):
                        if payload_type is not None:
                            raise SotlasBootstrapError(
                                "enum variant payload cannot also declare an integer discriminant",
                                self.current.line,
                                self.current.column,
                                self.filename,
                                self.source,
                            )
                        val_tok = self.expect("NUMBER")
                        vval = integer_literal_value(val_tok.text)
                    variants.append(
                        EnumVariant(vname, vval, payload_type)
                    )
                    if not self.accept(","):
                        if self.current.kind != "}":
                            self.expect(",")
                module.enums.append(Enum(name, variants, public))
                continue

            if self.accept("const"):
                name = self.ident(); self.expect(":"); typ = self.type()
                self.expect("="); val = self.expression(); self.expect(";")
                module.globals.append(Global(name, typ, val, is_const=True, is_mut=False, public=public))
                continue

            if self.accept("static"):
                is_mut = bool(self.accept("mut"))
                name = self.ident(); self.expect(":"); typ = self.type()
                self.expect("="); val = self.expression(); self.expect(";")
                module.globals.append(Global(name, typ, val, is_const=False, is_mut=is_mut, public=public))
                continue

            if self.accept("impl"):
                target_name = self.ident()
                self.expect("{")
                while not self.accept("}"):
                    member_attrs: list[str] = []
                    while self.current.kind == "ATTR":
                        member_attrs.append(self.accept("ATTR").text)
                    member_pub = bool(self.accept("pub"))
                    if self.accept("fn"):
                        module.functions.append(self._parse_method(target_name, member_pub, member_attrs))
                    else:
                        raise SotlasBootstrapError("apenas métodos 'fn' são permitidos dentro de blocos 'impl'", self.current.line, self.current.column, self.filename, self.source)
                continue

            if self.accept("fn"):
                module.functions.append(self.function(public, attributes))
                continue

            raise SotlasBootstrapError("declaração de topo Sotlas Bootstrap inválida", self.current.line, self.current.column, self.filename, self.source)
        return module

    def function(self, public: bool, attributes: list[str] | None = None) -> Function:
        name = self.ident(); self.expect("("); params = []
        if not self.accept(")"):
            while True:
                pname = self.ident(); self.expect(":"); params.append((pname, self.type()))
                if self.accept(")"): break
                self.expect(",")
        result = Type("void")
        if self.accept("->"): result = self.type()
        attributes = attributes or []
        if self.accept(";"):
            if "@extern(C)" not in attributes:
                raise SotlasBootstrapError(
                    "function declarations without a body require @extern(C)",
                    self.current.line, self.current.column,
                    self.filename, self.source,
                )
            return Function(name, params, result, [], public, attributes)
        return Function(name, params, result, self.block(), public, attributes)

    def block(self) -> list[Stmt]:
        self.expect("{"); body = []
        while not self.accept("}"): body.append(self.statement())
        return body

    def statement(self) -> Stmt:
        token = self.current
        if self.current.kind == "IDENT" and self.current.text == "discern":
            self.at += 1
            subject = self.expression()
            self.expect("{")
            cases = []
            while self.current.kind != "}":
                case_token = self.current
                if case_token.kind != "IDENT" or case_token.text == "_":
                    raise SotlasBootstrapError(
                        "discern State Space accepts named state arms only",
                        case_token.line, case_token.column,
                        self.filename, self.source,
                    )
                self.at += 1
                self.expect("=")
                self.expect(">")
                body = self.block()
                cases.append(StateCase(case_token, case_token.text, body))
                self.accept(",")
                self.accept(";")
            self.expect("}")
            return Discern(token, subject, cases)
        if self.accept("let"):
            is_mut = bool(self.accept("mut"))
            name = self.ident(); typ = None
            if self.accept(":"): typ = self.type()
            self.expect("="); value = self.expression(); self.expect(";")
            return Let(token, name, typ, value, is_mut=is_mut)
        if self.accept("const"):
            name = self.ident(); typ = None
            if self.accept(":"): typ = self.type()
            self.expect("="); value = self.expression(); self.expect(";")
            return Let(token, name, typ, value, is_const=True)
        if self.accept("static"):
            is_const = bool(self.accept("const"))
            is_mut = bool(self.accept("mut"))
            name = self.ident(); typ = None
            if self.accept(":"): typ = self.type()
            self.expect("="); value = self.expression(); self.expect(";")
            return Let(
                token,
                name,
                typ,
                value,
                is_mut=is_mut,
                is_const=is_const,
                is_static=True,
            )
        if self.accept("return"):
            value = None if self.current.kind == ";" else self.expression()
            self.expect(";"); return Return(token, value)
        if self.accept("break"):
            self.expect(";")
            return Break(token)
        if self.accept("continue"):
            self.expect(";")
            return Continue(token)
        if self.accept("handover"):
            value = self.expression()
            destination = None
            if self.current.kind == "IDENT" and self.current.text == "to":
                self.at += 1
                destination = self.expression()
            self.expect(";")
            return Handover(token, value, destination)
        if self.current.kind == "IDENT" and self.current.text == "quarantine":
            self.at += 1
            value = self.expression()
            self.expect(";")
            return Quarantine(token, value)
        if self.accept("if"):
            condition = self.expression()
            then_body = self.block()
            else_body = []
            if self.accept("else"):
                if self.current.kind == "if":
                    else_body = [self.statement()]
                else:
                    else_body = self.block()
            return If(token, condition, then_body, else_body)
        if self.accept("while"): return While(token, self.expression(), self.block())
        if self.accept("loop"): return Loop(token, self.block())
        if self.accept("for"):
            is_mut = bool(self.accept("mut"))
            var_name = self.ident()
            self.expect("in")
            start_expr = self.expression()
            self.expect("..")
            end_expr = self.expression()
            body = self.block()
            return For(token, var_name, start_expr, end_expr, body, is_mut)
        if self.accept("unsafe"): return Unsafe(token, self.block())
        if self.accept("defer"):
            if self.current.kind == "{":
                body = self.block()
                return Defer(token, body=body)
            else:
                expr = self.expression()
                if self.accept("="):
                    value = self.expression()
                    self.expect(";")
                    return Defer(token, Assign(token, expr, value))
                self.expect(";")
                return Defer(token, expr)

        if (self.current.kind == "IDENT" and self.current.text in ("__asm__", "asm")) or self.accept("emit"):
            tok = self.current
            if self.current.kind == "IDENT":
                self.at += 1
            if self.current.kind == "IDENT" and self.current.text in ("volatile", "__volatile__"):
                self.at += 1
            self.expect("(")
            asm_code = self.expect("STRING").text
            outputs, inputs, clobbers = [], [], []
            if self.accept(":"):
                while self.current.kind not in (":", ")", "EOF"):
                    outputs.append(self.expression())
                    if not self.accept(","): break
                if self.accept(":"):
                    while self.current.kind not in (":", ")", "EOF"):
                        inputs.append(self.expression())
                        if not self.accept(","): break
                    if self.accept(":"):
                        while self.current.kind not in (")", "EOF"):
                            if self.current.kind == "STRING":
                                clobbers.append(self.current.text)
                                self.at += 1
                            if not self.accept(","): break
            self.expect(")")
            self.expect(";")
            return Asm(tok, asm_code, outputs, inputs, clobbers)

        # Expressão ou Atribuição
        expr = self.expression()
        if self.accept("="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, value)
        if self.accept("+="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, Binary(token, expr, "+", value))
        if self.accept("-="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, Binary(token, expr, "-", value))
        if self.accept("*="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, Binary(token, expr, "*", value))
        if self.accept("/="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, Binary(token, expr, "/", value))
        if self.accept("&="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, Binary(token, expr, "&", value))
        if self.accept("|="):
            value = self.expression(); self.expect(";")
            return Assign(token, expr, Binary(token, expr, "|", value))
        self.expect(";")
        return Expression(token, expr)

    PRECEDENCE = {"||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6, "<": 7, "<=": 7, ">": 7, ">=": 7, "<<": 8, ">>": 8, "+": 9, "-": 9, "*": 10, "/": 10, "%": 10}

    def expression(self, minimum: int = 1) -> Expr:
        left = self.prefix()
        while self.current.kind in self.PRECEDENCE and self.PRECEDENCE[self.current.kind] >= minimum:
            op = self.current; self.at += 1
            right = self.expression(self.PRECEDENCE[op.kind] + 1)
            left = Binary(op, left, op.kind, right)
        return left

    def primary(self) -> Expr:
        token = self.current
        if self.accept("NUMBER"): expr = Number(token, token.text)
        elif self.accept("STRING"): expr = StringLit(token, token.text)
        elif self.accept("CHAR"): expr = CharLit(token, token.text)
        elif self.accept("null"): expr = NullLit(token)
        elif self.accept("true"): expr = Boolean(token, True)
        elif self.accept("false"): expr = Boolean(token, False)
        elif self.accept("unsafe"):
            self.expect("{")
            expr = UnsafeExpr(token, self.expression())
            self.expect("}")
        elif self.accept("["):
            elements = []
            if not self.accept("]"):
                first = self.expression()
                if self.accept(";"):
                    if self.current.kind == "NUMBER":
                        size_tok = self.expect("NUMBER")
                        size = integer_literal_value(size_tok.text)
                    else:
                        size_tok = self.expect("IDENT")
                        size = size_tok.text
                    self.expect("]")
                    expr = ArrayLit(token, [first], is_repeat=True, repeat_size=size)
                else:
                    elements.append(first)
                    while self.accept(","):
                        if self.current.kind == "]":
                            break
                        elements.append(self.expression())
                    self.expect("]")
                    expr = ArrayLit(token, elements)
            else:
                expr = ArrayLit(token, [])
        elif self.accept("if"):
            cond = self.expression()
            self.expect("{")
            then_expr = self.expression()
            self.expect("}")
            self.expect("else")
            if self.accept("{"):
                else_expr = self.expression()
                self.expect("}")
            elif self.current.kind == "if":
                else_expr = self.primary()
            else:
                else_expr = self.expression()
            expr = IfExpr(token, cond, then_expr, else_expr)
        elif self.accept("("):
            expr = self.expression()
            self.expect(")")
        elif self._accept_ident_or_contextual():
            token = self.tokens[self.at - 1]
            name = token.text
            # Optional generics: forge<T>
            if self.current.kind in ("forge", "IDENT") and self.current.text == "forge":
                self.at += 1
                if self.accept("<"):
                    depth = 1
                    while depth > 0 and self.current.kind != "EOF":
                        if self.current.kind == "<": depth += 1
                        elif self.current.kind == ">": depth -= 1
                        self.at += 1
            # Struct literal: IDENT { field: val, ... }
            if (self.current.kind == "{" and self.at + 2 < len(self.tokens) and
                    (self.tokens[self.at + 1].kind == "IDENT" or self.tokens[self.at + 1].kind in ("pulse", "probe", "forge", "enclave", "discern")) and self.tokens[self.at + 2].kind == ":"):
                self.expect("{")
                fields = []
                while not self.accept("}"):
                    fname = self.ident()
                    self.expect(":")
                    fval = self.expression()
                    fields.append((fname, fval))
                    if not self.accept(","):
                        if self.current.kind != "}":
                            self.expect(",")
                expr = StructLit(token, name, fields)
            elif self.accept("::"):
                variant_name = self.ident()
                if self.accept("("):
                    args = []
                    if not self.accept(")"):
                        while True:
                            args.append(self.expression())
                            if self.accept(")"): break
                            self.expect(",")
                    expr = Call(token, f"{name}_{variant_name}", args)
                else:
                    expr = EnumAccess(token, name, variant_name)
            elif self.accept("("):
                args = []
                if not self.accept(")"):
                    while True:
                        args.append(self.expression())
                        if self.accept(")"): break
                        self.expect(",")
                expr = Call(token, name, args)
            else:
                expr = Name(token, name)
        else:
            raise SotlasBootstrapError(f"expressão inválida: {self.current.text!r}", token.line, token.column, self.filename, self.source)

        # Postfix parsing: chamadas adicionais, índices, membros/métodos, casts
        while True:
            if self.accept("["):
                idx = self.expression()
                self.expect("]")
                expr = Index(expr.token, expr, idx)
            elif self.accept("."):
                field_name = self.ident()
                if self.accept("("):
                    args = []
                    if not self.accept(")"):
                        while True:
                            args.append(self.expression())
                            if self.accept(")"): break
                            self.expect(",")
                    expr = MethodCall(expr.token, expr, field_name, args)
                else:
                    expr = Member(expr.token, expr, field_name)
            elif self.accept("as"):
                target_type = self.type()
                expr = Cast(expr.token, expr, target_type)
            elif self.accept("?"):
                expr = TryExpr(expr.token, expr)
            else:
                break
        return expr

    def prefix(self) -> Expr:
        token = self.current
        if self.accept("move"):
            return MoveExpr(token, self.prefix())
        if self.accept("share"):
            return ShareExpr(token, self.prefix())
        if self.current.kind in ("!", "-", "*", "&", "~"):
            op = self.current.kind
            self.at += 1
            is_mut = bool(self.accept("mut")) if op == "&" else False
            return Unary(token, op, self.prefix(), mutable=is_mut)
        return self.primary()


def parse(source: str, filename: str | None = None) -> Module:
    return Parser(lex(source, filename), filename=filename, source=source).parse()


def same_type(left: Type, right: Type) -> bool:
    if left.is_fn_ptr or right.is_fn_ptr:
        if not (left.is_fn_ptr and right.is_fn_ptr):
            return False
        if len(left.fn_params) != len(right.fn_params):
            return False
        if not all(
            same_type(lparam, rparam)
            for lparam, rparam in zip(left.fn_params, right.fn_params)
        ):
            return False
        if left.fn_ret is None or right.fn_ret is None:
            return left.fn_ret is None and right.fn_ret is None
        return same_type(left.fn_ret, right.fn_ret)

    return (
        left.name == right.name
        and left.state_space == right.state_space
        and left.state_name == right.state_name
        and left.pointer == right.pointer
        and left.mutable == right.mutable
        and left.is_reference == right.is_reference
        and left.is_array == right.is_array
        and (
            not left.is_array
            or str(left.array_size) == str(right.array_size)
        )
    )

def assignable(actual: Type, expected: Type) -> bool:
    """Literais inteiros são polimórficos entre os inteiros fixos em Sotlas Bootstrap."""
    integers = {"u8", "u16", "u32", "u64", "usize", "i8", "i16", "i32", "i64", "isize"}
    if same_type(actual, expected):
        return True
    if not actual.pointer and not expected.pointer:
        if actual.name in integers and expected.name in integers:
            return True
        if actual.name in integers and (expected.is_array or expected.name not in PRIMITIVES):
            return True
        if actual.name in {"f32", "f64"} and expected.name in {"f32", "f64"}:
            return True
    if (
        actual.name == "null"
        and expected.pointer
        and not expected.is_reference
    ):
        return True
    if actual.pointer and expected.pointer:
        if actual.is_reference != expected.is_reference:
            return False
        if not (
            actual.name == expected.name
            or actual.name == "void"
            or expected.name == "void"
        ):
            return False
        if expected.mutable and not actual.mutable:
            return False
        return True
    return False


BUILTIN_FUNCTIONS: dict[str, Function] = {
    "__outb": Function("__outb", [("port", Type("u16")), ("val", Type("u8"))], Type("void"), [], public=True, attributes=["@system"]),
    "__inb": Function("__inb", [("port", Type("u16"))], Type("u8"), [], public=True, attributes=["@system"]),
    "__outw": Function("__outw", [("port", Type("u16")), ("val", Type("u16"))], Type("void"), [], public=True, attributes=["@system"]),
    "__inw": Function("__inw", [("port", Type("u16"))], Type("u16"), [], public=True, attributes=["@system"]),
    "__outl": Function("__outl", [("port", Type("u16")), ("val", Type("u32"))], Type("void"), [], public=True, attributes=["@system"]),
    "__inl": Function("__inl", [("port", Type("u16"))], Type("u32"), [], public=True, attributes=["@system"]),
    "__rdmsr": Function("__rdmsr", [("msr", Type("u32"))], Type("u64"), [], public=True, attributes=["@system"]),
    "__wrmsr": Function("__wrmsr", [("msr", Type("u32")), ("val", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
    "__cli": Function("__cli", [], Type("void"), [], public=True, attributes=["@system"]),
    "__sti": Function("__sti", [], Type("void"), [], public=True, attributes=["@system"]),
    "__hlt": Function("__hlt", [], Type("void"), [], public=True, attributes=["@system"]),
    "__dma_fence": Function("__dma_fence", [], Type("void"), [], public=True, attributes=["@system"]),
    "__sfence": Function("__sfence", [], Type("void"), [], public=True, attributes=["@system"]),
    "__lfence": Function("__lfence", [], Type("void"), [], public=True, attributes=["@system"]),
    "__cpu_pause": Function("__cpu_pause", [], Type("void"), [], public=True, attributes=["@system"]),
    "__atomic_exchange_u32": Function("__atomic_exchange_u32", [("addr", Type("u64")), ("val", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
    "__atomic_exchange_u64": Function("__atomic_exchange_u64", [("addr", Type("u64")), ("val", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
    "__atomic_add_u64": Function("__atomic_add_u64", [("addr", Type("u64")), ("val", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
    "__atomic_add_u32": Function("__atomic_add_u32", [("addr", Type("u64")), ("val", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
    "__atomic_sub_u64": Function("__atomic_sub_u64", [("addr", Type("u64")), ("val", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
    "__atomic_sub_u32": Function("__atomic_sub_u32", [("addr", Type("u64")), ("val", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
    "__atomic_load_u32": Function("__atomic_load_u32", [("addr", Type("u64"))], Type("u32"), [], public=True, attributes=["@system"]),
    "__atomic_load_u64": Function("__atomic_load_u64", [("addr", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
    "__atomic_store_u32": Function("__atomic_store_u32", [("addr", Type("u64")), ("val", Type("u32"))], Type("void"), [], public=True, attributes=["@system"]),
    "__atomic_store_u64": Function("__atomic_store_u64", [("addr", Type("u64")), ("val", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
    "__atomic_cmpxchg_u64": Function("__atomic_cmpxchg_u64", [("addr", Type("u64")), ("exp", Type("u64")), ("des", Type("u64"))], Type("u64"), [], public=True, attributes=["@system"]),
    "__atomic_cmpxchg_u32": Function("__atomic_cmpxchg_u32", [("addr", Type("u64")), ("exp", Type("u32")), ("des", Type("u32"))], Type("u32"), [], public=True, attributes=["@system"]),
    "__irq_save_disable": Function("__irq_save_disable", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__irq_restore": Function("__irq_restore", [("flags", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
    "__interrupts_enabled": Function("__interrupts_enabled", [], Type("bool"), [], public=True, attributes=["@system"]),
    "__read_cr0": Function("__read_cr0", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__write_cr0": Function("__write_cr0", [("val", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
    "__read_cr2": Function("__read_cr2", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__read_cr3": Function("__read_cr3", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__write_cr3": Function("__write_cr3", [("val", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
    "__read_cr4": Function("__read_cr4", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__write_cr4": Function("__write_cr4", [("val", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
    "__swapgs": Function("__swapgs", [], Type("void"), [], public=True, attributes=["@system"]),
    "__read_gs_base": Function("__read_gs_base", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__current_rsp": Function("__current_rsp", [], Type("u64"), [], public=True, attributes=["@system"]),
    "__invlpg": Function("__invlpg", [("addr", Type("u64"))], Type("void"), [], public=True, attributes=["@system"]),
}


def collect_imported_symbols(
    module: Module,
    available_modules: dict[str, Module],
) -> tuple[
    dict[str, Function],
    dict[str, Struct],
    dict[str, Enum],
    dict[str, Global],
]:
    """Collect public symbols from the module's direct wildcard imports.

    Module discovery stays outside this function. Once callers have a module
    map, build, LSP, tests, and stdlib checks share one import visibility rule.
    """
    imported_fns: dict[str, Function] = {}
    imported_types: dict[str, Struct] = {}
    imported_enums: dict[str, Enum] = {}
    imported_globals: dict[str, Global] = {}

    for dep_name in module.imports:
        dep_mod = available_modules.get(dep_name)
        if dep_mod is None:
            continue
        imported_fns.update({fn.name: fn for fn in dep_mod.functions if fn.public})
        imported_types.update({s.name: s for s in dep_mod.structs if s.public})
        imported_enums.update({e.name: e for e in dep_mod.enums if e.public})
        imported_globals.update({g.name: g for g in dep_mod.globals if g.public})

    return imported_fns, imported_types, imported_enums, imported_globals


def check_with_imports(
    module: Module,
    available_modules: dict[str, Module],
) -> None:
    """Typecheck a module using the canonical direct-import environment."""
    imported_fns, imported_types, imported_enums, imported_globals = (
        collect_imported_symbols(module, available_modules)
    )
    check(
        module,
        imported_fns,
        imported_types,
        imported_enums,
        imported_globals,
    )


def check(module: Module, imported_fns: dict[str, Function] | None = None,
          imported_types: dict[str, Struct] | None = None,
          imported_enums: dict[str, Enum] | None = None,
          imported_globals: dict[str, Global] | None = None) -> None:
    source = module.source
    filename = module.filename

    struct_map: dict[str, Struct] = {s.name: s for s in module.structs}
    if imported_types: struct_map.update(imported_types)

    enum_map: dict[str, Enum] = {e.name: e for e in module.enums}
    if imported_enums: enum_map.update(imported_enums)

    def enum_constructor(callee: str) -> tuple[Enum, EnumVariant] | None:
        for enum_obj in enum_map.values():
            for variant in enum_obj.variants:
                if f"{enum_obj.name}_{variant.name}" == callee:
                    return enum_obj, variant
        return None

    global_map: dict[str, Global] = {g.name: g for g in module.globals}
    if imported_globals: global_map.update(imported_globals)

    functions = dict(BUILTIN_FUNCTIONS)
    user_funcs = {item.name: item for item in module.functions}
    functions.update(user_funcs)
    if imported_fns: functions.update(imported_fns)
    state_transition_facts: dict[tuple[str, str], tuple] = {}
    current_function_name = "<module>"

    def binding_type(type_obj: Type, is_mut: bool) -> Type:
        bound = replace(type_obj)
        object.__setattr__(bound, "_sotlas_binding_mutable", bool(is_mut))
        return bound

    integer_widths = {
        "u8": 8, "u16": 16, "u32": 32, "u64": 64, "usize": 64,
        "i8": 8, "i16": 16, "i32": 32, "i64": 64, "isize": 64,
    }
    signed_integer_types = {"i8", "i16", "i32", "i64", "isize"}

    def integer_bounds_for(type_obj: Type) -> tuple[int, int]:
        width = integer_widths[type_obj.name]
        if type_obj.name in signed_integer_types:
            limit = 1 << (width - 1)
            return -limit, limit - 1
        return 0, (1 << width) - 1

    def validate_integer_constant(
        value: int, type_obj: Type, token: Token
    ) -> None:
        lower, upper = integer_bounds_for(type_obj)
        if value < lower or value > upper:
            raise SotlasBootstrapError(
                f"valor inteiro {value} fora do intervalo para {type_obj.name} "
                f"[{lower}, {upper}]",
                token.line, token.column, filename, source,
            )

    def scalar_integer(type_obj: Type) -> bool:
        return (
            not type_obj.pointer
            and not type_obj.is_array
            and not type_obj.is_reference
            and type_obj.name in INTEGER_LITERAL_SUFFIXES
        )

    def scalar_numeric(type_obj: Type) -> bool:
        return scalar_integer(type_obj) or (
            not type_obj.pointer
            and not type_obj.is_array
            and not type_obj.is_reference
            and type_obj.name in FLOAT_LITERAL_SUFFIXES
        )

    def integer_constant_value(expr: Expr) -> int | None:
        if isinstance(expr, Number):
            try:
                return integer_literal_value(expr.value)
            except ValueError:
                return None
        if isinstance(expr, Unary) and expr.op == "-":
            inner = integer_constant_value(expr.value)
            return -inner if inner is not None else None
        if isinstance(expr, Binary) and expr.op in ("+", "-", "*"):
            left_value = integer_constant_value(expr.left)
            right_value = integer_constant_value(expr.right)
            if left_value is None or right_value is None:
                return None
            if expr.op == "+":
                return left_value + right_value
            if expr.op == "-":
                return left_value - right_value
            return left_value * right_value
        return None

    def unsuffixed_integer_constant(expr: Expr) -> bool:
        if isinstance(expr, Number):
            base, suffix = numeric_literal_parts(expr.value)
            return suffix is None and "." not in base
        if isinstance(expr, Unary) and expr.op == "-":
            return unsuffixed_integer_constant(expr.value)
        if isinstance(expr, Binary) and expr.op in ("+", "-", "*"):
            return (
                unsuffixed_integer_constant(expr.left)
                and unsuffixed_integer_constant(expr.right)
            )
        return False

    def numeric_operand_types_compatible(
        left_expr: Expr,
        left_type: Type,
        right_expr: Expr,
        right_type: Type,
    ) -> bool:
        if same_type(left_type, right_type):
            return True
        if scalar_integer(left_type) and unsuffixed_integer_constant(right_expr):
            return True
        if scalar_integer(right_type) and unsuffixed_integer_constant(left_expr):
            return True
        return False

    def contextual_integer_operand_type(
        left_expr: Expr,
        left_type: Type,
        right_expr: Expr,
        right_type: Type,
    ) -> Type | None:
        if scalar_integer(left_type) and same_type(left_type, right_type):
            return left_type
        if scalar_integer(left_type) and unsuffixed_integer_constant(right_expr):
            return left_type
        if scalar_integer(right_type) and unsuffixed_integer_constant(left_expr):
            return right_type
        return None

    def equality_operand_types_compatible(
        left_expr: Expr,
        left_type: Type,
        right_expr: Expr,
        right_type: Type,
    ) -> bool:
        if same_type(left_type, right_type):
            return True
        pointer_null = (
            (
                left_type.pointer
                and not left_type.is_reference
                and right_type.name == "null"
            )
            or (
                right_type.pointer
                and not right_type.is_reference
                and left_type.name == "null"
            )
        )
        if pointer_null:
            return True
        if scalar_integer(left_type) and unsuffixed_integer_constant(right_expr):
            return True
        if scalar_integer(right_type) and unsuffixed_integer_constant(left_expr):
            return True
        return False

    def contextual_type_matches(
        value_expr: Expr,
        actual: Type,
        expected: Type,
        scope: dict[str, Type],
        in_unsafe: bool,
        is_system_fn: bool,
    ) -> bool:
        if same_type(actual, expected):
            return True

        if scalar_integer(expected) and unsuffixed_integer_constant(value_expr):
            value = integer_constant_value(value_expr)
            if value is not None:
                validate_integer_constant(value, expected, value_expr.token)
                return True

        if (
            actual.pointer
            and expected.pointer
            and actual.is_reference
            and expected.is_reference
            and actual.name == expected.name
            and not actual.is_array
            and not expected.is_array
            and actual.mutable
            and not expected.mutable
        ):
            return True

        if (
            actual.pointer
            and expected.pointer
            and not actual.is_reference
            and not expected.is_reference
            and not actual.is_array
            and not expected.is_array
            and (
                actual.name == expected.name
                or actual.name == "void"
                or expected.name == "void"
            )
            and not (expected.mutable and not actual.mutable)
        ):
            return True

        if (
            isinstance(value_expr, NullLit)
            and expected.pointer
            and not expected.is_reference
            and not expected.is_array
        ):
            return True

        if not isinstance(value_expr, ArrayLit) or not expected.is_array:
            return False

        actual_size = (
            value_expr.repeat_size
            if value_expr.is_repeat
            else len(value_expr.elements)
        )
        if str(actual_size) != str(expected.array_size):
            raise SotlasBootstrapError(
                f"tamanho de array incompatível: esperado "
                f"{expected.array_size}, recebido {actual_size}",
                value_expr.token.line, value_expr.token.column,
                filename, source,
            )
        if not value_expr.elements:
            raise SotlasBootstrapError(
                "não é possível contextualizar array literal vazio",
                value_expr.token.line, value_expr.token.column,
                filename, source,
            )

        expected_elem = expected.elem_type or Type(
            expected.name,
            pointer=expected.pointer,
            mutable=expected.mutable,
        )
        for element in value_expr.elements:
            element_type = expr_type(
                element, scope, in_unsafe, is_system_fn
            )
            if same_type(element_type, expected_elem):
                continue
            if (
                scalar_integer(expected_elem)
                and unsuffixed_integer_constant(element)
            ):
                element_value = integer_constant_value(element)
                if element_value is not None:
                    validate_integer_constant(
                        element_value, expected_elem, element.token
                    )
                    continue
            return False
        return True

    def mutable_place(expr: Expr, scope: dict[str, Type], in_unsafe: bool, is_system_fn: bool) -> bool:
        if isinstance(expr, Name):
            if expr.value in scope:
                return bool(
                    getattr(scope[expr.value], "_sotlas_binding_mutable", False)
                )
            global_item = global_map.get(expr.value)
            return bool(global_item and global_item.is_mut)
        if isinstance(expr, (Index, Member)):
            return mutable_place(
                expr.target, scope, in_unsafe, is_system_fn
            )
        if isinstance(expr, Unary) and expr.op == "*":
            pointee = expr_type(
                expr.value, scope, in_unsafe, is_system_fn
            )
            return bool(pointee.pointer and pointee.mutable)
        return False

    def expr_type(expr: Expr, scope: dict[str, Type], in_unsafe: bool, is_system_fn: bool) -> Type:
        if isinstance(expr, UnsafeExpr):
            return expr_type(expr.value, scope, True, is_system_fn)
        if isinstance(expr, MoveExpr):
            return expr_type(expr.value, scope, in_unsafe, is_system_fn)
        if isinstance(expr, ShareExpr):
            if not isinstance(expr.value, Name):
                raise SotlasBootstrapError(
                    "share exige binding direto de ownership",
                    expr.token.line, expr.token.column, filename, source,
                )
            source_type = scope.get(expr.value.value)
            if source_type is None:
                raise SotlasBootstrapError(
                    f"share source não declarado: {expr.value.value}",
                    expr.token.line, expr.token.column, filename, source,
                )
            source_struct = struct_map.get(source_type.name)
            if (
                source_struct is None
                or not source_struct.is_sole
                or source_type.pointer
                or source_type.is_reference
            ):
                raise SotlasBootstrapError(
                    f"share exige valor sole exclusivo, recebido {source_type.name}",
                    expr.token.line, expr.token.column, filename, source,
                )
            return source_type
        if isinstance(expr, Number):
            try:
                return Type(numeric_literal_type(expr.value))
            except ValueError as error:
                raise SotlasBootstrapError(str(error), expr.token.line, expr.token.column, filename, source)
        if isinstance(expr, Boolean):
            return Type("bool")
        if isinstance(expr, StringLit):
            return Type("u8", pointer=True)
        if isinstance(expr, CharLit):
            return Type("u8")
        if isinstance(expr, NullLit):
            return Type("null", pointer=True)
        if isinstance(expr, ArrayLit):
            for element in expr.elements:
                expr_type(element, scope, in_unsafe, is_system_fn)
            if expr.is_repeat:
                inner = expr_type(expr.elements[0], scope, in_unsafe, is_system_fn)
                return Type(inner.name, pointer=inner.pointer, is_array=True, array_size=expr.repeat_size, elem_type=inner)
            inner = expr_type(expr.elements[0], scope, in_unsafe, is_system_fn) if expr.elements else Type("void")
            return Type(inner.name, pointer=inner.pointer, is_array=True, array_size=len(expr.elements), elem_type=inner)
        if isinstance(expr, StructLit):
            struct = struct_map.get(expr.struct_name)
            if struct is None:
                raise SotlasBootstrapError(
                    f"tipo de struct literal não declarado: {expr.struct_name}",
                    expr.token.line, expr.token.column, filename, source,
                )
            declared_field_map = {
                field.name: field for field in struct.fields
            }
            declared_fields = set(declared_field_map)
            seen_fields: set[str] = set()
            for field_name, value in expr.fields:
                if field_name in seen_fields:
                    raise SotlasBootstrapError(
                        f"campo duplicado em struct literal "
                        f"{expr.struct_name}: {field_name}",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if field_name not in declared_fields:
                    raise SotlasBootstrapError(
                        f"campo não declarado em struct literal "
                        f"{expr.struct_name}: {field_name}",
                        expr.token.line, expr.token.column, filename, source,
                    )
                seen_fields.add(field_name)
                actual = expr_type(
                    value, scope, in_unsafe, is_system_fn
                )
                expected = declared_field_map[field_name].type
                if not contextual_type_matches(
                    value,
                    actual,
                    expected,
                    scope,
                    in_unsafe,
                    is_system_fn,
                ):
                    raise SotlasBootstrapError(
                        f"tipo incompatível no campo {field_name} de "
                        f"{expr.struct_name}: esperado {expected.name}, "
                        f"recebido {actual.name}",
                        value.token.line, value.token.column,
                        filename, source,
                    )
            missing_fields = declared_fields - seen_fields
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise SotlasBootstrapError(
                    f"campo(s) ausente(s) em struct literal "
                    f"{expr.struct_name}: {missing}",
                    expr.token.line, expr.token.column, filename, source,
                )
            return Type(expr.struct_name)
        if isinstance(expr, IfExpr):
            condition_t = expr_type(
                expr.condition, scope, in_unsafe, is_system_fn
            )
            if not same_type(condition_t, Type("bool")):
                raise SotlasBootstrapError(
                    "condição de expressão if deve ser bool",
                    expr.token.line, expr.token.column, filename, source,
                )
            then_t = expr_type(
                expr.then_expr, scope, in_unsafe, is_system_fn
            )
            else_t = expr_type(
                expr.else_expr, scope, in_unsafe, is_system_fn
            )
            if not same_type(then_t, else_t):
                raise SotlasBootstrapError(
                    "ramos da expressão if devem ter o mesmo tipo",
                    expr.token.line, expr.token.column, filename, source,
                )
            return then_t
        if isinstance(expr, Name):
            if expr.value in scope:
                return scope[expr.value]
            if expr.value in global_map:
                return global_map[expr.value].type
            function_value = functions.get(expr.value)
            if function_value is not None:
                return Type(
                    "__fn_ptr",
                    is_fn_ptr=True,
                    fn_params=tuple(param_type for _, param_type in function_value.params),
                    fn_ret=function_value.result,
                )
            raise SotlasBootstrapError(
                f"símbolo não declarado: {expr.value}", expr.token.line,
                expr.token.column, filename, source,
            )
        if isinstance(expr, EnumAccess):
            enum_obj = enum_map.get(expr.enum_name)
            if enum_obj is None:
                raise SotlasBootstrapError(
                    f"enum não declarado: {expr.enum_name}",
                    expr.token.line, expr.token.column, filename, source,
                )
            variant = next(
                (item for item in enum_obj.variants if item.name == expr.variant),
                None,
            )
            if variant is None:
                raise SotlasBootstrapError(
                    f"variante não declarada: {expr.enum_name}::{expr.variant}",
                    expr.token.line, expr.token.column, filename, source,
                )
            if variant.payload_type is not None:
                raise SotlasBootstrapError(
                    f"variante {expr.enum_name}::{expr.variant} exige payload",
                    expr.token.line, expr.token.column, filename, source,
                )
            return Type(expr.enum_name)
        if isinstance(expr, Unary):
            inner = expr_type(expr.value, scope, in_unsafe, is_system_fn)
            if expr.op == "*":
                if not inner.pointer:
                    raise SotlasBootstrapError(
                        "desreferenciamento exige ponteiro ou referência",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if not inner.is_reference and not in_unsafe:
                    raise SotlasBootstrapError(
                        "desreferenciamento de ponteiro exige bloco unsafe",
                        expr.token.line, expr.token.column, filename, source,
                    )
                return Type(inner.name, pointer=False, mutable=False)
            if expr.op == "&":
                if (
                    expr.mutable
                    and not mutable_place(
                        expr.value, scope, in_unsafe, is_system_fn
                    )
                ):
                    raise SotlasBootstrapError(
                        "referência mutável exige binding mutável",
                        expr.token.line, expr.token.column, filename, source,
                    )
                return Type(
                    inner.name,
                    pointer=True,
                    mutable=expr.mutable,
                    is_array=inner.is_array,
                    array_size=inner.array_size,
                    elem_type=inner.elem_type,
                    is_reference=True,
                )
            if expr.op == "!":
                if not same_type(inner, Type("bool")):
                    raise SotlasBootstrapError(
                        "operador ! exige operando bool",
                        expr.token.line, expr.token.column, filename, source,
                    )
                return Type("bool")
            if expr.op == "~":
                if not scalar_integer(inner):
                    raise SotlasBootstrapError(
                        "operador ~ exige operando inteiro escalar",
                        expr.token.line, expr.token.column, filename, source,
                    )
                return inner
            if expr.op == "-":
                signed_numeric = (
                    inner.name in signed_integer_types
                    or inner.name in FLOAT_LITERAL_SUFFIXES
                )
                if not scalar_numeric(inner) or not signed_numeric:
                    raise SotlasBootstrapError(
                        "operador - unário exige inteiro signed ou float",
                        expr.token.line, expr.token.column, filename, source,
                    )
                return inner
            raise SotlasBootstrapError(
                f"operador unário não suportado: {expr.op}",
                expr.token.line, expr.token.column, filename, source,
            )
        if isinstance(expr, Binary):
            left = expr_type(expr.left, scope, in_unsafe, is_system_fn)
            right = expr_type(expr.right, scope, in_unsafe, is_system_fn)
            if expr.op in ("&&", "||"):
                if (
                    not same_type(left, Type("bool"))
                    or not same_type(right, Type("bool"))
                ):
                    raise SotlasBootstrapError(
                        f"operador lógico {expr.op} exige operandos bool",
                        expr.token.line, expr.token.column, filename, source,
                    )
            if expr.op in ("<", "<=", ">", ">="):
                if not scalar_numeric(left) or not scalar_numeric(right):
                    raise SotlasBootstrapError(
                        f"operador relacional {expr.op} exige operandos numéricos escalares",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if not numeric_operand_types_compatible(
                    expr.left, left, expr.right, right
                ):
                    raise SotlasBootstrapError(
                        f"tipos incompatíveis em operador relacional {expr.op}: "
                        f"{left.name} vs {right.name}",
                        expr.token.line, expr.token.column, filename, source,
                    )
            if (
                expr.op in ("+", "-")
                and left.pointer
                and not left.is_reference
                and scalar_integer(right)
            ):
                if not in_unsafe:
                    raise SotlasBootstrapError(
                        "aritmética de ponteiro cru exige bloco unsafe",
                        expr.token.line, expr.token.column, filename, source,
                    )
                return left
            if expr.op in ("+", "-", "*", "/", "%"):
                if not scalar_numeric(left) or not scalar_numeric(right):
                    raise SotlasBootstrapError(
                        f"operador aritmético {expr.op} exige operandos numéricos escalares",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if not numeric_operand_types_compatible(
                    expr.left, left, expr.right, right
                ):
                    raise SotlasBootstrapError(
                        f"tipos incompatíveis em operador aritmético {expr.op}: "
                        f"{left.name} vs {right.name}",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if (
                    expr.op in ("/", "%")
                    and scalar_integer(left)
                    and integer_constant_value(expr.right) == 0
                ):
                    message = (
                        "divisão inteira por zero não é permitida"
                        if expr.op == "/"
                        else "módulo inteiro por zero não é permitida"
                    )
                    raise SotlasBootstrapError(
                        message,
                        expr.token.line, expr.token.column, filename, source,
                    )
                if (
                    expr.op in ("/", "%")
                    and left.name in signed_integer_types
                    and integer_constant_value(expr.right) == -1
                ):
                    left_value = integer_constant_value(expr.left)
                    minimum = -(1 << (integer_widths[left.name] - 1))
                    if left_value == minimum:
                        operation = "divisão" if expr.op == "/" else "módulo"
                        raise SotlasBootstrapError(
                            f"overflow de {operation} inteira para mínimo de "
                            f"{left.name} dividido por -1",
                            expr.token.line, expr.token.column, filename, source,
                        )
                if expr.op in ("+", "-", "*"):
                    result_type = contextual_integer_operand_type(
                        expr.left, left, expr.right, right
                    )
                    left_value = integer_constant_value(expr.left)
                    right_value = integer_constant_value(expr.right)
                    if (
                        result_type is not None
                        and left_value is not None
                        and right_value is not None
                    ):
                        if expr.op == "+":
                            constant_value = left_value + right_value
                        elif expr.op == "-":
                            constant_value = left_value - right_value
                        else:
                            constant_value = left_value * right_value
                        validate_integer_constant(
                            constant_value, result_type, expr.token
                        )
            if expr.op in ("&", "|", "^"):
                if not scalar_integer(left) or not scalar_integer(right):
                    raise SotlasBootstrapError(
                        f"operador bit a bit {expr.op} exige operandos inteiros escalares",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if not numeric_operand_types_compatible(
                    expr.left, left, expr.right, right
                ):
                    raise SotlasBootstrapError(
                        f"tipos incompatíveis em operador bit a bit {expr.op}: "
                        f"{left.name} vs {right.name}",
                        expr.token.line, expr.token.column, filename, source,
                    )
            if expr.op in ("<<", ">>"):
                if not scalar_integer(left) or not scalar_integer(right):
                    raise SotlasBootstrapError(
                        f"operador de deslocamento {expr.op} exige operandos inteiros escalares",
                        expr.token.line, expr.token.column, filename, source,
                    )
                shift = integer_constant_value(expr.right)
                if shift is not None:
                    width = integer_widths[left.name]
                    if shift < 0 or shift >= width:
                        raise SotlasBootstrapError(
                            f"contador de deslocamento {shift} fora do intervalo "
                            f"para {left.name} de largura {width}",
                            expr.token.line, expr.token.column, filename, source,
                        )
                    left_value = integer_constant_value(expr.left)
                    if (
                        left.name in signed_integer_types
                        and left_value is not None
                        and left_value < 0
                    ):
                        direction = (
                            "esquerda" if expr.op == "<<" else "direita"
                        )
                        raise SotlasBootstrapError(
                            f"deslocamento à {direction} de inteiro signed "
                            "negativo não é permitido",
                            expr.token.line, expr.token.column, filename, source,
                        )
                    if expr.op == "<<" and left_value is not None:
                        validate_integer_constant(
                            left_value << shift, left, expr.token
                        )
            if expr.op in ("==", "!="):
                reference_null = (
                    (left.is_reference and right.name == "null")
                    or (right.is_reference and left.name == "null")
                )
                if reference_null:
                    raise SotlasBootstrapError(
                        "referência segura não pode ser comparada a null",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if not equality_operand_types_compatible(
                    expr.left, left, expr.right, right
                ):
                    raise SotlasBootstrapError(
                        f"tipos incompatíveis em comparação {expr.op}: "
                        f"{left.name} vs {right.name}",
                        expr.token.line, expr.token.column, filename, source,
                    )
            return Type("bool") if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||") else left
        if isinstance(expr, Call):
            if expr.callee == "transition" and getattr(
                module, "state_space_frontend_plan", None
            ) is not None:
                if not in_unsafe:
                    raise SotlasBootstrapError(
                        "typestate transition requires an unsafe block because "
                        "the operation asserts that the resource changed state",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if (
                    len(expr.args) != 2
                    or not isinstance(expr.args[0], MoveExpr)
                    or not isinstance(expr.args[0].value, Name)
                    or not isinstance(expr.args[1], Name)
                ):
                    raise SotlasBootstrapError(
                        "transition syntax is transition(move(binding), TargetState)",
                        expr.token.line, expr.token.column, filename, source,
                    )
                source_type = expr_type(
                    expr.args[0], scope, in_unsafe, is_system_fn
                )
                space_name = getattr(source_type, "state_space", None)
                source_state = getattr(source_type, "state_name", None)
                target_state = expr.args[1].value
                source_struct = struct_map.get(source_type.name)
                if (
                    not isinstance(space_name, str)
                    or not isinstance(source_state, str)
                    or source_type.pointer
                    or source_type.is_reference
                    or source_type.is_array
                    or source_struct is None
                    or not source_struct.is_sole
                ):
                    raise SotlasBootstrapError(
                        "transition requires a by-value typestate of a sole struct",
                        expr.args[0].token.line,
                        expr.args[0].token.column,
                        filename,
                        source,
                    )
                try:
                    from .state_typestate import (
                        certify_typestate,
                        transition_typestate,
                    )

                    plan = module.state_space_frontend_plan
                    space = plan.space(space_name)
                    current = certify_typestate(
                        space, source_type.name, source_state
                    )
                    point_id = (
                        f"state_transition@{expr.token.line}:{expr.token.column}"
                    )
                    fact = transition_typestate(
                        space, current, target_state, point_id=point_id
                    )
                except ValueError as error:
                    raise SotlasBootstrapError(
                        str(error), expr.token.line, expr.token.column,
                        filename, source,
                    ) from error
                state_transition_facts[(current_function_name, point_id)] = (
                    current_function_name,
                    point_id,
                    expr.args[0].value.value,
                    fact,
                )
                scope[expr.args[0].value.value] = replace(
                    source_type, state_name=fact.target.state_name
                )
                return replace(source_type, state_name=fact.target.state_name)

            argument_types = [
                expr_type(argument, scope, in_unsafe, is_system_fn)
                for argument in expr.args
            ]

            constructor = enum_constructor(expr.callee)
            if constructor is not None:
                enum_obj, variant = constructor
                if variant.payload_type is None:
                    raise SotlasBootstrapError(
                        f"variante {enum_obj.name}::{variant.name} não possui payload",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if len(expr.args) != 1:
                    raise SotlasBootstrapError(
                        f"constructor {enum_obj.name}::{variant.name} exige 1 payload",
                        expr.token.line, expr.token.column, filename, source,
                    )
                actual = argument_types[0]
                expected = variant.payload_type
                if not contextual_type_matches(
                    expr.args[0],
                    actual,
                    expected,
                    scope,
                    in_unsafe,
                    is_system_fn,
                ):
                    raise SotlasBootstrapError(
                        f"payload incompatível em {enum_obj.name}::{variant.name}: "
                        f"esperado {expected.name}, recebido {actual.name}",
                        expr.args[0].token.line,
                        expr.args[0].token.column,
                        filename,
                        source,
                    )
                return Type(enum_obj.name)

            function = functions.get(expr.callee)
            if function:
                if len(argument_types) != len(function.params):
                    raise SotlasBootstrapError(
                        f"quantidade de argumentos incompatível em chamada "
                        f"{expr.callee}: esperado {len(function.params)}, "
                        f"recebido {len(argument_types)}",
                        expr.token.line, expr.token.column, filename, source,
                    )
                for index, (argument, actual, (_, expected)) in enumerate(
                    zip(expr.args, argument_types, function.params), start=1
                ):
                    if not contextual_type_matches(
                        argument,
                        actual,
                        expected,
                        scope,
                        in_unsafe,
                        is_system_fn,
                    ):
                        raise SotlasBootstrapError(
                            f"argumento {index} incompatível em chamada "
                            f"{expr.callee}: esperado {expected.name}, "
                            f"recebido {actual.name}",
                            argument.token.line, argument.token.column,
                            filename, source,
                        )
                return function.result
            if expr.callee.startswith("__"):
                return Type("u64")
            raise SotlasBootstrapError(
                f"função não declarada: {expr.callee}", expr.token.line,
                expr.token.column, filename, source,
            )
        if isinstance(expr, Index):
            target_t = expr_type(expr.target, scope, in_unsafe, is_system_fn)
            index_t = expr_type(expr.index, scope, in_unsafe, is_system_fn)
            index_is_scalar_integer = (
                not index_t.pointer
                and not index_t.is_array
                and not index_t.is_reference
                and index_t.name in INTEGER_LITERAL_SUFFIXES
            )
            if not index_is_scalar_integer:
                raise SotlasBootstrapError(
                    "índice deve ser inteiro escalar",
                    expr.token.line, expr.token.column, filename, source,
                )
            if (
                target_t.pointer
                and not target_t.is_reference
                and not in_unsafe
            ):
                raise SotlasBootstrapError(
                    "indexação de ponteiro exige bloco unsafe",
                    expr.token.line, expr.token.column, filename, source,
                )
            if not target_t.is_array and not target_t.pointer:
                raise SotlasBootstrapError(
                    "indexação exige array ou ponteiro",
                    expr.token.line, expr.token.column, filename, source,
                )
            if target_t.is_array and target_t.elem_type:
                return target_t.elem_type
            return Type(target_t.name, pointer=False, mutable=target_t.mutable)
        if isinstance(expr, Member):
            target_t = expr_type(expr.target, scope, in_unsafe, is_system_fn)
            if target_t.pointer and not target_t.is_reference and not in_unsafe:
                raise SotlasBootstrapError(
                    "acesso a campo via ponteiro exige bloco unsafe",
                    expr.token.line, expr.token.column, filename, source,
                )
            expr.is_pointer_target = target_t.pointer
            struct_def = struct_map.get(target_t.name)
            if struct_def is None:
                raise SotlasBootstrapError(
                    f"acesso a campo exige struct conhecido: {target_t.name}",
                    expr.token.line, expr.token.column, filename, source,
                )
            fld = next(
                (f for f in struct_def.fields if f.name == expr.field),
                None,
            )
            if fld is None:
                raise SotlasBootstrapError(
                    f"campo não declarado: {target_t.name}.{expr.field}",
                    expr.token.line, expr.token.column, filename, source,
                )
            return fld.type
        if isinstance(expr, MethodCall):
            target_t = expr_type(expr.target, scope, in_unsafe, is_system_fn)
            argument_types = [
                expr_type(argument, scope, in_unsafe, is_system_fn)
                for argument in expr.args
            ]
            expr.target_type = target_t
            if expr.method == "as_ptr":
                return Type(target_t.name if not target_t.is_array else (target_t.elem_type.name if target_t.elem_type else "u8"), pointer=True)
            if expr.method == "abs":
                return target_t
            if expr.method == "add":
                return target_t
            s_def = struct_map.get(target_t.name)
            if s_def:
                fld = next((f for f in s_def.fields if f.name == expr.method), None)
                if fld and getattr(fld.type, "is_fn_ptr", False):
                    if (
                        target_t.pointer
                        and not target_t.is_reference
                        and not in_unsafe
                    ):
                        raise SotlasBootstrapError(
                            "chamada de campo de função via ponteiro exige bloco unsafe",
                            expr.token.line, expr.token.column, filename, source,
                        )
                    expected_params = tuple(fld.type.fn_params)
                    if len(expr.args) != len(expected_params):
                        raise SotlasBootstrapError(
                            f"quantidade de argumentos incompatível em campo de função "
                            f"{target_t.name}.{expr.method}: esperado "
                            f"{len(expected_params)}, recebido {len(expr.args)}",
                            expr.token.line, expr.token.column, filename, source,
                        )
                    for index, (argument, actual, expected) in enumerate(
                        zip(expr.args, argument_types, expected_params), start=1
                    ):
                        if not contextual_type_matches(
                            argument,
                            actual,
                            expected,
                            scope,
                            in_unsafe,
                            is_system_fn,
                        ):
                            raise SotlasBootstrapError(
                                f"argumento {index} incompatível em campo de função "
                                f"{target_t.name}.{expr.method}: esperado "
                                f"{expected.name}, recebido {actual.name}",
                                argument.token.line, argument.token.column,
                                filename, source,
                            )
                    expr.is_vtable_call = True
                    expr.is_arrow = target_t.pointer
                    return fld.type.fn_ret or Type("void")
            method = functions.get(f"{target_t.name}_{expr.method}")
            if method:
                if not method.params:
                    raise SotlasBootstrapError(
                        f"método {target_t.name}.{expr.method} não possui parâmetro self",
                        expr.token.line, expr.token.column, filename, source,
                    )
                self_name, self_type = method.params[0]
                if self_name != "self" or self_type.name != target_t.name:
                    raise SotlasBootstrapError(
                        f"self incompatível em método {target_t.name}.{expr.method}",
                        expr.token.line, expr.token.column, filename, source,
                    )
                if target_t.pointer and not self_type.pointer:
                    raise SotlasBootstrapError(
                        f"receiver incompatível em método {target_t.name}.{expr.method}",
                        expr.token.line, expr.token.column, filename, source,
                    )

                user_params = method.params[1:]
                if len(argument_types) != len(user_params):
                    raise SotlasBootstrapError(
                        f"quantidade de argumentos incompatível em método "
                        f"{target_t.name}.{expr.method}: esperado {len(user_params)}, "
                        f"recebido {len(argument_types)}",
                        expr.token.line, expr.token.column, filename, source,
                    )
                for index, (argument, actual, (_, expected)) in enumerate(
                    zip(expr.args, argument_types, user_params), start=1
                ):
                    if not contextual_type_matches(
                        argument,
                        actual,
                        expected,
                        scope,
                        in_unsafe,
                        is_system_fn,
                    ):
                        raise SotlasBootstrapError(
                            f"argumento {index} incompatível em método "
                            f"{target_t.name}.{expr.method}: esperado {expected.name}, "
                            f"recebido {actual.name}",
                            argument.token.line, argument.token.column,
                            filename, source,
                        )

                expr.pass_by_ref = bool(
                    self_type.pointer and not target_t.pointer
                )
                return method.result
            raise SotlasBootstrapError(
                f"método não declarado: {target_t.name}.{expr.method}",
                expr.token.line, expr.token.column, filename, source,
            )
        if isinstance(expr, TryExpr):
            inner_t = expr_type(expr.expr, scope, in_unsafe, is_system_fn)
            if inner_t.name.startswith("Result"):
                val_t_name = inner_t.name[6:].lower()
                return Type(val_t_name)
            return Type("u32")
        if isinstance(expr, Cast):
            source_t = expr_type(expr.expr, scope, in_unsafe, is_system_fn)
            target_t = expr.target_type
            source_is_integer = (
                not source_t.pointer
                and not source_t.is_array
                and not source_t.is_reference
                and source_t.name in INTEGER_LITERAL_SUFFIXES
            )
            if source_is_integer and target_t.pointer and not in_unsafe:
                raise SotlasBootstrapError(
                    "conversão de inteiro para ponteiro exige bloco unsafe",
                    expr.token.line, expr.token.column, filename, source,
                )
            reference_to_raw_pointer = (
                source_t.is_reference
                and target_t.pointer
                and not target_t.is_reference
            )
            if reference_to_raw_pointer and not in_unsafe:
                raise SotlasBootstrapError(
                    "conversão de referência para ponteiro cru exige bloco unsafe",
                    expr.token.line, expr.token.column, filename, source,
                )
            return target_t
        raise AssertionError(type(expr))

    def statements(items: list[Stmt], scope: dict[str, Type], expected_return: Type, in_unsafe: bool, is_system_fn: bool) -> None:
        for item in items:
            if isinstance(item, Let):
                actual = expr_type(item.value, scope, in_unsafe, is_system_fn)
                declared = item.type or actual
                if (
                    item.type is not None
                    and item.type.is_fn_ptr
                    and not same_type(actual, item.type)
                ):
                    raise SotlasBootstrapError(
                        "assinatura de function pointer incompatível",
                        item.token.line, item.token.column, filename, source,
                    )
                scope[item.name] = binding_type(
                    declared, bool(getattr(item, "is_mut", False))
                )
            elif isinstance(item, Assign):
                if isinstance(item.target, (Index, Member)):
                    container_t = expr_type(
                        item.target.target, scope, in_unsafe, is_system_fn
                    )
                    if container_t.is_reference and not container_t.mutable:
                        raise SotlasBootstrapError(
                            "atribuição por referência imutável não é permitida",
                            item.token.line, item.token.column, filename, source,
                        )
                elif (
                    isinstance(item.target, Unary)
                    and item.target.op == "*"
                ):
                    pointee_t = expr_type(
                        item.target.value, scope, in_unsafe, is_system_fn
                    )
                    if pointee_t.is_reference and not pointee_t.mutable:
                        raise SotlasBootstrapError(
                            "atribuição por referência imutável não é permitida",
                            item.token.line, item.token.column, filename, source,
                        )
                target_type = expr_type(
                    item.target, scope, in_unsafe, is_system_fn
                )
                expected_value_type = target_type
                target_carries_lvalue_mutability = (
                    isinstance(item.target, Index)
                    or (
                        isinstance(item.target, Unary)
                        and item.target.op == "*"
                    )
                )
                if (
                    target_carries_lvalue_mutability
                    and not target_type.pointer
                    and not target_type.is_reference
                ):
                    expected_value_type = replace(
                        target_type, mutable=False
                    )
                value_type = expr_type(
                    item.value, scope, in_unsafe, is_system_fn
                )
                if not contextual_type_matches(
                    item.value,
                    value_type,
                    expected_value_type,
                    scope,
                    in_unsafe,
                    is_system_fn,
                ):
                    raise SotlasBootstrapError(
                        "atribuição incompatível", item.token.line,
                        item.token.column, filename, source,
                    )
            elif isinstance(item, Handover):
                if not isinstance(item.value, Name):
                    raise SotlasBootstrapError(
                        "handover exige binding direto de ownership",
                        item.token.line, item.token.column, filename, source,
                    )
                target_type = scope.get(item.value.value)
                target_struct = (
                    struct_map.get(target_type.name)
                    if target_type is not None else None
                )
                if (
                    target_type is None
                    or target_struct is None
                    or not target_struct.is_sole
                    or target_type.pointer
                    or target_type.is_reference
                ):
                    raise SotlasBootstrapError(
                        f"handover exige valor sole exclusivo: {item.value.value}",
                        item.token.line, item.token.column, filename, source,
                    )
                expr_type(item.value, scope, in_unsafe, is_system_fn)
                if item.destination is not None:
                    if not isinstance(item.destination, Name):
                        raise SotlasBootstrapError(
                            "handover destino exige binding direto de ownership",
                            item.token.line, item.token.column, filename, source,
                        )
                    if item.destination.value == item.value.value:
                        raise SotlasBootstrapError(
                            "handover origem e destino devem ser bindings distintos",
                            item.token.line, item.token.column, filename, source,
                        )
                    destination_type = scope.get(item.destination.value)
                    destination_struct = (
                        struct_map.get(destination_type.name)
                        if destination_type is not None else None
                    )
                    if (
                        destination_type is None
                        or destination_struct is None
                        or not destination_struct.is_sole
                        or destination_type.pointer
                        or destination_type.is_reference
                    ):
                        raise SotlasBootstrapError(
                            f"handover destino exige valor sole exclusivo: {item.destination.value}",
                            item.token.line, item.token.column, filename, source,
                        )
                    comparable_destination = replace(
                        destination_type, ownership_domain=None
                    )
                    comparable_source = replace(
                        target_type, ownership_domain=None
                    )
                    if comparable_destination != comparable_source:
                        raise SotlasBootstrapError(
                            "handover origem e destino devem ter o mesmo tipo exclusivo",
                            item.token.line, item.token.column, filename, source,
                        )
                    expr_type(
                        item.destination, scope, in_unsafe, is_system_fn
                    )
            elif isinstance(item, Quarantine):
                if not isinstance(item.value, Name):
                    raise SotlasBootstrapError(
                        "quarantine exige binding direto de ownership",
                        item.token.line, item.token.column, filename, source,
                    )
                target_type = scope.get(item.value.value)
                target_struct = (
                    struct_map.get(target_type.name)
                    if target_type is not None else None
                )
                if (
                    target_type is None
                    or target_struct is None
                    or not target_struct.is_sole
                    or target_type.pointer
                    or target_type.is_reference
                ):
                    raise SotlasBootstrapError(
                        f"quarantine exige valor sole exclusivo: {item.value.value}",
                        item.token.line, item.token.column, filename, source,
                    )
                expr_type(item.value, scope, in_unsafe, is_system_fn)
            elif isinstance(item, Return):
                if item.value is not None:
                    actual = expr_type(
                        item.value, scope, in_unsafe, is_system_fn
                    )
                    actual_value_type = actual
                    return_carries_lvalue_mutability = (
                        isinstance(item.value, Index)
                        or (
                            isinstance(item.value, Unary)
                            and item.value.op == "*"
                        )
                    )
                    if (
                        return_carries_lvalue_mutability
                        and not actual.pointer
                        and not actual.is_reference
                    ):
                        actual_value_type = replace(
                            actual, mutable=False
                        )
                    if not contextual_type_matches(
                        item.value,
                        actual_value_type,
                        expected_return,
                        scope,
                        in_unsafe,
                        is_system_fn,
                    ):
                        raise SotlasBootstrapError(
                            "retorno incompatível", item.token.line,
                            item.token.column, filename, source,
                        )
            elif isinstance(item, (Break, Continue)):
                continue
            elif isinstance(item, (If, While)):
                condition_t = expr_type(
                    item.condition, scope, in_unsafe, is_system_fn
                )
                if not same_type(condition_t, Type("bool")):
                    construct = "if" if isinstance(item, If) else "while"
                    raise SotlasBootstrapError(
                        f"condição de {construct} deve ser bool",
                        item.token.line, item.token.column, filename, source,
                    )
                statements(item.then_body if isinstance(item, If) else item.body, dict(scope), expected_return, in_unsafe, is_system_fn)
                if isinstance(item, If) and item.else_body:
                    statements(item.else_body, dict(scope), expected_return, in_unsafe, is_system_fn)
            elif isinstance(item, Discern):
                subject_type = expr_type(
                    item.subject, scope, in_unsafe, is_system_fn
                )
                space_name = subject_type.state_space
                if space_name is None or subject_type.state_name is None:
                    raise SotlasBootstrapError(
                        "discern requires a value with a certified State Space type",
                        item.token.line, item.token.column, filename, source,
                    )
                if not isinstance(item.subject, Name):
                    raise SotlasBootstrapError(
                        "discern State Space requires a direct named binding",
                        item.token.line, item.token.column, filename, source,
                    )
                item.state_space_name = space_name
                item.state_name = subject_type.state_name
                try:
                    plan = module.state_space_frontend_plan
                    space = plan.space(space_name)
                    if any(state.payload for state in space.states):
                        raise ValueError(
                            "discern payload patterns remain PREVIEW"
                        )
                    from .state_frontend import require_exhaustive_state_space_coverage
                    require_exhaustive_state_space_coverage(
                        space, tuple(case.state_name for case in item.cases)
                    )
                except ValueError as error:
                    raise SotlasBootstrapError(
                        str(error), item.token.line, item.token.column,
                        filename, source,
                    ) from error
                for case in item.cases:
                    statements(
                        case.body, dict(scope), expected_return,
                        in_unsafe, is_system_fn,
                    )
            elif isinstance(item, Loop):
                statements(item.body, dict(scope), expected_return, in_unsafe, is_system_fn)
            elif isinstance(item, For):
                start_t = expr_type(
                    item.start, scope, in_unsafe, is_system_fn
                )
                end_t = expr_type(
                    item.end, scope, in_unsafe, is_system_fn
                )
                if not scalar_integer(start_t) or not scalar_integer(end_t):
                    raise SotlasBootstrapError(
                        "limites de for devem ser inteiros escalares",
                        item.token.line, item.token.column, filename, source,
                    )
                if not same_type(start_t, end_t):
                    raise SotlasBootstrapError(
                        f"tipos dos limites de for incompatíveis: "
                        f"{start_t.name} vs {end_t.name}",
                        item.token.line, item.token.column, filename, source,
                    )
                for_scope = dict(scope)
                for_scope[item.var_name] = binding_type(
                    start_t, bool(getattr(item, "is_mut", False))
                )
                statements(item.body, for_scope, expected_return, in_unsafe, is_system_fn)
            elif isinstance(item, Unsafe):
                statements(item.body, scope, expected_return, in_unsafe=True, is_system_fn=is_system_fn)
            elif isinstance(item, Expression):
                expr_type(item.value, scope, in_unsafe, is_system_fn)
            elif isinstance(item, Defer):
                if item.body is not None:
                    statements(item.body, dict(scope), expected_return, in_unsafe, is_system_fn)
                elif isinstance(item.value, Assign):
                    expr_type(item.value.target, scope, in_unsafe, is_system_fn)
                    expr_type(item.value.value, scope, in_unsafe, is_system_fn)
                elif item.value is not None:
                    expr_type(item.value, scope, in_unsafe, is_system_fn)
            elif isinstance(item, Asm):
                for e in item.outputs: expr_type(e, scope, in_unsafe, is_system_fn)
                for e in item.inputs: expr_type(e, scope, in_unsafe, is_system_fn)

    for function in module.functions:
        current_function_name = function.name
        is_system = "@system" in function.attributes or "@inline" in function.attributes
        statements(function.body, dict(function.params), function.result, in_unsafe=False, is_system_fn=is_system)
    module.state_transition_facts = tuple(state_transition_facts.values())


def _c_ident(name: str) -> str:
    return name.replace("::", "__").replace("-", "_")


def _emit_expr(
    expr: Expr,
    mod_prefix: str = "",
    shared_boxes: dict[str, str] | None = None,
) -> str:
    shared_boxes = shared_boxes or {}
    if isinstance(expr, UnsafeExpr):
        return _emit_expr(expr.value, mod_prefix, shared_boxes)
    if isinstance(expr, MoveExpr):
        return _emit_expr(expr.value, mod_prefix, shared_boxes)
    if isinstance(expr, ShareExpr):
        raise SotlasBootstrapError("share is only valid in a supported local binding", expr.token.line, expr.token.column)
    if isinstance(expr, Number):
        base, suffix = numeric_literal_parts(expr.value)
        if suffix == "u64":
            base += "ULL"
        elif suffix == "i64":
            base += "LL"
        return f"(({C_TYPES[suffix]})({base}))" if suffix else base
    if isinstance(expr, Boolean): return "1" if expr.value else "0"
    if isinstance(expr, StringLit): return f"((const uint8_t *){expr.value})"
    if isinstance(expr, CharLit): return expr.value
    if isinstance(expr, NullLit): return "NULL"
    if isinstance(expr, Name):
        box = shared_boxes.get(expr.value)
        return f"({box}->value)" if box else expr.value
    if isinstance(expr, EnumAccess): return f"{expr.enum_name}_{expr.variant}"
    if isinstance(expr, Unary):
        if expr.op == "&":
            return f"(&{_emit_expr(expr.value, mod_prefix, shared_boxes)})"
        return f"({expr.op}{_emit_expr(expr.value, mod_prefix, shared_boxes)})"
    if isinstance(expr, Binary): return f"({_emit_expr(expr.left, mod_prefix, shared_boxes)} {expr.op} {_emit_expr(expr.right, mod_prefix, shared_boxes)})"
    if isinstance(expr, Call):
        if expr.callee == "transition" and expr.args:
            return _emit_expr(expr.args[0], mod_prefix, shared_boxes)
        callee = expr.callee
        return f"{callee}(" + ", ".join(_emit_expr(item, mod_prefix, shared_boxes) for item in expr.args) + ")"
    if isinstance(expr, MethodCall):
        if getattr(expr, "is_vtable_call", False):
            target_str = _emit_expr(expr.target, mod_prefix, shared_boxes)
            arrow = "->" if getattr(expr, "is_arrow", False) else "."
            callee = f"{target_str}{arrow}{expr.method}"
            args_s = ", ".join(_emit_expr(item, mod_prefix, shared_boxes) for item in expr.args)
            return f"({callee})({args_s})"
        if expr.method == "as_ptr":
            return _emit_expr(expr.target, mod_prefix, shared_boxes)
        if expr.method == "abs":
            target_str = _emit_expr(expr.target, mod_prefix, shared_boxes)
            return f"((int32_t)({target_str}) < 0 ? -(int32_t)({target_str}) : (int32_t)({target_str}))"
        if expr.method == "add":
            target_str = _emit_expr(expr.target, mod_prefix, shared_boxes)
            arg_str = _emit_expr(expr.args[0], mod_prefix, shared_boxes) if expr.args else "0"
            return f"(({target_str}) + ({arg_str}))"
        target_str = _emit_expr(expr.target, mod_prefix, shared_boxes)
        if getattr(expr, "pass_by_ref", False):
            target_str = f"&({target_str})"
        fn_name = f"{expr.target_type.name}_{expr.method}" if expr.target_type else expr.method
        all_args = [target_str] + [_emit_expr(item, mod_prefix, shared_boxes) for item in expr.args]
        return f"{fn_name}(" + ", ".join(all_args) + ")"
    if isinstance(expr, Index):
        return f"{_emit_expr(expr.target, mod_prefix, shared_boxes)}[{_emit_expr(expr.index, mod_prefix, shared_boxes)}]"
    if isinstance(expr, Member):
        arrow = "->" if getattr(expr, "is_pointer_target", False) else "."
        return f"{_emit_expr(expr.target, mod_prefix, shared_boxes)}{arrow}{expr.field}"
    if isinstance(expr, Cast):
        return f"(({expr.target_type.c()})({_emit_expr(expr.expr, mod_prefix, shared_boxes)}))"
    if isinstance(expr, ArrayLit):
        if expr.is_repeat:
            if isinstance(expr.elements[0], Number) and expr.elements[0].value == "0":
                return "{0}"
            val_s = _emit_expr(expr.elements[0], mod_prefix)
            if isinstance(expr.repeat_size, int):
                return "{" + ", ".join([val_s] * expr.repeat_size) + "}"
            return "{" + val_s + "}"
        return "{" + ", ".join(_emit_expr(e, mod_prefix) for e in expr.elements) + "}"
    if isinstance(expr, StructLit):
        field_strs = [f".{f} = {_emit_expr(v, mod_prefix)}" for f, v in expr.fields]
        return f"({expr.struct_name}){{" + ", ".join(field_strs) + "}"
    if isinstance(expr, IfExpr):
        cond_s = _emit_expr(expr.condition, mod_prefix)
        then_s = _emit_expr(expr.then_expr, mod_prefix)
        else_s = _emit_expr(expr.else_expr, mod_prefix)
        return f"(({cond_s}) ? ({then_s}) : ({else_s}))"
    if isinstance(expr, TryExpr):
        inner_str = _emit_expr(expr.expr, mod_prefix)
        return f"({{ __auto_type _res = ({inner_str}); if (_res.status != 0) return _res; _res.value; }})"
    raise AssertionError(type(expr))


PREAMBLE = """/* Gerado pelo frontend Sotlas Bootstrap. */
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#if defined(__GNUC__) || defined(__clang__)
#pragma GCC diagnostic ignored "-Wunused-function"
#if defined(__clang__)
#pragma GCC diagnostic ignored "-Wparentheses-equality"
#endif
#endif

static inline void __outb(uint16_t port, uint8_t val) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile ("outb %0, %1" : : "a"(val), "Nd"(port));
#else
    (void)port; (void)val;
#endif
}

static inline uint8_t __inb(uint16_t port) {
#if defined(__x86_64__) || defined(__i386__)
    uint8_t ret;
    __asm__ volatile ("inb %1, %0" : "=a"(ret) : "Nd"(port));
    return ret;
#else
    (void)port; return 0;
#endif
}

static inline void __outw(uint16_t port, uint16_t val) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile ("outw %0, %1" : : "a"(val), "Nd"(port));
#else
    (void)port; (void)val;
#endif
}

static inline uint16_t __inw(uint16_t port) {
#if defined(__x86_64__) || defined(__i386__)
    uint16_t ret;
    __asm__ volatile ("inw %1, %0" : "=a"(ret) : "Nd"(port));
    return ret;
#else
    (void)port; return 0;
#endif
}

static inline void __outl(uint16_t port, uint32_t val) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile ("outl %0, %1" : : "a"(val), "Nd"(port));
#else
    (void)port; (void)val;
#endif
}

static inline uint32_t __inl(uint16_t port) {
#if defined(__x86_64__) || defined(__i386__)
    uint32_t ret;
    __asm__ volatile ("inl %1, %0" : "=a"(ret) : "Nd"(port));
    return ret;
#else
    (void)port; return 0;
#endif
}

#ifndef __rdmsr_defined
#define __rdmsr_defined
static inline uint64_t __rdmsr(uint32_t msr) {
#if defined(__x86_64__) || defined(__i386__)
    uint32_t low, high;
    __asm__ volatile ("rdmsr" : "=a"(low), "=d"(high) : "c"(msr));
    return ((uint64_t)high << 32) | low;
#else
    (void)msr; return 0;
#endif
}

static inline void __wrmsr(uint32_t msr, uint64_t val) {
#if defined(__x86_64__) || defined(__i386__)
    uint32_t low = (uint32_t)val;
    uint32_t high = (uint32_t)(val >> 32);
    __asm__ volatile ("wrmsr" : : "a"(low), "d"(high), "c"(msr));
#else
    (void)msr; (void)val;
#endif
}
#endif

static inline void __cli(void) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile ("cli");
#endif
}

static inline void __sti(void) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile ("sti");
#endif
}

static inline void __hlt(void) {
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile ("hlt");
#endif
}

"""


_ARC_ATOMIC_INTRINSICS = """/* SOTLAS_ATOMIC_INTRINSICS */
static inline uint64_t __atomic_cmpxchg_u64(uint64_t address, uint64_t expected, uint64_t desired) {
    uint64_t old = expected;
    __atomic_compare_exchange_n((volatile uint64_t *)(uintptr_t)address,
                                &old, desired, false,
                                __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
    return old;
}
static inline void __atomic_store_u64(uint64_t address, uint64_t value) {
    __atomic_store_n((volatile uint64_t *)(uintptr_t)address, value,
                     __ATOMIC_SEQ_CST);
}
static inline uint64_t __atomic_load_u64(uint64_t address) {
    return __atomic_load_n((volatile uint64_t *)(uintptr_t)address,
                           __ATOMIC_SEQ_CST);
}
"""


def _c_func_attributes(attributes: list[str]) -> str:
    attrs = []
    for a in attributes:
        if a == "@naked":
            attrs.append("__attribute__((naked))")
        elif a == "@interrupt":
            attrs.append("__attribute__((interrupt))")
        elif a == "@noinline":
            attrs.append("__attribute__((noinline))")
        elif a == "@noreturn":
            attrs.append("__attribute__((noreturn))")
        elif a.startswith("@section(") and a.endswith(")"):
            inner = a[9:-1].strip()
            if not inner.startswith('"'):
                inner = f'"{inner}"'
            attrs.append(f"__attribute__((section({inner})))")
        elif a.startswith("@aligned(") and a.endswith(")"):
            inner = a[9:-1].strip()
            attrs.append(f"__attribute__((aligned({inner})))")
    if attrs:
        return " ".join(attrs) + " "
    return ""


def _c_struct_attributes(attributes: list[str]) -> str:
    attrs = []
    for a in attributes:
        if a == "@packed":
            attrs.append("__attribute__((packed))")
        elif a.startswith("@aligned(") and a.endswith(")"):
            inner = a[9:-1].strip()
            attrs.append(f"__attribute__((aligned({inner})))")
    if attrs:
        return " " + " ".join(attrs)
    return ""


def _emit_c_enum(enum_obj: Enum) -> list[str]:
    """C11 representation for scalar tagged unions; ownership needs separate lowering."""
    payloads = [v for v in enum_obj.variants if v.payload_type is not None]
    if not payloads:
        result = [f"typedef enum {enum_obj.name} {{"]
        for variant in enum_obj.variants:
            value = f" = {variant.value}" if variant.value is not None else ""
            result.append(f"    {enum_obj.name}_{variant.name}{value},")
        return result + [f"}} {enum_obj.name};"]
    for variant in payloads:
        typ = variant.payload_type
        if (typ.name not in PRIMITIVES or typ.name == "void" or typ.is_array
                or typ.is_fn_ptr or typ.pointer or typ.is_reference):
            raise SotlasBootstrapError(
                f"C11 backend does not lower payload enum {enum_obj.name!r} "
                f"with non-scalar payload {typ.name!r} yet"
            )
    result = [f"typedef struct {enum_obj.name} {{", "    uint64_t tag;", "    union {"]
    for variant in payloads:
        result.append(f"        {variant.payload_type.c_decl(variant.name)};")
    result += ["    } payload;", f"}} {enum_obj.name};"]
    tag = 0
    seen_tags: set[int] = set()
    for variant in enum_obj.variants:
        if variant.value is not None:
            tag = variant.value
        if not 0 <= tag <= 0xFFFFFFFFFFFFFFFF:
            raise SotlasBootstrapError(
                f"C11 payload enum {enum_obj.name!r} discriminant {tag} "
                "is outside the uint64 tag range"
            )
        if tag in seen_tags:
            raise SotlasBootstrapError(
                f"C11 payload enum {enum_obj.name!r} has duplicate discriminant {tag}"
            )
        seen_tags.add(tag)
        if variant.payload_type is None:
            result.append(
                f"#define {enum_obj.name}_{variant.name} "
                f"(({enum_obj.name}){{.tag = UINT64_C({tag})}})"
            )
        else:
            result += [
                f"static inline {enum_obj.name} {enum_obj.name}_{variant.name}"
                f"({variant.payload_type.c_decl('value')}) {{",
                f"    return ({enum_obj.name}){{.tag = UINT64_C({tag}), "
                f".payload.{variant.name} = value}};",
                "}",
            ]
        tag += 1
    return result

def emit_c(module: Module, mangle: bool = False, include_preamble: bool = True,
           include_import_headers: bool = False) -> str:
    functions_for_defer = {function.name: function for function in module.functions}

    def _deferred_expression(statement: Defer) -> Expr | None:
        if statement.value is not None:
            return statement.value
        if statement.body is not None and len(statement.body) == 1:
            body_statement = statement.body[0]
            if isinstance(body_statement, Expression):
                return body_statement.value
        return None

    def _safe_shared_defer_method(
        statement: Defer, shared_names: set[str]
    ) -> bool:
        expression = _deferred_expression(statement)
        if (
            not isinstance(expression, MethodCall)
            or not isinstance(expression.target, Name)
            or expression.target.value not in shared_names
        ):
            return False
        owner_name = getattr(
            getattr(expression, "target_type", None), "name", None
        )
        method = (
            functions_for_defer.get(f"{owner_name}_{expression.method}")
            if owner_name
            else None
        )
        if (
            method is None
            or not method.params
            or "@extern(C)" in method.attributes
            or len(method.params) != len(expression.args) + 1
        ):
            return False
        receiver_type = method.params[0][1]
        immutable_receiver = (
            receiver_type.is_reference
            and not receiver_type.mutable
            and receiver_type.ownership_domain is None
        )
        arguments_do_not_capture_alias = all(
            not any(
                isinstance(node, Name) and node.value in shared_names
                for node in _walk_expr(argument)
            )
            for argument in expression.args
        )
        return immutable_receiver and arguments_do_not_capture_alias

    def _safe_shared_direct_call(
        expression: Expr | None, shared_names: set[str]
    ) -> bool:
        is_method = isinstance(expression, MethodCall)
        if isinstance(expression, Call):
            callee_name = expression.callee
            arguments = tuple(expression.args)
        elif is_method:
            owner_name = getattr(
                getattr(expression, "target_type", None), "name", None
            )
            if not owner_name or not isinstance(expression.target, Name):
                return False
            callee_name = f"{owner_name}_{expression.method}"
            arguments = (expression.target, *tuple(expression.args))
        else:
            return False
        callee = functions_for_defer.get(callee_name)
        if (
            callee is None
            or "@extern(C)" in callee.attributes
            or len(callee.params) != len(arguments)
        ):
            return False
        found_shared_borrow = False
        for argument, (_, parameter_type) in zip(
            arguments, callee.params
        ):
            if parameter_type.ownership_domain == "direct":
                if is_method and argument is expression.target:
                    if argument.value not in shared_names:
                        return False
                    found_shared_borrow = True
                    continue
                if (
                    not isinstance(argument, Unary)
                    or argument.op != "&"
                    or not isinstance(argument.value, Name)
                ):
                    return False
                if argument.value.value in shared_names:
                    found_shared_borrow = True
                continue
            if parameter_type.ownership_domain == "whisper":
                if (
                    not isinstance(argument, Unary)
                    or argument.op != "&"
                    or not isinstance(argument.value, Name)
                    or argument.value.value not in shared_names
                ):
                    return False
                found_shared_borrow = True
                continue
            if any(
                isinstance(node, Name) and node.value in shared_names
                for node in _walk_expr(argument)
            ):
                return False
        return found_shared_borrow

    def _safe_shared_defer_call(
        statement: Defer, shared_names: set[str]
    ) -> bool:
        expression = _deferred_expression(statement)
        return bool(
            isinstance(expression, Call)
            and _safe_shared_direct_call(expression, shared_names)
        )

    def _walk_expr(expr: Expr | None):
        if expr is None:
            return
        yield expr
        for name in ("value", "left", "right", "target", "index", "expr", "condition", "then_expr", "else_expr"):
            child = getattr(expr, name, None)
            if isinstance(child, Expr):
                yield from _walk_expr(child)
        for child in getattr(expr, "args", ()):
            yield from _walk_expr(child)
        for _, child in getattr(expr, "fields", ()):
            if isinstance(child, Expr):
                yield from _walk_expr(child)
        for child in getattr(expr, "elements", ()):
            if isinstance(child, Expr):
                yield from _walk_expr(child)

    def _walk_statements_recursive(statements):
        for statement in statements or ():
            yield statement
            if isinstance(statement, Discern):
                for case in statement.cases:
                    yield from _walk_statements_recursive(case.body)
                continue
            for attribute in ("body", "then_body", "else_body"):
                nested = getattr(statement, attribute, None)
                if nested:
                    yield from _walk_statements_recursive(nested)

    shared_functions = {
        function.name: function
        for function in module.functions
        if any(
            isinstance(item, Let) and isinstance(item.value, ShareExpr)
            for item in _walk_statements_recursive(function.body)
        )
    }
    shared_type_names: set[str] = set()
    for function in shared_functions.values():
        function_items = tuple(_walk_statements_recursive(function.body))
        declared_types = dict(function.params)
        for item in function_items:
            if not isinstance(item, Let):
                continue
            if item.type is not None:
                declared_types[item.name] = item.type
            elif isinstance(item.value, StructLit):
                declared_types[item.name] = Type(item.value.struct_name)
            elif (
                isinstance(item.value, ShareExpr)
                and isinstance(item.value.value, Name)
                and item.value.value.value in declared_types
            ):
                declared_types[item.name] = declared_types[
                    item.value.value.value
                ]
        function_owner_names = {
            item.value.value.value
            for item in function_items
            if isinstance(item, Let) and isinstance(item.value, ShareExpr)
            and isinstance(item.value.value, Name)
        }
        for item in function_items:
            if (
                isinstance(item, Let)
                and isinstance(item.value, ShareExpr)
                and isinstance(item.value.value, Name)
            ):
                function_owner_names.add(item.name)
        shared_type_names.update(
            typ.name for name, typ in declared_types.items()
            if name in function_owner_names
        )
        for item in function_items:
            if not isinstance(item, Let) or item.name not in function_owner_names:
                continue
            if isinstance(item.value, StructLit):
                shared_type_names.add(item.value.struct_name)
            if item.type is not None:
                shared_type_names.add(item.type.name)
    shared_structs = {item.name: item for item in module.structs if item.name in shared_type_names}
    if shared_functions:
        if "core::arc" not in module.imports:
            raise SotlasBootstrapError(
                "C11 share lowering requires import core::arc::*",
                1, 1, module.filename, module.source,
            )
        try:
            typed_ast = (
                importlib.import_module(f"{__package__}.typed_ast")
                if __package__ else None
            )
        except ModuleNotFoundError:
            typed_ast = None
        if typed_ast is None:
            typed_ast_path = Path(__file__).with_name("typed_ast.py")
            if not typed_ast_path.is_file():
                raise SotlasBootstrapError(
                    "C11 share lowering requires the canonical ownership analyzer",
                    1, 1, module.filename, module.source,
                )
            spec = importlib.util.spec_from_file_location(
                "_sotlas_canonical_typed_ast", typed_ast_path
            )
            if spec is None or spec.loader is None:
                raise SotlasBootstrapError(
                    "C11 share lowering requires the canonical ownership analyzer",
                    1, 1, module.filename, module.source,
                )
            typed_ast = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = typed_ast
            spec.loader.exec_module(typed_ast)
        try:
            typed_module = typed_ast.build_declaration_typed_ast(module)
            canonical_points: dict[str, set[tuple[str, str]]] = {}
            for function in shared_functions.values():
                trace = typed_ast.analyze_function_ownership(
                    module, typed_module, function.name
                )
                canonical_points[function.name] = {
                    (event.source_binding or event.via.split(":", 1)[1], event.name)
                    for event in trace.events
                    if event.kind == "retain"
                    and event.domain is typed_ast.OwnershipDomain.SHARED
                    and event.via.startswith("share:")
                }
        except (typed_ast.Phase1SemanticError, ValueError) as error:
            raise SotlasBootstrapError(
                f"C11 share failed canonical ownership validation: {error}",
                1, 1, module.filename, module.source,
            ) from error
        for function in shared_functions.values():
            if any(
                not isinstance(item, (
                    Let, Assign, Return, Expression, Defer, If, While, Loop,
                    For, Unsafe, Break, Continue,
                ))
                for item in function.body
            ):
                raise SotlasBootstrapError(
                    "C11 share contains an unsupported statement",
                    1, 1, module.filename, module.source,
                )
            aliases: dict[str, str] = {}

            def shared_value_read(expr, shared_names: set[str]) -> bool:
                if expr is None:
                    return True
                if isinstance(expr, Name):
                    return expr.value not in shared_names
                if isinstance(expr, (Member, Index)):
                    root = expr
                    indexes = []
                    while isinstance(root, (Member, Index)):
                        if isinstance(root, Index):
                            indexes.append(root.index)
                        root = root.target
                    if isinstance(root, Name) and root.value in shared_names:
                        return all(
                            not any(
                                isinstance(node, Name)
                                and node.value in shared_names
                                for node in _walk_expr(index)
                            )
                            for index in indexes
                        )
                    if isinstance(expr, Member):
                        return shared_value_read(expr.target, shared_names)
                    return (
                        shared_value_read(expr.target, shared_names)
                        and shared_value_read(expr.index, shared_names)
                    )
                if isinstance(expr, Binary):
                    return (
                        shared_value_read(expr.left, shared_names)
                        and shared_value_read(expr.right, shared_names)
                    )
                return not any(
                    isinstance(node, Name) and node.value in shared_names
                    for node in _walk_expr(expr)
                )

            def nested_statements(statements):
                yield from _walk_statements_recursive(statements)

            for statement in nested_statements(function.body):
                if (
                    isinstance(statement, Let)
                    and isinstance(statement.value, ShareExpr)
                ):
                    if not isinstance(statement.value.value, Name):
                        raise SotlasBootstrapError(
                            "share requires a direct sole binding",
                            statement.token.line, statement.token.column,
                            module.filename, module.source,
                        )
                    aliases[statement.name] = statement.value.value.value

            for item in function.body:
                if isinstance(item, Let) and isinstance(item.value, ShareExpr):
                    if not isinstance(item.value.value, Name):
                        raise SotlasBootstrapError("share requires a direct sole binding")
                    aliases[item.name] = item.value.value.value
                elif isinstance(item, Let) and isinstance(item.value, Name) and item.value.value in aliases:
                    raise SotlasBootstrapError(
                        "C11 share does not lower implicit shared alias copies",
                        item.token.line, item.token.column, module.filename, module.source,
                    )
                elif isinstance(item, Assign) and any(
                    isinstance(node, Name) and node.value in (set(aliases) | set(aliases.values()))
                    for node in _walk_expr(item.target)
                ):
                    raise SotlasBootstrapError("C11 shared bindings are immutable")
                elif isinstance(item, Return) and isinstance(item.value, Name) and item.value.value in aliases:
                    raise SotlasBootstrapError("C11 shared values cannot escape their function")
                elif isinstance(item, (Return, Expression, Defer)):
                    value = (
                        _deferred_expression(item)
                        if isinstance(item, Defer)
                        else getattr(item, "value", None)
                    )
                    is_member_read = isinstance(item, Return) and shared_value_read(
                        value, set(aliases) | set(aliases.values())
                    )
                    safe_defer_read = (
                        isinstance(item, Defer)
                        and (
                            _safe_shared_defer_method(
                                item, set(aliases) | set(aliases.values())
                            )
                            or _safe_shared_defer_call(
                                item, set(aliases) | set(aliases.values())
                            )
                        )
                    )
                    safe_direct_read = (
                        not isinstance(item, Defer)
                        and _safe_shared_direct_call(
                            value, set(aliases) | set(aliases.values())
                        )
                    )
                    if any(
                        isinstance(node, Name)
                        and node.value in (set(aliases) | set(aliases.values()))
                        for node in _walk_expr(value)
                    ) and not (
                        is_member_read or safe_defer_read or safe_direct_read
                    ):
                        raise SotlasBootstrapError(
                            "C11 shared aliases cannot escape or be captured outside their scope",
                            item.token.line, item.token.column,
                            module.filename, module.source,
                        )
                elif isinstance(item, (If, While, Loop, For, Unsafe, Discern)):
                    shared_names = set(aliases) | set(aliases.values())
                    for statement in nested_statements((item,)):
                        if isinstance(statement, (Break, Continue)):
                            continue
                        if isinstance(statement, Defer):
                            expression = _deferred_expression(statement)
                            safe_defer_read = _safe_shared_defer_method(
                                statement, shared_names
                            ) or _safe_shared_defer_call(
                                statement, shared_names
                            )
                            if any(
                                isinstance(node, Name)
                                and node.value in shared_names
                                for node in _walk_expr(expression)
                            ) and not safe_defer_read:
                                raise SotlasBootstrapError(
                                    "C11 shared aliases cannot be captured "
                                    "outside their scope",
                                    statement.token.line, statement.token.column,
                                    module.filename, module.source,
                                )
                        if isinstance(statement, Assign) and any(
                            isinstance(node, Name)
                            and node.value in shared_names
                            for node in _walk_expr(statement.target)
                        ):
                            raise SotlasBootstrapError(
                                "C11 shared bindings are immutable",
                                statement.token.line, statement.token.column,
                                module.filename, module.source,
                            )
                        if (
                            isinstance(statement, Let)
                            and isinstance(statement.value, ShareExpr)
                        ):
                            continue
                        expressions = (
                            getattr(statement, "condition", None),
                            getattr(statement, "value", None),
                            getattr(statement, "start", None),
                            getattr(statement, "end", None),
                        )
                        for expression in expressions:
                            if expression is None:
                                continue
                            has_shared_name = any(
                                isinstance(node, Name)
                                and node.value in shared_names
                                for node in _walk_expr(expression)
                            )
                            if has_shared_name and not shared_value_read(
                                expression, shared_names
                            ) and not (
                                isinstance(statement, Defer)
                                and (
                                    _safe_shared_defer_method(
                                        statement, shared_names
                                    )
                                    or _safe_shared_defer_call(
                                        statement, shared_names
                                    )
                                )
                            ) and not (
                                not isinstance(statement, Defer)
                                and _safe_shared_direct_call(
                                    expression, shared_names
                                )
                            ):
                                raise SotlasBootstrapError(
                                    "C11 shared aliases cannot escape or be "
                                    "captured outside their scope",
                                    statement.token.line, statement.token.column,
                                    module.filename, module.source,
                                )
            expected_points = {
                (source, alias) for alias, source in aliases.items()
            }
            if canonical_points.get(function.name) != expected_points:
                raise SotlasBootstrapError(
                    "C11 share lowering does not match canonical ownership transitions",
                    1, 1, module.filename, module.source,
                )
        for struct_name, struct in shared_structs.items():
            if not struct.is_sole or struct.is_register or not struct.fields:
                raise SotlasBootstrapError(
                    "C11 shared allocation requires a non-empty sole struct",
                    1, 1, module.filename, module.source,
                )

        shared_struct_by_name = {item.name: item for item in module.structs}
        struct_order = {item.name: index for index, item in enumerate(module.structs)}
        deinit_names = {
            function.name for function in module.functions
            if function.name.endswith("_deinit") and function.params
        }

        def deinit_references_self(node) -> bool:
            if node is None:
                return False
            if type(node).__name__ == "Name":
                return getattr(node, "value", None) == "self"
            if isinstance(node, (tuple, list)):
                return any(deinit_references_self(item) for item in node)
            fields = getattr(node, "__dataclass_fields__", None)
            if not fields:
                return False
            return any(
                deinit_references_self(getattr(node, field_name, None))
                for field_name in fields
                if field_name != "token"
            )

        def nested_deinit_is_detached(struct_name: str) -> bool:
            deinit = next(
                (
                    function for function in module.functions
                    if function.name == f"{struct_name}_deinit"
                    and function.params
                ),
                None,
            )
            if deinit is None:
                return True
            return not any(
                deinit_references_self(statement)
                for statement in deinit.body
            )

        def contains_owned_descendant(
            type_obj: Type,
            active: frozenset[str] = frozenset(),
        ) -> bool:
            while type_obj.is_array and type_obj.elem_type is not None:
                type_obj = type_obj.elem_type
            if (
                type_obj.pointer or type_obj.is_reference
                or type_obj.is_fn_ptr or type_obj.name in active
            ):
                return False
            child = shared_struct_by_name.get(type_obj.name)
            if child is None:
                return False
            if child.is_sole:
                return True
            return any(
                contains_owned_descendant(
                    field.type, active | {child.name}
                )
                for field in child.fields
            )

        def plain_shared_payload(
            type_obj: Type,
            parent_name: str,
            active: frozenset[str] = frozenset(),
        ) -> bool:
            if type_obj.is_array:
                if (
                    type_obj.elem_type is None
                    or type_obj.elem_type.pointer
                    or type_obj.elem_type.is_fn_ptr
                    or type_obj.elem_type.is_reference
                ):
                    return False
                return plain_shared_payload(
                    type_obj.elem_type, parent_name, active
                )
            if (
                type_obj.pointer or type_obj.is_fn_ptr
                or type_obj.is_reference
                or getattr(type_obj, "ownership_domain", None) is not None
            ):
                return False
            if type_obj.name in PRIMITIVES:
                return type_obj.name != "void"
            nested = shared_struct_by_name.get(type_obj.name)
            if nested is None or nested.is_register or not nested.fields:
                return False
            if nested.name in active or struct_order[nested.name] >= struct_order[parent_name]:
                return False
            if nested.is_sole:
                return all(
                    plain_shared_payload(
                        field.type, nested.name, active | {nested.name}
                    )
                    for field in nested.fields
                )
            if (
                f"{nested.name}_deinit" in deinit_names
                and not nested_deinit_is_detached(nested.name)
            ):
                return False
            return all(
                plain_shared_payload(
                    field.type, nested.name, active | {nested.name}
                )
                for field in nested.fields
            )

        for struct_name, struct in shared_structs.items():
            if any(
                not plain_shared_payload(field.type, struct_name)
                for field in struct.fields
            ):
                raise SotlasBootstrapError(
                    f"C11 shared allocation has an unsupported payload field in {struct_name}",
                    1, 1, module.filename, module.source,
                )
            if (
                f"{struct_name}_deinit" in deinit_names
                and any(
                    contains_owned_descendant(field.type)
                    for field in struct.fields
                )
                and not nested_deinit_is_detached(struct_name)
            ):
                raise SotlasBootstrapError(
                    f"C11 shared allocation has an unsupported payload field in {struct_name}",
                    1, 1, module.filename, module.source,
                )

    def _contains_domain(type_obj: Type | None, domain: str) -> bool:
        if type_obj is None:
            return False
        if getattr(type_obj, "ownership_domain", None) == domain:
            return True
        if (
            getattr(type_obj, "elem_type", None) is not None
            and _contains_domain(type_obj.elem_type, domain)
        ):
            return True
        if any(
            _contains_domain(param, domain)
            for param in getattr(type_obj, "fn_params", ())
        ):
            return True
        return _contains_domain(getattr(type_obj, "fn_ret", None), domain)

    def _module_contains_domain(domain: str) -> bool:
        return (
            any(
                _contains_domain(field.type, domain)
                for struct in module.structs for field in struct.fields
            )
            or any(_contains_domain(item.type, domain) for item in module.globals)
            or any(
                _contains_domain(getattr(variant, "payload_type", None), domain)
                for enum in module.enums
                for variant in enum.variants
            )
            or any(
                _contains_domain(type_obj, domain)
                for fn in module.functions for _, type_obj in fn.params
            )
            or any(_contains_domain(fn.result, domain) for fn in module.functions)
        )

    region_structs: dict[str, Struct] = {}
    region_struct_order: dict[str, int] = {}
    region_drop_types: set[str] = set()
    region_composite_drop_types: set[str] = set()
    if _module_contains_domain("region"):
        try:
            typed_ast_module = importlib.import_module(
                f"{__package__}.typed_ast"
                if __package__ else "sotlas_compile.typed_ast"
            )
            typed_region_module = (
                typed_ast_module.build_declaration_typed_ast(module)
            )
            typed_region_analysis = (
                typed_ast_module.analyze_module_ownership(
                    module, typed_region_module
                )
            )
            region_graph = typed_ast_module.build_ownership_domain_graph(
                typed_region_analysis
            )
        except (ImportError, ValueError) as error:
            raise SotlasBootstrapError(
                f"C11 region failed canonical ownership validation: {error}",
                1, 1, module.filename, module.source,
            ) from error
        region_root_names = {
            node.type.name
            for node in region_graph.nodes
            if node.domain is typed_ast_module.OwnershipDomain.REGION
        }
        all_region_structs = {item.name: item for item in module.structs}
        region_struct_order = {
            item.name: index for index, item in enumerate(module.structs)
        }
        region_drop_visiting: set[str] = set()

        def collect_region_drop_types(
            struct_name: str, region_owned: bool = False
        ) -> bool:
            if struct_name in region_drop_visiting:
                return True
            struct = all_region_structs.get(struct_name)
            if struct is None:
                return False
            region_drop_visiting.add(struct_name)
            has_region_child = False
            for field in struct.fields:
                field_type = field.type
                while field_type.is_array and field_type.elem_type is not None:
                    field_type = field_type.elem_type
                child = all_region_structs.get(field_type.name)
                if (
                    child is None or field_type.pointer
                    or field_type.is_reference or field_type.is_fn_ptr
                ):
                    continue
                child_has_region = collect_region_drop_types(
                    child.name, field_type.ownership_domain == "region"
                )
                if child_has_region:
                    region_structs[child.name] = child
                    has_region_child = True
            region_drop_visiting.remove(struct_name)
            if has_region_child:
                region_composite_drop_types.add(struct_name)
            if region_owned or has_region_child:
                region_structs[struct_name] = struct
                region_drop_types.add(struct_name)
                return True
            return False

        for region_name in region_root_names:
            collect_region_drop_types(region_name, region_owned=True)

        def region_deinit_references_self(node) -> bool:
            if node is None:
                return False
            if type(node).__name__ == "Name":
                return getattr(node, "value", None) == "self"
            if isinstance(node, (tuple, list)):
                return any(region_deinit_references_self(item) for item in node)
            fields = getattr(node, "__dataclass_fields__", None)
            if not fields:
                return False
            return any(
                region_deinit_references_self(getattr(node, field_name, None))
                for field_name in fields
                if field_name != "token"
            )

        for struct_name, struct in region_structs.items():
            has_region_children = False
            for field in struct.fields:
                child_type = field.type
                while child_type.is_array and child_type.elem_type is not None:
                    child_type = child_type.elem_type
                if child_type.name in region_drop_types:
                    has_region_children = True
                    break
            if not has_region_children:
                continue
            deinit = next(
                (
                    fn for fn in module.functions
                    if fn.name == f"{struct_name}_deinit" and fn.params
                ),
                None,
            )
            if deinit is not None and any(
                region_deinit_references_self(statement)
                for statement in deinit.body
            ):
                raise SotlasBootstrapError(
                    "C11 region recursive cleanup requires a detached owner "
                    "deinit when region-owned fields are present",
                    1, 1, module.filename, module.source,
                )

    if _module_contains_domain("device"):
        raise SotlasBootstrapError(
            "C11 backend does not lower device ownership domain yet",
            1, 1, module.filename, module.source,
        )

    if _module_contains_domain("external"):
        external_error = (
            "C11 external lowering supports only repr(C) sole owners "
            "consumed by an explicit external function boundary"
        )
        external_structs = {
            item.name: item
            for item in module.structs
            if item.is_sole and "@repr(C)" in item.attributes
        }
        all_external_structs = {item.name: item for item in module.structs}
        external_types = {
            (param_type.name, param_type.ownership_domain)
            for function in module.functions
            for _, param_type in function.params
            if _contains_domain(param_type, "external")
        }
        external_pod_fields = {
            "bool", "u8", "i8", "u16", "i16", "u32", "i32",
            "u64", "i64", "usize", "isize", "f32", "f64",
        }

        def type_contains_external(
            type_info: Type | None, visiting: frozenset[str] = frozenset()
        ) -> bool:
            if type_info is None:
                return False
            if _contains_domain(type_info, "external"):
                return True
            nested = all_external_structs.get(type_info.name)
            if nested is None or nested.name in visiting:
                return False
            next_visiting = visiting | {nested.name}
            return any(
                type_contains_external(field.type, next_visiting)
                for field in nested.fields
            )

        def external_wrapper_is_representable(
            struct: Struct, visiting: frozenset[str] = frozenset()
        ) -> bool:
            if struct.name not in external_structs:
                return False
            if struct.name in visiting:
                return False
            next_visiting = visiting | {struct.name}

            def field_is_representable(field_type: Type) -> bool:
                if (
                    field_type.pointer or field_type.is_reference
                    or field_type.is_fn_ptr
                ):
                    return False
                if field_type.is_array:
                    return (
                        isinstance(field_type.array_size, int)
                        and field_type.array_size > 0
                        and field_type.elem_type is not None
                        and field_is_representable(field_type.elem_type)
                    )
                if type_contains_external(field_type):
                    return (
                        field_type.ownership_domain == "external"
                        and field_type.name in external_structs
                        and external_wrapper_is_representable(
                            external_structs[field_type.name], next_visiting
                        )
                    )
                return field_type.name in external_pod_fields

            return all(field_is_representable(field.type) for field in struct.fields)

        has_external_storage = (
            any(
                type_contains_external(field.type)
                and not external_wrapper_is_representable(struct)
                for struct in module.structs for field in struct.fields
            )
            or any(type_contains_external(item.type) for item in module.globals)
            or any(
                type_contains_external(getattr(variant, "payload_type", None))
                for enum in module.enums for variant in enum.variants
            )
            or any(
                type_contains_external(field.type)
                for cls in module.classes for field in cls.fields
            )
            or any(
                type_contains_external(function.result)
                for function in module.functions
            )
            or any(
                type_contains_external(param_type)
                and param_type.ownership_domain != "external"
                for function in module.functions
                for _, param_type in function.params
            )
        )
        if (
            has_external_storage
            or any(
                domain != "external"
                or type_name not in external_structs
                for type_name, domain in external_types
            )
        ):
            raise SotlasBootstrapError(
                external_error, 1, 1, module.filename, module.source,
            )

        external_declarations = {
            function.name
            for function in module.functions
            if "@extern(C)" in function.attributes and not function.body
        }

        def external_sink_count(statement, parameter_name: str) -> int:
            if type(statement).__name__ != "Expression":
                return 0
            call = getattr(statement, "value", None)
            if (
                type(call).__name__ != "Call"
                or getattr(call, "callee", None) not in external_declarations
            ):
                return 0
            count = 0
            for argument in getattr(call, "args", ()):
                moved = (
                    argument.value
                    if type(argument).__name__ == "MoveExpr"
                    else argument
                )
                if (
                    type(moved).__name__ == "Name"
                    and getattr(moved, "value", None) == parameter_name
                ):
                    count += 1
            return count

        def external_sink_paths(statements, incoming, parameter_name):
            alive = set(incoming)
            completed: set[int] = set()
            for statement in statements or ():
                if not alive:
                    break
                kind = type(statement).__name__
                if kind == "If":
                    then_alive, then_completed = external_sink_paths(
                        statement.then_body, alive, parameter_name
                    )
                    if statement.else_body:
                        else_alive, else_completed = external_sink_paths(
                            statement.else_body, alive, parameter_name
                        )
                    else:
                        else_alive, else_completed = set(alive), set()
                    alive = then_alive | else_alive
                    completed.update(then_completed)
                    completed.update(else_completed)
                elif kind == "Unsafe":
                    alive, nested_completed = external_sink_paths(
                        statement.body, alive, parameter_name
                    )
                    completed.update(nested_completed)
                elif kind == "Return":
                    completed.update(alive)
                    alive.clear()
                else:
                    count = external_sink_count(statement, parameter_name)
                    alive = {path_count + count for path_count in alive}
            return alive, completed

        for function in module.functions:
            if "@extern(C)" in function.attributes and function.body and any(
                _contains_domain(param_type, "external")
                for _, param_type in function.params
            ):
                raise SotlasBootstrapError(
                    "C11 external owner boundary must be a bodyless @extern(C) declaration",
                    1, 1, module.filename, module.source,
                )
            if any(
                isinstance(item, Let)
                and item.type is not None
                and item.type.ownership_domain == "external"
                for item in _walk_statements_recursive(function.body)
            ):
                raise SotlasBootstrapError(
                    external_error, 1, 1, module.filename, module.source,
                )

        try:
            typed_ast_module = importlib.import_module(
                f"{__package__}.typed_ast"
                if __package__ else "sotlas_compile.typed_ast"
            )
            typed_external_module = (
                typed_ast_module.build_declaration_typed_ast(module)
            )
            for function in module.functions:
                external_params = [
                    name for name, param_type in function.params
                    if param_type.ownership_domain == "external"
                ]
                if not external_params or not function.body:
                    continue
                trace = typed_ast_module.analyze_function_ownership(
                    module, typed_external_module, function.name
                )
                for name in external_params:
                    sinks = [
                        event for event in trace.events
                        if event.kind == "move"
                        and event.name == name
                        and event.source_domain
                        is typed_ast_module.OwnershipDomain.EXTERNAL
                    ]
                    final_paths, completed_paths = external_sink_paths(
                        function.body, {0}, name
                    )
                    completed_paths.update(final_paths)
                    path_event_count = sum(
                        external_sink_count(statement, name)
                        for statement in _walk_statements_recursive(
                            function.body
                        )
                    )
                    if (
                        not sinks
                        or len(sinks) != path_event_count
                        or completed_paths != {1}
                        or any(
                            not event.via.startswith("call:")
                            or event.via.removeprefix("call:")
                            not in external_declarations
                            for event in sinks
                        )
                    ):
                        raise SotlasBootstrapError(
                            external_error, 1, 1,
                            module.filename, module.source,
                        )
        except SotlasBootstrapError:
            raise
        except (ImportError, ValueError) as error:
            raise SotlasBootstrapError(
                f"C11 external failed canonical ownership validation: {error}",
                1, 1, module.filename, module.source,
            ) from error

    if _module_contains_domain("island"):
        sole_type_names = {
            struct.name for struct in module.structs if struct.is_sole
        }
        structs_by_name = {struct.name: struct for struct in module.structs}
        deinit_names = {
            function.name for function in module.functions
            if function.name.endswith("_deinit") and function.params
        }

        def _direct_island_value(type_obj: Type | None) -> bool:
            return bool(
                type_obj is not None
                and getattr(type_obj, "ownership_domain", None) == "island"
                and not type_obj.pointer
                and not type_obj.is_reference
                and not type_obj.is_array
                and not type_obj.is_fn_ptr
                and type_obj.name in sole_type_names
            )

        def _plain_island_payload(
            type_obj: Type,
            active: frozenset[str] = frozenset(),
        ) -> bool:
            if (
                type_obj.pointer or type_obj.is_reference or type_obj.is_array
                or type_obj.is_fn_ptr
                or getattr(type_obj, "ownership_domain", None) is not None
            ):
                return False
            if type_obj.name in PRIMITIVES:
                return type_obj.name != "void"
            nested = structs_by_name.get(type_obj.name)
            if (
                nested is None or nested.is_sole or nested.is_register
                or not nested.fields or nested.name in active
                or f"{nested.name}_deinit" in deinit_names
            ):
                return False
            return all(
                _plain_island_payload(
                    field.type, active | {nested.name}
                )
                for field in nested.fields
            )

        def _safe_island_field(container: Struct, field: FieldDef) -> bool:
            payload = structs_by_name.get(field.type.name)
            return bool(
                container.is_sole
                and _direct_island_value(field.type)
                and payload is not None
                and f"{payload.name}_deinit" not in deinit_names
                and all(_plain_island_payload(child.type) for child in payload.fields)
            )

        island_field_storage = any(
            not _safe_island_field(container, field)
            for container in module.structs
            for field in container.fields
            if _contains_domain(field.type, "island")
        )

        island_storage = (
            island_field_storage
            or any(
                _contains_domain(item.type, "island") for item in module.globals
            )
            or any(
                _contains_domain(variant.payload_type, "island")
                for enum in module.enums for variant in enum.variants
            )
            or any(
                _contains_domain(field.type, "island")
                for class_decl in module.classes for field in class_decl.fields
            )
        )
        island_signature_gap = any(
            (
                _contains_domain(param_type, "island")
                and not _direct_island_value(param_type)
            )
            for function in module.functions
            for _, param_type in function.params
        ) or any(
            _contains_domain(function.result, "island")
            and not _direct_island_value(function.result)
            for function in module.functions
        )
        if island_storage or island_signature_gap:
            raise SotlasBootstrapError(
                "C11 island lowering currently supports only direct by-value "
                "sole function parameters/returns and POD island fields in "
                "sole containers",
                1, 1, module.filename, module.source,
            )
    if _module_contains_domain("whisper"):
        whisper_storage = (
            any(
                _contains_domain(field.type, "whisper")
                for struct in module.structs for field in struct.fields
            )
            or any(
                _contains_domain(item.type, "whisper") for item in module.globals
            )
            or any(
                _contains_domain(getattr(variant, "payload_type", None), "whisper")
                for enum in module.enums for variant in enum.variants
            )
            or any(
                _contains_domain(field.type, "whisper")
                for cls in module.classes for field in cls.fields
            )
            or any(
                _contains_domain(function.result, "whisper")
                for function in module.functions
            )
        )
        external_whisper_param = any(
            "@extern(C)" in function.attributes
            and any(_contains_domain(param_type, "whisper") for _, param_type in function.params)
            for function in module.functions
        )
        if whisper_storage or external_whisper_param:
            raise SotlasBootstrapError(
                "C11 whisper lowering supports only internal function parameters",
                1, 1, module.filename, module.source,
            )

    prefix = f"{_c_ident(module.name)}__" if mangle else ""
    guards: list[str] = []
    fn_names = {f.name for f in module.functions}
    for hook in (
        "sotlas_x86_scheduler_thread_exit",
        "sotlas_x86_scheduler_exit_probe_entry",
        "sotlas_x86_scheduler_idle_entry",
        "sotlas_x86_smp_ap_runtime_entry",
        "sotlas_x86_scheduler_smp_probe_entry",
        "sotlas_x86_scheduler_wait_probe_entry",
        "sotlas_x86_scheduler_wake_probe_entry",
        "sotlas_x86_userspace_bootstrap_entry",
        "sotlas_x86_exception_dispatch",
        "sotlas_x86_irq_dispatch",
    ):
        if hook in fn_names:
            guards.append(f"#define SOTLAS_OVERRIDE_{hook.upper()} 1")
    lines = guards + ([PREAMBLE] if include_preamble else [])
    if shared_functions:
        lines.append("#include <stdlib.h>")
    if include_import_headers:
        lines.extend(f'#include "{_c_ident(name)}.h"' for name in module.imports)
        if module.imports:
            lines.append("")

    # Constantes escalares precisam existir antes de tipos que as usam como
    # tamanho de array (em C, static const não é uma expressão integral constante).
    for g in module.globals:
        if g.is_const and not g.type.is_array:
            lines.append(f"#define {g.name} (({g.type.c()})({_emit_expr(g.value, prefix)}))")
    if any(g.is_const and not g.type.is_array for g in module.globals):
        lines.append("")

    # Enums
    for enum_obj in module.enums:
        lines.extend(_emit_c_enum(enum_obj))
        lines.append("")

    # Forward typedefs das structs para suportar ponteiros de função autorreferenciais e vtables
    for struct in module.structs:
        if getattr(struct, "is_register", False):
            lines.append(f"typedef union {struct.name} {struct.name};")
        else:
            lines.append(f"typedef struct {struct.name} {struct.name};")
    if module.structs:
        lines.append("")

    # Structs & Registers
    for struct in module.structs:
        if getattr(struct, "is_register", False):
            backing_c = struct.backing_type.c() if struct.backing_type else "uint32_t"
            lines.append(f"typedef union {struct.name} {{")
            lines.append(f"    {backing_c} raw;")
            lines.append(f"    struct __attribute__((packed)) {{")
            for fld in struct.fields:
                bw = f" : {fld.bit_width}" if fld.bit_width else ""
                lines.append(f"        {backing_c} {fld.name}{bw};")
            lines.append(f"    }};")
            lines.append(f"}} {struct.name};\n")
        else:
            pack_attr = _c_struct_attributes(struct.attributes)
            lines.append(f"typedef struct{pack_attr} {struct.name} {{")
            for fld in struct.fields:
                bw = f" : {fld.bit_width}" if getattr(fld, "bit_width", None) else ""
                lines.append(f"    {fld.type.c_decl(fld.name)}{bw};")
            lines.append(f"}} {struct.name};\n")

    # Forward declarations das funções (antes dos globais para suportar ponteiros de função)
    for function in module.functions:
        is_export = "@export" in function.attributes or function.public
        is_extern_c = "@extern(C)" in function.attributes
        fname = (
            function.name
            if (is_export or is_extern_c or not mangle)
            else f"{prefix}{function.name}"
        )
        parameters = ", ".join(f"{typ.c_decl(name)}" for name, typ in function.params) or "void"
        inline_attr = "static inline " if "@inline" in function.attributes and not is_export else ""
        extra_attrs = _c_func_attributes(function.attributes)
        lines.append(f"{inline_attr}{extra_attrs}{function.result.c()} {fname}({parameters});")
    if module.functions:
        lines.append("")

    if shared_functions:
        shared_drop_type_names: set[str] = set()
        shared_drop_type_visiting: set[str] = set()

        def collect_shared_drop_types(struct_name: str) -> bool:
            if struct_name in shared_drop_type_names:
                return True
            if struct_name in shared_drop_type_visiting:
                return False
            struct = shared_struct_by_name.get(struct_name)
            if struct is None:
                return False
            shared_drop_type_visiting.add(struct_name)
            contains_owned_fields = False
            for field in struct.fields:
                field_type = field.type
                while field_type.is_array and field_type.elem_type is not None:
                    field_type = field_type.elem_type
                child = (
                    shared_struct_by_name.get(field_type.name)
                    if field_type is not None else None
                )
                if (
                    child is not None
                    and not field_type.pointer
                    and not field_type.is_fn_ptr
                    and not field_type.is_reference
                ):
                    contains_owned_fields = (
                        collect_shared_drop_types(child.name)
                        or contains_owned_fields
                    )
            shared_drop_type_visiting.remove(struct_name)
            if struct.is_sole or contains_owned_fields:
                shared_drop_type_names.add(struct_name)
                return True
            return False

        for shared_type_name in shared_structs:
            collect_shared_drop_types(shared_type_name)

        lines.append("/* Shared boxes and recursive sole payload cleanup. */")
        for struct_name in sorted(shared_drop_type_names):
            lines.append(
                f"static inline void __sotlas_shared_drop_{struct_name}"
                f"({struct_name} *value);"
            )
        for struct_name in sorted(
            shared_drop_type_names,
            key=lambda name: struct_order[name],
        ):
            struct = shared_struct_by_name[struct_name]
            deinit = next(
                (
                    fn for fn in module.functions
                    if fn.name == f"{struct_name}_deinit" and fn.params
                ),
                None,
            )
            lines.append(
                f"static inline void __sotlas_shared_drop_{struct_name}"
                f"({struct_name} *value) {{"
            )
            if deinit is not None:
                deinit_arg = "value" if deinit.params[0][1].pointer else "*value"
                lines.append(f"    {struct_name}_deinit({deinit_arg});")
            for field in reversed(struct.fields):
                field_type = field.type
                array_dims = []
                while field_type.is_array and field_type.elem_type is not None:
                    array_dims.append(field_type)
                    field_type = field_type.elem_type
                child = (
                    shared_struct_by_name.get(field_type.name)
                    if field_type is not None else None
                )
                if (
                    child is not None
                    and child.name in shared_drop_type_names
                    and not field_type.pointer
                    and not field_type.is_fn_ptr
                    and not field_type.is_reference
                ):
                    if not array_dims:
                        lines.append(
                            f"    __sotlas_shared_drop_{child.name}"
                            f"(&value->{field.name});"
                        )
                    else:
                        indent = "    "
                        access = f"value->{field.name}"
                        for dimension, _ in enumerate(array_dims):
                            index_name = _c_ident(
                                f"__sotlas_drop_index_{struct_name}_"
                                f"{field.name}_{dimension}"
                            )
                            lines.append(
                                f"{indent}for (size_t {index_name} = "
                                f"sizeof({access}) / sizeof({access}[0]); "
                                f"{index_name} > 0; --{index_name}) {{"
                            )
                            indent += "    "
                            access += f"[{index_name} - 1]"
                        lines.append(
                            f"{indent}__sotlas_shared_drop_{child.name}"
                            f"(&{access});"
                        )
                        for _ in array_dims:
                            indent = indent[:-4]
                            lines.append(f"{indent}}}")
            lines.append("}")
        for struct_name in sorted(shared_structs):
            box_name = f"__sotlas_shared_box_{struct_name}"
            lines.extend([
                f"typedef struct {box_name} {{ ArcHeader header; {struct_name} value; }} {box_name};",
                f"static inline {box_name} *__sotlas_shared_new_{struct_name}({struct_name} value) {{",
                f"    {box_name} *box = ({box_name} *)malloc(sizeof(*box));",
                "    if (box == NULL) abort();",
                f"    box->value = value; arc_init(&box->header, sizeof({struct_name}));",
                "    return box;",
                "}",
                f"static inline void __sotlas_shared_release_{struct_name}({box_name} *box) {{",
                "    if (box == NULL) return;",
                "    if (arc_release(&box->header)) {",
                f"        __sotlas_shared_drop_{struct_name}(&box->value);",
                "        free(box);",
                "    }",
                "}",
            ])
        lines.append("")

    if region_drop_types:
        lines.append("/* Region ownership recursive cleanup. */")
        for struct_name in sorted(region_drop_types):
            lines.append(
                f"static inline void __sotlas_region_drop_{struct_name}"
                f"({struct_name} *value);"
            )
        for struct_name in sorted(
            region_drop_types,
            key=lambda name: region_struct_order[name],
        ):
            struct = region_structs[struct_name]
            deinit = next(
                (
                    fn for fn in module.functions
                    if fn.name == f"{struct_name}_deinit" and fn.params
                ),
                None,
            )
            lines.append(
                f"static inline void __sotlas_region_drop_{struct_name}"
                f"({struct_name} *value) {{"
            )
            if deinit is not None:
                arg = "value" if deinit.params[0][1].pointer else "*value"
                lines.append(f"    {struct_name}_deinit({arg});")
            for field in reversed(struct.fields):
                field_type = field.type
                array_dims = []
                while field_type.is_array and field_type.elem_type is not None:
                    array_dims.append(field_type)
                    field_type = field_type.elem_type
                child = region_structs.get(field_type.name)
                if (
                    child is None or child.name not in region_drop_types
                    or field_type.pointer or field_type.is_reference
                    or field_type.is_fn_ptr
                ):
                    continue
                indent = "    "
                access = f"value->{field.name}"
                for dimension, _ in enumerate(array_dims):
                    index_name = _c_ident(
                        f"__sotlas_region_drop_{struct_name}_"
                        f"{field.name}_{dimension}"
                    )
                    lines.append(
                        f"{indent}for (size_t {index_name} = sizeof({access}) / "
                        f"sizeof({access}[0]); {index_name} > 0; --{index_name}) {{"
                    )
                    indent += "    "
                    access += f"[{index_name} - 1]"
                lines.append(
                    f"{indent}__sotlas_region_drop_{child.name}(&{access});"
                )
                for _ in array_dims:
                    indent = indent[:-4]
                    lines.append(f"{indent}}}")
            lines.append("}")
        lines.append("")

    # Globals / Consts
    for g in module.globals:
        if g.is_const and not g.type.is_array:
            continue
        specifier = "static const" if g.is_const else "static"
        if g.type.is_array and not g.type.pointer and isinstance(g.value, Number) and g.value.value == "0":
            lines.append(f"{specifier} {g.type.c_decl(g.name)} = {{0}};")
        elif isinstance(g.value, ArrayLit) and g.value.is_repeat:
            lines.append(f"{specifier} {g.type.c_decl(g.name)} = {_emit_expr(g.value, prefix)};")
        else:
            lines.append(f"{specifier} {g.type.c_decl(g.name)} = {_emit_expr(g.value, prefix)};")
    if module.globals: lines.append("")

    def _emit_defer_action(
        d: Defer, pad: str, shared_boxes: dict[str, str] | None = None
    ) -> str:
        if isinstance(d.value, Assign):
            target_str = _emit_expr(
                d.value.target, prefix, shared_boxes
            ) if isinstance(d.value.target, Expr) else str(d.value.target)
            return (
                f"{pad}{target_str} = "
                f"{_emit_expr(d.value.value, prefix, shared_boxes)};"
            )
        return f"{pad}{_emit_expr(d.value, prefix, shared_boxes)};"

    sole_types = {
        item.name for item in module.structs if item.is_sole
    }

    function_by_name = {
        item.name: item for item in module.functions
    }

    struct_by_name = {
        item.name: item for item in module.structs
    }

    def _sole_struct_transfer_names(expr: Expr | None) -> set[str]:
        if expr is None:
            return set()

        names: set[str] = set()

        if isinstance(expr, StructLit):
            struct = struct_by_name.get(expr.struct_name)
            field_map = (
                {field.name: field for field in struct.fields}
                if struct is not None
                else {}
            )
            if struct is not None and struct.is_sole:
                for field_name, value in expr.fields:
                    field = field_map.get(field_name)
                    if (
                        field is not None
                        and field.type.name in sole_types
                        and not field.type.pointer
                        and not field.type.is_reference
                    ):
                        moved_value = (
                            value.value
                            if isinstance(value, MoveExpr)
                            else value
                        )
                        if isinstance(moved_value, Name):
                            names.add(moved_value.value)

                    names.update(_sole_struct_transfer_names(value))
            return names

        if isinstance(expr, (UnsafeExpr, MoveExpr)):
            names.update(_sole_struct_transfer_names(expr.value))
        elif isinstance(expr, TryExpr):
            names.update(_sole_struct_transfer_names(expr.expr))
        elif isinstance(expr, Binary):
            names.update(_sole_struct_transfer_names(expr.left))
            names.update(_sole_struct_transfer_names(expr.right))
        elif isinstance(expr, Unary):
            names.update(_sole_struct_transfer_names(expr.value))
        elif isinstance(expr, Cast):
            names.update(_sole_struct_transfer_names(expr.expr))
        elif isinstance(expr, Index):
            names.update(_sole_struct_transfer_names(expr.target))
            names.update(_sole_struct_transfer_names(expr.index))
        elif isinstance(expr, Member):
            names.update(_sole_struct_transfer_names(expr.target))
        elif isinstance(expr, Call):
            for argument in expr.args:
                names.update(_sole_struct_transfer_names(argument))
        elif isinstance(expr, MethodCall):
            names.update(_sole_struct_transfer_names(expr.target))
            for argument in expr.args:
                names.update(_sole_struct_transfer_names(argument))
        elif isinstance(expr, ArrayLit):
            for element in expr.elements:
                names.update(_sole_struct_transfer_names(element))
        elif isinstance(expr, IfExpr):
            names.update(_sole_struct_transfer_names(expr.condition))
            names.update(_sole_struct_transfer_names(expr.then_expr))
            names.update(_sole_struct_transfer_names(expr.else_expr))

        return names

    def _sole_transfer_names(expr: Expr | None) -> set[str]:
        return (
            _sole_call_transfer_names(expr)
            | _sole_struct_transfer_names(expr)
        )

    def _sole_call_transfer_names(expr: Expr | None) -> set[str]:
        if expr is None:
            return set()

        names: set[str] = set()

        if isinstance(expr, Call):
            callee = function_by_name.get(expr.callee)
            if expr.callee == "transition" and expr.args:
                moved = expr.args[0]
                if (
                    isinstance(moved, MoveExpr)
                    and isinstance(moved.value, Name)
                ):
                    names.add(moved.value.value)
                for argument in expr.args:
                    names.update(_sole_call_transfer_names(argument))
                return names
            if callee is not None:
                for argument, (_, parameter_type) in zip(
                    expr.args, callee.params
                ):
                    if (
                        parameter_type.name in sole_types
                        and not parameter_type.pointer
                        and getattr(parameter_type, "ownership_domain", None)
                            != "whisper"
                    ):
                        moved_argument = (
                            argument.value
                            if isinstance(argument, MoveExpr)
                            else argument
                        )
                        if isinstance(moved_argument, Name):
                            names.add(moved_argument.value)
            for argument in expr.args:
                names.update(_sole_call_transfer_names(argument))
            return names

        if isinstance(expr, MethodCall):
            target_type = getattr(expr, "target_type", None)
            owner_name = getattr(target_type, "name", None)
            callee = (
                function_by_name.get(f"{owner_name}_{expr.method}")
                if owner_name
                else None
            )
            if callee is not None and callee.params:
                self_type = callee.params[0][1]
                if (
                    self_type.name in sole_types
                    and not self_type.pointer
                ):
                    moved_receiver = (
                        expr.target.value
                        if isinstance(expr.target, MoveExpr)
                        else expr.target
                    )
                    if isinstance(moved_receiver, Name):
                        names.add(moved_receiver.value)
            user_params = callee.params[1:] if callee is not None else ()
            for argument, (_, parameter_type) in zip(expr.args, user_params):
                if (
                    parameter_type.name in sole_types
                    and not parameter_type.pointer
                ):
                    moved_argument = (
                        argument.value
                        if isinstance(argument, MoveExpr)
                        else argument
                    )
                    if isinstance(moved_argument, Name):
                        names.add(moved_argument.value)
            names.update(_sole_call_transfer_names(expr.target))
            for argument in expr.args:
                names.update(_sole_call_transfer_names(argument))
            return names

        if isinstance(expr, (UnsafeExpr, MoveExpr, TryExpr)):
            inner = (
                expr.expr
                if isinstance(expr, TryExpr)
                else expr.value
            )
            names.update(_sole_call_transfer_names(inner))
            return names

        if isinstance(expr, Binary):
            names.update(_sole_call_transfer_names(expr.left))
            names.update(_sole_call_transfer_names(expr.right))
            return names

        if isinstance(expr, Unary):
            names.update(_sole_call_transfer_names(expr.value))
            return names

        if isinstance(expr, Cast):
            names.update(_sole_call_transfer_names(expr.expr))
            return names

        if isinstance(expr, Index):
            names.update(_sole_call_transfer_names(expr.target))
            names.update(_sole_call_transfer_names(expr.index))
            return names

        if isinstance(expr, Member):
            names.update(_sole_call_transfer_names(expr.target))
            return names

        if isinstance(expr, ArrayLit):
            for element in expr.elements:
                names.update(_sole_call_transfer_names(element))
            return names

        if isinstance(expr, StructLit):
            for _, value in expr.fields:
                names.update(_sole_call_transfer_names(value))
            return names

        if isinstance(expr, IfExpr):
            names.update(_sole_call_transfer_names(expr.condition))
            names.update(_sole_call_transfer_names(expr.then_expr))
            names.update(_sole_call_transfer_names(expr.else_expr))
            return names

        return names

    def _suppress_auto_cleanups(
        defer_scopes: list[list[Defer]],
        binding_names: set[str],
    ) -> None:
        if not binding_names:
            return
        for cleanup_scope in defer_scopes:
            cleanup_scope[:] = [
                cleanup for cleanup in cleanup_scope
                if cleanup.auto_cleanup_name not in binding_names
            ]

    def _auto_cleanup_type(cleanup: Defer) -> str | None:
        if cleanup.auto_cleanup_name is None:
            return None
        if not isinstance(cleanup.value, Call):
            return None
        callee = cleanup.value.callee
        if not callee.endswith("_deinit"):
            return None
        return callee.rsplit("_deinit", 1)[0]

    def _find_auto_cleanup(
        defer_scopes: list[list[Defer]],
        binding_name: str,
    ) -> Defer | None:
        for cleanup_scope in reversed(defer_scopes):
            for cleanup in reversed(cleanup_scope):
                if cleanup.auto_cleanup_name == binding_name:
                    return cleanup
        return None

    def _block_definitely_returns(statements) -> bool:
        for statement in statements or ():
            if isinstance(statement, Return):
                return True
            if isinstance(statement, Discern) and statement.cases and all(
                _block_definitely_returns(case.body)
                for case in statement.cases
            ):
                return True
            if isinstance(statement, Unsafe) and _block_definitely_returns(
                statement.body
            ):
                return True
            if (
                isinstance(statement, If)
                and statement.else_body
                and _block_definitely_returns(statement.then_body)
                and _block_definitely_returns(statement.else_body)
            ):
                return True
        return False

    def emit_statements(
        items: list[Stmt],
        depth: int,
        defer_scopes: list[list[Defer]],
        loop_scope_depth: int | None = None,
        ret_type: Type | None = None,
        owned_params: list[tuple[str, Type]] | None = None,
        shared_boxes: dict[str, str] | None = None,
        shared_cleanups: list[tuple[str, str]] | None = None,
        shared_owner_names: set[str] | None = None,
        shared_local_types: dict[str, Type] | None = None,
        loop_shared_cleanup_entry_count: int | None = None,
        is_function_scope: bool = False,
    ) -> list[str]:
        pad = "    " * depth; out: list[str] = []
        shared_boxes = shared_boxes if shared_boxes is not None else {}
        local_shared_cleanups = (
            shared_cleanups if shared_cleanups is not None else []
        )
        shared_cleanup_entry_count = len(local_shared_cleanups)
        shared_local_types = dict(shared_local_types or {})
        shared_local_types.update(dict(owned_params or []))
        shared_owner_cleanup_names = (
            shared_owner_names if shared_owner_names is not None else set()
        )
        shared_names_at_entry = set(shared_owner_cleanup_names)
        scope_local_owner_names: set[str] = set()
        for statement in items:
            if not isinstance(statement, Let):
                continue
            local_type = statement.type
            if local_type is None and isinstance(statement.value, StructLit):
                local_type = Type(statement.value.struct_name)
            if (
                local_type is not None
                and local_type.name in sole_types
                and not local_type.pointer
            ):
                scope_local_owner_names.add(statement.name)
        available_shared_boxes = set(shared_boxes)
        share_sources_are_scope_local_or_shared = True
        for statement in items:
            if not (
                isinstance(statement, Let)
                and isinstance(statement.value, ShareExpr)
                and isinstance(statement.value.value, Name)
            ):
                continue
            source_name = statement.value.value.value
            if (
                source_name not in available_shared_boxes
                and source_name not in scope_local_owner_names
            ):
                share_sources_are_scope_local_or_shared = False
            available_shared_boxes.add(statement.name)
        defer_scopes.append([])
        deinit_methods: dict[str, bool] = {}
        for fn in module.functions:
            if fn.name.endswith("_deinit") and len(fn.params) >= 1 and fn.params[0][0] == "self":
                sname = fn.name.rsplit("_deinit", 1)[0]
                deinit_methods[sname] = fn.params[0][1].pointer

        def region_cleanup_for(
            typ: Type, name: str, token: Token
        ) -> Defer | None:
            if (
                typ.name not in region_drop_types
                or not (
                    typ.ownership_domain == "region"
                    or typ.name in region_composite_drop_types
                )
                or typ.pointer or typ.is_array or typ.is_reference
            ):
                return None
            return Defer(
                token,
                value=Call(
                    token,
                    f"__sotlas_region_drop_{typ.name}",
                    [Unary(token, "&", Name(token, name))],
                ),
                auto_cleanup_name=name,
            )

        if owned_params is not None:
            for param_name, param_type in owned_params:
                region_cleanup = region_cleanup_for(
                    param_type, param_name,
                    Token("IDENT", param_name, 0, 0),
                )
                if region_cleanup is not None:
                    defer_scopes[-1].append(region_cleanup)
                if (
                    param_type.name in sole_types
                    and not param_type.pointer
                    and param_type.ownership_domain != "region"
                    and getattr(param_type, "ownership_domain", None)
                        != "whisper"
                    and param_type.name in deinit_methods
                ):
                    token = Token("IDENT", param_name, 0, 0)
                    takes_ptr = deinit_methods[param_type.name]
                    arg_node = (
                        Unary(token, "&", Name(token, param_name))
                        if takes_ptr
                        else Name(token, param_name)
                    )
                    call_expr = Call(
                        token,
                        f"{param_type.name}_deinit",
                        [arg_node],
                    )
                    defer_scopes[-1].append(
                        Defer(
                            token,
                            value=call_expr,
                            auto_cleanup_name=param_name,
                        )
                    )

        for item in items:
            if isinstance(item, Let):
                if isinstance(item.value, ShareExpr):
                    source_name = item.value.value.value
                    source_type = shared_local_types.get(source_name)
                    if source_type is None or source_type.name not in shared_structs:
                        raise SotlasBootstrapError("C11 share source type is not a supported sole struct", item.token.line, item.token.column)
                    struct_name = source_type.name
                    box = f"_st_shared_box_{item.name}"
                    source_box = shared_boxes.get(source_name)
                    if source_box is None:
                        out.append(f"{pad}{_c_ident('__sotlas_shared_box_' + struct_name)} *{box} = __sotlas_shared_new_{struct_name}({source_name});")
                        out.append(f"{pad}if (arc_retain(&{box}->header) == NULL) abort();")
                        _suppress_auto_cleanups(defer_scopes, {source_name})
                    else:
                        out.append(f"{pad}{_c_ident('__sotlas_shared_box_' + struct_name)} *{box} = {source_box};")
                        out.append(f"{pad}if (arc_retain(&{box}->header) == NULL) abort();")
                    shared_boxes[source_name] = source_box or box
                    shared_boxes[item.name] = box
                    shared_local_types[item.name] = source_type
                    release = Call(
                        item.token,
                        f"__sotlas_shared_release_{struct_name}",
                        [Name(item.token, box)],
                    )
                    cleanup = Defer(item.token, value=release)
                    cleanup.auto_cleanup_name = item.name
                    defer_scopes[-1].append(cleanup)
                    if source_box is None:
                        local_shared_cleanups.extend(((box, struct_name), (box, struct_name)))
                    else:
                        local_shared_cleanups.append((box, struct_name))
                    for shared_owner in (source_name, item.name):
                        shared_owner_cleanup_names.add(shared_owner)
                    continue
                _suppress_auto_cleanups(
                    defer_scopes,
                    _sole_transfer_names(item.value),
                )
                if item.type is not None:
                    typ = item.type
                    shared_local_types[item.name] = typ
                    if typ.name in sole_types and not typ.pointer:
                        moved_value = (
                            item.value.value
                            if isinstance(item.value, MoveExpr)
                            else item.value
                        )
                        if isinstance(moved_value, Name):
                            source_name = moved_value.value
                            for cleanup_scope in defer_scopes:
                                cleanup_scope[:] = [
                                    d for d in cleanup_scope
                                    if d.auto_cleanup_name != source_name
                                ]
                    if (typ.is_array or typ.name not in PRIMITIVES) and not typ.pointer and isinstance(item.value, Number) and item.value.value == "0":
                        out.append(f"{pad}{typ.c_decl(item.name)} = {{0}};")
                    elif typ.is_array:
                        decl = typ.c_decl(item.name)
                        prefix_spec = "static " if decl.startswith("const ") else "static const "
                        out.append(f"{pad}{prefix_spec}{decl} = {_emit_expr(item.value, prefix)};")
                    else:
                        out.append(f"{pad}{typ.c_decl(item.name)} = {_emit_expr(item.value, prefix, shared_boxes)};")
                    region_cleanup = region_cleanup_for(
                        typ, item.name, item.token
                    )
                    if region_cleanup is not None:
                        defer_scopes[-1].append(region_cleanup)
                    if (
                        typ.name in deinit_methods and not typ.pointer
                        and region_cleanup is None
                    ):
                        takes_ptr = deinit_methods[typ.name]
                        arg_node = Unary(item.token, "&", Name(item.token, item.name)) if takes_ptr else Name(item.token, item.name)
                        call_expr = Call(item.token, f"{typ.name}_deinit", [arg_node])
                        defer_scopes[-1].append(
                            Defer(
                                item.token,
                                value=call_expr,
                                auto_cleanup_name=item.name,
                            )
                        )
                elif isinstance(item.value, StructLit):
                    typ = Type(item.value.struct_name)
                    shared_local_types[item.name] = typ
                    out.append(
                        f"{pad}{typ.c_decl(item.name)} = "
                        f"{_emit_expr(item.value, prefix, shared_boxes)};"
                    )
                    region_cleanup = region_cleanup_for(
                        typ, item.name, item.token
                    )
                    if region_cleanup is not None:
                        defer_scopes[-1].append(region_cleanup)
                    if (
                        typ.name in deinit_methods
                        and region_cleanup is None
                    ):
                        takes_ptr = deinit_methods[typ.name]
                        arg_node = (
                            Unary(item.token, "&", Name(item.token, item.name))
                            if takes_ptr
                            else Name(item.token, item.name)
                        )
                        defer_scopes[-1].append(Defer(
                            item.token,
                            value=Call(
                                item.token, f"{typ.name}_deinit", [arg_node]
                            ),
                            auto_cleanup_name=item.name,
                        ))
                else:
                    if isinstance(item.value, ArrayLit) and not item.value.is_repeat:
                        first_e = item.value.elements[0] if item.value.elements else None
                        if first_e and isinstance(first_e, Number):
                            out.append(f"{pad}uint32_t {item.name}[] = {_emit_expr(item.value, prefix)};")
                        else:
                            out.append(f"{pad}const uint8_t *{item.name}[] = {_emit_expr(item.value, prefix)};")
                    else:
                        out.append(f"{pad}__auto_type {item.name} = {_emit_expr(item.value, prefix, shared_boxes)};")
                        inferred_type_name = (
                            item.value.struct_name
                            if isinstance(item.value, StructLit)
                            else None
                        )
                        if inferred_type_name in deinit_methods:
                            takes_ptr = deinit_methods[inferred_type_name]
                            arg_node = (
                                Unary(
                                    item.token,
                                    "&",
                                    Name(item.token, item.name),
                                )
                                if takes_ptr
                                else Name(item.token, item.name)
                            )
                            call_expr = Call(
                                item.token,
                                f"{inferred_type_name}_deinit",
                                [arg_node],
                            )
                            defer_scopes[-1].append(
                                Defer(
                                    item.token,
                                    value=call_expr,
                                    auto_cleanup_name=item.name,
                                )
                            )
            elif isinstance(item, Assign):
                _suppress_auto_cleanups(
                    defer_scopes,
                    _sole_transfer_names(item.value),
                )
                target_str = _emit_expr(item.target, prefix, shared_boxes) if isinstance(item.target, Expr) else str(item.target)

                target_name = (
                    item.target.value
                    if isinstance(item.target, Name)
                    else None
                )
                moved_value = (
                    item.value.value
                    if isinstance(item.value, MoveExpr)
                    else item.value
                )
                source_name = (
                    moved_value.value
                    if isinstance(moved_value, Name)
                    else None
                )

                if (
                    target_name is not None
                    and source_name is not None
                    and target_name != source_name
                ):
                    target_cleanup = _find_auto_cleanup(
                        defer_scopes, target_name
                    )
                    if (
                        target_cleanup is not None
                        and _auto_cleanup_type(target_cleanup) in sole_types
                    ):
                        out.append(_emit_defer_action(
                            target_cleanup, pad, shared_boxes
                        ))
                        for cleanup_scope in defer_scopes:
                            cleanup_scope[:] = [
                                cleanup for cleanup in cleanup_scope
                                if cleanup.auto_cleanup_name != source_name
                            ]

                if (isinstance(item.value, ArrayLit) and item.value.is_repeat and
                        isinstance(item.value.elements[0], Number) and item.value.elements[0].value == "0"):
                    out.append(f"{pad}__builtin_memset(&({target_str}), 0, sizeof({target_str}));")
                else:
                    out.append(f"{pad}{target_str} = {_emit_expr(item.value, prefix, shared_boxes)};")
            elif isinstance(item, Handover):
                source_name = (
                    item.value.value
                    if isinstance(item.value, Name)
                    else None
                )
                destination_name = (
                    item.destination.value
                    if isinstance(item.destination, Name)
                    else None
                )
                if source_name is None or destination_name is None:
                    raise SotlasBootstrapError(
                        "C11 handover requires a validated binding destination",
                        item.token.line, item.token.column,
                    )
                _suppress_auto_cleanups(defer_scopes, {source_name})
                out.append(
                    f"{pad}{destination_name} = {source_name};"
                )
                destination_type = shared_local_types.get(destination_name)
                if destination_type is not None:
                    destination_cleanup = region_cleanup_for(
                        destination_type, destination_name, item.token
                    )
                    if destination_cleanup is None and (
                        destination_type.name in deinit_methods
                        and destination_type.name in sole_types
                        and not destination_type.pointer
                    ):
                        takes_ptr = deinit_methods[destination_type.name]
                        arg_node = (
                            Unary(
                                item.token, "&",
                                Name(item.token, destination_name),
                            )
                            if takes_ptr
                            else Name(item.token, destination_name)
                        )
                        destination_cleanup = Defer(
                            item.token,
                            value=Call(
                                item.token,
                                f"{destination_type.name}_deinit",
                                [arg_node],
                            ),
                            auto_cleanup_name=destination_name,
                        )
                    if destination_cleanup is not None:
                        defer_scopes[-1].append(destination_cleanup)
            elif isinstance(item, Quarantine):
                source_name = (
                    item.value.value
                    if isinstance(item.value, Name)
                    else None
                )
                if source_name is None:
                    raise SotlasBootstrapError(
                        "C11 quarantine requires a validated ownership binding",
                        item.token.line, item.token.column,
                    )
                # The ownership transition is statically checked. In the
                # supported C11 subset, quarantine changes no representation;
                # island aliases and other runtime effects remain gated.
                out.append(
                    f"{pad}/* quarantine {source_name}: compile-time ownership transition */"
                )
            elif isinstance(item, Defer):
                deferred_expression = _deferred_expression(item)
                safe_defer_read = _safe_shared_defer_method(
                    item, shared_owner_cleanup_names
                ) or _safe_shared_defer_call(
                    item, shared_owner_cleanup_names
                )
                if shared_owner_cleanup_names and any(
                    isinstance(node, Name)
                    and node.value in shared_owner_cleanup_names
                    for node in _walk_expr(deferred_expression)
                ) and not safe_defer_read:
                    raise SotlasBootstrapError(
                        "C11 shared aliases cannot be captured by defer",
                        item.token.line, item.token.column,
                        module.filename, module.source,
                    )
                _suppress_auto_cleanups(
                    defer_scopes, _sole_transfer_names(deferred_expression)
                )
                defer_scopes[-1].append(item)
            elif isinstance(item, Return):
                _suppress_auto_cleanups(
                    defer_scopes,
                    _sole_transfer_names(item.value),
                )
                all_defers = [
                    d
                    for scope in reversed(defer_scopes)
                    for d in reversed(scope)
                ]
                transferred_name: str | None = None
                if (
                    item.value is not None
                    and ret_type is not None
                    and ret_type.name in sole_types
                ):
                    moved_value = (
                        item.value.value
                        if isinstance(item.value, MoveExpr)
                        else item.value
                    )
                    if isinstance(moved_value, Name):
                        transferred_name = moved_value.value

                if transferred_name is not None:
                    all_defers = [
                        d for d in all_defers
                        if d.auto_cleanup_name != transferred_name
                    ]

                if item.value:
                    val_str = _emit_expr(item.value, prefix, shared_boxes)
                    if all_defers or shared_owner_cleanup_names:
                        c_ret_type = ret_type.c() if ret_type else "int64_t"
                        out.append(f"{pad}{c_ret_type} _st_ret = {val_str};")
                        for d in all_defers:
                            if (
                                local_shared_cleanups
                                and isinstance(d.value, Call)
                                and d.value.callee.startswith("__sotlas_shared_release_")
                            ):
                                continue
                            if d.body is not None:
                                out.extend(emit_statements(
                                    d.body, depth, defer_scopes,
                                    loop_scope_depth, ret_type,
                                    shared_boxes=shared_boxes,
                                ))
                            else:
                                out.append(_emit_defer_action(d, pad, shared_boxes))
                        for box_name, shared_struct_name in reversed(local_shared_cleanups):
                            out.append(
                                f"{pad}__sotlas_shared_release_{shared_struct_name}({box_name});"
                            )
                        out.append(f"{pad}return _st_ret;")
                        return out
                    else:
                        out.append(f"{pad}return {val_str};")
                        return out
                else:
                    for d in all_defers:
                        if (
                            local_shared_cleanups
                            and isinstance(d.value, Call)
                            and d.value.callee.startswith(
                                "__sotlas_shared_release_"
                            )
                        ):
                            continue
                        if d.body is not None:
                            out.extend(emit_statements(
                                d.body, depth, defer_scopes,
                                loop_scope_depth, ret_type,
                                shared_boxes=shared_boxes,
                            ))
                        else:
                            out.append(_emit_defer_action(d, pad, shared_boxes))
                    for box_name, shared_struct_name in reversed(local_shared_cleanups):
                        out.append(
                            f"{pad}__sotlas_shared_release_{shared_struct_name}({box_name});"
                        )
                    out.append(f"{pad}return;")
                    return out
            elif isinstance(item, Break):
                if loop_scope_depth is not None:
                    loop_defers = [d for scope in reversed(defer_scopes[loop_scope_depth:]) for d in reversed(scope)]
                    for d in loop_defers:
                        if (
                            loop_shared_cleanup_entry_count is not None
                            and isinstance(d.value, Call)
                            and d.value.callee.startswith("__sotlas_shared_release_")
                        ):
                            continue
                        if d.body is not None:
                            out.extend(emit_statements(
                                d.body, depth, defer_scopes,
                                loop_scope_depth, ret_type,
                                shared_boxes=shared_boxes,
                            ))
                        else:
                            out.append(_emit_defer_action(d, pad, shared_boxes))
                if loop_shared_cleanup_entry_count is not None:
                    for box_name, shared_struct_name in reversed(
                        local_shared_cleanups[loop_shared_cleanup_entry_count:]
                    ):
                        out.append(
                            f"{pad}__sotlas_shared_release_{shared_struct_name}"
                            f"({box_name});"
                        )
                out.append(f"{pad}break;")
            elif isinstance(item, Continue):
                if loop_scope_depth is not None:
                    loop_defers = [d for scope in reversed(defer_scopes[loop_scope_depth:]) for d in reversed(scope)]
                    for d in loop_defers:
                        if (
                            loop_shared_cleanup_entry_count is not None
                            and isinstance(d.value, Call)
                            and d.value.callee.startswith("__sotlas_shared_release_")
                        ):
                            continue
                        if d.body is not None:
                            out.extend(emit_statements(
                                d.body, depth, defer_scopes,
                                loop_scope_depth, ret_type,
                                shared_boxes=shared_boxes,
                            ))
                        else:
                            out.append(_emit_defer_action(d, pad, shared_boxes))
                if loop_shared_cleanup_entry_count is not None:
                    for box_name, shared_struct_name in reversed(
                        local_shared_cleanups[loop_shared_cleanup_entry_count:]
                    ):
                        out.append(
                            f"{pad}__sotlas_shared_release_{shared_struct_name}"
                            f"({box_name});"
                        )
                out.append(f"{pad}continue;")
            elif isinstance(item, Expression):
                _suppress_auto_cleanups(
                    defer_scopes,
                    _sole_transfer_names(item.value),
                )
                out.append(f"{pad}{_emit_expr(item.value, prefix, shared_boxes)};")
            elif isinstance(item, Asm):
                parts = [item.code]
                if item.outputs or item.inputs or item.clobbers:
                    out_s = ", ".join(_emit_expr(e, prefix) for e in item.outputs)
                    in_s = ", ".join(_emit_expr(e, prefix) for e in item.inputs)
                    clob_s = ", ".join(item.clobbers)
                    parts.append(f": {out_s} : {in_s} : {clob_s}")
                out.append(f"{pad}__asm__ volatile({ ' '.join(parts) });")
            elif isinstance(item, Unsafe):
                out.extend(emit_statements(
                    item.body, depth, defer_scopes, loop_scope_depth, ret_type,
                    shared_boxes=dict(shared_boxes),
                    shared_cleanups=list(local_shared_cleanups),
                    shared_owner_names=set(shared_owner_cleanup_names),
                    shared_local_types=dict(shared_local_types),
                    loop_shared_cleanup_entry_count=loop_shared_cleanup_entry_count,
                ))
            elif isinstance(item, While):
                out.append(
                    f"{pad}while ({_emit_expr(item.condition, prefix, shared_boxes)}) {{"
                )
                out.extend(emit_statements(
                    item.body, depth + 1, defer_scopes,
                    loop_scope_depth=len(defer_scopes), ret_type=ret_type,
                    shared_boxes=dict(shared_boxes),
                    shared_cleanups=list(local_shared_cleanups),
                    shared_owner_names=set(shared_owner_cleanup_names),
                    shared_local_types=dict(shared_local_types),
                    loop_shared_cleanup_entry_count=len(local_shared_cleanups),
                ))
                out.append(f"{pad}}}")
            elif isinstance(item, Loop):
                out.append(f"{pad}for (;;) {{")
                out.extend(emit_statements(
                    item.body, depth + 1, defer_scopes,
                    loop_scope_depth=len(defer_scopes), ret_type=ret_type,
                    shared_boxes=dict(shared_boxes),
                    shared_cleanups=list(local_shared_cleanups),
                    shared_owner_names=set(shared_owner_cleanup_names),
                    shared_local_types=dict(shared_local_types),
                    loop_shared_cleanup_entry_count=len(local_shared_cleanups),
                ))
                out.append(f"{pad}}}")
            elif isinstance(item, For):
                start_str = _emit_expr(item.start, prefix, shared_boxes)
                end_str = _emit_expr(item.end, prefix, shared_boxes)
                out.append(f"{pad}for (size_t {item.var_name} = {start_str}; {item.var_name} < {end_str}; ++{item.var_name}) {{")
                out.extend(emit_statements(
                    item.body, depth + 1, defer_scopes,
                    loop_scope_depth=len(defer_scopes), ret_type=ret_type,
                    shared_boxes=dict(shared_boxes),
                    shared_cleanups=list(local_shared_cleanups),
                    shared_owner_names=set(shared_owner_cleanup_names),
                    shared_local_types=dict(shared_local_types),
                    loop_shared_cleanup_entry_count=len(local_shared_cleanups),
                ))
                out.append(f"{pad}}}")
            elif isinstance(item, If):
                live_cleanups = {
                    d.auto_cleanup_name
                    for scope in defer_scopes for d in scope
                    if d.auto_cleanup_name is not None
                }
                out.append(
                    f"{pad}if ({_emit_expr(item.condition, prefix, shared_boxes)}) {{"
                )
                then_scopes = [scope.copy() for scope in defer_scopes]
                out.extend(emit_statements(
                    item.then_body, depth + 1, then_scopes, loop_scope_depth,
                    ret_type, shared_boxes=dict(shared_boxes),
                    shared_cleanups=list(local_shared_cleanups),
                    shared_owner_names=set(shared_owner_cleanup_names),
                    shared_local_types=dict(shared_local_types),
                    loop_shared_cleanup_entry_count=loop_shared_cleanup_entry_count,
                ))
                remaining = {
                    d.auto_cleanup_name
                    for scope in then_scopes for d in scope
                    if d.auto_cleanup_name is not None
                }
                if live_cleanups - remaining and not (
                    item.then_body and isinstance(item.then_body[-1], Return)
                ):
                    raise SotlasBootstrapError(
                        "C11 backend cannot conditionally transfer sole ownership "
                        "from an if branch that continues"
                    )
                out.append(f"{pad}}}")
                if item.else_body:
                    out.append(f"{pad}else {{")
                    else_scopes = [scope.copy() for scope in defer_scopes]
                    out.extend(emit_statements(
                        item.else_body, depth + 1, else_scopes, loop_scope_depth,
                        ret_type, shared_boxes=dict(shared_boxes),
                        shared_cleanups=list(local_shared_cleanups),
                        shared_owner_names=set(shared_owner_cleanup_names),
                        shared_local_types=dict(shared_local_types),
                        loop_shared_cleanup_entry_count=loop_shared_cleanup_entry_count,
                    ))
                    remaining = {
                        d.auto_cleanup_name
                        for scope in else_scopes for d in scope
                        if d.auto_cleanup_name is not None
                    }
                    if live_cleanups - remaining and not isinstance(item.else_body[-1], Return):
                        raise SotlasBootstrapError(
                            "C11 backend cannot conditionally transfer sole ownership "
                            "from an if branch that continues"
                        )
                    out.append(f"{pad}}}")
            elif isinstance(item, Discern):
                chosen = next(
                    (case for case in item.cases
                     if case.state_name == getattr(item, "state_name", None)),
                    None,
                )
                if chosen is None:
                    raise SotlasBootstrapError(
                        "C11 discern could not resolve its statically known state",
                        item.token.line, item.token.column,
                        module.filename, module.source,
                    )
                out.append(f"{pad}{{")
                out.extend(emit_statements(
                    chosen.body, depth + 1,
                    [scope.copy() for scope in defer_scopes],
                    loop_scope_depth, ret_type,
                    shared_boxes=dict(shared_boxes),
                    shared_cleanups=list(local_shared_cleanups),
                    shared_owner_names=set(shared_owner_cleanup_names),
                    shared_local_types=dict(shared_local_types),
                    loop_shared_cleanup_entry_count=loop_shared_cleanup_entry_count,
                ))
                out.append(f"{pad}}}")
        current_defers = defer_scopes.pop()
        if (
            shared_owner_cleanup_names - shared_names_at_entry
            and not _block_definitely_returns(items)
            and not share_sources_are_scope_local_or_shared
            and not (
                is_function_scope
                and ret_type is not None
                and ret_type.name in ("void", "Void")
            )
        ):
            raise SotlasBootstrapError(
                "C11 shared aliases require every path to return or explicitly "
                "transfer the owner; outer-scope shared owners cannot escape "
                "their lexical cleanup block",
                1, 1, module.filename, module.source,
            )
        if local_shared_cleanups and any(
            isinstance(item, Return) for item in items
        ):
            current_defers = [
                cleanup for cleanup in current_defers
                if not (
                    cleanup.auto_cleanup_name in shared_owner_cleanup_names
                    and isinstance(cleanup.value, Call)
                    and cleanup.value.callee.startswith("__sotlas_shared_release_")
                )
            ]
        for d in reversed(current_defers):
            if d.auto_cleanup_name in shared_owner_cleanup_names:
                continue
            if d.body is not None:
                out.extend(emit_statements(
                    d.body, depth, defer_scopes,
                    loop_scope_depth, ret_type,
                    shared_boxes=shared_boxes,
                ))
            else:
                out.append(_emit_defer_action(d, pad, shared_boxes))
        if not _block_definitely_returns(items):
            for box_name, shared_struct_name in reversed(
                local_shared_cleanups[shared_cleanup_entry_count:]
            ):
                out.append(
                    f"{pad}__sotlas_shared_release_{shared_struct_name}"
                    f"({box_name});"
                )
        return out


    for function in module.functions:
        if not function.body and "@extern(C)" in function.attributes:
            continue
        is_export = "@export" in function.attributes or function.public
        is_extern_c = "@extern(C)" in function.attributes
        fname = (
            function.name
            if (is_export or is_extern_c or not mangle)
            else f"{prefix}{function.name}"
        )
        parameters = ", ".join(f"{typ.c_decl(name)}" for name, typ in function.params) or "void"
        inline_attr = "static inline " if "@inline" in function.attributes and not is_export else ""
        extra_attrs = _c_func_attributes(function.attributes)
        lines.append(f"{inline_attr}{extra_attrs}{function.result.c()} {fname}({parameters}) {{")
        lines.extend(f"    (void){name};" for name, _ in function.params)
        lines.extend(
            emit_statements(
                function.body,
                1,
                defer_scopes=[],
                loop_scope_depth=None,
                ret_type=function.result,
                owned_params=function.params,
                shared_boxes={},
                is_function_scope=True,
            )
        )
        lines.append("}\n")
    return "\n".join(lines)


def _public_import_maps(imported_modules: list[Module] | None) -> tuple[dict, dict, dict, dict]:
    functions: dict[str, Function] = {}
    structs: dict[str, Struct] = {}
    enums: dict[str, Enum] = {}
    globals_: dict[str, Global] = {}
    for dependency in imported_modules or []:
        functions.update({fn.name: fn for fn in dependency.functions if fn.public})
        structs.update({item.name: item for item in dependency.structs if item.public})
        enums.update({item.name: item for item in dependency.enums if item.public})
        globals_.update({item.name: item for item in dependency.globals if item.public})
    return functions, structs, enums, globals_


def emit_header(module: Module) -> str:
    """Emite a ABI C pública de um módulo, derivada apenas do AST Sotlas."""
    module_id = _c_ident(module.name)
    guard = f"SOTLAS_GENERATED_{module_id.upper()}_H"
    lines = [
        "/* Interface gerada do AST Sotlas. Não edite. */",
        f"#ifndef {guard}",
        f"#define {guard}",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "#include <stdbool.h>",
    ]
    lines.extend(f'#include "{_c_ident(name)}.h"' for name in module.imports)

    for global_ in module.globals:
        if global_.public and global_.is_const and not global_.type.is_array:
            lines.append(f"#define {global_.name} (({global_.type.c()})({_emit_expr(global_.value)}))")

    for enum_obj in module.enums:
        if enum_obj.public:
            lines.extend(_emit_c_enum(enum_obj))

    for struct in module.structs:
        if struct.public:
            if getattr(struct, "is_register", False):
                lines.append(f"typedef union {struct.name} {struct.name};")
            else:
                lines.append(f"typedef struct {struct.name} {struct.name};")
    if any(struct.public for struct in module.structs):
        lines.append("")

    for struct in module.structs:
        if not struct.public:
            continue
        if getattr(struct, "is_register", False):
            backing_c = struct.backing_type.c() if struct.backing_type else "uint32_t"
            lines.append(f"typedef union {struct.name} {{")
            lines.append(f"    {backing_c} raw;")
            lines.append(f"    struct __attribute__((packed)) {{")
            for fld in struct.fields:
                bw = f" : {fld.bit_width}" if fld.bit_width else ""
                lines.append(f"        {backing_c} {fld.name}{bw};")
            lines.append(f"    }};")
            lines.append(f"}} {struct.name};")
        else:
            pack_attr = _c_struct_attributes(struct.attributes)
            lines.append(f"typedef struct{pack_attr} {struct.name} {{")
            lines.extend(f"    {field.type.c_decl(field.name)}{(' : ' + str(field.bit_width)) if getattr(field, 'bit_width', None) else ''};" for field in struct.fields)
            lines.append(f"}} {struct.name};")

    for function in module.functions:
        if not function.public and "@export" not in function.attributes:
            continue
        parameters = ", ".join(typ.c_decl(name) for name, typ in function.params) or "void"
        extra_attrs = _c_func_attributes(function.attributes)
        lines.append(f"{extra_attrs}{function.result.c()} {function.name}({parameters});")
    lines.extend(("", f"#endif /* {guard} */", ""))
    return "\n".join(lines)


def compile_module(module: Module, imported_modules: list[Module] | None = None,
                   include_import_headers: bool = False) -> str:
    imported = _public_import_maps(imported_modules)
    check(module, *imported)
    return emit_c(module, include_import_headers=include_import_headers)


def compile_source(source: str, filename: str | None = None,
                   imported_modules: list[Module] | None = None,
                   include_import_headers: bool = False) -> str:
    module = parse(source, filename=filename)
    if imported_modules is None and module.imports and filename:
        cur_file = Path(filename).resolve()
        search_dirs = [cur_file.parent]
        for p in cur_file.parents:
            search_dirs.extend([p, p / "src", p / "bootstrap" / "sotlas" / "native_compiler"])
        loaded_mods: list[Module] = []
        for imp in module.imports:
            mod_name = imp.split("::")[-1] if isinstance(imp, str) else imp[-1]
            for d in search_dirs:
                cand = d / f"{mod_name}.sotlas"
                if cand.is_file() and cand != cur_file:
                    try:
                        loaded_mods.append(parse(cand.read_text(encoding="utf-8"), filename=str(cand)))
                    except Exception:
                        pass
                    break
        imported_modules = loaded_mods
    return compile_module(module, imported_modules, include_import_headers)


def compile_file(source: Path, output: Path) -> None:
    text = source.read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(compile_source(text, filename=str(source)), encoding="utf-8")


def compile_project(entry: Path) -> list[Module]:
    root = entry.parent
    while root.parent != root and not (root / "core").is_dir():
        root = root.parent
    if not (root / "core").is_dir():
        raise SotlasBootstrapError(f"raiz do projeto contendo 'core/' não encontrada a partir de {entry}", 1, 1)
    units: dict[str, Module] = {}
    for path in list(root.rglob("*.sotlas")) + list(root.rglob("*.sth")) + list(root.rglob("*.st")):
        if "tests" in path.parts or "fixtures" in path.parts or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            unit = parse(text, filename=str(path))
            if unit.name in units and units[unit.name].filename != str(path):
                raise SotlasBootstrapError(f"módulo duplicado: {unit.name}", 1, 1, str(path), text)
            units[unit.name] = unit
        except SotlasBootstrapError as e:
            if "módulo duplicado" in e.message:
                raise
            continue
        except Exception:
            continue

    start_text = entry.read_text(encoding="utf-8")
    start = parse(start_text, filename=str(entry)).name
    order: list[Module] = []; visiting: list[str] = []; visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise SotlasBootstrapError("import circular: " + " -> ".join(visiting + [name]), 1, 1)
        if name in visited: return
        unit = units.get(name)
        if not unit:
            raise SotlasBootstrapError(f"import não resolvido: {name}", 1, 1)
        visiting.append(name)
        for dependency in unit.imports:
            visit(dependency)
        visiting.pop(); visited.add(name)
        imported_fns: dict[str, Function] = {}
        imported_types: dict[str, Struct] = {}
        imported_enums: dict[str, Enum] = {}
        imported_globals: dict[str, Global] = {}
        for dependency in unit.imports:
            dep = units[dependency]
            imported_fns.update({fn.name: fn for fn in dep.functions if fn.public})
            imported_types.update({s.name: s for s in dep.structs if s.public})
            imported_enums.update({e.name: e for e in dep.enums if e.public})
            imported_globals.update({g.name: g for g in dep.globals if g.public})
        check(unit, imported_fns, imported_types, imported_enums, imported_globals)
        order.append(unit)

    visit(start)
    return order


def emit_c_project(entry: Path, output: Path) -> None:
    modules = compile_project(entry)
    preamble = PREAMBLE
    if any(module.name == "core::arc" for module in modules):
        if "SOTLAS_ATOMIC_INTRINSICS" not in preamble:
            preamble = preamble.rstrip() + "\n" + _ARC_ATOMIC_INTRINSICS + "\n"
    fragments = [preamble]
    for module in modules:
        fragments.append(emit_c(module, mangle=False, include_preamble=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(fragments), encoding="utf-8")
