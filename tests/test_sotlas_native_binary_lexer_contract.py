"""Pin the bounded binary-integer lexical foundation in the Sotlas-written lexer."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
TOOLS_DIR = ROOT / "tools"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sotlas_compile.bootstrap import compile_module, emit_c, parse


class SotlasNativeBinaryLexerContractTests(unittest.TestCase):
    def test_binary_prefix_is_lexed_as_bounded_integer_literal(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        token_path = module_dir / "token.sotlas"
        lexer_path = module_dir / "lexer.sotlas"

        token_module = parse(token_path.read_text(encoding="utf-8"), filename=str(token_path))
        lexer_text = lexer_path.read_text(encoding="utf-8")
        lexer_module = parse(lexer_text, filename=str(lexer_path))

        # The change must remain self-hostable by the production compiler.
        compile_module(token_module, [lexer_module])
        compile_module(lexer_module, [token_module])
        emitted = emit_c(lexer_module, mangle=False, include_preamble=False)
        self.assertTrue(emitted)

        # Bounded lexical contract only: 0b/0B stays one IntLit token and the
        # body accepts binary digits plus Sotlas numeric separators. Semantic
        # range checking and C11 canonicalization are intentionally separate.
        self.assertIn(
            "ch == 48 && (self.peek() == 98 || self.peek() == 66)",
            lexer_text,
        )
        self.assertIn("if p == 48 || p == 49 || p == 95", lexer_text)
        self.assertIn("TokenKind::IntLit", lexer_text)

        # Do not accidentally broaden binary digits to the decimal/hex ranges.
        binary_branch = lexer_text.split(
            "else if ch == 48 && (self.peek() == 98 || self.peek() == 66)", 1
        )[1].split("} else {", 1)[0]
        self.assertNotIn("p >= 48 && p <= 57", binary_branch)
        self.assertNotIn("p >= 65 && p <= 70", binary_branch)
        self.assertNotIn("p >= 97 && p <= 102", binary_branch)


if __name__ == "__main__":
    unittest.main()
