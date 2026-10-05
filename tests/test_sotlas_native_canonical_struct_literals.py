"""End-to-end gate for canonical native struct/array literal lowering."""
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


class CanonicalNativeStructLiteralTests(unittest.TestCase):
    @unittest.skipUnless(default_toolchain.is_available(), "native C toolchain unavailable")
    def test_top_level_nested_struct_and_zero_array_repeat_compile_and_execute(self):
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

        source = (
            "module test::canonical_literals;\n"
            "struct Span { line: u32; }\n"
            "struct Packet { span: Span; bytes: [u8; 4]; code: i32; }\n"
            "pub fn make() -> Packet { return Packet { span: Span { line: 7 }, bytes: [0; 4], code: 35 }; }\n"
        )

        with tempfile.TemporaryDirectory(prefix="sotlas-native-canonical-literals-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            driver_c = root / "driver.c"
            compiler_obj = root / "native_compiler.obj"
            driver_obj = root / "driver.obj"
            compiler_exe = root / ("native_compiler.exe" if os.name == "nt" else "native_compiler")
            generated_c = root / "generated.c"
            generated_obj = root / "generated.obj"
            caller_c = root / "caller.c"
            caller_obj = root / "caller.obj"
            app_exe = root / ("app.exe" if os.name == "nt" else "app")

            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            escaped = source.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            driver_c.write_text(
                "#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\n"
                "extern size_t sotlas_native_compile_diagnostic(const uint8_t *, size_t, uint8_t *, size_t, uint32_t *, uint32_t *);\n"
                "int main(int argc, char **argv) {\n"
                f"  static const uint8_t src[] = \"{escaped}\";\n"
                "  uint8_t output[65536]; uint32_t line = 0, col = 0;\n"
                "  size_t size = sotlas_native_compile_diagnostic(src, sizeof(src)-1, output, sizeof(output), &line, &col);\n"
                "  if (size == 0 || line != 0 || col != 0 || argc != 2) return 1;\n"
                "  FILE *f = fopen(argv[1], \"wb\"); if (!f) return 2;\n"
                "  size_t written = fwrite(output, 1, size, f); fclose(f);\n"
                "  return written == size ? 0 : 3;\n}\n",
                encoding="utf-8",
            )

            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], compiler_exe)
            compile_result = subprocess.run(
                [str(compiler_exe), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            generated = generated_c.read_text(encoding="utf-8")
            self.assertIn("(Packet){", generated)
            self.assertIn("(Span){", generated)
            self.assertIn(".bytes = {0}", generated)

            caller_c.write_text(
                "#include <stdint.h>\n"
                "typedef struct Span { uint32_t line; } Span;\n"
                "typedef struct Packet { Span span; uint8_t bytes[4]; int32_t code; } Packet;\n"
                "extern Packet make(void);\n"
                "int main(void) { Packet p = make(); return (p.span.line == 7 && p.bytes[0] == 0 && p.bytes[3] == 0 && p.code == 35) ? 0 : 1; }\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(generated_c, generated_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(caller_c, caller_obj, opt_level=0)
            default_toolchain.link_native_binary([generated_obj, caller_obj], app_exe)
            run = subprocess.run([str(app_exe)], capture_output=True, text=True, check=False)
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
