"""Guard semantic resolution for the bounded native static-impl call subset."""
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


class SotlasNativeStaticImplCallSemanticsTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_qualified_static_calls_resolve_before_lowering(self):
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
    static const uint8_t valid[] =
        "module test::valid;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
        "}\n"
        "pub fn answer() -> i32 { return Counter::add(20, 22); }\n";
    static const uint8_t missing[] =
        "module test::missing;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
        "}\n"
        "pub fn answer() -> i32 { return Counter::missing(20, 22); }\n";
    static const uint8_t wrong_arity[] =
        "module test::arity;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
        "}\n"
        "pub fn answer() -> i32 { return Counter::add(20); }\n";

    uint8_t output[65536];
    uint32_t line = 999;
    uint32_t col = 999;

    size_t size = sotlas_native_compile_diagnostic(
        valid, sizeof(valid) - 1, output, sizeof(output), &line, &col
    );
    /* Semantic resolution succeeds, but ExprPath lowering is deliberately
       still fail-closed in this commit. */
    if (size != 0 || line != 0 || col != 0) {
        fprintf(stderr, "valid qualified call: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        missing, sizeof(missing) - 1, output, sizeof(output), &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "missing method: size=%zu line=%u col=%u\n", size, line, col);
        return 2;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        wrong_arity, sizeof(wrong_arity) - 1, output, sizeof(output), &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "wrong arity: size=%zu line=%u col=%u\n", size, line, col);
        return 3;
    }
    return 0;
}
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-static-impl-call-sema-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            exe = root / ("impl_call_sema.exe" if os.name == "nt" else "impl_call_sema")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], exe)

            result = subprocess.run([str(exe)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
