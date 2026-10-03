"""M16.4g1b x86-64 SysV aggregate argument/return transport gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_aggregate_transport_compile"


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
_transport = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_aggregate_transport"
)
_core = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_core")


def _function(name, parameters, return_type="void"):
    return {
        "name": name,
        "parameters": [
            {"name": parameter_name, "type": parameter_type}
            for parameter_name, parameter_type in parameters
        ],
        "return_type": return_type,
        "blocks": [{
            "label": "0",
            "instructions": [{"op": "return", "operands": [], "attributes": {}}],
        }],
    }


def _base_target_ir():
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "aggregate_transport",
        "functions": [],
        "limitations": [],
    }


def _pair_and_large_layouts():
    return [
        {
            "name": "Pair64",
            "fields": [
                {"name": "a", "type": "u64"},
                {"name": "b", "type": "u64"},
            ],
        },
        {
            "name": "Large",
            "fields": [
                {"name": "a", "type": "u64"},
                {"name": "b", "type": "u64"},
                {"name": "c", "type": "u64"},
            ],
        },
    ]


class SotlasX8664AggregateTransportTests(unittest.TestCase):
    def test_slice_pair_consumes_two_integer_argument_registers(self):
        target_ir = _base_target_ir()
        target_ir["functions"] = [_function(
            "read",
            [
                ("values__data", "u32*"),
                ("values__len", "usize"),
                ("tail", "u64"),
            ],
        )]
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

        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        function = plan["functions"][0]
        self.assertFalse(function["sret"])
        self.assertEqual(
            [(item["name"], item["transport"]) for item in function["parameters"]],
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

    def test_two_integer_struct_parameter_and_return_use_sysv_register_pairs(self):
        target_ir = _base_target_ir()
        target_ir["struct_layouts"] = _pair_and_large_layouts()
        target_ir["functions"] = [_function(
            "roundtrip",
            [("pair", "Pair64"), ("tail", "u32")],
            return_type="Pair64",
        )]

        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        function = plan["functions"][0]
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rdi", "rsi"]},
        )
        self.assertEqual(
            function["parameters"][1]["transport"],
            {"kind": "registers", "registers": ["rdx"]},
        )
        self.assertEqual(
            function["return"]["transport"],
            {"kind": "registers", "registers": ["rax", "rdx"]},
        )

    def test_register_exhaustion_rolls_back_whole_aggregate(self):
        target_ir = _base_target_ir()
        target_ir["struct_layouts"] = _pair_and_large_layouts()
        target_ir["functions"] = [_function(
            "pressure",
            [
                ("a", "u64"),
                ("b", "u64"),
                ("c", "u64"),
                ("d", "u64"),
                ("e", "u64"),
                ("pair", "Pair64"),
                ("tail", "u64"),
            ],
        )]

        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        parameters = plan["functions"][0]["parameters"]
        pair = next(item for item in parameters if item["name"] == "pair")
        tail = next(item for item in parameters if item["name"] == "tail")

        self.assertEqual(pair["transport"]["kind"], "stack")
        self.assertEqual(pair["transport"]["reason"], "register_exhaustion")
        self.assertEqual(pair["transport"]["size_bytes"], 16)
        self.assertNotIn("offset_bytes", pair["transport"])
        self.assertEqual(
            tail["transport"],
            {"kind": "registers", "registers": ["r9"]},
        )

    def test_memory_return_reserves_sret_and_shifts_integer_arguments(self):
        target_ir = _base_target_ir()
        target_ir["struct_layouts"] = _pair_and_large_layouts()
        target_ir["functions"] = [_function(
            "make_large",
            [("seed", "u64")],
            return_type="Large",
        )]

        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        function = plan["functions"][0]
        self.assertTrue(function["sret"])
        self.assertEqual(
            function["return"]["transport"],
            {
                "kind": "indirect",
                "sret_register": "rdi",
                "returns_pointer_in": "rax",
            },
        )
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rsi"]},
        )

    def test_memory_parameter_does_not_consume_integer_argument_register(self):
        target_ir = _base_target_ir()
        target_ir["struct_layouts"] = _pair_and_large_layouts()
        target_ir["functions"] = [_function(
            "consume_large",
            [("large", "Large"), ("tail", "u64")],
        )]

        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        parameters = plan["functions"][0]["parameters"]
        self.assertEqual(parameters[0]["transport"]["kind"], "stack")
        self.assertEqual(parameters[0]["transport"]["reason"], "memory_class")
        self.assertEqual(parameters[0]["transport"]["size_bytes"], 24)
        self.assertEqual(
            parameters[1]["transport"],
            {"kind": "registers", "registers": ["rdi"]},
        )

    def test_tag_only_enum_uses_single_integer_transport_slot(self):
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
        target_ir["functions"] = [_function(
            "echo_command",
            [("command", "Command")],
            return_type="Command",
        )]

        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        function = plan["functions"][0]
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rdi"]},
        )
        self.assertEqual(
            function["return"]["transport"],
            {"kind": "registers", "registers": ["rax"]},
        )

    def test_payload_enum_without_certified_byte_layout_remains_fail_closed(self):
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
        target_ir["functions"] = [_function(
            "echo",
            [("value", "MaybeValue")],
            return_type="MaybeValue",
        )]

        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "payload enum ABI classification requires certified tagged-union byte layout",
        ):
            _transport.plan_x86_64_sysv_aggregate_transport(target_ir)

    def test_slice_components_must_be_contiguous_parameters(self):
        target_ir = _base_target_ir()
        target_ir["functions"] = [_function(
            "bad",
            [
                ("values__data", "u32*"),
                ("other", "u64"),
                ("values__len", "usize"),
            ],
        )]
        target_ir["slice_views"] = [{
            "function": "bad",
            "name": "values",
            "logical_type": "&[u32]",
            "element_type": "u32",
            "mutable": False,
            "data": "values__data",
            "length": "values__len",
            "representation": "pointer_length",
            "source_point_id": "slice_view@1:1",
        }]
        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "data/length parameters must be contiguous",
        ):
            _transport.plan_x86_64_sysv_aggregate_transport(target_ir)

    def test_transport_plan_contains_no_machine_emission_claims(self):
        target_ir = _base_target_ir()
        target_ir["struct_layouts"] = _pair_and_large_layouts()
        target_ir["functions"] = [_function(
            "roundtrip",
            [("pair", "Pair64")],
            return_type="Pair64",
        )]
        plan = _transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        rendered = repr(plan)
        for forbidden in (
            "mov ",
            "call ",
            "ret ",
            "stack_offset_bytes",
            "assembly",
            "opcode",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_compiler_and_tools_transport_planner_remain_identical(self):
        relative = (
            Path("sotlas_compile")
            / "_machine_x86_64_aggregate_transport.py"
        )
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
