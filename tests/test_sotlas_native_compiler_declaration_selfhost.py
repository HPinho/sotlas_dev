"""Compile real native-compiler declarations through the compiled native frontend."""
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


class SotlasNativeCompilerDeclarationSelfhostTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_real_token_declarations_cross_native_frontend_and_compile_as_c11(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        order = (
            "token", "ast", "lexer", "parser", "sema", "emitter_c",
            "target_ir", "lower_scalar", "x86_64_scalar", "main",
        )
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
            fragments.append(
                emit_c(modules[name], mangle=False, include_preamble=False)
            )

        token_source = (module_dir / "token.sotlas").read_text(encoding="utf-8")
        self.assertIn("\nimpl Token {", token_source)
        declarations = token_source.split("\nimpl Token {", 1)[0].rstrip() + "\n"

        driver = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

extern size_t sotlas_native_compile_diagnostic(
    const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *
);

int main(int argc, char **argv) {
    static uint8_t source[1 << 20];
    static uint8_t output[1 << 20];
    if (argc != 3) return 10;

    FILE *input = fopen(argv[1], "rb");
    if (input == NULL) return 11;
    size_t source_len = fread(source, 1, sizeof(source), input);
    if (ferror(input)) { fclose(input); return 12; }
    fclose(input);
    if (source_len == sizeof(source)) return 13;

    uint32_t line = 999;
    uint32_t col = 999;
    size_t output_len = sotlas_native_compile_diagnostic(
        source, source_len, output, sizeof(output), &line, &col
    );
    if (output_len == 0 || line != 0 || col != 0) {
        fprintf(stderr, "native declaration compile: size=%zu line=%u col=%u\n",
                output_len, line, col);
        return 14;
    }

    FILE *out = fopen(argv[2], "wb");
    if (out == NULL) return 15;
    size_t written = fwrite(output, 1, output_len, out);
    fclose(out);
    return written == output_len ? 0 : 16;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-native-declaration-selfhost-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            exe = root / ("native_decl.exe" if os.name == "nt" else "native_decl")
            source_file = root / "token_declarations.sotlas"
            generated_c = root / "token_declarations.c"
            generated_obj = root / "token_declarations.obj"

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            source_file.write_text(declarations, encoding="utf-8")

            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], exe)

            result = subprocess.run(
                [str(exe), str(source_file), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = generated_c.read_text(encoding="utf-8")
            self.assertIn("typedef enum TokenKind {", generated)
            self.assertIn("TokenKind_Eof = 0", generated)
            self.assertIn("TokenKind_CloseBracket = 115", generated)
            self.assertIn("typedef struct Span {", generated)
            self.assertIn("uint32_t line;", generated)
            self.assertIn("typedef struct Token {", generated)
            self.assertIn("TokenKind kind;", generated)
            self.assertIn("Span span;", generated)
            self.assertIn("uint8_t text[128];", generated)
            self.assertIn("size_t text_len;", generated)

            default_toolchain.compile_c_to_obj(generated_c, generated_obj, opt_level=0)
            self.assertTrue(generated_obj.is_file())


if __name__ == "__main__":
    unittest.main()
