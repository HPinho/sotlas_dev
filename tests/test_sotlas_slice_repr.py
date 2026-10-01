"""M16.4f1 backend-neutral logical slice representation gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = ROOT / "tools"
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_slice_repr_compile"

sys.path.insert(0, str(TOOLS_ROOT))

from sotlas.sir.instructions import SIRFunction, SIRModule, SIRValue, ReturnInst
from sotlas.sir.slices import SliceViewFact


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
_target_calls = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_calls")
_slices = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_slices")


def _slice_sir(*, mutable: bool = False) -> SIRModule:
    module = SIRModule(name="slice_repr")
    data = SIRValue("data", "u32*")
    length = SIRValue("length", "usize")
    function = SIRFunction(
        name="inspect",
        parameters=[data, length],
        return_type="void",
    )
    function.add_block("0").add(ReturnInst())
    module.add_function(function)
    module.slice_view_facts = (
        SliceViewFact(
            function="inspect",
            name="values",
            element_type="u32",
            mutable=mutable,
            data=data,
            length=length,
            point_id="slice_view@1:1",
        ),
    )
    return module


class SotlasSliceRepresentationTests(unittest.TestCase):
    def test_sir_slice_fact_preserves_pointer_length_identity(self):
        module = _slice_sir()
        fact = module.slice_view_facts[0]
        self.assertEqual(fact.function, "inspect")
        self.assertEqual(fact.name, "values")
        self.assertEqual(fact.element_type, "u32")
        self.assertFalse(fact.mutable)
        self.assertEqual(fact.data.type_name, "u32*")
        self.assertEqual(fact.length.type_name, "usize")
        self.assertEqual(fact.logical_type, "&[u32]")

    def test_target_ir_attaches_logical_pointer_length_slice_view(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(_slice_sir())
        self.assertEqual(
            target_ir["slice_views"],
            [{
                "function": "inspect",
                "name": "values",
                "logical_type": "&[u32]",
                "element_type": "u32",
                "mutable": False,
                "data": "data",
                "length": "length",
                "representation": "pointer_length",
                "source_point_id": "slice_view@1:1",
            }],
        )
        self.assertIsNone(_slices.validate_target_ir_slice_views(target_ir))

    def test_mutable_slice_identity_is_preserved_without_layout_claim(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(
            _slice_sir(mutable=True)
        )
        view = target_ir["slice_views"][0]
        self.assertEqual(view["logical_type"], "&mut [u32]")
        self.assertTrue(view["mutable"])
        self.assertEqual(view["representation"], "pointer_length")
        for forbidden in (
            "size_bytes",
            "alignment_bytes",
            "data_offset_bytes",
            "length_offset_bytes",
            "abi_class",
            "register_class",
        ):
            self.assertNotIn(forbidden, view)

    def test_slice_view_rejects_target_byte_layout_and_abi_claims(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(_slice_sir())
        for key, value in (
            ("size_bytes", 16),
            ("alignment_bytes", 8),
            ("data_offset_bytes", 0),
            ("length_offset_bytes", 8),
            ("abi_class", "INTEGER_PAIR"),
        ):
            damaged = {
                **target_ir,
                "slice_views": [dict(target_ir["slice_views"][0])],
            }
            damaged["slice_views"][0][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    _slices.TargetIRSliceError,
                    "cannot carry target byte layout or ABI classification",
                ):
                    _slices.validate_target_ir_slice_views(damaged)

    def test_slice_data_and_length_types_are_proven(self):
        bad_data = _slice_sir()
        bad_data.slice_view_facts = (
            SliceViewFact(
                function="inspect",
                name="values",
                element_type="u32",
                mutable=False,
                data=SIRValue("data", "u64*"),
                length=SIRValue("length", "usize"),
                point_id="slice_view@1:1",
            ),
        )
        with self.assertRaisesRegex(
            _slices.TargetIRSliceError,
            "malformed slice view fact",
        ):
            _target_calls.lower_sir_to_typed_target_ir(bad_data)

        bad_length = _slice_sir()
        bad_length.slice_view_facts = (
            SliceViewFact(
                function="inspect",
                name="values",
                element_type="u32",
                mutable=False,
                data=SIRValue("data", "u32*"),
                length=SIRValue("length", "u64"),
                point_id="slice_view@1:1",
            ),
        )
        with self.assertRaisesRegex(
            _slices.TargetIRSliceError,
            "malformed slice view fact",
        ):
            _target_calls.lower_sir_to_typed_target_ir(bad_length)

    def test_target_ir_rejects_duplicate_slice_identity(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(_slice_sir())
        target_ir["slice_views"].append(dict(target_ir["slice_views"][0]))
        with self.assertRaisesRegex(
            _slices.TargetIRSliceError,
            "duplicate slice view",
        ):
            _slices.validate_target_ir_slice_views(target_ir)

    def test_compiler_and_tools_slice_paths_remain_identical(self):
        relatives = (
            Path("sotlas") / "sir" / "slices.py",
            Path("sotlas_compile") / "target_ir_slices.py",
            Path("sotlas_compile") / "target_ir_calls.py",
        )
        for relative in relatives:
            compiler_path = ROOT / "compiler" / relative
            tools_path = ROOT / "tools" / relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                str(relative),
            )


if __name__ == "__main__":
    unittest.main()
