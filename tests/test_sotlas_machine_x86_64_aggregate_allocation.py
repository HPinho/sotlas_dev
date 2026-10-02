"""M16.4g1c1 aggregate-aware x86-64 physical allocation gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_aggregate_allocation_compile"


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
_allocation = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_aggregate_allocation"
)
_scalar_plan = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_call_plan"
)


def _function(parameters):
    return {
        "name": "read",
        "parameters": [
            {"name": name, "type": type_name}
            for name, type_name in parameters
        ],
        "return_type": "void",
        "blocks": [{
            "label": "0",
            "instructions": [
                {"op": "return", "operands": [], "attributes": {}},
            ],
        }],
    }


def _target_ir(parameters, *, with_slice=True):
    target_ir = {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "aggregate_allocation",
        "functions": [_function(parameters)],
        "limitations": [],
    }
    if with_slice:
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
    return target_ir


class SotlasX8664AggregateAllocationTests(unittest.TestCase):
    def test_slice_transport_is_attached_to_physical_allocation(self):
        target_ir = _target_ir([
            ("values__data", "u32*"),
            ("values__len", "usize"),
            ("tail", "u64"),
        ])

        plan = _allocation.plan_x86_64_sysv_aggregate_allocation(target_ir)
        self.assertEqual(
            plan["aggregate_transport_schema"],
            "sotlas.aggregate-transport.x86_64-sysv.v1",
        )
        self.assertTrue(plan["aggregate_transport_active"])

        function = plan["functions"][0]
        transport = function["abi_transport"]
        self.assertEqual(
            [
                (item["name"], item["transport"])
                for item in transport["parameters"]
            ],
            [
                (
                    "values",
                    {"kind": "registers", "registers": ["rdi", "rsi"]},
                ),
                (
                    "tail",
                    {"kind": "registers", "registers": ["rdx"]},
                ),
            ],
        )
        self.assertEqual(function["aggregate_incoming_stack_units"], 0)
        self.assertEqual(function["aggregate_incoming_stack_bytes"], 0)

    def test_register_exhausted_slice_remains_one_stack_unit(self):
        target_ir = _target_ir([
            ("a", "u64"),
            ("b", "u64"),
            ("c", "u64"),
            ("d", "u64"),
            ("e", "u64"),
            ("values__data", "u32*"),
            ("values__len", "usize"),
            ("tail", "u64"),
        ])

        plan = _allocation.plan_x86_64_sysv_aggregate_allocation(target_ir)
        function = plan["functions"][0]
        parameters = function["abi_transport"]["parameters"]
        slice_unit = next(item for item in parameters if item["name"] == "values")
        tail = next(item for item in parameters if item["name"] == "tail")

        self.assertEqual(slice_unit["transport"]["kind"], "stack")
        self.assertEqual(
            slice_unit["transport"]["reason"],
            "register_exhaustion",
        )
        self.assertEqual(slice_unit["transport"]["size_bytes"], 16)
        self.assertEqual(
            tail["transport"],
            {"kind": "registers", "registers": ["r9"]},
        )
        self.assertEqual(function["aggregate_incoming_stack_units"], 1)
        self.assertEqual(function["aggregate_incoming_stack_bytes"], 16)

    def test_no_slice_keeps_legacy_allocation_shape_unchanged(self):
        target_ir = _target_ir(
            [("value", "u64")],
            with_slice=False,
        )
        legacy = _scalar_plan.plan_x86_64_sysv_allocation(target_ir)
        composed = _allocation.plan_x86_64_sysv_aggregate_allocation(target_ir)
        self.assertEqual(composed, legacy)
        self.assertNotIn("aggregate_transport_schema", composed)
        self.assertNotIn("abi_transport", composed["functions"][0])

    def test_compiler_and_tools_composition_remain_identical(self):
        relative = (
            Path("sotlas_compile")
            / "_machine_x86_64_aggregate_allocation.py"
        )
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
