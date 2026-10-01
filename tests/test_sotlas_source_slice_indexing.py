"""M16.4f3 source slice indexing and checked Target IR gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_slice_indexing_compile"


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
_canonical_sir = importlib.import_module(f"{_CANONICAL_PACKAGE}.canonical_sir")
_local_addressing = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.local_addressing"
)
_target_calls = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_calls")


def _source(
    *,
    element_type: str = "u32",
    index_type: str = "usize",
    index_expression: str = "index",
    mutable: bool = False,
) -> str:
    qualifier = "&mut " if mutable else "&"
    return f"""module slice_indexing;
fn read(values: {qualifier}[{element_type}], index: {index_type}) -> {element_type} {{
    return values[{index_expression}];
}}
"""


def _lower_preview(source: str):
    parsed = _bootstrap.parse(source, filename="<slice-index-preview>")
    sir = _canonical_sir.load_canonical_sir()
    generator_type = _local_addressing.make_local_addressing_generator(sir)
    module = generator_type(module_name=parsed.name).generate_from_ast(parsed)
    return parsed, module


class SotlasSourceSliceIndexingTests(unittest.TestCase):
    def test_runtime_usize_slice_index_emits_explicit_bounds_proof(self):
        _, module = _lower_preview(_source())
        function = module.functions[0]

        self.assertEqual(
            [(item.name, item.type_name) for item in function.parameters],
            [
                ("values__data", "u32*"),
                ("values__len", "usize"),
                ("index", "usize"),
            ],
        )
        self.assertIn("read", tuple(module.unlowered_functions))

        instructions = function.blocks[0].instructions
        self.assertEqual(
            [type(item).__name__ for item in instructions],
            [
                "AllocStackInst",
                "StoreInst",
                "AllocStackInst",
                "StoreInst",
                "AllocStackInst",
                "StoreInst",
                "BoundsCheckInst",
                "SliceElementAddressInst",
                "LoadInst",
                "ReturnInst",
            ],
        )

        bounds = instructions[6]
        projection = instructions[7]
        self.assertEqual(bounds.index.name, "index")
        self.assertEqual(bounds.index.type_name, "usize")
        self.assertEqual(bounds.length.name, "values__len")
        self.assertEqual(bounds.length.type_name, "usize")
        self.assertFalse(bounds.can_eliminate)

        self.assertEqual(projection.base.name, "values__data")
        self.assertEqual(projection.base.type_name, "u32*")
        self.assertIs(projection.index, bounds.index)
        self.assertIs(projection.length, bounds.length)
        self.assertEqual(projection.result.type_name, "u32*")
        self.assertEqual(projection.element_type, "u32")
        self.assertEqual(projection.bounds_policy, "checked")
        self.assertTrue(projection.point_id.startswith("slice_address@"))

    def test_slice_view_fact_and_index_projection_share_same_data_and_length(self):
        _, module = _lower_preview(_source(mutable=True, element_type="u16"))
        self.assertEqual(len(module.slice_view_facts), 1)
        fact = module.slice_view_facts[0]
        projection = next(
            item
            for item in module.functions[0].blocks[0].instructions
            if type(item).__name__ == "SliceElementAddressInst"
        )

        self.assertTrue(fact.mutable)
        self.assertEqual(fact.logical_type, "&mut [u16]")
        self.assertIs(projection.base, fact.data)
        self.assertIs(projection.length, fact.length)
        self.assertEqual(projection.element_type, fact.element_type)

    def test_slice_indexing_carries_no_target_layout_claim(self):
        _, module = _lower_preview(_source())
        projection = next(
            item
            for item in module.functions[0].blocks[0].instructions
            if type(item).__name__ == "SliceElementAddressInst"
        )
        for forbidden in (
            "size_bytes",
            "alignment_bytes",
            "stride_bytes",
            "offset_bytes",
            "abi_class",
            "register_class",
        ):
            self.assertFalse(hasattr(projection, forbidden), forbidden)

    def test_literal_index_remains_fail_closed_for_f3a(self):
        _, module = _lower_preview(_source(index_expression="0"))
        self.assertIn("read", tuple(module.unlowered_functions))
        self.assertEqual(tuple(getattr(module, "slice_view_facts", ())), ())
        self.assertFalse(
            any(
                type(item).__name__ == "SliceElementAddressInst"
                for item in module.functions[0].blocks[0].instructions
            )
        )

    def test_non_usize_runtime_index_remains_fail_closed(self):
        _, module = _lower_preview(_source(index_type="u32"))
        self.assertIn("read", tuple(module.unlowered_functions))
        self.assertEqual(tuple(getattr(module, "slice_view_facts", ())), ())
        self.assertFalse(
            any(
                type(item).__name__ == "BoundsCheckInst"
                for item in module.functions[0].blocks[0].instructions
            )
        )

    def test_target_ir_preserves_bounds_check_and_slice_address(self):
        _, module = _lower_preview(_source())
        target_ir = _target_calls.lower_sir_to_typed_target_ir(module)
        function = target_ir["functions"][0]
        instructions = function["blocks"][0]["instructions"]
        bounds = next(item for item in instructions if item["op"] == "bounds_check")
        projection = next(item for item in instructions if item["op"] == "slice_address")

        self.assertEqual(bounds["operands"], ["index", "values__len"])
        self.assertEqual(bounds["attributes"], {"can_eliminate": False})
        self.assertEqual(
            projection["operands"],
            ["values__data", "index", "values__len"],
        )
        self.assertEqual(projection["type"], "u32*")
        self.assertEqual(projection["attributes"]["element_type"], "u32")
        self.assertEqual(projection["attributes"]["bounds_policy"], "checked")
        self.assertTrue(
            projection["attributes"]["source_point_id"].startswith("slice_address@")
        )
        for forbidden in (
            "size_bytes",
            "alignment_bytes",
            "stride_bytes",
            "offset_bytes",
            "abi_class",
            "register_class",
        ):
            self.assertNotIn(forbidden, projection["attributes"])

        self.assertEqual(target_ir["slice_views"][0]["data"], "values__data")
        self.assertEqual(target_ir["slice_views"][0]["length"], "values__len")

    def test_target_ir_rejects_slice_address_without_matching_bounds_proof(self):
        _, module = _lower_preview(_source())
        block = module.functions[0].blocks[0]
        block.instructions = [
            item for item in block.instructions
            if type(item).__name__ != "BoundsCheckInst"
        ]
        with self.assertRaisesRegex(
            _target_calls.TargetIRLoweringError,
            "lacks a dominating bounds proof",
        ):
            _target_calls.lower_sir_to_typed_target_ir(module)

    def test_target_ir_rejects_non_usize_slice_length(self):
        _, module = _lower_preview(_source())
        projection = next(
            item
            for item in module.functions[0].blocks[0].instructions
            if type(item).__name__ == "SliceElementAddressInst"
        )
        projection.length.type_name = "u32"
        with self.assertRaisesRegex(
            _target_calls.TargetIRLoweringError,
            "malformed slice bounds proof|malformed slice projection facts",
        ):
            _target_calls.lower_sir_to_typed_target_ir(module)

    def test_compiler_and_tools_slice_indexing_paths_remain_identical(self):
        relatives = (
            Path("sotlas") / "sir" / "slices.py",
            Path("sotlas_compile") / "slice_source_generator.py",
            Path("sotlas_compile") / "target_ir_slice_indexing.py",
            Path("sotlas_compile") / "target_ir_calls.py",
        )
        for relative in relatives:
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
                str(relative),
            )


if __name__ == "__main__":
    unittest.main()
