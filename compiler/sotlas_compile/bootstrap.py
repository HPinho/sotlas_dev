"""Frontend Sotlas Bootstrap: lexer, parser recursivo, tipagem, verificação unsafe e emissor C11.

Este módulo define o contrato executável do subconjunto procedural da linguagem Sotlas:
módulos, structs com atributos, enums, globais/constantes, funções, tipos fixos,
arrays fixos [T; N], ponteiros unsafe, casts ('as'), expressões, fluxo e mangling.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import re


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
            "unsafe", "true", "false", "as", "null", "defer", "loop", "register", "sole", "move", "handover", "impl"}
MULTI = ("::", "->", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "&=", "|=", "^=", "<<=", ">>=", "&&", "||", "<<", ">>", "..")
SINGLE = set(";,:{}()[]=+-*/%!<>&|^~.?")
PRIMITIVES = {"void", "bool", "u8", "u16", "u32", "u64", "usize",
              "i8", "i16", "i32", "i64", "isize", "f32", "f64", "str"}
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
class Loop(Stmt): body: list[Stmt]
@dataclass
class If(Stmt): condition: Expr; then_body: list[Stmt]; else_body: list[Stmt]
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
        if self.accept("!"):
            return Type("void")
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
            return Type(name=elem_type.name, pointer=elem_type.pointer, mutable=elem_type.mutable, is_array=True, array_size=size, elem_type=elem_type)
        if self.accept("&"):
            is_mut = bool(self.accept("mut"))
            inner = self.type()
            return Type(name=inner.name, pointer=True, mutable=is_mut, is_array=inner.is_array, array_size=inner.array_size, elem_type=inner.elem_type, is_reference=True)
        pointer = False; mutable = False
        if self.accept("*"):
            pointer = True
            if self.accept("mut"): mutable = True
            elif self.accept("const"): mutable = False
            elif self.current.kind == "IDENT" and self.current.text in ("const", "mut"):
                mutable = (self.current.text == "mut")
                self.at += 1
            inner = self.type()
            return Type(name=inner.name, pointer=True, mutable=mutable, is_array=inner.is_array, array_size=inner.array_size, elem_type=inner.elem_type)
        base_name = self.ident()
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
                    if self.accept("="):
                        val_tok = self.expect("NUMBER")
                        vval = integer_literal_value(val_tok.text)
                    variants.append(EnumVariant(vname, vval))
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
        return Function(name, params, result, self.block(), public, attributes or [])

    def block(self) -> list[Stmt]:
        self.expect("{"); body = []
        while not self.accept("}"): body.append(self.statement())
        return body

    def statement(self) -> Stmt:
        token = self.current
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
        if self.current.kind in ("!", "-", "*", "&", "~"):
            op = self.current.kind
            self.at += 1
            is_mut = bool(self.accept("mut")) if op == "&" else False
            return Unary(token, op, self.prefix(), mutable=is_mut)
        return self.primary()


def parse(source: str, filename: str | None = None) -> Module:
    return Parser(lex(source, filename), filename=filename, source=source).parse()


def same_type(left: Type, right: Type) -> bool:
    return (
        left.name == right.name
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

    global_map: dict[str, Global] = {g.name: g for g in module.globals}
    if imported_globals: global_map.update(imported_globals)

    functions = dict(BUILTIN_FUNCTIONS)
    user_funcs = {item.name: item for item in module.functions}
    functions.update(user_funcs)
    if imported_fns: functions.update(imported_fns)

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
            raise SotlasBootstrapError(
                f"símbolo não declarado: {expr.value}", expr.token.line,
                expr.token.column, filename, source,
            )
        if isinstance(expr, EnumAccess):
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
                return Type(inner.name, pointer=False, mutable=inner.mutable)
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
            argument_types = [
                expr_type(argument, scope, in_unsafe, is_system_fn)
                for argument in expr.args
            ]
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
        is_system = "@system" in function.attributes or "@inline" in function.attributes
        statements(function.body, dict(function.params), function.result, in_unsafe=False, is_system_fn=is_system)


def _c_ident(name: str) -> str:
    return name.replace("::", "__").replace("-", "_")


def _emit_expr(expr: Expr, mod_prefix: str = "") -> str:
    if isinstance(expr, UnsafeExpr):
        return _emit_expr(expr.value, mod_prefix)
    if isinstance(expr, MoveExpr):
        return _emit_expr(expr.value, mod_prefix)
    if isinstance(expr, Number):
        base, suffix = numeric_literal_parts(expr.value)
        return f"(({C_TYPES[suffix]})({base}))" if suffix else base
    if isinstance(expr, Boolean): return "1" if expr.value else "0"
    if isinstance(expr, StringLit): return f"((const uint8_t *){expr.value})"
    if isinstance(expr, CharLit): return expr.value
    if isinstance(expr, NullLit): return "NULL"
    if isinstance(expr, Name): return expr.value
    if isinstance(expr, EnumAccess): return f"{expr.enum_name}_{expr.variant}"
    if isinstance(expr, Unary):
        if expr.op == "&":
            return f"(&{_emit_expr(expr.value, mod_prefix)})"
        return f"({expr.op}{_emit_expr(expr.value, mod_prefix)})"
    if isinstance(expr, Binary): return f"({_emit_expr(expr.left, mod_prefix)} {expr.op} {_emit_expr(expr.right, mod_prefix)})"
    if isinstance(expr, Call):
        callee = expr.callee
        return f"{callee}(" + ", ".join(_emit_expr(item, mod_prefix) for item in expr.args) + ")"
    if isinstance(expr, MethodCall):
        if getattr(expr, "is_vtable_call", False):
            target_str = _emit_expr(expr.target, mod_prefix)
            arrow = "->" if getattr(expr, "is_arrow", False) else "."
            callee = f"{target_str}{arrow}{expr.method}"
            args_s = ", ".join(_emit_expr(item, mod_prefix) for item in expr.args)
            return f"({callee})({args_s})"
        if expr.method == "as_ptr":
            return _emit_expr(expr.target, mod_prefix)
        if expr.method == "abs":
            target_str = _emit_expr(expr.target, mod_prefix)
            return f"((int32_t)({target_str}) < 0 ? -(int32_t)({target_str}) : (int32_t)({target_str}))"
        if expr.method == "add":
            target_str = _emit_expr(expr.target, mod_prefix)
            arg_str = _emit_expr(expr.args[0], mod_prefix) if expr.args else "0"
            return f"(({target_str}) + ({arg_str}))"
        target_str = _emit_expr(expr.target, mod_prefix)
        if getattr(expr, "pass_by_ref", False):
            target_str = f"&({target_str})"
        fn_name = f"{expr.target_type.name}_{expr.method}" if expr.target_type else expr.method
        all_args = [target_str] + [_emit_expr(item, mod_prefix) for item in expr.args]
        return f"{fn_name}(" + ", ".join(all_args) + ")"
    if isinstance(expr, Index):
        return f"{_emit_expr(expr.target, mod_prefix)}[{_emit_expr(expr.index, mod_prefix)}]"
    if isinstance(expr, Member):
        arrow = "->" if getattr(expr, "is_pointer_target", False) else "."
        return f"{_emit_expr(expr.target, mod_prefix)}{arrow}{expr.field}"
    if isinstance(expr, Cast):
        return f"(({expr.target_type.c()})({_emit_expr(expr.expr, mod_prefix)}))"
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


def emit_c(module: Module, mangle: bool = False, include_preamble: bool = True,
           include_import_headers: bool = False) -> str:
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
        lines.append(f"typedef enum {enum_obj.name} {{")
        for v in enum_obj.variants:
            val_str = f" = {v.value}" if v.value is not None else ""
            lines.append(f"    {enum_obj.name}_{v.name}{val_str},")
        lines.append(f"}} {enum_obj.name};\n")

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
        fname = function.name if (is_export or not mangle) else f"{prefix}{function.name}"
        parameters = ", ".join(f"{typ.c_decl(name)}" for name, typ in function.params) or "void"
        inline_attr = "static inline " if "@inline" in function.attributes and not is_export else ""
        extra_attrs = _c_func_attributes(function.attributes)
        lines.append(f"{inline_attr}{extra_attrs}{function.result.c()} {fname}({parameters});")
    if module.functions:
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

    def _emit_defer_action(d: Defer, pad: str) -> str:
        if isinstance(d.value, Assign):
            target_str = _emit_expr(d.value.target, prefix) if isinstance(d.value.target, Expr) else str(d.value.target)
            return f"{pad}{target_str} = {_emit_expr(d.value.value, prefix)};"
        return f"{pad}{_emit_expr(d.value, prefix)};"

    def emit_statements(
        items: list[Stmt],
        depth: int,
        defer_scopes: list[list[Defer]],
        loop_scope_depth: int | None = None,
        ret_type: Type | None = None,
    ) -> list[str]:
        pad = "    " * depth; out: list[str] = []
        defer_scopes.append([])
        deinit_methods: dict[str, bool] = {}
        for fn in module.functions:
            if fn.name.endswith("_deinit") and len(fn.params) >= 1 and fn.params[0][0] == "self":
                sname = fn.name.rsplit("_deinit", 1)[0]
                deinit_methods[sname] = fn.params[0][1].pointer

        for item in items:
            if isinstance(item, Let):
                if item.type is not None:
                    typ = item.type
                    if (typ.is_array or typ.name not in PRIMITIVES) and not typ.pointer and isinstance(item.value, Number) and item.value.value == "0":
                        out.append(f"{pad}{typ.c_decl(item.name)} = {{0}};")
                    elif typ.is_array:
                        decl = typ.c_decl(item.name)
                        prefix_spec = "static " if decl.startswith("const ") else "static const "
                        out.append(f"{pad}{prefix_spec}{decl} = {_emit_expr(item.value, prefix)};")
                    else:
                        out.append(f"{pad}{typ.c_decl(item.name)} = {_emit_expr(item.value, prefix)};")
                    if typ.name in deinit_methods and not typ.pointer:
                        takes_ptr = deinit_methods[typ.name]
                        arg_node = Unary(item.token, "&", Name(item.token, item.name)) if takes_ptr else Name(item.token, item.name)
                        call_expr = Call(item.token, f"{typ.name}_deinit", [arg_node])
                        defer_scopes[-1].append(Defer(item.token, value=call_expr))
                else:
                    if isinstance(item.value, ArrayLit) and not item.value.is_repeat:
                        first_e = item.value.elements[0] if item.value.elements else None
                        if first_e and isinstance(first_e, Number):
                            out.append(f"{pad}uint32_t {item.name}[] = {_emit_expr(item.value, prefix)};")
                        else:
                            out.append(f"{pad}const uint8_t *{item.name}[] = {_emit_expr(item.value, prefix)};")
                    else:
                        out.append(f"{pad}__auto_type {item.name} = {_emit_expr(item.value, prefix)};")
            elif isinstance(item, Assign):
                target_str = _emit_expr(item.target, prefix) if isinstance(item.target, Expr) else str(item.target)
                if (isinstance(item.value, ArrayLit) and item.value.is_repeat and
                        isinstance(item.value.elements[0], Number) and item.value.elements[0].value == "0"):
                    out.append(f"{pad}__builtin_memset(&({target_str}), 0, sizeof({target_str}));")
                else:
                    out.append(f"{pad}{target_str} = {_emit_expr(item.value, prefix)};")
            elif isinstance(item, Defer):
                defer_scopes[-1].append(item)
            elif isinstance(item, Return):
                all_defers = [d for scope in reversed(defer_scopes) for d in reversed(scope)]
                if item.value:
                    val_str = _emit_expr(item.value, prefix)
                    if all_defers:
                        c_ret_type = ret_type.c() if ret_type else "int64_t"
                        out.append(f"{pad}{c_ret_type} _st_ret = {val_str};")
                        for d in all_defers:
                            if d.body is not None:
                                out.extend(emit_statements(d.body, depth, defer_scopes, loop_scope_depth, ret_type))
                            else:
                                out.append(_emit_defer_action(d, pad))
                        out.append(f"{pad}return _st_ret;")
                    else:
                        out.append(f"{pad}return {val_str};")
                else:
                    for d in all_defers:
                        if d.body is not None:
                            out.extend(emit_statements(d.body, depth, defer_scopes, loop_scope_depth, ret_type))
                        else:
                            out.append(_emit_defer_action(d, pad))
                    out.append(f"{pad}return;")
            elif isinstance(item, Break):
                if loop_scope_depth is not None:
                    loop_defers = [d for scope in reversed(defer_scopes[loop_scope_depth:]) for d in reversed(scope)]
                    for d in loop_defers:
                        if d.body is not None:
                            out.extend(emit_statements(d.body, depth, defer_scopes, loop_scope_depth, ret_type))
                        else:
                            out.append(_emit_defer_action(d, pad))
                out.append(f"{pad}break;")
            elif isinstance(item, Continue):
                if loop_scope_depth is not None:
                    loop_defers = [d for scope in reversed(defer_scopes[loop_scope_depth:]) for d in reversed(scope)]
                    for d in loop_defers:
                        if d.body is not None:
                            out.extend(emit_statements(d.body, depth, defer_scopes, loop_scope_depth, ret_type))
                        else:
                            out.append(_emit_defer_action(d, pad))
                out.append(f"{pad}continue;")
            elif isinstance(item, Expression):
                out.append(f"{pad}{_emit_expr(item.value, prefix)};")
            elif isinstance(item, Asm):
                parts = [item.code]
                if item.outputs or item.inputs or item.clobbers:
                    out_s = ", ".join(_emit_expr(e, prefix) for e in item.outputs)
                    in_s = ", ".join(_emit_expr(e, prefix) for e in item.inputs)
                    clob_s = ", ".join(item.clobbers)
                    parts.append(f": {out_s} : {in_s} : {clob_s}")
                out.append(f"{pad}__asm__ volatile({ ' '.join(parts) });")
            elif isinstance(item, Unsafe):
                out.extend(emit_statements(item.body, depth, defer_scopes, loop_scope_depth, ret_type))
            elif isinstance(item, While):
                out.append(f"{pad}while ({_emit_expr(item.condition, prefix)}) {{")
                out.extend(emit_statements(item.body, depth + 1, defer_scopes, loop_scope_depth=len(defer_scopes), ret_type=ret_type))
                out.append(f"{pad}}}")
            elif isinstance(item, Loop):
                out.append(f"{pad}for (;;) {{")
                out.extend(emit_statements(item.body, depth + 1, defer_scopes, loop_scope_depth=len(defer_scopes), ret_type=ret_type))
                out.append(f"{pad}}}")
            elif isinstance(item, For):
                start_str = _emit_expr(item.start, prefix)
                end_str = _emit_expr(item.end, prefix)
                out.append(f"{pad}for (size_t {item.var_name} = {start_str}; {item.var_name} < {end_str}; ++{item.var_name}) {{")
                out.extend(emit_statements(item.body, depth + 1, defer_scopes, loop_scope_depth=len(defer_scopes), ret_type=ret_type))
                out.append(f"{pad}}}")
            elif isinstance(item, If):
                out.append(f"{pad}if ({_emit_expr(item.condition, prefix)}) {{")
                out.extend(emit_statements(item.then_body, depth + 1, defer_scopes, loop_scope_depth, ret_type))
                out.append(f"{pad}}}")
                if item.else_body:
                    out.append(f"{pad}else {{")
                    out.extend(emit_statements(item.else_body, depth + 1, defer_scopes, loop_scope_depth, ret_type))
                    out.append(f"{pad}}}")
        current_defers = defer_scopes.pop()
        for d in reversed(current_defers):
            if d.body is not None:
                out.extend(emit_statements(d.body, depth, defer_scopes, loop_scope_depth, ret_type))
            else:
                out.append(_emit_defer_action(d, pad))
        return out


    for function in module.functions:
        is_export = "@export" in function.attributes or function.public
        fname = function.name if (is_export or not mangle) else f"{prefix}{function.name}"
        parameters = ", ".join(f"{typ.c_decl(name)}" for name, typ in function.params) or "void"
        inline_attr = "static inline " if "@inline" in function.attributes and not is_export else ""
        extra_attrs = _c_func_attributes(function.attributes)
        lines.append(f"{inline_attr}{extra_attrs}{function.result.c()} {fname}({parameters}) {{")
        lines.extend(emit_statements(function.body, 1, defer_scopes=[], loop_scope_depth=None, ret_type=function.result))
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
        if not enum_obj.public:
            continue
        lines.append(f"typedef enum {enum_obj.name} {{")
        for variant in enum_obj.variants:
            value = f" = {variant.value}" if variant.value is not None else ""
            lines.append(f"    {enum_obj.name}_{variant.name}{value},")
        lines.append(f"}} {enum_obj.name};")

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
    fragments = [PREAMBLE]
    for module in modules:
        fragments.append(emit_c(module, mangle=False, include_preamble=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(fragments), encoding="utf-8")