"""Testes unitários para a infraestrutura de self-hosting e runtime standalone."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.llvm_toolchain import canonical_llvm_frontend, default_toolchain
from sotlas.lexer import Lexer

compile_source = canonical_llvm_frontend().compile_source


class SotlasBootstrapSelfhostTests(unittest.TestCase):
    def test_bootstrap_lexer_in_sotlas_compiles(self):
        bootstrap_path = ROOT / "bootstrap" / "sotlas_bootstrap.sotlas"
        self.assertTrue(bootstrap_path.exists())
        text = bootstrap_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(bootstrap_path))

        self.assertIn("TokenKind", c_code)
        self.assertIn("Span", c_code)
        self.assertIn("SotlasLexer", c_code)
        self.assertIn("next_token", c_code)
        self.assertIn("skip_whitespace", c_code)

        compiler = (
            default_toolchain.find_tool("clang")
            or shutil.which("clang")
            or shutil.which("gcc")
        )
        if compiler is None:
            self.skipTest("Clang or GCC is required for native bootstrap validation")
        with tempfile.TemporaryDirectory(prefix="sotlas-bootstrap-lexer-") as temp:
            generated = Path(temp) / "bootstrap_lexer.c"
            caller = Path(temp) / "lexer_caller.c"
            native_object = Path(temp) / "bootstrap_lexer.o"
            executable = Path(temp) / "bootstrap_lexer_test"
            generated.write_text(c_code, encoding="utf-8")
            caller.write_text(
                r"""#include <stddef.h>
#include <stdint.h>

typedef enum {
    TokenKind_Eof = 0,
    TokenKind_Identifier = 1,
    TokenKind_NumberLiteral = 2,
    TokenKind_StringLiteral = 3,
    TokenKind_KwFn = 6,
    TokenKind_Arrow = 34,
    TokenKind_Error = 42,
    TokenKind_KwSole = 46
} TokenKind;
typedef struct { uint32_t line, col; size_t offset, length; } Span;
typedef struct { TokenKind kind; Span span; } Token;
typedef struct {
    const uint8_t *source;
    size_t source_len, cursor;
    uint32_t current_line, current_col;
} SotlasLexer;

SotlasLexer SotlasLexer_new(const uint8_t *source, size_t length);
Token SotlasLexer_next_token(SotlasLexer *lexer);

int main(void) {
    static const uint8_t source[] = "// first line\nfn name sole -> 42\n\"hi\\\"x\"";
    SotlasLexer lexer = SotlasLexer_new(source, sizeof(source) - 1);
    Token token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_KwFn || token.span.line != 2 ||
        token.span.col != 1 || token.span.offset != 14 || token.span.length != 2)
        return 1;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_Identifier || token.span.offset != 17 ||
        token.span.length != 4)
        return 2;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_KwSole || token.span.offset != 22 ||
        token.span.length != 4)
        return 3;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_Arrow || token.span.offset != 27 ||
        token.span.length != 2)
        return 4;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_NumberLiteral || token.span.offset != 30 ||
        token.span.length != 2)
        return 5;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_StringLiteral || token.span.line != 3 ||
        token.span.col != 1 || token.span.offset != 33 || token.span.length != 7)
        return 6;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_Eof) return 7;

    static const uint8_t malformed[] = {'"', 'x', '\\'};
    lexer = SotlasLexer_new(malformed, sizeof(malformed));
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_Error || token.span.length != sizeof(malformed))
        return 8;

    lexer = SotlasLexer_new(NULL, 4);
    token = SotlasLexer_next_token(&lexer);
    return token.kind == TokenKind_Eof ? 0 : 9;
}
""",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(generated), str(caller), "-o", str(executable),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_sotlas_lite_lexer_tracks_columns_across_comments(self):
        token_path = ROOT / "bootstrap" / "sotlas" / "sotlas_lite" / "token.sotlas"
        lexer_path = ROOT / "bootstrap" / "sotlas" / "sotlas_lite" / "lexer.sotlas"

        def without_module_import_lines(source: str) -> str:
            return "\n".join(
                line for line in source.splitlines()
                if not line.lstrip().startswith(("module ", "import "))
            )

        source = "\n".join((
            "module sotlas_compile::lexer_conformance;",
            without_module_import_lines(token_path.read_text(encoding="utf-8")),
            """
pub fn str_eq(a: *const u8, b: *const u8) -> bool {
    if a == null || b == null { return a == b; }
    let mut i: usize = 0;
    unsafe {
        while a[i] != 0 && b[i] != 0 {
            if a[i] != b[i] { return false; }
            i = i + 1;
        }
        return a[i] == b[i];
    }
}
""".strip(),
            without_module_import_lines(lexer_path.read_text(encoding="utf-8")),
        ))
        generated_c = compile_source(source, "<sotlas-lite-lexer-conformance>")

        compiler = (
            default_toolchain.find_tool("clang")
            or shutil.which("clang")
            or shutil.which("gcc")
        )
        if compiler is None:
            self.skipTest("Clang or GCC is required for native self-host lexer validation")

        source_text = "fn /* block */ name // line comment\n  return"
        caller_source = r"""#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

typedef enum { TokenKind_Eof = 0, TokenKind_Ident = 1, TokenKind_Number = 2,
               TokenKind_StringLit = 3, TokenKind_Keyword = 4,
               TokenKind_Symbol = 5, TokenKind_Attr = 6 } TokenKind;
typedef struct { TokenKind kind; uint8_t text[256]; uint32_t line, col; } Token;
size_t lex_source(const uint8_t *source, Token *tokens, size_t max_tokens);

int main(void) {
    Token tokens[16] = {0};
    static const uint8_t source[] = "fn /* block */ name // line comment\n  return";
    size_t count = lex_source(source, tokens, 16);
    if (count != 4) return 1;
    for (size_t i = 0; i < count; i++)
        printf("%d|%s|%u|%u\n", (int)tokens[i].kind, tokens[i].text,
               tokens[i].line, tokens[i].col);
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="sotlas-lite-lexer-conformance-") as temp:
            temp_path = Path(temp)
            generated = temp_path / "lexer.c"
            caller = temp_path / "caller.c"
            executable = temp_path / ("lexer-test.exe" if os.name == "nt" else "lexer-test")
            generated.write_text(generated_c, encoding="utf-8")
            caller.write_text(caller_source, encoding="utf-8")
            result = subprocess.run(
                [str(compiler), "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(generated), str(caller), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, f"native lexer probe exited {executed.returncode}")
            python_tokens = Lexer(source_text, filename="<lexer-parity>").tokenize()
            expected_rows = []
            for token in python_tokens:
                token_name = token.kind.name
                if token_name == "EOF":
                    native_kind = 0
                elif token_name == "IDENT":
                    native_kind = 1
                else:
                    native_kind = 4
                expected_rows.append(
                    f"{native_kind}|{token.value}|{token.line}|{token.col}"
                )
            self.assertEqual(executed.stdout.splitlines(), expected_rows)

    def test_libsotlas_rt_headers_and_sources_exist(self):
        rt_header = ROOT / "runtime" / "libsotlas_rt.h"
        rt_source = ROOT / "runtime" / "libsotlas_rt.c"
        self.assertTrue(rt_header.exists())
        self.assertTrue(rt_source.exists())

        header_content = rt_header.read_text(encoding="utf-8")
        self.assertIn("sotlas_rt_alloc", header_content)
        self.assertIn("sotlas_rt_arc_retain", header_content)
        self.assertIn("sotlas_rt_panic", header_content)


if __name__ == "__main__":
    unittest.main()
