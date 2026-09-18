"""Testes unitários para o operador de propagação de erros (?) desaçucarado em Sotlas."""
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


class TestSotlasTryOperator(unittest.TestCase):
    def test_try_operator_parsing_and_codegen(self):
        source = """module test::try_operator;

pub struct Device {
    base_addr: u64;
}

pub struct DriverError {
    code: i32;
}

pub fn ler_pci_bar(id: u32, bar_idx: u32) -> u64 {
    return 0xF0000000;
}

pub fn carregar_driver(pci_id: u32) -> u64 {
    let bar0 = ler_pci_bar(pci_id, 0)?;
    return bar0;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn("carregar_driver", c_code)
        self.assertIn("_res", c_code)
        self.assertIn("if (_res.status != 0) return _res;", c_code)


if __name__ == "__main__":
    unittest.main()
