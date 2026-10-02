"""M16.4g1a x86-64 SysV aggregate ABI classification gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_aggregate_abi_compile"


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
_abi = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_aggregate_abi")
_core = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_core")


def _base_target_ir():
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "aggregate_abi",
        "functions": [],
        "limitations": [],
    }


class SotlasX8664AggregateABIClassificationTests(unittest.TestCase):
    def test_slice_is_two_integer_eightbytes_without_register_assignment(self):
        target_ir = _base_target_ir()
        target_ir["functions"] = [{
            "name": "read",
            "parameters": [
                {"name": "values__data", "type": "u32*"},
                {"name": "values__len", "type": "usize"},
            ],
            "return_type": "void",
            "blocks": [{"label": "0", "instructions": [
                {"op": "return", "operands": [], "attributes": {}}
            ]}],
        }]
        target_ir["slice_views"] = [{
            "function": "read",
            "name": "values",
            "logical_type": "&[u32]",
            "element_type": "u32",
            "mutable": False,
            "data": "values__data",
            "length": "values__len",
            "representation": "pointer_length",
            "source_point_id": "slice_view@1:1",
        }]
        plan = _abi.classify_x86_64_sysv_aggregates(target_ir)
        self.assertEqual(plan["schema"], "sotlas.aggregate-abi.x86_64-sysv.v1")
        classified = plan["aggregates"][0]
        self.assertEqual(classified["kind"], "slice")
        self.assertEqual(classified["size_bytes"], 16)
        self.assertEqual(classified["alignment_bytes"], 8)
        self.assertEqual(classified["classes"], ["INTEGER", "INTEGER"])
        self.assertEqual(
            [(item["source"], item["value"]) for item in classified["eightbytes"]],
            [("data", "values__data"), ("length", "values__len")],
        )
        rendered = repr(classified)
        for forbidden in ("rdi", "rsi", "rax", "stack_offset", "register"):
            self.assertNotIn(forbidden, rendered)

    def test_scalar_struct_classes_follow_existing_machine_layout(self):
        target_ir = _base_target_ir()
        target_ir["struct_layouts"] = [
            {"name": "Tiny", "fields": [
                {"name": "a", "type": "u32"},
                {"name": "b", "type": "u32"},
            ]},
            {"name": "Pair64", "fields": [
                {"name": "a", "type": "u64"},
                {"name": "b", "type": "u64"},
            ]},
            {"name": "Large", "fields": [
                {"name": "a", "type": "u64"},
                {"name": "b", "type": "u64"},
                {"name": "c", "type": "u64"},
            ]},
        ]
        plan = _abi.classify_x86_64_sysv_aggregates(target_ir)
        by_name = {
            item["name"]: item
            for item in plan["aggregates"]
            if item["kind"] == "struct"
        }
        self.assertEqual(by_name["Tiny"]["size_bytes"], 8)
        self.assertEqual(by_name["Tiny"]["classes"], ["INTEGER"])
        self.assertEqual(by_name["Pair64"]["size_bytes"], 16)
        self.assertEqual(by_name["Pair64"]["classes"], ["INTEGER", "INTEGER"])
        self.assertEqual(by_name["Large"]["size_bytes"], 24)
        self.assertEqual(by_name["Large"]["classes"], ["MEMORY"])
        self.assertEqual(
            [field["offset_bytes"] for field in by_name["Large"]["field_offsets"]],
            [0, 8, 16],
        )

    def test_tag_only_u32_enum_is_one_integer_class(self):
        target_ir = _base_target_ir()
        target_ir["enum_declarations"] = [{
            "name": "Command",
            "tag_type": "u32",
            "storage": "tag_only",
            "variants": [
                {"name": "None", "discriminant": 0},
                {"name": "Build", "discriminant": 7},
            ],
        }]
        plan = _abi.classify_x86_64_sysv_aggregates(target_ir)
        classified = plan["aggregates"][0]
        self.assertEqual(classified["kind"], "enum")
        self.assertEqual(classified["size_bytes"], 4)
        self.assertEqual(classified["alignment_bytes"], 4)
        self.assertEqual(classified["classes"], ["INTEGER"])

    def test_payload_enum_remains_fail_closed_without_byte_layout(self):
        target_ir = _base_target_ir()
        target_ir["enum_declarations"] = [{
            "name": "MaybeValue",
            "tag_type": "u32",
            "storage": "tagged_union",
            "variants": [
                {"name": "None", "discriminant": 0},
                {"name": "Some", "discriminant": 1, "payload_type": "u32"},
            ],
        }]
        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "payload enum ABI classification requires certified tagged-union byte layout",
        ):
            _abi.classify_x86_64_sysv_aggregates(target_ir)

    def test_malformed_slice_view_fails_closed(self):
        target_ir = _base_target_ir()
        target_ir["slice_views"] = [{
            "function": "missing",
            "name": "values",
            "logical_type": "&[u32]",
            "element_type": "u32",
            "mutable": False,
            "data": "data",
            "length": "len",
            "representation": "pointer_length",
            "source_point_id": "slice_view@1:1",
        }]
        with self.assertRaises(_core.MachineBackendError):
            _abi.classify_x86_64_sysv_aggregates(target_ir)

    def test_compiler_and_tools_classifier_remain_identical(self):
        relative = Path("sotlas_compile") / "_machine_x86_64_aggregate_abi.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
