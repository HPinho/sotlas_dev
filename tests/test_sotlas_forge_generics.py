"""Testes unitários para Generics Monomorfizados com forge<T> em Sotlas.

Cobertura:
- Struct genérico simples (forge<T>)
- Monomorphization com múltiplos tipos concretos
- Funções standalone genéricas
- Bounds de spec em parâmetros genéricos (forge<T: SomeSpec>)
- Violação de bounds detectada pelo sema
- Const-generics (forge<const N: USize>)
- Combinação de múltiplos parâmetros genéricos
- Métodos genéricos dentro de struct genérico
- Generics com tipos de ownership (sole, whisper)
"""
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC


def _pipeline(src: str):
    tokens = Lexer(src, "<test>").tokenize()
    ast = Parser(tokens, "<test>").parse()
    Sema(ast, "<test>", src).check()
    return ast


def _compile(src: str) -> str:
    ast = _pipeline(src)
    return CodegenC(ast).emit()


def _check_raises(src: str, fragment: str):
    tokens = Lexer(src, "<test>").tokenize()
    ast = Parser(tokens, "<test>").parse()
    with unittest.TestCase().assertRaisesRegex(SotlasSemaError, fragment):
        Sema(ast, "<test>", src).check()


class TestForgeStructBasic(unittest.TestCase):
    """Testes básicos de struct genérico."""

    def test_generic_struct_declaration_parses(self):
        src = """\
module test::generics;

pub struct Container forge<T> {
    pub item: T;

    pub fn new(val: T) -> Container forge<T> {
        return Container { item: val };
    }
}
"""
        ast = _pipeline(src)
        self.assertEqual(len(ast.decls), 1)
        struct_decl = ast.decls[0]
        self.assertEqual(struct_decl.name, "Container")
        self.assertEqual(struct_decl.generics, ["T"])

    def test_generic_struct_emits_c(self):
        src = """\
module test::generics;

pub struct Container forge<T> {
    pub item: T;
}
"""
        c_code = _compile(src)
        self.assertIn("struct Container", c_code)

    def test_generic_struct_two_params(self):
        src = """\
module test::pair;

pub struct Pair forge<A, B> {
    pub first: A;
    pub second: B;
}
"""
        c_code = _compile(src)
        self.assertIn("struct Pair", c_code)

    def test_monomorphization_two_concrete_types(self):
        src = """\
module test::monomorph;

pub struct Pair forge<A, B> {
    pub first: A;
    pub second: B;
}

pub fn make_pair() -> Pair forge<UInt32, Int64> {
    return Pair { first: 10, second: 20 };
}
"""
        c_code = _compile(src)
        # Codegen deve emitir versão monomorfizada
        self.assertIn("Pair", c_code)
        self.assertIn("uint32_t", c_code)
        self.assertIn("int64_t", c_code)


class TestForgeGenericFunctions(unittest.TestCase):
    """Testes de funções standalone genéricas."""

    def test_generic_fn_single_param(self):
        src = """\
module test::genfn;

pub fn identity forge<T>(val: T) -> T {
    return val;
}
"""
        ast = _pipeline(src)
        fn_decl = ast.decls[0]
        self.assertEqual(fn_decl.name, "identity")
        self.assertTrue(len(getattr(fn_decl, "generics", [])) > 0)

    def test_generic_fn_two_params(self):
        src = """\
module test::genfn2;

pub fn swap forge<A, B>(a: A, b: B) -> A {
    return a;
}
"""
        _pipeline(src)  # não deve levantar

    def test_generic_fn_with_generic_return(self):
        src = """\
module test::genfn3;

pub struct Box forge<T> {
    pub value: T;
}

pub fn wrap forge<T>(val: T) -> Box forge<T> {
    return Box { value: val };
}
"""
        _pipeline(src)  # não deve levantar


