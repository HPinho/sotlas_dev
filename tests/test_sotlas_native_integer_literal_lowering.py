"""Require Sotlas integer separators to lower to valid C11 literals."""
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


class SotlasNativeIntegerLiteralLoweringTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_numeric_separators_lower_to_c11_and_execute(self):
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

        driver = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

extern size_t sotlas_native_compile_diagnostic(
    const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *
);

int main(int argc, char **argv) {
    static const uint8_t source[] =
        "module test::integer_separator;\n"
        "fn decimal() -> u8 { return 4_2; }\n"
        "fn hex_value() -> u8 { return 0x2_A; }\n"
        "pub fn answer() -> u8 { return decimal(); }\n";

    uint8_t output[65536];
    uint32_t line = 99;
    uint32_t col = 99;
    if (argc != 2) return 10;

    size_t size = sotlas_native_compile_diagnostic(
        source, sizeof(source) - 1, output, sizeof(output) - 1, &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "separator source: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }

    FILE *file = fopen(argv[1], "wb");
    if (file == NULL) return 2;
    size_t written = fwrite(output, 1, size, file);
    fclose(file);
    return written == size ? 0 : 3;
}
'''

        consumer = r'''
#include <stdint.h>
uint8_t answer(void);
int main(void) { return answer() == 42 ? 0 : 1; }
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-int-separator-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            compiler_obj = root / "native_compiler.obj"
            driver_c = root / "driver.c"
            driver_obj = root / "driver.obj"
            driver_exe = root / ("separator_driver.exe" if os.name == "nt" else "separator_driver")
            generated_c = root / "separator.c"
            generated_obj = root / "separator.obj"
            consumer_c = root / "consumer.c"
            consumer_obj = root / "consumer.obj"
            consumer_exe = root / ("separator_consumer.exe" if os.name == "nt" else "separator_consumer")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            consumer_c.write_text(consumer, encoding="utf-8")

            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], driver_exe)

            result = subprocess.run(
                [str(driver_exe), str(generated_c)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            generated_text = generated_c.read_text(encoding="utf-8")
            self.assertNotIn("4_2", generated_text)
            self.assertNotIn("0x2_A", generated_text)
            self.assertIn("42", generated_text)
            self.assertIn("0x2A", generated_text)

            default_toolchain.compile_c_to_obj(generated_c, generated_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(consumer_c, consumer_obj, opt_level=0)
            default_toolchain.link_native_binary([generated_obj, consumer_obj], consumer_exe)
            run_consumer = subprocess.run(
                [str(consumer_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(run_consumer.returncode, 0, run_consumer.stderr)


if __name__ == "__main__":
    unittest.main()
