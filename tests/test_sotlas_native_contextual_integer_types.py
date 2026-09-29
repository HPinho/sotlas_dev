"""Exercise bounded contextual integer typing in the Sotlas-written frontend."""
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


class SotlasNativeContextualIntegerTypeTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_integer_literals_use_parameter_field_and_return_context(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
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

extern size_t sotlas_native_compile_diagnostic(
    const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *
);

static int expect_rejection(
    const uint8_t *source,
    size_t source_len,
    uint8_t *output,
    size_t output_len,
    uint32_t expected_line,
    uint32_t expected_col,
    const char *label,
    int code
) {
    uint32_t line = 0;
    uint32_t col = 0;
    size_t size = sotlas_native_compile_diagnostic(
        source, source_len, output, output_len, &line, &col
    );
    if (size != 0 || line != expected_line || col != expected_col) {
        fprintf(
            stderr,
            "%s: size=%zu line=%u col=%u expected=%u:%u\n",
            label, size, line, col, expected_line, expected_col
        );
        return code;
    }
    return 0;
}

int main(int argc, char **argv) {
    static const uint8_t good[] =
        "module test::context_good;\n"
        "struct Box { value: u8; }\n"
        "impl Box { fn make(value: u8) -> u8 { return value; } }\n"
        "fn direct(value: u8) -> u8 { return value; }\n"
        "fn signed_min() -> i8 { return -128; }\n"
        "pub fn answer() -> u8 { return direct(Box::make(0x2A)); }\n";

    static const uint8_t bad_direct[] =
        "module test::bad_direct;\n"
        "fn take(value: u8) -> u8 { return value; }\n"
        "fn bad() -> u8 { return take(256); }\n";

    static const uint8_t bad_static[] =
        "module test::bad_static;\n"
        "struct Box { value: u8; }\n"
        "impl Box { fn make(value: u8) -> u8 { return value; } }\n"
        "fn bad() -> u8 { return Box::make(300); }\n";

    static const uint8_t bad_return[] =
        "module test::bad_return;\n"
        "fn bad() -> i8 { return 128; }\n";

    static const uint8_t bad_unsigned_negative[] =
        "module test::bad_unsigned_negative;\n"
        "fn bad() -> u8 { return -1; }\n";

    static const uint8_t bad_signed_negative[] =
        "module test::bad_signed_negative;\n"
        "fn bad() -> i8 { return -129; }\n";

    static const uint8_t bad_hex[] =
        "module test::bad_hex;\n"
        "fn bad() -> u8 { return 0x100; }\n";

    static const uint8_t bad_underscore[] =
        "module test::bad_underscore;\n"
        "fn bad() -> u8 { return 2_56; }\n";

    static const uint8_t bad_u64[] =
        "module test::bad_u64;\n"
        "fn bad() -> u64 { return 18446744073709551616; }\n";

    uint8_t output[65536];
    uint32_t line = 99;
    uint32_t col = 99;

    if (argc != 2) return 20;

    size_t size = sotlas_native_compile_diagnostic(
        good, sizeof(good) - 1, output, sizeof(output) - 1, &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "good contextual integers: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }
    output[size] = 0;

    FILE *file = fopen(argv[1], "wb");
    if (file == NULL) return 2;
    size_t written = fwrite(output, 1, size, file);
    fclose(file);
    if (written != size) return 3;

    int rejected = expect_rejection(
        bad_direct, sizeof(bad_direct) - 1, output, sizeof(output) - 1,
        3, 30, "u8 direct overflow", 4
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_static, sizeof(bad_static) - 1, output, sizeof(output) - 1,
        4, 35, "u8 static overflow", 5
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_return, sizeof(bad_return) - 1, output, sizeof(output) - 1,
        2, 25, "i8 positive overflow", 6
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_unsigned_negative, sizeof(bad_unsigned_negative) - 1,
        output, sizeof(output) - 1,
        2, 25, "negative unsigned literal", 7
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_signed_negative, sizeof(bad_signed_negative) - 1,
        output, sizeof(output) - 1,
        2, 25, "i8 negative overflow", 8
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_hex, sizeof(bad_hex) - 1, output, sizeof(output) - 1,
        2, 25, "hex overflow", 9
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_underscore, sizeof(bad_underscore) - 1,
        output, sizeof(output) - 1,
        2, 25, "underscore overflow", 10
    );
    if (rejected != 0) return rejected;

    rejected = expect_rejection(
        bad_u64, sizeof(bad_u64) - 1, output, sizeof(output) - 1,
        2, 26, "u64 overflow", 11
    );
    if (rejected != 0) return rejected;

    return 0;
}
'''

        consumer = r'''
#include <stdint.h>
uint8_t answer(void);
int main(void) { return answer() == 42 ? 0 : 1; }
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-context-int-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            compiler_obj = root / "native_compiler.obj"
            driver_c = root / "driver.c"
            driver_obj = root / "driver.obj"
            driver_exe = root / ("context_int.exe" if os.name == "nt" else "context_int")
            generated_c = root / "context_good.c"
            generated_obj = root / "context_good.obj"
            consumer_c = root / "consumer.c"
            consumer_obj = root / "consumer.obj"
            consumer_exe = root / ("context_good_consumer.exe" if os.name == "nt" else "context_good_consumer")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            consumer_c.write_text(consumer, encoding="utf-8")

            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], driver_exe)

            result = subprocess.run(
                [str(driver_exe), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(generated_c.is_file())

            default_toolchain.compile_c_to_obj(generated_c, generated_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(consumer_c, consumer_obj, opt_level=0)
            default_toolchain.link_native_binary([generated_obj, consumer_obj], consumer_exe)
            run_consumer = subprocess.run(
                [str(consumer_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(run_consumer.returncode, 0, run_consumer.stderr)


if __name__ == "__main__":
    unittest.main()
