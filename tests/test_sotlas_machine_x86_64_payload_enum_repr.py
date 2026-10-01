"""M16.4e3 scalar payload enum representation coverage."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_payload_enum_repr_compile"


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
_machine = importlib.import_module(f"{_CANONICAL_PACKAGE}.machine_x86_64")
_phase1 = importlib.import_module(f"{_CANONICAL_PACKAGE}.phase1_pipeline")
_canonical_sir = importlib.import_module(f"{_CANONICAL_PACKAGE}.canonical_sir")
_target_calls = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_calls")
_enums = importlib.import_module(f"{_CANONICAL_PACKAGE}.target_ir_enums")
_typed_ast = importlib.import_module(f"{_CANONICAL_PACKAGE}.typed_ast")


SOURCE = """
module test::payload_enum_repr;

pub enum MaybeValue {
    None = 0,
    Some(u32)
}

pub fn wrap(value: u32) -> MaybeValue {
    return MaybeValue::Some(value);
}
"""


class SotlasPayloadEnumRepresentationTests(unittest.TestCase):
    def _checked(
        self,
        source: str = SOURCE,
        filename: str = "payload_enum_repr.sotlas",
    ):
        return _phase1.analyze_source_phase1(source, filename=filename)

    def _checked_sir(
        self,
        source: str = SOURCE,
        filename: str = "payload_enum_repr.sotlas",
    ):
        checked = self._checked(source, filename)
        checked_sir, _ = _canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir.module

    def test_phase1_normalizes_implicit_payload_variant_discriminant(self):
        checked = self._checked()
        enum = next(
            item for item in checked.semantic.typed_module.enums
            if item.name == "MaybeValue"
        )
        layout = _typed_ast.lower_enum_layout(enum)
        self.assertEqual(layout.storage, "tagged_union")
        self.assertEqual(
            [
                (item.name, item.tag, item.payload_type.name if item.payload_type else None)
                for item in layout.variants
            ],
            [
                ("None", 0, None),
                ("Some", 1, "u32"),
            ],
        )

    def test_checked_source_preserves_payload_enum_identity_in_canonical_sir(self):
        module = self._checked_sir()
        self.assertEqual(tuple(module.unlowered_functions), ())
        self.assertEqual(len(module.payload_enum_facts), 1)

        declaration = module.payload_enum_facts[0]
        self.assertEqual(declaration.name, "MaybeValue")
        self.assertEqual(declaration.tag_type, "u32")
        self.assertEqual(declaration.storage, "tagged_union")
        self.assertEqual(
            [
                (item.name, item.discriminant, item.payload_type)
                for item in declaration.variants
            ],
            [
                ("None", 0, None),
                ("Some", 1, "u32"),
            ],
        )

        function = next(
            item for item in module.functions
            if item.name == "wrap"
        )
        instructions = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
        ]
        constructs = [
            instruction
            for instruction in instructions
            if type(instruction).__name__ == "EnumConstructInst"
        ]
        self.assertEqual(len(constructs), 1)
        construct = constructs[0]
        self.assertEqual(construct.enum_name, "MaybeValue")
        self.assertEqual(construct.variant, "Some")
        self.assertEqual(construct.discriminant, 1)
        self.assertEqual(construct.payload.name, "value")
        self.assertEqual(construct.payload.type_name, "u32")
        self.assertEqual(construct.payload_type, "u32")
        self.assertEqual(construct.result.type_name, "MaybeValue")
        self.assertTrue(construct.point_id.startswith("enum_construct@"))

    def test_target_ir_preserves_logical_tagged_union_without_byte_layout(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(
            self._checked_sir()
        )
        self.assertEqual(
            target_ir["enum_layouts"]["MaybeValue"],
            {
                "tag_type": "u32",
                "storage": "tagged_union",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {
                        "name": "Some",
                        "discriminant": 1,
                        "payload_type": "u32",
                    },
                ],
            },
        )

        function = next(
            item for item in target_ir["functions"]
            if item["name"] == "wrap"
        )
        self.assertEqual(function["return_type"], "MaybeValue")
        instructions = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        constructs = [
            instruction
            for instruction in instructions
            if instruction["op"] == "enum_construct"
        ]
        self.assertEqual(len(constructs), 1)
        construct = constructs[0]
        self.assertEqual(construct["type"], "MaybeValue")
        self.assertEqual(construct["operands"], ["value"])
        self.assertEqual(construct["attributes"]["enum"], "MaybeValue")
        self.assertEqual(construct["attributes"]["variant"], "Some")
        self.assertEqual(construct["attributes"]["discriminant"], 1)
        self.assertEqual(construct["attributes"]["payload_type"], "u32")
        self.assertFalse(
            {
                "size_bytes",
                "alignment_bytes",
                "offset_bytes",
                "payload_offset_bytes",
                "payload_size_bytes",
                "payload_alignment_bytes",
            }
            & set(construct["attributes"])
        )
        self.assertIsNone(
            _enums.validate_target_ir_enum_representation(target_ir)
        )

    def test_machine_backend_keeps_nominal_payload_enum_abi_fail_closed(self):
        with self.assertRaisesRegex(
            _machine.MachineBackendError,
            "MaybeValue",
        ):
            _machine.compile_source_to_x86_64_sysv_assembly(
                SOURCE,
                "payload_enum_repr.sotlas",
            )

    def test_non_parameter_payload_constructor_remains_unlowered(self):
        source = """
module test::payload_enum_literal;

pub enum MaybeValue {
    None = 0,
    Some(u32)
}

pub fn wrap() -> MaybeValue {
    return MaybeValue::Some(7);
}
"""
        module = self._checked_sir(
            source,
            "payload_enum_literal.sotlas",
        )
        self.assertEqual(len(module.payload_enum_facts), 1)
        self.assertIn("wrap", module.unlowered_functions)

    def test_target_ir_rejects_payload_byte_layout_claims(self):
        target_ir = _target_calls.lower_sir_to_typed_target_ir(
            self._checked_sir()
        )
        construct = next(
            instruction
            for function in target_ir["functions"]
            for block in function["blocks"]
            for instruction in block["instructions"]
            if instruction["op"] == "enum_construct"
        )
        construct["attributes"]["payload_offset_bytes"] = 4
        with self.assertRaisesRegex(
            _enums.TargetIREnumError,
            "cannot carry payload or target byte layout",
        ):
            _enums.validate_target_ir_enum_representation(target_ir)

    def test_compiler_and_tools_e3_paths_remain_identical(self):
        pairs = (
            ("sotlas/sir/enums.py", "sotlas/sir/enums.py"),
            (
                "sotlas_compile/canonical_sir.py",
                "sotlas_compile/canonical_sir.py",
            ),
            (
                "sotlas_compile/enum_source_generator.py",
                "sotlas_compile/enum_source_generator.py",
            ),
            (
                "sotlas_compile/target_ir_struct_fields.py",
                "sotlas_compile/target_ir_struct_fields.py",
            ),
            (
                "sotlas_compile/target_ir_enums.py",
                "sotlas_compile/target_ir_enums.py",
            ),
        )
        for compiler_relative, tools_relative in pairs:
            compiler_path = ROOT / "compiler" / compiler_relative
            tools_path = ROOT / "tools" / tools_relative
            self.assertEqual(
                compiler_path.read_text(encoding="utf-8"),
                tools_path.read_text(encoding="utf-8"),
                compiler_relative,
            )


if __name__ == "__main__":
    unittest.main()
