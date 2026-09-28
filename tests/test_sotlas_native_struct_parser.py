"""Exercise the bounded native aggregate parser/emitter subset."""
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


class SotlasNativeAggregateParserTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_explicit_enum_and_semicolon_struct_fields_lower_to_c11(self):
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
            fragments.append(
                emit_c(modules[name], mangle=False, include_preamble=False)
            )

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
        "enum Choice {\n"
        " Ready = 7,\n"
        " Done = 11,\n"
        "}\n"
        "struct Item {\n"
        " state: Choice;\n"
        " value: i32;\n"
        " next: u32;\n"
        "}\n";
    static const uint8_t comma_member[] =
        "module test::comma_member;\n"
        "struct Item {\n"
        " value: i32,\n"
        "}\n";
    static const uint8_t implicit_variant[] =
        "module test::implicit_variant;\n"
        "enum Choice {\n"
        " Ready,\n"
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
        fprintf(stderr, "represented aggregates: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }
    output[size] = 0;
    if (strstr((const char *)output, "typedef enum Choice {") == NULL
        || strstr((const char *)output, "Choice_Ready = 7") == NULL
        || strstr((const char *)output, "Choice_Done = 11") == NULL
        || strstr((const char *)output, "} Choice;") == NULL
        || strstr((const char *)output, "typedef struct Item {") == NULL
        || strstr((const char *)output, "Choice state;") == NULL
        || strstr((const char *)output, "int32_t value;") == NULL
        || strstr((const char *)output, "uint32_t next;") == NULL
        || strstr((const char *)output, "} Item;") == NULL) {
        fprintf(stderr, "generated aggregate declarations are incomplete\n");
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
        comma_member, sizeof(comma_member) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size != 0 || line != 3 || col != 2) {
        fprintf(stderr, "comma member: size=%zu line=%u col=%u\n", size, line, col);
        return 5;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        implicit_variant, sizeof(implicit_variant) - 1,
        output, sizeof(output) - 1, &line, &col
    );
    if (size != 0 || line != 3 || col != 2) {
        fprintf(stderr, "implicit enum: size=%zu line=%u col=%u\n", size, line, col);
        return 6;
    }
    return 0;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-native-aggregate-parser-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            exe = root / ("aggregate_parser.exe" if os.name == "nt" else "aggregate_parser")
            generated_c = root / "represented.c"
            generated_obj = root / "represented.obj"

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
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
            self.assertTrue(generated_obj.is_file())


if __name__ == "__main__":
    unittest.main()
