"""Require native struct semantics without widening the certified lowering surface."""
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


class SotlasNativeStructLiteralSemaTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_struct_semantics_stay_strict_and_lowering_stays_bounded(self):
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

static int expect_success(const char *name, const char *source) {
    uint8_t output[65536];
    uint32_t line = 999;
    uint32_t col = 999;
    size_t size = sotlas_native_compile_diagnostic(
        (const uint8_t *)source, strlen(source), output, sizeof(output), &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "%s: expected success, size=%zu line=%u col=%u\n",
                name, size, line, col);
        return 1;
    }
    return 0;
}

static int expect_emitter_boundary(const char *name, const char *source) {
    uint8_t output[65536];
    uint32_t line = 999;
    uint32_t col = 999;
    size_t size = sotlas_native_compile_diagnostic(
        (const uint8_t *)source, strlen(source), output, sizeof(output), &line, &col
    );
    if (size != 0 || line != 0 || col != 0) {
        fprintf(stderr, "%s: expected bounded emitter refusal, size=%zu line=%u col=%u\n",
                name, size, line, col);
        return 1;
    }
    return 0;
}

static int expect_semantic_failure(const char *name, const char *source) {
    uint8_t output[65536];
    uint32_t line = 999;
    uint32_t col = 999;
    size_t size = sotlas_native_compile_diagnostic(
        (const uint8_t *)source, strlen(source), output, sizeof(output), &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "%s: expected semantic failure, size=%zu line=%u col=%u\n",
                name, size, line, col);
        return 1;
    }
    return 0;
}

int main(void) {
    static const char valid_impl[] =
        "module test::valid_impl;\n"
        "struct Pair { a: i32; b: i32; }\n"
        "impl Pair {\n"
        " pub fn make() -> Pair { return Pair { a: 0, b: 1 }; }\n"
        "}\n";

    static const char valid_top_level_shape[] =
        "module test::valid_top_level_shape;\n"
        "struct Pair { a: i32; b: i32; }\n"
        "pub fn make() -> Pair { return Pair { a: 0, b: 1 }; }\n";

    static const char unknown_field[] =
        "module test::unknown_field;\n"
        "struct Pair { a: i32; b: i32; }\n"
        "pub fn make() -> Pair { return Pair { a: 0, c: 1 }; }\n";

    static const char duplicate_field[] =
        "module test::duplicate_field;\n"
        "struct Pair { a: i32; b: i32; }\n"
        "pub fn make() -> Pair { return Pair { a: 0, a: 1 }; }\n";

    static const char missing_field[] =
        "module test::missing_field;\n"
        "struct Pair { a: i32; b: i32; }\n"
        "pub fn make() -> Pair { return Pair { a: 0 }; }\n";

    static const char nested_type_mismatch[] =
        "module test::nested_type_mismatch;\n"
        "struct Span { line: u32; }\n"
        "struct Other { line: u32; }\n"
        "struct Holder { span: Span; }\n"
        "pub fn make() -> Holder { return Holder { span: Other { line: 0 } }; }\n";

    static const char array_count_mismatch[] =
        "module test::array_count_mismatch;\n"
        "struct Buffer { bytes: [u8; 4]; }\n"
        "pub fn make() -> Buffer { return Buffer { bytes: [0; 3] }; }\n";

    static const char array_nonzero_repeat[] =
        "module test::array_nonzero_repeat;\n"
        "struct Buffer { bytes: [u8; 4]; }\n"
        "pub fn make() -> Buffer { return Buffer { bytes: [1; 4] }; }\n";

    static const char return_type_mismatch[] =
        "module test::return_type_mismatch;\n"
        "struct Pair { a: i32; b: i32; }\n"
        "struct Other { a: i32; b: i32; }\n"
        "pub fn make() -> Other { return Pair { a: 0, b: 1 }; }\n";

    if (expect_success("valid_impl", valid_impl) != 0) return 1;
    if (expect_emitter_boundary("valid_top_level_shape", valid_top_level_shape) != 0) return 2;
    if (expect_semantic_failure("unknown_field", unknown_field) != 0) return 3;
    if (expect_semantic_failure("duplicate_field", duplicate_field) != 0) return 4;
    if (expect_semantic_failure("missing_field", missing_field) != 0) return 5;
    if (expect_semantic_failure("nested_type_mismatch", nested_type_mismatch) != 0) return 6;
    if (expect_semantic_failure("array_count_mismatch", array_count_mismatch) != 0) return 7;
    if (expect_semantic_failure("array_nonzero_repeat", array_nonzero_repeat) != 0) return 8;
    if (expect_semantic_failure("return_type_mismatch", return_type_mismatch) != 0) return 9;
    return 0;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-native-struct-sema-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            exe = root / ("struct_sema.exe" if os.name == "nt" else "struct_sema")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], exe)

            result = subprocess.run(
                [str(exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
