"""Exercise the bounded native parser/emitter impl subset."""
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


class SotlasNativeImplParserTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_static_method_lowers_to_namespaced_c11_while_unsupported_forms_fail_closed(self):
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
#include <string.h>

extern size_t sotlas_native_compile_diagnostic(
    const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *
);

int main(int argc, char **argv) {
    static const uint8_t represented[] =
        "module test::represented;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn zero() -> i32 { return 0; }\n"
        " pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
        "}\n";
    static const uint8_t unsupported_member[] =
        "module test::unsupported_member;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " struct Nested { value: i32; }\n"
        "}\n";
    static const uint8_t unsupported_receiver[] =
        "module test::unsupported_receiver;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn read(self: Counter) -> i32 { return 0; }\n"
        "}\n";
    static const uint8_t unsupported_target[] =
        "module test::unsupported_target;\n"
        "impl Ghost {\n"
        " pub fn zero() -> i32 { return 0; }\n"
        "}\n";
    static const uint8_t duplicate_method[] =
        "module test::duplicate_method;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn zero() -> i32 { return 0; }\n"
        " pub fn zero() -> i32 { return 0; }\n"
        "}\n";
    uint8_t output[65536];
    uint32_t line = 999;
    uint32_t col = 999;

    if (argc != 2) return 10;
    size_t size = sotlas_native_compile_diagnostic(
        represented, sizeof(represented) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "represented impl: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }
    output[size] = 0;
    if (strstr((const char *)output, "int32_t Counter_zero(") == NULL
        || strstr((const char *)output, "int32_t Counter_add(") == NULL) {
        fprintf(stderr, "missing namespaced static method\n");
        return 2;
    }

    FILE *file = fopen(argv[1], "wb");
    if (file == NULL) return 3;
    size_t written = fwrite(output, 1, size, file);
    fclose(file);
    if (written != size) return 4;

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        unsupported_member, sizeof(unsupported_member) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "unsupported impl member: size=%zu line=%u col=%u\n", size, line, col);
        return 5;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        unsupported_receiver, sizeof(unsupported_receiver) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "unsupported receiver: size=%zu line=%u col=%u\n", size, line, col);
        return 6;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        unsupported_target, sizeof(unsupported_target) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "unsupported impl target: size=%zu line=%u col=%u\n", size, line, col);
        return 7;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        duplicate_method, sizeof(duplicate_method) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "duplicate impl method: size=%zu line=%u col=%u\n", size, line, col);
        return 8;
    }
    return 0;
}
'''

        consumer = r'''
#include <stdint.h>
int32_t Counter_zero(void);
int32_t Counter_add(int32_t left, int32_t right);
int main(void) {
    if (Counter_zero() != 0) return 1;
    return Counter_add(20, 22) == 42 ? 0 : 2;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-native-impl-parser-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            exe = root / ("impl_parser.exe" if os.name == "nt" else "impl_parser")
            generated_c = root / "represented_impl.c"
            generated_obj = root / "represented_impl.obj"
            consumer_c = root / "consumer.c"
            consumer_obj = root / "consumer.obj"
            consumer_exe = root / ("impl_consumer.exe" if os.name == "nt" else "impl_consumer")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            consumer_c.write_text(consumer, encoding="utf-8")
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], exe)

            result = subprocess.run(
                [str(exe), str(generated_c)],
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