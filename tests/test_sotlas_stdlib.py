"""Testes da Biblioteca Padrão (stdlib) da Linguagem Sotlas."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = ROOT / "compiler" / "sotlas_compile" / "bootstrap.py"
SPEC = importlib.util.spec_from_file_location(
    "sotlas_stdlib_canonical_bootstrap", BOOTSTRAP_PATH
)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)


class SotlasStdlibTests(unittest.TestCase):
    def test_stdlib_primitives_parse_and_typecheck(self):
        source = (ROOT / "stdlib" / "core" / "primitives.sotlas").read_text(encoding="utf-8")
        module = bootstrap.parse(source, filename="<stdlib/primitives>")
        bootstrap.check(module)
        emitted = bootstrap.emit_c(module)
        self.assertIn("min_u32", emitted)
        self.assertIn("clamp_u32", emitted)
        self.assertIn("abs_i32", emitted)

    def test_stdlib_option_parses_and_typecheck(self):
        source = (ROOT / "stdlib" / "core" / "option.sotlas").read_text(encoding="utf-8")
        module = bootstrap.parse(source, filename="<stdlib/option>")
        bootstrap.check(module)
        emitted = bootstrap.emit_c(module)
        self.assertIn("OptionU32", emitted)
        self.assertIn("OptionI32", emitted)
        self.assertIn("OptionPtr", emitted)

    def test_stdlib_result_parses_and_typecheck(self):
        source = (ROOT / "stdlib" / "core" / "result.sotlas").read_text(encoding="utf-8")
        module = bootstrap.parse(source, filename="<stdlib/result>")
        bootstrap.check(module)
        emitted = bootstrap.emit_c(module)
        self.assertIn("ResultU32", emitted)
        self.assertIn("ResultI32", emitted)

    def test_stdlib_mem_parses_and_typecheck(self):
        source = (ROOT / "stdlib" / "core" / "mem.sotlas").read_text(encoding="utf-8")
        module = bootstrap.parse(source, filename="<stdlib/mem>")
        bootstrap.check(module)
        emitted = bootstrap.emit_c(module)
        self.assertIn("zero_memory", emitted)
        self.assertIn("copy_memory", emitted)
        self.assertIn("compare_memory", emitted)

    def test_stdlib_slice_and_string_parse_and_typecheck(self):
        slice_src = (ROOT / "stdlib" / "core" / "slice.sotlas").read_text(encoding="utf-8")
        str_src = (ROOT / "stdlib" / "core" / "string.sotlas").read_text(encoding="utf-8")
        mod_slice = bootstrap.parse(slice_src, filename="<stdlib/slice>")
        bootstrap.check(mod_slice)
        emitted_slice = bootstrap.emit_c(mod_slice)
        self.assertIn("ByteSlice", emitted_slice)

        alloc_src = (ROOT / "stdlib" / "core" / "alloc.sotlas").read_text(encoding="utf-8")
        mod_alloc = bootstrap.parse(alloc_src, filename="<stdlib/alloc>")
        bootstrap.check(mod_alloc)
        emitted_alloc = bootstrap.emit_c(mod_alloc)
        self.assertIn("Allocator", emitted_alloc)
        self.assertIn("allocator_alloc", emitted_alloc)
        self.assertIn("allocator_realloc", emitted_alloc)
        self.assertIn("allocator_free", emitted_alloc)
        self.assertIn("arena_as_allocator", emitted_alloc)

        mod_str = bootstrap.parse(str_src, filename="<stdlib/string>")
        bootstrap.check_with_imports(
            mod_str,
            {mod_alloc.name: mod_alloc},
        )
        emitted_str = bootstrap.emit_c(mod_str)
        self.assertIn("StringSlice", emitted_str)
        self.assertIn("string_equals", emitted_str)
        self.assertIn("string_new_in_arena", emitted_str)
        self.assertIn("string_new_with_allocator", emitted_str)
        self.assertIn("string_reserve", emitted_str)


if __name__ == "__main__":
    unittest.main()
