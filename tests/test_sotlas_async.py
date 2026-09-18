"""Testes unitários para funções assíncronas (async fn) e suspensão (await) sem heap em Sotlas."""
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


class TestSotlasAsync(unittest.TestCase):
    def test_async_fn_and_await_compiles(self):
        source = """module test::async_coroutine;

pub async fn fetch_hardware_data() -> u32 {
    return 42;
}

pub async fn process_pipeline() -> u32 {
    let val: u32 = await fetch_hardware_data();
    return val;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn("fetch_hardware_data", c_code)
        self.assertIn("process_pipeline", c_code)
        self.assertIn("/* await */", c_code)

    def test_await_rejected_in_synchronous_fn(self):
        source = """module test::await_sync_rejected;

pub fn sync_caller() -> u32 {
    let val = await 10;
    return val;
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("await", str(ctx.exception).lower())

    def test_await_rejected_inside_clinch(self):
        source = """module test::await_clinch_rejected;

pub async fn critical_hazard() {
    unsafe {
        clinch {
            await 10;
        } revert {
            rebound;
        }
    }
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("clinch", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
