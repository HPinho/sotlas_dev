"""Sotlas 0.4 — Soundness Test Suite.

Valida as garantias formais de compile-time do Sotlas 0.4:
1. Rastreamento CFG de moves em ramos condicionais (if/else).
2. Proibição de transferências (moves) em laços sem reinicialização.
3. Rastreamento de empréstimos (whisper vs whisper mut).
4. Proibição de transferir (handover/move) recursos sob empréstimo ativo.
5. Effect System de hardware: proibição de 'alloc', 'blocking' e 'async' em 'trapfn'.
6. Proibição de suspensão ('await') e bloqueio em seção crítica de hardware ('clinch').
7. Semântica estrita de Topology Pointers (*rawphys, *virtmap).
8. Codegen de expressões whisper para C.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC


class SotlasSoundness04Tests(unittest.TestCase):

    def check_src(self, src: str):
        tokens = Lexer(src, "<test>").tokenize()
        ast = Parser(tokens, "<test>").parse()
        Sema(ast, "<test>", source=src).check()
        return ast

    def compile_src(self, src: str) -> str:
        ast = self.check_src(src)
        return CodegenC(ast).emit()

    # ------------------------------------------------------------------------
    # 1. CFG Move Rastreamento em Ramos Condicionais (if / else)
    # ------------------------------------------------------------------------

    def test_cfg_move_branch_merge_rejected(self):
        """Recurso sole movido em apenas um dos ramos de 'if' torna-se MAYBE_MOVED e é rejeitado após o if."""
        src = """module test::cfg_branch;
        sole struct Device {
            pub id: i32;
        }
        pub fn test(cond: bool) -> i32 {
            let d1 = Device { id: 42 };
            if cond {
                let d2 = d1; // movido somente no ramo THEN
            }
            return d1.id; // ERRO: d1 pode ter sido transferido no fluxo condicional anterior
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("pode ter sido transferido em ramo condicional anterior", err)

    def test_cfg_move_both_branches_rejected(self):
        """Recurso sole movido em ambos os ramos de 'if/else' torna-se MOVED com certeza."""
        src = """module test::cfg_both;
        sole struct Device {
            pub id: i32;
        }
        pub fn test(cond: bool) -> i32 {
            let d1 = Device { id: 42 };
            if cond {
                let d2 = d1;
            } else {
                let d3 = d1;
            }
            return d1.id; // ERRO: d1 foi movido com certeza
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("após transferência (handover)", err)

    # ------------------------------------------------------------------------
    # 2. CFG Move em Laços de Repetição
    # ------------------------------------------------------------------------

    def test_cfg_move_in_while_loop_rejected(self):
        """Mover um recurso sole dentro de um laço sem reinicializá-lo é proibido."""
        src = """module test::cfg_loop;
        sole struct Handle {
            pub val: i32;
        }
        pub fn test() {
            let h = Handle { val: 1 };
            while true {
                let h2 = h; // ERRO: h seria consumido na iteração 1 e causaria use-after-move na iteração 2
            }
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("não pode ser transferido dentro de laço sem ser reinicializado", err)

    # ------------------------------------------------------------------------
    # 3. Borrow Checking: whisper e whisper mut
    # ------------------------------------------------------------------------

    def test_borrow_whisper_and_whisper_mut_conflict(self):
        """Não é permitido criar borrow mutável enquanto houver borrow imutável ativo."""
        src = """module test::borrow_conflict;
        struct Buffer {
            pub len: u32;
        }
        pub fn test() {
            let mut buf = Buffer { len: 64 };
            let x = whisper buf;
            let y = whisper mut buf; // ERRO: empréstimo mutável concorrente com whisper imutável
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("não é permitido criar empréstimo mutável (whisper mut) enquanto houver outros empréstimos ativos", err)

    def test_handover_prohibited_during_active_borrow(self):
        """Não é permitido transferir um recurso sole enquanto ele estiver sob empréstimo ativo."""
        src = """module test::move_borrow;
        sole struct Buffer {
            pub len: u32;
        }
        pub fn test() {
            let buf = Buffer { len: 64 };
            let x = whisper buf;
            handover buf; // ERRO: não pode fazer handover enquanto emprestado
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("não é permitido transferir recurso 'sole' 'buf' enquanto estiver sob empréstimo ativo", err)

    # ------------------------------------------------------------------------
    # 4. Hardware & OS Effect System em 'trapfn' (ISRs)
    # ------------------------------------------------------------------------

    def test_trapfn_alloc_forbidden(self):
        """Alocação dinâmica de memória é proibida em contexto de interrupção (trapfn)."""
        src = """module test::trapfn_alloc;
        fn heap_allocate(sz: usize) -> usize {
            return 0;
        }
        trapfn isr_keyboard() {
            let ptr = heap_allocate(128); // ERRO: alloc em trapfn
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("error[E0712]: alocação dinâmica (efeito 'alloc') é terminantemente proibida em contexto de interrupção", err)

    def test_trapfn_blocking_forbidden(self):
        """Operações bloqueantes ou sleep são proibidas em contexto de interrupção (trapfn)."""
        src = """module test::trapfn_blocking;
        fn sleep(ms: u32) {}
        trapfn isr_timer() {
            sleep(10); // ERRO: blocking em trapfn
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("error[E0713]: operação bloqueante (efeito 'blocking') é terminantemente proibida em contexto de interrupção", err)

    def test_trapfn_async_forbidden(self):
        """Suspensão assíncrona ('await') é terminantemente proibida em contexto de interrupção (trapfn)."""
        src = """module test::trapfn_async;
        async fn poll_packet() -> i32 {
            return 0;
        }
        trapfn isr_net() {
            let p = await poll_packet(); // ERRO: async em trapfn
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("error[E0714]: suspensão assíncrona (efeito 'async') é terminantemente proibida em contexto de interrupção", err)

    # ------------------------------------------------------------------------
    # 5. Hardware Critical Section ('clinch')
    # ------------------------------------------------------------------------

    def test_clinch_await_forbidden(self):
        """Suspensão assíncrona é terminantemente proibida dentro de seção crítica de hardware ('clinch')."""
        src = """module test::clinch_suspension;
        async fn fetch_val() -> i32 {
            return 1;
        }
        pub fn main() {
            clinch {
                let v = await fetch_val(); // ERRO: suspensão com lock de hardware
            }
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("suspensão ('await') é terminantemente proibida dentro de seção crítica de hardware ('clinch')", err)

    def test_clinch_blocking_forbidden(self):
        """Bloqueio de thread ou sleep é proibido dentro de seção crítica de hardware ('clinch')."""
        src = """module test::clinch_blocking;
        fn sleep(ms: u32) {}
        pub fn main() {
            clinch {
                sleep(5); // ERRO: blocking em clinch
            }
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("operação bloqueante é terminantemente proibida dentro de seção crítica de hardware ('clinch')", err)

    # ------------------------------------------------------------------------
    # 6. Topology Pointers & Codegen C
    # ------------------------------------------------------------------------

    def test_topology_pointers_cross_assignment_rejected(self):
        """Atribuição cruzada entre *rawphys e *virtmap exige cast explícito."""
        src = """module test::topo_cast;
        struct IoRegs { pub v: u32; }
        pub fn configure(p: *virtmap IoRegs) {
            let r: *rawphys IoRegs = p; // ERRO: topologias incompatíveis sem cast
        }"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self.check_src(src)
        err = str(ctx.exception)
        self.assertIn("atribuição de topologia incompatível", err)

    def test_whisper_expression_codegen(self):
        """Expressão 'whisper buf' compila para endereço (&) no código C."""
        src = """module test::whisper_cg;
        struct Buffer {
            pub len: u32;
        }
        fn inspect(b: *const Buffer) -> u32 {
            return 0;
        }
        pub fn main() -> u32 {
            let b = Buffer { len: 128 };
            let p = whisper b;
            return inspect(p);
        }"""
        c = self.compile_src(src)
        self.assertIn("(&(b))", c)


if __name__ == "__main__":
    unittest.main()
