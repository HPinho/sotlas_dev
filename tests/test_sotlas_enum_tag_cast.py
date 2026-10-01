"""Phase-1 gates for the M16.4e2 nullary enum tag cast contract."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_enum_tag_cast_compile"


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


_load_compiler_package()
_phase1 = importlib.import_module(f"{_CANONICAL_PACKAGE}.phase1_pipeline")
_typed_ast = importlib.import_module(f"{_CANONICAL_PACKAGE}.typed_ast")


class SotlasEnumTagCastTests(unittest.TestCase):
    def test_phase1_accepts_direct_tag_only_enum_variant_to_u32(self):
        source = """
module test::enum_tag_cast;
pub enum Command {
    None = 0,
    Build = 7
}
pub fn command_build_tag() -> u32 {
    return Command::Build as u32;
}
"""
        checked = _phase1.analyze_source_phase1(
            source,
            filename="enum_tag_cast.sotlas",
        )
        enum = next(
            item for item in checked.semantic.typed_module.enums
            if item.name == "Command"
        )
        layout = _typed_ast.lower_enum_layout(enum)
        self.assertEqual(layout.storage, "tag_only")
        self.assertEqual(
            [(item.name, item.tag) for item in layout.variants],
            [("None", 0), ("Build", 7)],
        )

    def test_phase1_rejects_tagged_union_variant_to_u32(self):
        source = """
module test::enum_tagged_union_cast;
pub enum MaybeValue {
    None = 0,
    Some(u32)
}
pub fn none_tag() -> u32 {
    return MaybeValue::None as u32;
}
"""
        with self.assertRaisesRegex(
            _typed_ast.Phase1SemanticError,
            "enum tag cast requires tag_only enum",
        ):
            _phase1.analyze_source_phase1(
                source,
                filename="enum_tagged_union_cast.sotlas",
            )

    def test_phase1_keeps_non_u32_enum_cast_fail_closed(self):
        source = """
module test::enum_u64_cast;
pub enum Command {
    None = 0,
    Build = 7
}
pub fn command_build_tag() -> u64 {
    return Command::Build as u64;
}
"""
        with self.assertRaisesRegex(
            _typed_ast.Phase1SemanticError,
            "invalid cast from Command to u64",
        ):
            _phase1.analyze_source_phase1(
                source,
                filename="enum_u64_cast.sotlas",
            )

    def test_compiler_and_tools_enum_tag_typing_bridge_remain_identical(self):
        compiler_path = ROOT / "compiler" / "sotlas_compile" / "enum_typed_ast.py"
        tools_path = ROOT / "tools" / "sotlas_compile" / "enum_typed_ast.py"
        self.assertEqual(
            compiler_path.read_bytes(),
            tools_path.read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
