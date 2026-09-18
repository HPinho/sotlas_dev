import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError


class TestSotlasGenericBounds(unittest.TestCase):
    def test_valid_generic_spec_bound(self):
        code = """module test_valid;
        pub spec Printable {
            pub fn print(self);
        }

        pub struct Doc adopts Printable {
            pub id: u32;
        }

        pub struct Caixa forge<T: Printable> {
            pub item: T;
        }

        pub fn test_run() {
            let d: Doc = Doc { id: 1 };
            let c: Caixa<Doc> = Caixa { item: d };
        }
        """
        tokens = Lexer(code, "test_valid.sotlas").tokenize()
        ast = Parser(tokens, "test_valid.sotlas").parse()
        sema = Sema(ast, "test_valid.sotlas")
        sema.check()
        self.assertEqual(len(sema.errors), 0)

    def test_invalid_generic_spec_bound_rejected(self):
        code = """module test_invalid;
        pub spec Printable {
            pub fn print(self);
        }

        pub struct NotPrintable {
            pub id: u32;
        }

        pub struct Caixa forge<T: Printable> {
            pub item: T;
        }

        pub fn test_run() {
            let np: NotPrintable = NotPrintable { id: 2 };
            let c: Caixa<NotPrintable> = Caixa { item: np };
        }
        """
        tokens = Lexer(code, "test_invalid.sotlas").tokenize()
        ast = Parser(tokens, "test_invalid.sotlas").parse()
        sema = Sema(ast, "test_invalid.sotlas")
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("não satisfaz o bound de spec 'Printable'", str(ctx.exception))

    def test_undeclared_spec_bound_rejected(self):
        code = """module test_undeclared;
        pub struct Caixa forge<T: NonExistentSpec> {
            pub item: T;
        }
        """
        tokens = Lexer(code, "test_undeclared.sotlas").tokenize()
        ast = Parser(tokens, "test_undeclared.sotlas").parse()
        sema = Sema(ast, "test_undeclared.sotlas")
        with self.assertRaises(SotlasSemaError) as ctx:
            sema.check()
        self.assertIn("spec bound 'NonExistentSpec' não declarado", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
