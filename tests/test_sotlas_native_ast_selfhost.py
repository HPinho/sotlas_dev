"""Advance the native self-host ladder through the real token and AST modules."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
TOOLS_DIR = ROOT / "tools"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sotlas.llvm_toolchain import default_toolchain
from sotlas_compile.bootstrap import PREAMBLE, compile_module, emit_c, parse


class NativeAstSelfHostTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_native_compiler_compiles_real_token_and_ast_modules(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        order = ("token", "ast", "lexer", "parser", "sema", "emitter_c", "target_ir", "lower_scalar", "x86_64_scalar", "main")
        modules = {
            path.stem: parse(path.read_text(encoding="utf-8"), filename=str(path))
            for path in module_dir.rglob("*.sotlas")
        }
        self.assertEqual(set(modules), set(order))

        fragments = [PREAMBLE]
        for name in order:
            compile_module(
                modules[name],
                [modules[dependency] for dependency in order if dependency != name],
            )
            fragments.append(emit_c(modules[name], mangle=False, include_preamble=False))

        with tempfile.TemporaryDirectory(prefix="sotlas-native-ast-selfhost-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            compiler_exe = root / ("native_compiler.exe" if os.name == "nt" else "native_compiler")
            token_c = root / "token.c"
            ast_c = root / "ast.c"
            combined_c = root / "token_ast.c"
            combined_obj = root / "token_ast.obj"
            caller_c = root / "caller.c"
            caller_obj = root / "caller.obj"
            app_exe = root / ("ast_selfhost.exe" if os.name == "nt" else "ast_selfhost")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(
                "#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
                "extern size_t sotlas_native_compile_diagnostic(const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *);\n"
                "int main(int argc, char **argv) {\n"
                "  if (argc != 3) return 1;\n"
                "  FILE *in = fopen(argv[1], \"rb\"); if (!in) return 2;\n"
                "  if (fseek(in, 0, SEEK_END) != 0) return 3; long n = ftell(in); if (n < 0) return 4; rewind(in);\n"
                "  uint8_t *src = (uint8_t *)malloc((size_t)n); if (!src) return 5;\n"
                "  if (fread(src, 1, (size_t)n, in) != (size_t)n) { fclose(in); free(src); return 6; } fclose(in);\n"
                "  uint8_t *out = (uint8_t *)malloc(262144); if (!out) { free(src); return 7; }\n"
                "  uint32_t line = 0, col = 0; size_t size = sotlas_native_compile_diagnostic(src, (size_t)n, out, 262144, &line, &col);\n"
                "  free(src); if (size == 0 || line != 0 || col != 0) { free(out); return 8; }\n"
                "  FILE *dest = fopen(argv[2], \"wb\"); if (!dest) { free(out); return 9; }\n"
                "  size_t written = fwrite(out, 1, size, dest); fclose(dest); free(out);\n"
                "  return written == size ? 0 : 10;\n}\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], compiler_exe)

            token_source = module_dir / "token.sotlas"
            ast_source = module_dir / "ast.sotlas"
            for source, output in ((token_source, token_c), (ast_source, ast_c)):
                result = subprocess.run(
                    [str(compiler_exe), str(source), str(output)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, f"{source.name}: {result.stderr}")
                self.assertGreater(output.stat().st_size, 0)

            token_text = token_c.read_text(encoding="utf-8")
            ast_text = ast_c.read_text(encoding="utf-8")
            self.assertIn("Token Token_new(", token_text)
            self.assertIn("typedef enum AstKind", ast_text)
            self.assertIn("typedef struct AstNode", ast_text)
            self.assertIn("AstNode AstNode_new(", ast_text)
            self.assertIn("(AstNode){", ast_text)

            combined_c.write_text(token_text + "\n" + ast_text, encoding="utf-8")
            default_toolchain.compile_c_to_obj(combined_c, combined_obj, opt_level=0)

            caller_c.write_text(
                "#include <stdint.h>\n#include <stddef.h>\n"
                "typedef struct Span { uint32_t line; uint32_t col; size_t offset; size_t length; } Span;\n"
                "typedef enum AstKind { AstKind_Module = 1 } AstKind;\n"
                "typedef struct AstNode { AstKind kind; Span span; int64_t int_value; size_t str_offset; size_t str_len; size_t first_child; size_t next_sibling; size_t parent; } AstNode;\n"
                "extern AstNode AstNode_new(AstKind kind, Span span);\n"
                "int main(void) { Span s = { 9, 4, 12, 3 }; AstNode n = AstNode_new(AstKind_Module, s);\n"
                "  return (n.kind == AstKind_Module && n.span.line == 9 && n.span.col == 4 && n.span.offset == 12 && n.span.length == 3 && n.int_value == 0 && n.str_offset == 0 && n.str_len == 0 && n.first_child == 0 && n.next_sibling == 0 && n.parent == 0) ? 0 : 1; }\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(caller_c, caller_obj, opt_level=0)
            default_toolchain.link_native_binary([combined_obj, caller_obj], app_exe)
            run = subprocess.run([str(app_exe)], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
