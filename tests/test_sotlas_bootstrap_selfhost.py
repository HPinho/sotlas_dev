"""Testes unitários para a infraestrutura de self-hosting e runtime standalone."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.llvm_toolchain import canonical_llvm_frontend, default_toolchain

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
                """#include <stddef.h>
#include <stdint.h>

typedef enum {
    TokenKind_Eof = 0,
    TokenKind_Identifier = 1,
    TokenKind_NumberLiteral = 2,
    TokenKind_Arrow = 34
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
    static const uint8_t source[] = "name -> 42";
    SotlasLexer lexer = SotlasLexer_new(source, sizeof(source) - 1);
    Token token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_Identifier || token.span.line != 1 ||
        token.span.col != 1 || token.span.offset != 0 || token.span.length != 4)
        return 1;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_Arrow || token.span.offset != 5 ||
        token.span.length != 2)
        return 2;
    token = SotlasLexer_next_token(&lexer);
    if (token.kind != TokenKind_NumberLiteral || token.span.offset != 8 ||
        token.span.length != 2)
        return 3;
    token = SotlasLexer_next_token(&lexer);
    return token.kind == TokenKind_Eof ? 0 : 4;
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
