"""Guard and execute the bounded native static-impl semantic subset."""
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
    def test_qualified_static_calls_resolve_lower_and_execute(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        main_text = (module_dir / "main.sotlas").read_text(encoding="utf-8")
        sema_text = (module_dir / "sema.sotlas").read_text(encoding="utf-8")
        emitter_text = (module_dir / "emitter_c.sotlas").read_text(encoding="utf-8")

        # main.sotlas is orchestration only: the semantic ownership of bounded
        # static impls belongs to Sema, while lowering belongs to CEmitter.
        self.assertNotIn("LOWERED_SOURCE_BUFFER_CAPACITY", main_text)
        self.assertNotIn("g_lowered_source_buffer", main_text)
        self.assertNotIn("lower_native_static_impl_calls_to_c_symbols", main_text)
        self.assertNotIn("emit_native_static_impl_function", main_text)
        self.assertNotIn("emit_native_impl", main_text)
        self.assertNotIn("emit_native_module", main_text)
        self.assertNotIn("native_module_has_impl", main_text)
        self.assertNotIn("native_validate_static_impl_calls", main_text)
        self.assertNotIn("semantic_emitter", main_text)
        self.assertEqual(main_text.count("CEmitter::new("), 1)

        self.assertIn("pub fn check_impl_declaration", sema_text)
        self.assertIn("pub fn check_qualified_static_call", sema_text)
        self.assertIn("pub fn find_static_impl_method_for_path", sema_text)
        self.assertIn("pub fn path_matches_static_method", sema_text)
        self.assertIn("self.check_impl_declaration(", sema_text)
        self.assertIn("self.check_qualified_static_call(", sema_text)

        self.assertIn("pub fn find_static_impl_method_for_path", emitter_text)
        self.assertIn("pub fn emit_static_impl_symbol", emitter_text)
        self.assertIn("pub fn emit_impl", emitter_text)
        self.assertIn("self.find_static_impl_method_for_path(callee)", emitter_text)
        self.assertIn("self.emit_static_impl_symbol(method_index)", emitter_text)
        self.assertIn("self.emit_impl(child)", emitter_text)

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

static int expect_semantic_rejection(
    const uint8_t *source,
    size_t source_len,
    uint8_t *output,
    size_t output_len,
    const char *label,
    int code
) {
    uint32_t line = 999;
    uint32_t col = 999;
    size_t size = sotlas_native_compile_diagnostic(
        source, source_len, output, output_len, &line, &col
    );
    if (size != 0 || line == 0 || col == 0) {
        fprintf(stderr, "%s: size=%zu line=%u col=%u\n", label, size, line, col);
        return code;
    }
    return 0;
}

int main(int argc, char **argv) {
    static const uint8_t valid_zero[] =
        "module test::zero;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn zero() -> i32 { return 0; }\n"
        "}\n"
        "pub fn answer_zero() -> i32 { return Counter::zero(); }\n";
    static const uint8_t valid[] =
        "module test::valid;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
        " pub fn forty_two() -> i32 { return Counter::add(20, 22); }\n"
        "}\n"
        "pub fn answer() -> i32 { return Counter::forty_two(); }\n";
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
    static const uint8_t unknown_target[] =
        "module test::unknown_target;\n"
        "impl Missing {\n"
        " pub fn zero() -> i32 { return 0; }\n"
        "}\n";
    static const uint8_t duplicate_method[] =
        "module test::duplicate_method;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter { pub fn zero() -> i32 { return 0; } }\n"
        "impl Counter { pub fn zero() -> i32 { return 1; } }\n";
    static const uint8_t receiver[] =
        "module test::receiver;\n"
        "struct Counter { value: i32; }\n"
        "impl Counter {\n"
        " pub fn read(self: Counter) -> i32 { return 0; }\n"
        "}\n";

    uint8_t output[65536];
    uint32_t line = 999;
    uint32_t col = 999;

    if (argc != 2) return 10;

    size_t size = sotlas_native_compile_diagnostic(
        valid_zero, sizeof(valid_zero) - 1, output, sizeof(output) - 1, &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "valid zero-arity qualified call: size=%zu line=%u col=%u\n", size, line, col);
        return 11;
    }
    output[size] = 0;
    if (strstr((const char *)output, "Counter_zero(") == NULL) {
        fprintf(stderr, "missing lowered Counter_zero call\n");
        return 12;
    }

    line = 999;
    col = 999;
    size = sotlas_native_compile_diagnostic(
        valid, sizeof(valid) - 1, output, sizeof(output) - 1, &line, &col
    );
    if (size == 0 || line != 0 || col != 0) {
        fprintf(stderr, "valid qualified call: size=%zu line=%u col=%u\n", size, line, col);
        return 1;
    }
    output[size] = 0;
    if (strstr((const char *)output, "Counter_add(") == NULL
        || strstr((const char *)output, "Counter_forty_two(") == NULL) {
        fprintf(stderr, "missing canonical namespaced static calls\n");
        return 2;
    }

    FILE *file = fopen(argv[1], "wb");
    if (file == NULL) return 3;
    size_t written = fwrite(output, 1, size, file);
    fclose(file);
    if (written != size) return 4;

    int rejected = expect_semantic_rejection(
        missing, sizeof(missing) - 1, output, sizeof(output) - 1, "missing method", 5
    );
    if (rejected != 0) return rejected;
    rejected = expect_semantic_rejection(
        wrong_arity, sizeof(wrong_arity) - 1, output, sizeof(output) - 1, "wrong arity", 6
    );
    if (rejected != 0) return rejected;
    rejected = expect_semantic_rejection(
        unknown_target, sizeof(unknown_target) - 1, output, sizeof(output) - 1, "unknown impl target", 7
    );
    if (rejected != 0) return rejected;
    rejected = expect_semantic_rejection(
        duplicate_method, sizeof(duplicate_method) - 1, output, sizeof(output) - 1, "duplicate static method", 8
    );
    if (rejected != 0) return rejected;
    rejected = expect_semantic_rejection(
        receiver, sizeof(receiver) - 1, output, sizeof(output) - 1, "unsupported receiver", 9
    );
    if (rejected != 0) return rejected;
    return 0;
}
'''

        consumer = r'''
#include <stdint.h>
int32_t answer(void);
int main(void) { return answer() == 42 ? 0 : 1; }
'''

        with tempfile.TemporaryDirectory(prefix="sotlas-static-impl-call-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            exe = root / ("impl_call.exe" if os.name == "nt" else "impl_call")
            generated_c = root / "qualified_call.c"
            generated_obj = root / "qualified_call.obj"
            consumer_c = root / "consumer.c"
            consumer_obj = root / "consumer.obj"
            consumer_exe = root / ("qualified_call_consumer.exe" if os.name == "nt" else "qualified_call_consumer")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(driver, encoding="utf-8")
            consumer_c.write_text(consumer, encoding="utf-8")
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], exe)

            result = subprocess.run(
                [str(exe), str(generated_c)], capture_output=True, text=True, check=False
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
