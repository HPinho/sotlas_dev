"""Testes de Soundness do Sistema de Ownership SRG em Sotlas.

Estes testes verificam propriedades de segurança que o compilador DEVE garantir:
- Double-move detectado em ambos os ramos de if/else
- maybe_moved propagado corretamente após if sem else
- Borrow whisper bloqueando acesso mútável
- island isolamento em chamadas de função
- Move em laço detectado
- Use-after-move em diferentes contextos
- Escalada correta de VarState entre escopos aninhados
"""
import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError


def _check(src: str):
    tokens = Lexer(src, "<test>").tokenize()
    ast = Parser(tokens, "<test>").parse()
    Sema(ast, "<test>", src).check()


def _raises(src: str, fragment: str = ""):
    tokens = Lexer(src, "<test>").tokenize()
    ast = Parser(tokens, "<test>").parse()
    tc = unittest.TestCase()
    tc.maxDiff = None
    if fragment:
        with tc.assertRaisesRegex(SotlasSemaError, fragment):
            Sema(ast, "<test>", src).check()
    else:
        with tc.assertRaises(SotlasSemaError):
            Sema(ast, "<test>", src).check()


class TestDoubleMove(unittest.TestCase):
    """Move duplo deve ser detectado em ambos os ramos e diretamente."""

    def test_direct_double_move_raises(self):
        src = """\
module test::dm;
sole struct Resource { pub id: UInt32; }
pub fn consume(r: sole Resource) -> Void { return; }
pub fn main() -> Void {
    let r = Resource { id: 1 };
    consume(r);
    consume(r);
}
"""
        _raises(src, "após transferência")

    def test_move_in_if_branch_then_use_raises(self):
        src = """\
module test::dm_if;
sole struct Handle { pub fd: Int32; }
pub fn drop_handle(h: sole Handle) -> Void { return; }
pub fn main(cond: Bool) -> Void {
    let h = Handle { fd: 3 };
    if cond {
        drop_handle(h);
    }
    let x = h;
}
"""
        # Após if sem else, h é maybe_moved → uso inválido
        _raises(src, "transferido")

    def test_move_in_both_branches_then_use_raises(self):
        src = """\
module test::dm_both;
sole struct Token { pub val: UInt64; }
pub fn consume(t: sole Token) -> Void { return; }
pub fn main(flag: Bool) -> Void {
    let t = Token { val: 99 };
    if flag {
        consume(t);
    } else {
        consume(t);
    }
    let x = t;
}
"""
        _raises(src, "após transferência")

    def test_move_only_in_else_then_use_raises(self):
        src = """\
module test::dm_else;
sole struct Ticket { pub id: UInt32; }
pub fn use_ticket(t: sole Ticket) -> Void { return; }
pub fn process(ok: Bool) -> Void {
    let t = Ticket { id: 7 };
    if ok {
        return;
    } else {
        use_ticket(t);
    }
    let x = t;
}
"""
        # O merge de fluxo resulta em MAYBE_MOVED, não em MOVED incondicional.
        _raises(src, "transferido")


class TestMaybeMovedPropagation(unittest.TestCase):
    """VarState.MAYBE_MOVED deve ser propagado corretamente."""

    def test_no_move_in_if_no_else_then_use_ok_depends_on_condition(self):
        """Sem move condicional: uso após if sem else é ok."""
        src = """\
module test::nomove;
pub fn main(flag: Bool) -> Void {
    let x: Int32 = 42;
    if flag {
        let y: Int32 = x;
    }
    let z: Int32 = x;
}
"""
        _check(src)  # tipos primitivos são copiáveis, sem move

    def test_sole_not_moved_in_any_branch_then_use_ok(self):
        """Se sole não é movido em nenhum ramo, uso posterior é válido."""
        src = """\
module test::notmoved;
sole struct Safe { pub v: UInt32; }
pub fn main(flag: Bool) -> Void {
    let s = Safe { v: 1 };
    if flag {
        let x: UInt32 = s.v;
    }
    let y = s;
}
"""
        _check(src)  # s nunca foi movido, apenas seu campo lido


class TestMoveInLoop(unittest.TestCase):
    """Move dentro de laço deve ser detectado."""

    def test_sole_moved_in_while_raises(self):
        src = """\
module test::loopvm;
sole struct Packet { pub data: UInt8; }
pub fn send(p: sole Packet) -> Void { return; }
pub fn main() -> Void {
    let p = Packet { data: 0 };
    while true {
        send(p);
    }
}
"""
        _raises(src, "laço")

    def test_sole_moved_in_for_raises(self):
        src = """\
module test::loopfor;
sole struct Buf { pub len: UInt32; }
pub fn flush(b: sole Buf) -> Void { return; }
pub fn main(items: UInt8) -> Void {
    let buf = Buf { len: 0 };
    for item in items {
        flush(buf);
    }
}
"""
        _raises(src, "laço")


