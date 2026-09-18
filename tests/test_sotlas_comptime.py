"""Testes unitários para a avaliação em tempo de compilação (comptime) de Sotlas."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC


class TestSotlasComptime(unittest.TestCase):
    def test_comptime_arithmetic_constant_folding(self):
        source = """module test::comptime_math;

pub fn main() -> i64 {
    let x: i64 = comptime (1024 * 1024 / 2);
    return x;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        # O valor 524288 deve ser dobrado em tempo de compilação
        self.assertIn("524288", c_code)

    def test_comptime_bitwise_constant_folding(self):
        source = """module test::comptime_bitwise;

pub fn main() -> u64 {
    let mask: u64 = comptime ((1 << 8) | 0x0F);
    return mask;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        # (256 | 15) = 271
        self.assertIn("271", c_code)

    def test_comptime_block_statement(self):
        source = """module test::comptime_block;

pub fn main() -> i32 {
    comptime {
        let a = 10;
        let b = 20;
    }
    return 0;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn("return 0", c_code)

    def test_comptime_rejects_runtime_dynamic_variables(self):
        source = """module test::comptime_invalid;

pub fn compute(dynamic_val: i32) -> i32 {
    let c = comptime (dynamic_val * 2);
    return c;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("comptime", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