class TestForgeSpecBounds(unittest.TestCase):
    """Testes de bounds de spec em parâmetros genéricos."""

    def test_bound_resolved_correctly(self):
        src = """\
module test::bounds;

spec Printable {
    fn print() -> Void;
}

struct Label adopts Printable {
    pub text: UInt8;
    fn print() -> Void { return; }
}

pub fn print_it forge<T: Printable>(val: T) -> Void {
    return;
}
"""
        _pipeline(src)  # não deve levantar

    def test_struct_generic_with_bound(self):
        src = """\
module test::structbound;

spec Comparable {
    fn compare(other: Self) -> Int32;
}

pub struct SortedPair forge<T: Comparable> {
    pub lo: T;
    pub hi: T;
}
"""
        _pipeline(src)  # bound verificado — não deve levantar

    def test_bound_violation_raises(self):
        """Tipo concreto que não adota o spec exigido deve causar erro."""
        src = """\
module test::boundviol;

spec Hashable {
    fn hash() -> UInt64;
}

pub struct HashMap forge<K: Hashable, V> {
    pub dummy: UInt32;
}

struct RawKey {
    pub id: UInt32;
}

pub fn make_map() -> HashMap forge<RawKey, UInt8> {
    return HashMap { dummy: 0 };
}
"""
        _check_raises(src, "não satisfaz o bound")

    def test_undeclared_bound_raises(self):
        """Spec bound inexistente deve causar erro semântico."""
        src = """\
module test::undeclbound;

pub fn do_it forge<T: NonExistentSpec>(val: T) -> Void {
    return;
}
"""
        _check_raises(src, "não declarado")


class TestForgeConstGenerics(unittest.TestCase):
    """Testes de const-generics (forge<const N: USize>)."""

    def test_const_generic_in_struct(self):
        src = """\
module test::constgen;

pub struct FixedArray forge<T, const N: USize> {
    pub data: [T; N];
}
"""
        _pipeline(src)  # não deve levantar

    def test_const_generic_fn(self):
        src = """\
module test::constgenfn;

pub fn zero_fill forge<const N: USize>(val: UInt8) -> Void {
    return;
}
"""
        _pipeline(src)


class TestForgeWithOwnership(unittest.TestCase):
    """Testes de generics interagindo com o sistema de ownership."""

    def test_generic_struct_with_sole_field(self):
        src = """\
module test::gensole;

pub struct UniqueBox forge<T> {
    pub inner: sole T;
}
"""
        _pipeline(src)  # não deve levantar

    def test_generic_fn_whisper_param(self):
        src = """\
module test::genwhisper;

pub struct Node forge<T> {
    pub value: T;
}

pub fn peek forge<T>(n: whisper Node forge<T>) -> Void {
    return;
}
"""
        _pipeline(src)

    def test_generic_struct_in_barecore(self):
        src = """\
barecore;
module hal::genbuf;

pub struct Buffer forge<const N: USize> {
    pub data: [UInt8; N];
}
"""
        _pipeline(src)  # buffers de tamanho fixo são ok em barecore


class TestForgeCodegenMonomorphization(unittest.TestCase):
    """Testes de emissão C correta para múltiplos tipos monomorfizados."""

    def test_pair_uint32_int64_monomorphized(self):
        src = """\
module test::monomorph;

pub struct Pair forge<A, B> {
    pub first: A;
    pub second: B;
}

pub fn make_pair() -> Pair forge<UInt32, Int64> {
    return Pair { first: 10, second: 20 };
}
"""
        c_code = _compile(src)
        self.assertIn("Pair", c_code)

    def test_box_with_concrete_type_emits(self):
        src = """\
module test::boxed;

pub struct Box forge<T> {
    pub value: T;
}

pub fn make_int_box() -> Box forge<Int32> {
    return Box { value: 42 };
}
"""
        c_code = _compile(src)
        self.assertIn("Box", c_code)
        self.assertIn("int32_t", c_code)

    def test_generic_struct_codegen_has_no_syntax_errors(self):
        """O C gerado não deve conter erros óbvios de sintaxe."""
        src = """\
module test::syntax;

pub struct Wrapper forge<T> {
    pub data: T;
    pub len: UInt32;
}
"""
        c_code = _compile(src)
        self.assertIn("struct Wrapper", c_code)
        # Verificações básicas de estrutura C válida
        self.assertIn("{", c_code)
        self.assertIn("}", c_code)
        self.assertNotIn("forge<", c_code)  # forge<T> não deve vazar para o C


if __name__ == "__main__":
    unittest.main()
