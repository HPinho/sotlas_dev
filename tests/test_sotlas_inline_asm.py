"""Testes unitários para a funcionalidade de assembly inline estruturado (asm volatile) em Sotlas."""
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


class TestSotlasInlineAsm(unittest.TestCase):
    def test_asm_volatile_inside_unsafe_block(self):
        source = """module test::inline_asm_unsafe;

pub fn disable_interrupts() {
    unsafe {
        asm volatile ("cli");
    }
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn('__asm__ volatile("cli")', c_code)

    def test_asm_volatile_inside_system_fn(self):
        source = """module test::inline_asm_system;

@system pub fn halt_cpu() {
    asm volatile ("hlt");
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn('__asm__ volatile("hlt")', c_code)

    def test_asm_with_inputs_and_clobbers(self):
        source = """module test::inline_asm_operands;

unsafe pub fn write_port(port: u16, val: u8) {
    asm volatile ("outb %0, %1" : : "a"(val), "Nd"(port) : "memory");
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        sema.check()

        c_code = CodegenC(ast).emit()
        self.assertIn('__asm__ volatile("outb %0, %1"', c_code)
        self.assertIn('"memory"', c_code)

    def test_asm_rejected_outside_unsafe_or_system(self):
        source = """module test::inline_asm_rejected;

pub fn safe_fn() {
    asm volatile ("cli");
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("assembly inline", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
