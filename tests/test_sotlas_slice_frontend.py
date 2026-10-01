"""M16.4f2 explicit slice frontend/Typed-AST identity gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_slice_frontend_compile"


def _load_compiler_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            COMPILER_PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(COMPILER_PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


_package = _load_compiler_package()
_bootstrap = _package.bootstrap
_typed_ast = importlib.import_module(f"{_CANONICAL_PACKAGE}.typed_ast")


def _parse(parameter_type: str):
    return _bootstrap.parse(
        f"""
module slice_demo;
fn inspect(values: {parameter_type}) -> void {{
}}
"""
    )


class SotlasSliceFrontendTests(unittest.TestCase):
    def test_parser_carries_immutable_slice_identity(self):
        module = _parse("&[u32]")
        type_info = module.functions[0].params[0][1]
        self.assertIsInstance(type_info, _bootstrap.SliceType)
        self.assertTrue(type_info.is_slice)
        self.assertTrue(type_info.pointer)
        self.assertTrue(type_info.is_reference)
        self.assertFalse(type_info.mutable)
        self.assertFalse(type_info.is_array)
        self.assertEqual(type_info.elem_type.name, "u32")
        self.assertEqual(type_info.display(), "&[u32]")

    def test_parser_carries_mutable_slice_identity(self):
        module = _parse("&mut [u16]")
        type_info = module.functions[0].params[0][1]
        self.assertIsInstance(type_info, _bootstrap.SliceType)
        self.assertTrue(type_info.mutable)
        self.assertEqual(type_info.elem_type.name, "u16")
        self.assertEqual(type_info.display(), "&mut [u16]")

    def test_reference_to_fixed_array_keeps_existing_identity(self):
        module = _parse("&[u32; 4]")
        type_info = module.functions[0].params[0][1]
        self.assertNotIsInstance(type_info, _bootstrap.SliceType)
        self.assertTrue(type_info.pointer)
        self.assertTrue(type_info.is_reference)
        self.assertTrue(type_info.is_array)
        self.assertEqual(type_info.array_size, 4)
        self.assertIsNotNone(type_info.elem_type)
        self.assertEqual(type_info.elem_type.name, "u32")

    def test_slice_element_subset_is_fail_closed(self):
        with self.assertRaisesRegex(
            _bootstrap.SotlasBootstrapError,
            "slice element must be one direct unsigned scalar",
        ):
            _parse("&[i32]")

    def test_slice_and_plain_reference_are_distinct_types(self):
        slice_type = _parse("&[u32]").functions[0].params[0][1]
        reference_type = _parse("&u32").functions[0].params[0][1]
        self.assertFalse(_bootstrap.same_type(slice_type, reference_type))
        self.assertFalse(_bootstrap.same_type(reference_type, slice_type))
        self.assertFalse(_bootstrap.assignable(reference_type, slice_type))
        self.assertFalse(_bootstrap.assignable(slice_type, reference_type))

    def test_mutable_slice_coerces_only_toward_immutable_slice(self):
        mutable = _parse("&mut [u32]").functions[0].params[0][1]
        immutable = _parse("&[u32]").functions[0].params[0][1]
        self.assertTrue(_bootstrap.assignable(mutable, immutable))
        self.assertFalse(_bootstrap.assignable(immutable, mutable))
        self.assertTrue(_bootstrap.same_type(immutable, immutable))
        self.assertFalse(_bootstrap.same_type(mutable, immutable))

    def test_typed_ast_preserves_slice_identity(self):
        module = _parse("&[u32]")
        typed_module = _typed_ast.build_declaration_typed_ast(module)
        parameter = typed_module.functions[0].params[0]
        type_info = parameter.type
        self.assertIsInstance(type_info, _typed_ast.SliceSemanticType)
        self.assertTrue(type_info.is_slice)
        self.assertTrue(type_info.pointer)
        self.assertTrue(type_info.is_reference)
        self.assertFalse(type_info.mutable)
        self.assertIsNotNone(type_info.elem_type)
        self.assertEqual(type_info.elem_type.name, "u32")
        self.assertNotEqual(
            type_info,
            _typed_ast.SemanticType(
                "u32",
                pointer=True,
                is_reference=True,
            ),
        )

    def test_production_check_remains_fail_closed_until_slice_lowering(self):
        module = _parse("&[u32]")
        with self.assertRaisesRegex(
            _bootstrap.SotlasBootstrapError,
            "executable slice lowering is not implemented yet",
        ):
            _bootstrap.check(module)

    def test_c11_rendering_cannot_drop_slice_length(self):
        type_info = _parse("&[u32]").functions[0].params[0][1]
        with self.assertRaisesRegex(
            _bootstrap.SotlasBootstrapError,
            "executable slice lowering is not implemented yet",
        ):
            type_info.c_decl("values")

    def test_compiler_and_tools_slice_frontend_remain_identical(self):
        compiler_path = ROOT / "compiler" / "sotlas_compile" / "slice_frontend.py"
        tools_path = ROOT / "tools" / "sotlas_compile" / "slice_frontend.py"
        self.assertEqual(
            compiler_path.read_text(encoding="utf-8"),
            tools_path.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