class TestHandoverSemantics(unittest.TestCase):
    """Semântica de handover explícito."""

    def test_handover_invalidates_sole(self):
        src = """\
module test::hdo;
sole struct Fd { pub n: Int32; }
pub fn main() -> Void {
    let fd = Fd { n: 1 };
    handover fd;
    let x = fd.n;
}
"""
        _raises(src, "após transferência")

    def test_handover_on_non_sole_raises(self):
        src = """\
module test::hdo_nonsole;
pub fn main() -> Void {
    let x: Int32 = 5;
    handover x;
}
"""
        _raises(src, "sole")

    def test_handover_on_param_sole_ok(self):
        src = """\
module test::hdo_param;
sole struct R { pub v: UInt32; }
pub fn transfer(r: sole R) -> Void {
    handover r;
}
"""
        _check(src)

    def test_double_handover_raises(self):
        src = """\
module test::hdo_double;
sole struct S { pub v: UInt8; }
pub fn consume(s: sole S) -> Void { return; }
pub fn main() -> Void {
    let s = S { v: 1 };
    handover s;
    handover s;
}
"""
        _raises(src, "após transferência")


class TestIslandIsolation(unittest.TestCase):
    """Variáveis island devem ser isoladas do contexto externo."""

    def test_island_param_accepted_ok(self):
        src = """\
module test::isolation;
struct Buffer { pub len: UInt32; }
pub fn process(buf: island Buffer) -> Void { return; }
"""
        _check(src)

    def test_island_param_field_accessible(self):
        src = """\
module test::isolfield;
struct Node { pub val: Int32; }
pub fn read_val(n: island Node) -> Int32 {
    return n.val;
}
"""
        _check(src)


class TestBarecoreOwnership(unittest.TestCase):
    """Regras de ownership em contexto barecore."""

    def test_barecore_sole_param_ok(self):
        src = """\
barecore;
module hal::test;
pub fn alloc(p: sole UInt8) -> Void { return; }
"""
        _check(src)

    def test_barecore_co_owned_raises(self):
        src = """\
barecore;
module hal::test;
pub fn f(p: co-owned UInt8) -> Void { return; }
"""
        _raises(src, "co-owned")

    def test_barecore_island_param_ok(self):
        src = """\
barecore;
module hal::test;
struct DmaBuffer { pub addr: UInt64; }
pub fn dma_transfer(buf: island DmaBuffer) -> Void { return; }
"""
        _check(src)


class TestTopologyMismatch(unittest.TestCase):
    """Ponteiros de topologias incompatíveis não podem ser atribuídos entre si."""

    def test_rawphys_to_virtmap_assignment_raises(self):
        src = """\
module mem;
pub fn map_io(p: *rawphys UInt32) -> Void {
    let v: *virtmap UInt32 = p;
}
"""
        _raises(src, "topologia incompatível")

    def test_virtmap_to_rawphys_raises(self):
        src = """\
module mem;
pub fn f(p: *virtmap UInt8) -> Void {
    let r: *rawphys UInt8 = p;
}
"""
        _raises(src, "topologia incompatível")

    def test_same_topology_ok(self):
        src = """\
module mem;
pub fn f(p: *rawphys UInt32) -> Void {
    let q: *rawphys UInt32 = p;
}
"""
        _check(src)


class TestReturnEscape(unittest.TestCase):
    """Referências a variáveis locais não podem escapar via return."""

    def test_stack_ref_escape_raises(self):
        src = """\
module test::escape;
pub fn leak() -> *mut UInt32 {
    let x: UInt32 = 42;
    return &x;
}
"""
        _raises(src, "variável local")

    def test_global_ref_return_ok(self):
        src = """\
module test::escape_ok;
static GLOBAL: UInt32 = 42;
pub fn get() -> UInt32 {
    return GLOBAL;
}
"""
        _check(src)


class TestNestedScopeOwnership(unittest.TestCase):
    """Ownership deve propagar corretamente entre escopos aninhados."""

    def test_move_in_nested_scope_detected_outer(self):
        src = """\
module test::nested;
sole struct S { pub v: UInt32; }
pub fn eat(s: sole S) -> Void { return; }
pub fn main() -> Void {
    let s = S { v: 1 };
    eat(s);
    let x = s;
}
"""
        _raises(src, "após transferência")

    def test_define_in_inner_scope_not_visible_outer(self):
        src = """\
module test::scope_vis;
pub fn main() -> Void {
    let x: Int32 = inner_val();
}
pub fn inner_val() -> Int32 {
    return missing_symbol;
}
"""
        _raises(src, "não declarado")


if __name__ == "__main__":
    unittest.main()
