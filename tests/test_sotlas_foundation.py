"""Testes unitários para a biblioteca padrão hospedada (sotlas-foundation)."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas import compile_source
from sotlas_compile import bootstrap, emit_c_project


class SotlasFoundationTests(unittest.TestCase):
    def setUp(self):
        self.foundation_dir = ROOT / "stdlib" / "foundation"

    def test_alloc_module_parses_and_compiles(self):
        alloc_path = self.foundation_dir / "alloc.sotlas"
        self.assertTrue(alloc_path.exists())
        text = alloc_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(alloc_path))
        self.assertIn("ArenaAllocator", c_code)
        self.assertIn("MemoryBlock", c_code)

    def test_vec_module_parses_and_compiles(self):
        vec_path = self.foundation_dir / "vec.sotlas"
        self.assertTrue(vec_path.exists())
        text = vec_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(vec_path))
        self.assertIn("VecU32", c_code)
        self.assertIn("push", c_code)
        self.assertIn("pop", c_code)

    def test_generic_vec_module_parses_and_typechecks(self):
        generic_vec_path = self.foundation_dir / "generic_vec.sotlas"
        self.assertTrue(generic_vec_path.exists())
        text = generic_vec_path.read_text(encoding="utf-8")
        module = bootstrap.parse(text, str(generic_vec_path))
        bootstrap.check(module)
        self.assertTrue(module.structs[0].has_generic_parameters)

    def test_generic_vec_backend_rejects_uninstantiated_template(self):
        generic_vec_path = self.foundation_dir / "generic_vec.sotlas"
        with self.assertRaisesRegex(
            Exception,
            "C11 backend does not support generic struct monomorphization yet: Vec",
        ):
            compile_source(
                generic_vec_path.read_text(encoding="utf-8"),
                str(generic_vec_path),
            )

    def test_generic_vec_native_instantiation_fails_closed_until_monomorphization(self):
        """The frontend rejects unsupported generic method calls with a clear error."""
        with tempfile.TemporaryDirectory(prefix="sotlas-generic-vec-") as temporary:
            project = Path(temporary)
            (project / "core").mkdir()
            (project / "foundation").mkdir()
            (project / "foundation" / "generic_vec.sotlas").write_text(
                (self.foundation_dir / "generic_vec.sotlas").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            source = project / "core" / "main.sotlas"
            source.write_text("""\
module core::main;
import foundation::generic_vec::*;

pub fn exercise(storage: *mut u32) -> bool {
    let mut values: Vec forge<u32> = Vec::with_capacity(2, storage);
    if !values.push(17u32) {
        return false;
    }
    return values.len() == 1;
}
""", encoding="utf-8")
            with self.assertRaisesRegex(
                Exception,
                "C11 generic method specialization is not implemented: "
                "Vec.with_capacity|C11 backend does not support generic struct "
                "monomorphization yet: Vec",
            ):
                emit_c_project(source, project / "build" / "main.c")

    def test_string_buf_module_parses_and_compiles(self):
        sb_path = self.foundation_dir / "string_buf.sotlas"
        self.assertTrue(sb_path.exists())
        text = sb_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(sb_path))
        self.assertIn("StringBuf", c_code)
        self.assertIn("append_str", c_code)

    def test_hashmap_module_parses_and_compiles(self):
        hm_path = self.foundation_dir / "hashmap.sotlas"
        self.assertTrue(hm_path.exists())
        text = hm_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(hm_path))
        self.assertIn("HashMapU64", c_code)
        self.assertIn("OptionU64", c_code)
        self.assertIn("hash_key", c_code)
        self.assertIn("insert", c_code)

    def test_file_module_parses_and_compiles(self):
        f_path = self.foundation_dir / "file.sotlas"
        self.assertTrue(f_path.exists())
        text = f_path.read_text(encoding="utf-8")
        c_code = compile_source(text, str(f_path))
        self.assertIn("File", c_code)
        self.assertIn("FileMode", c_code)


if __name__ == "__main__":
    unittest.main()
