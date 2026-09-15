"""Testes unitários para as novas capacidades do Sotlas 0.4.5:
- Hardware Typestate para drivers (verificação de transição de estado em compile-time)
- Const Generics (forge<T, const N: usize>) e type checking de dimensões
- Comptime mould & static probe assertions
- Confinamento estrito de island
- DMA barriers e fences
- Sincronização de versão 0.4.5
"""
import json
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "compiler"))

import sotlas
from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC
from sotlas.ast_nodes import GenericParam


class TestSotlasFeatures045(unittest.TestCase):
    def _compile_ast(self, source: str, filename: str = "<test>"):
        tokens = Lexer(source, filename).tokenize()
        ast = Parser(tokens, filename).parse()
        sema = Sema(ast, filename, source)
        sema.check()
        return ast

    def test_version_045_synchronization(self):
        """Valida que todos os metadados de versão estão em 0.4.5."""
        self.assertEqual(sotlas.SOTLAS_VERSION, "0.4.5")
        self.assertEqual(sotlas.SOTLAS_LANG_VERSION, "0.4.5")
        self.assertEqual(sotlas.__version__, "0.4.5")

        lockfile = _ROOT / "toolchain" / "sotlas.lock.json"
        data = json.loads(lockfile.read_text(encoding="utf-8"))
        self.assertEqual(data["language_version"], "0.4.5")

    def test_hardware_typestate_valid_flow(self):
        """Fluxo correto de transição de typestate Detached -> Attached -> Active."""
        source = """\
module test::typestate_valid;

pub struct Detached {}
pub struct Attached {}
pub struct Active {}

pub struct Device forge<S> {
    pub id: u32;
}

pub fn attach(dev: Device<Detached>) -> Device<Attached> {
    return Device<Attached> { id: dev.id };
}

pub fn activate(dev: Device<Attached>) -> Device<Active> {
    return Device<Active> { id: dev.id };
}

pub fn transmit(dev: whisper Device<Active>, data: u32) {
}

pub fn run_driver() {
    let d1: Device<Detached> = Device<Detached> { id: 1 };
    let d2: Device<Attached> = attach(d1);
    let d3: Device<Active> = activate(d2);
    transmit(whisper d3, 42);
}
"""
        ast = self._compile_ast(source)
        c_code = CodegenC(ast).emit()
        self.assertIn("Device_Active", c_code)
        self.assertIn("Device_Attached", c_code)
        self.assertIn("Device_Detached", c_code)

    def test_hardware_typestate_mismatch_rejected(self):
        """Tentativa de chamar transmit(whisper d1) onde d1 é Device<Detached> deve ser rejeitada."""
        source = """\
module test::typestate_invalid;

pub struct Detached {}
pub struct Active {}

pub struct Device forge<S> {
    pub id: u32;
}

pub fn transmit(dev: whisper Device<Active>, data: u32) {}

pub fn fail() {
    let d1: Device<Detached> = Device<Detached> { id: 1 };
    transmit(whisper d1, 100);
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("mismatched typestate: expected 'Active', found 'Detached'", str(ctx.exception))

    def test_const_generics_declaration_and_parsing(self):
        """Declaração de struct com const generics forge<T, const N: usize>."""
        source = """\
module test::const_generics;

pub struct RingBuffer forge<T, const N: usize> {
    pub head: usize;
    pub tail: usize;
}

pub fn create_buffer() -> RingBuffer<u8, 64> {
    return RingBuffer<u8, 64> { head: 0, tail: 0 };
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        struct_decl = ast.decls[0]
        self.assertEqual(len(struct_decl.generics), 2)
        self.assertEqual(struct_decl.generics[0], "T")
        self.assertIsInstance(struct_decl.generics[1], GenericParam)
        self.assertTrue(struct_decl.generics[1].is_const)
        self.assertEqual(struct_decl.generics[1].name, "N")
        self.assertEqual(struct_decl.generics[1].const_type, "usize")

        sema = Sema(ast, "<test>", source)
        sema.check()
        c_code = CodegenC(ast).emit()
        self.assertIn("RingBuffer_uint8_t_64", c_code)

    def test_const_generics_mismatch_rejected(self):
        """Passar RingBuffer<u8, 32> onde se espera RingBuffer<u8, 64> é rejeitado em compile-time."""
        source = """\
module test::const_generics_mismatch;

pub struct Buffer forge<T, const N: usize> {
    pub size: usize;
}

pub fn consume_64(b: Buffer<u8, 64>) {}

pub fn fail() {
    let b32: Buffer<u8, 32> = Buffer<u8, 32> { size: 32 };
    consume_64(b32);
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("type mismatch: expected 'Buffer<u8, 64>', found 'Buffer<u8, 32>'", str(ctx.exception))

    def test_mould_comptime_probe_pass(self):
        """Invariantes estáticas satisfeitas dentro de bloco mould compilam com sucesso."""
        source = """\
module test::mould_pass;

mould {
    probe 64 >= 32, "buffer size invariant";
    probe span_of<u32>() == 4, "u32 must be 4 bytes";
    probe 1 + 1 == 2, "math invariant";
}
"""
        ast = self._compile_ast(source)
        self.assertIsNotNone(ast)

    def test_mould_comptime_probe_failure_rejected(self):
        """Invariante falsa em probe dispara erro de compilação com a mensagem correspondente."""
        source = """\
module test::mould_fail;

mould {
    probe 16 >= 32, "buffer minimum size is 32 bytes";
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("static probe assertion failed: buffer minimum size is 32 bytes", str(ctx.exception))

    def test_island_confinement_violation_rejected(self):
        """Variável island compartilhada com função normal sem handover é bloqueada."""
        source = """\
module test::island_fail;

pub struct KernelMessage {
    pub code: u32;
}

pub fn send_external(msg: KernelMessage) {}

pub fn test_confinement() {
    let msg: island KernelMessage = KernelMessage { code: 10 };
    send_external(msg);
}
"""
        tokens = Lexer(source, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        sema = Sema(ast, "<test>", source)
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("confinamento de 'island' violado", str(ctx.exception))

    def test_dma_fence_codegen(self):
        """Chamadas de dma_fence() emitem barreira de hardware __sync_synchronize() no C."""
        source = """\
module test::dma;

pub fn sync_dma_region() {
    dma_fence();
}
"""
        ast = self._compile_ast(source)
        c_code = CodegenC(ast).emit()
        self.assertIn("__sync_synchronize()", c_code)


if __name__ == "__main__":
    unittest.main()
