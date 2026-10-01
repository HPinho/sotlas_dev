"""M16.4f2b source-to-canonical-SIR slice representation gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_source_slice_compile"


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
_canonical_sir = importlib.import_module(f"{_CANONICAL_PACKAGE}.canonical_sir")
_local_addressing = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.local_addressing"
)
_target_calls = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_calls")


def _source(parameter_type: str = "&[u32]") -> str:
    return f"""module slice_demo;
fn inspect(values: {parameter_type}) -> void {{
    return;
}}
"""


def _lower_preview(source: str):
    parsed = _bootstrap.parse(source, filename="<slice-preview>")
    typed = _typed_ast.build_declaration_typed_ast(parsed)
    sir = _canonical_sir.load_canonical_sir()
    generator_type = _local_addressing.make_local_addressing_generator(sir)
    module = generator_type(module_name=parsed.name).generate_from_ast(parsed)
    return parsed, typed, module


class SotlasSourceSliceRepresentationTests(unittest.TestCase):
    def test_source_slice_parameter_becomes_pointer_length_sir_fact(self):
        parsed, typed, module = _lower_preview(_source())

        source_type = parsed.functions[0].params[0][1]
        semantic_type = typed.functions[0].params[0].type
        self.assertIsInstance(source_type, _bootstrap.SliceType)
        self.assertIsInstance(semantic_type, _typed_ast.SliceSemanticType)

        function = module.functions[0]
        self.assertEqual(
            [(item.name, item.type_name) for item in function.parameters],
            [("values__data", "u32*"), ("values__len", "usize")],
        )
        self.assertEqual(len(module.slice_view_facts), 1)
        fact = module.slice_view_facts[0]
        self.assertEqual(fact.function, "inspect")
        self.assertEqual(fact.name, "values")
        self.assertEqual(fact.element_type, "u32")
        self.assertFalse(fact.mutable)
        self.assertEqual(fact.data.name, "values__data")
        self.assertEqual(fact.data.type_name, "u32*")
        self.assertEqual(fact.length.name, "values__len")
        self.assertEqual(fact.length.type_name, "usize")
        self.assertTrue(fact.point_id.startswith("slice_view@"))

    def test_source_slice_stays_unlowered_until_executable_body_and_abi_exist(self):
        _, _, module = _lower_preview(_source())
        self.assertIn("inspect", tuple(module.unlowered_functions))

        function = module.functions[0]
        instructions = function.blocks[0].instructions
        self.assertEqual(
            [type(item).__name__ for item in instructions],
            [
                "AllocStackInst",
                "StoreInst",
                "AllocStackInst",
                "StoreInst",
                "ReturnInst",
            ],
        )

    def test_target_ir_preserves_source_slice_view_without_abi_claim(self):
        _, _, module = _lower_preview(_source())
        target_ir = _target_calls.lower_sir_to_typed_target_ir(module)
        function = target_ir["functions"][0]
        self.assertEqual(
            [(item["name"], item["type"]) for item in function["parameters"]],
            [("values__data", "u32*"), ("values__len", "usize")],
        )
        self.assertEqual(
            target_ir["slice_views"],
            [{
                "function": "inspect",
                "name": "values",
                "logical_type": "&[u32]",
                "element_type": "u32",
                "mutable": False,
                "data": "values__data",
                "length": "values__len",
                "representation": "pointer_length",
                "source_point_id": module.slice_view_facts[0].point_id,
            }],
        )
        for forbidden in (
            "size_bytes",
            "alignment_bytes",
            "data_offset_bytes",
            "length_offset_bytes",
            "abi_class",
            "register_class",
        ):
            self.assertNotIn(forbidden, target_ir["slice_views"][0])

    def test_mutable_source_slice_preserves_write_capability(self):
        _, _, module = _lower_preview(_source("&mut [u16]"))
        fact = module.slice_view_facts[0]
        self.assertTrue(fact.mutable)
        self.assertEqual(fact.element_type, "u16")
        self.assertEqual(fact.logical_type, "&mut [u16]")
        self.assertEqual(fact.data.type_name, "u16*")
        self.assertEqual(fact.length.type_name, "usize")

    def test_nontrivial_slice_body_remains_without_slice_view_fact(self):
        source = """module slice_demo;
fn inspect(values: &[u32]) -> void {
    values[0];
    return;
}
"""
        _, _, module = _lower_preview(source)
        self.assertIn("inspect", tuple(module.unlowered_functions))
        self.assertEqual(tuple(getattr(module, "slice_view_facts", ())), ())

    def test_production_checker_remains_fail_closed(self):
        parsed = _bootstrap.parse(_source(), filename="<slice-production>")
        with self.assertRaisesRegex(
            _bootstrap.SotlasBootstrapError,
            "executable slice lowering is not implemented yet",
        ):
            _bootstrap.check(parsed)

    def test_compiler_and_tools_source_slice_bridge_remain_identical(self):
        relatives = (
            Path("sotlas_compile") / "slice_source_generator.py",
            Path("sotlas_compile") / "local_addressing.py",
        )
        for relative in relatives:
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
                str(relative),
            )


if __name__ == "__main__":
    unittest.main()
