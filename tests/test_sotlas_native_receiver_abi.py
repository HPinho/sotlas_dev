"""End-to-end gate for the bounded native receiver ABI."""
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


class NativeReceiverAbiTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_const_and_mut_receiver_lowering_execute_and_enforce_mutability(self):
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

        positive = (
            "module test::receiver_abi;\n"
            "struct Counter { value: i32; }\n"
            "impl Counter {\n"
            "  pub fn get(self: &Self) -> i32 { return self.value; }\n"
            "  pub fn set(mut self: &mut Self, value: i32) { self.value = value; }\n"
            "}\n"
        )
        immutable_write = (
            "module test::receiver_immutable;\n"
            "struct Counter { value: i32; }\n"
            "impl Counter {\n"
            "  pub fn bad(self: &Self) { self.value = 9; }\n"
            "}\n"
        )

        with tempfile.TemporaryDirectory(prefix="sotlas-native-receiver-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            compiler_exe = root / ("native_compiler.exe" if os.name == "nt" else "native_compiler")
            source_file = root / "input.sotlas"
            generated_c = root / "generated.c"
            generated_obj = root / "generated.obj"
            caller_c = root / "caller.c"
            caller_obj = root / "caller.obj"
            app_exe = root / ("receiver.exe" if os.name == "nt" else "receiver")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(
                "#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
                "extern size_t sotlas_native_compile_diagnostic(const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *);\n"
                "int main(int argc, char **argv) {\n"
                "  if (argc != 3) return 90; FILE *in = fopen(argv[1], \"rb\"); if (!in) return 91;\n"
                "  fseek(in, 0, SEEK_END); long n = ftell(in); rewind(in); if (n < 0) return 92;\n"
                "  uint8_t *src = (uint8_t *)malloc((size_t)n); uint8_t *out = (uint8_t *)malloc(65536); if (!src || !out) return 93;\n"
                "  if (fread(src, 1, (size_t)n, in) != (size_t)n) return 94; fclose(in);\n"
                "  uint32_t line = 0, col = 0; size_t size = sotlas_native_compile_diagnostic(src, (size_t)n, out, 65536, &line, &col); free(src);\n"
                "  if (size == 0) { fprintf(stderr, \"%u:%u\\n\", line, col); free(out); return 2; }\n"
                "  FILE *dest = fopen(argv[2], \"wb\"); if (!dest) { free(out); return 95; } size_t written = fwrite(out, 1, size, dest); fclose(dest); free(out);\n"
                "  return written == size ? 0 : 96;\n}\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], compiler_exe)

            source_file.write_text(positive, encoding="utf-8")
            result = subprocess.run(
                [str(compiler_exe), str(source_file), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = generated_c.read_text(encoding="utf-8")
            self.assertIn("Counter_get(const Counter *self)", generated)
            self.assertIn("Counter_set(Counter *self, int32_t value)", generated)
            self.assertIn("self->value", generated)
            default_toolchain.compile_c_to_obj(generated_c, generated_obj, opt_level=0)

            caller_c.write_text(
                "#include <stdint.h>\n"
                "typedef struct Counter { int32_t value; } Counter;\n"
                "extern int32_t Counter_get(const Counter *self);\n"
                "extern void Counter_set(Counter *self, int32_t value);\n"
                "int main(void) { Counter c = { 1 }; Counter_set(&c, 42); return (c.value == 42 && Counter_get(&c) == 42) ? 0 : 1; }\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(caller_c, caller_obj, opt_level=0)
            default_toolchain.link_native_binary([generated_obj, caller_obj], app_exe)
            run = subprocess.run([str(app_exe)], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)

            source_file.write_text(immutable_write, encoding="utf-8")
            bad = subprocess.run(
                [str(compiler_exe), str(source_file), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad.returncode, 2)
            self.assertTrue(bad.stderr.startswith("4:"), bad.stderr)


if __name__ == "__main__":
    unittest.main()
