"""Exercise native semantic typing for qualified static impl calls."""
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


class SotlasNativeStaticImplTypeTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_static_impl_calls_use_method_parameter_and_return_types(self):
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

int main(void) {
    static const uint8_t wrong_argument[] =
        "module test::static_arg;\n"
        "struct Box {\n"
        " value: u32,\n"
        "}\n"
        "impl Box {\n"
        " fn make(value: u32) -> Box { return Box { value: value }; }\n"
        "}\n"
        "fn bad(value: f32) -> Box { return Box::make(value); }\n";

    static const uint8_t wrong_return[] =
        "module test::static_return;\n"
        "struct Box {\n"
        " value: u32,\n"
        "}\n"
        "struct Other {\n"
        " value: u32,\n"
        "}\n"
        "impl Box {\n"
        " fn make(value: u32) -> Box { return Box { value: value }; }\n"
        "}\n"
        "fn bad(value: u32) -> Other { return Box::make(value); }\n";

    static const uint8_t good[] =
        "module test::static_good;\n"
        "struct Box {\n"
        " value: u32,\n"
        "}\n"
        "impl Box {\n"
        " fn make(value: u32) -> Box { return Box { value: value }; }\n"
        "}\n"
        "fn good(value: u32) -> Box { return Box::make(value); }\n";

    uint8_t output[65536];
    uint32_t line = 0;
    uint32_t col = 0;

    size_t size = sotlas_native_compile_diagnostic(
        wrong_argument, sizeof(wrong_argument) - 1,
        output, sizeof(output), &line, &col
    );
    if (size != 0 || line != 8 || col != 46) {
        fprintf(stderr, "wrong static argument: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }

    line = 0;
    col = 0;
    size = sotlas_native_compile_diagnostic(
        wrong_return, sizeof(wrong_return) - 1,
        output, sizeof(output), &line, &col
    );
    if (size != 0 || line != 11 || col != 38) {
        fprintf(stderr, "wrong static return: size=%zu line=%u col=%u\n", size, line, col);
        return 2;
    }

    line = 99;
    col = 99;
    size = sotlas_native_compile_diagnostic(
        good, sizeof(good) - 1,
        output, sizeof(output), &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "good static call: size=%zu line=%u col=%u\n", size, line, col);
        return 3;
    }
    return 0;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-native-static-types-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            compiler_obj = root / "native_compiler.obj"
            driver_c = root / "driver.c"
            driver_obj = root / "driver.obj"
            exe = root / ("static_types.exe" if os.name == "nt" else "static_types")

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
