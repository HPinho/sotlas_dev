"""Exercise the real native Token::new constructor through executable C11 lowering."""
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


class SotlasNativeTokenConstructorParserTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_real_token_constructor_lowers_to_valid_c11(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        token_source = module_dir / "token.sotlas"
        source_text = token_source.read_text(encoding="utf-8")
        self.assertIn("return Token {", source_text)
        self.assertIn("span: Span {", source_text)
        self.assertIn("text: [0; 128]", source_text)

        order = ("token", "ast", "lexer", "parser", "sema", "emitter_c", "main")
        modules = {
            path.stem: parse(path.read_text(encoding="utf-8"), filename=str(path))
            for path in module_dir.glob("*.sotlas")
        }
        self.assertEqual(set(modules), set(order))

        fragments = [PREAMBLE]
        for name in order:
            compile_module(
                modules[name],
                [modules[dependency] for dependency in order if dependency != name],
            )
            fragments.append(emit_c(modules[name], mangle=False, include_preamble=False))

        driver = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

extern size_t sotlas_native_compile_diagnostic(
    const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *
);

int main(int argc, char **argv) {
    if (argc != 3) return 10;
    FILE *file = fopen(argv[1], "rb");
    if (file == NULL) return 11;
    if (fseek(file, 0, SEEK_END) != 0) { fclose(file); return 12; }
    long raw_size = ftell(file);
    if (raw_size <= 0 || raw_size > 1048576) { fclose(file); return 13; }
    if (fseek(file, 0, SEEK_SET) != 0) { fclose(file); return 14; }

    size_t source_size = (size_t)raw_size;
    uint8_t *source = (uint8_t *)malloc(source_size);
    if (source == NULL) { fclose(file); return 15; }
    size_t read_size = fread(source, 1, source_size, file);
    fclose(file);
    if (read_size != source_size) { free(source); return 16; }

    uint8_t output[262144];
    uint32_t line = 999;
    uint32_t col = 999;
    size_t size = sotlas_native_compile_diagnostic(
        source, source_size, output, sizeof(output), &line, &col
    );
    free(source);

    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "real Token::new: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }

    FILE *lowered = fopen(argv[2], "wb");
    if (lowered == NULL) return 17;
    size_t written = fwrite(output, 1, size, lowered);
    fclose(lowered);
    if (written != size) return 18;
    return 0;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-native-token-constructor-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            lowered_c = root / "token_lowered.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            lowered_obj = root / "token_lowered.obj"
            exe = root / ("token_constructor.exe" if os.name == "nt" else "token_constructor")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], exe)

            result = subprocess.run(
                [str(exe), str(token_source), str(lowered_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            lowered_text = lowered_c.read_text(encoding="utf-8")
            self.assertIn("Token Token_new(", lowered_text)
            self.assertIn("Token __sotlas_return_value = (Token){ ", lowered_text)
            self.assertIn("return __sotlas_return_value;", lowered_text)
            self.assertIn(".span = (Span){ ", lowered_text)
            self.assertIn(".text = {0}", lowered_text)

            # The native compiler must not merely print plausible C.  Its
            # generated constructor has to satisfy the real C11 toolchain.
            default_toolchain.compile_c_to_obj(lowered_c, lowered_obj, opt_level=0)


if __name__ == "__main__":
    unittest.main()
