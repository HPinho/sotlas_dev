"""Testes unitários para verificação de regiões de memória e tempos de vida (lifetimes de pilha) em Sotlas."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError


class TestSotlasStackLifetimes(unittest.TestCase):
    def test_direct_local_reference_escape_rejected(self):
        source = """module test::stack_escape_direct;

pub fn criar_ponteiro_invalido() -> &u32 {
    let valor: u32 = 42;
    return &valor;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("variável local de pilha", str(ctx.exception).lower())
        self.assertIn("não pode escapar", str(ctx.exception).lower())

    def test_indirect_local_reference_escape_rejected(self):
        source = """module test::stack_escape_indirect;

pub fn criar_ponteiro_indireto() -> &u32 {
    let valor: u32 = 100;
    let p = &valor;
    return p;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("variável local de pilha", str(ctx.exception).lower())

    def test_global_reference_return_allowed(self):
        source = """module test::global_reference_allowed;

static GLOBAL_CONFIG: u32 = 999;

pub fn obter_config() -> &u32 {
    return &GLOBAL_CONFIG;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()  # Não deve lançar erro!


if __name__ == "__main__":
    unittest.main()
