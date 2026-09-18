"""Testes unitários para ergonomia de padrões (if let e while let) em Sotlas."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema
from sotlas.codegen_c import CodegenC


class TestSotlasIfLetWhileLet(unittest.TestCase):
    def test_if_let_enum_pattern_compiles(self):
        source = """module test::if_let_pattern;

pub enum Option {
    None,
    Some(u32),
}

pub fn process_packet(packet: u32) -> u32 {
    return packet + 1;
}

pub fn handle_queue(opt: Option) -> u32 {
    if let Option::Some(packet) = opt {
        return process_packet(packet);
    } else {
        return 0;
    }
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn("handle_queue", c_code)
        self.assertIn("_let_val", c_code)
        self.assertIn("packet", c_code)
        self.assertIn("process_packet(packet)", c_code)

    def test_while_let_pattern_compiles(self):
        source = """module test::while_let_pattern;

pub enum Option {
    None,
    Some(u32),
}

pub fn consume_queue(opt: Option) -> u32 {
    let mut total: u32 = 0;
    while let Option::Some(item) = opt {
        total = total + item;
        break;
    }
    return total;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn("consume_queue", c_code)
        self.assertIn("while (1)", c_code)
        self.assertIn("item", c_code)


if __name__ == "__main__":
    unittest.main()
