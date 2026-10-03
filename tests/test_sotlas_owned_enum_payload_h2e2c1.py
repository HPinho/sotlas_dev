"""M16.4h2e2c1 explicit SysV transport gates for nominal payload enums."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2e2c1_compile"


def _load_package():
    package = sys.modules.get(_PACKAGE)
    if package is not None:
        return package
    spec = importlib.util.spec_from_file_location(
        _PACKAGE,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical sotlas_compile package")
    package = importlib.util.module_from_spec(spec)
    sys.modules[_PACKAGE] = package
    spec.loader.exec_module(package)
    return package


_load_package()
enum_transport = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_enum_transport"
)
aggregate_transport = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_aggregate_transport"
)
machine = importlib.import_module(f"{_PACKAGE}.machine_x86_64")


def _function(name, parameters, return_type="void"):
    return {
        "name": name,
        "parameters": [
            {"name": parameter_name, "type": parameter_type}
            for parameter_name, parameter_type in parameters
        ],
        "return_type": return_type,
        "blocks": [],
    }


def _target_ir(struct_name, fields, enum_name, functions):
    return {
        "schema": "sotlas.target-ir.v1",
        "struct_layouts": [{
            "name": struct_name,
            "fields": fields,
        }],
        "nominal_enum_payloads": {
            enum_name: {
                "tag_type": "u32",
                "storage": "tagged_union",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {
                        "name": "Some",
                        "discriminant": 1,
                        "payload_type": struct_name,
                        "payload_representation": "nominal_struct",
                    },
                ],
            },
        },
        "functions": functions,
    }


class SotlasOwnedEnumPayloadH2E2C1Tests(unittest.TestCase):
    def test_eight_byte_enum_uses_one_argument_and_return_register(self):
        target_ir = _target_ir(
            "Token",
            [{"name": "value", "type": "u32"}],
            "MaybeToken",
            [_function(
                "echo",
                [("value", "MaybeToken")],
                return_type="MaybeToken",
            )],
        )
        plan = enum_transport.plan_x86_64_sysv_nominal_enum_transport(
            target_ir
        )
        function = plan["functions"][0]
        self.assertFalse(function["sret"])
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rdi"]},
        )
        self.assertEqual(
            function["return"]["transport"],
            {"kind": "registers", "registers": ["rax"]},
        )

    def test_sixteen_byte_enum_uses_register_pairs(self):
        target_ir = _target_ir(
            "Token64",
            [{"name": "value", "type": "u64"}],
            "MaybeToken64",
            [_function(
                "roundtrip",
                [("value", "MaybeToken64")],
                return_type="MaybeToken64",
            )],
        )
        function = (
            enum_transport.plan_x86_64_sysv_nominal_enum_transport(
                target_ir
            )["functions"][0]
        )
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rdi", "rsi"]},
        )
        self.assertEqual(
            function["return"]["transport"],
            {"kind": "registers", "registers": ["rax", "rdx"]},
        )

    def test_memory_enum_uses_stack_and_sret_without_consuming_integer_register(self):
        target_ir = _target_ir(
            "Wide",
            [
                {"name": "head", "type": "u8"},
                {"name": "wide", "type": "u64"},
            ],
            "MaybeWide",
            [_function(
                "roundtrip",
                [("value", "MaybeWide"), ("tail", "u64")],
                return_type="MaybeWide",
            )],
        )
        function = (
            enum_transport.plan_x86_64_sysv_nominal_enum_transport(
                target_ir
            )["functions"][0]
        )
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
            {
                "kind": "stack",
                "stack_ordinal": 0,
                "size_bytes": 24,
                "alignment_bytes": 8,
                "reason": "memory_class",
            },
        )
        self.assertEqual(
            function["parameters"][1]["transport"],
            {"kind": "registers", "registers": ["rsi"]},
        )

    def test_register_exhaustion_spills_whole_two_eightbyte_enum(self):
        target_ir = _target_ir(
            "Token64",
            [{"name": "value", "type": "u64"}],
            "MaybeToken64",
            [_function(
                "pressure",
                [
                    ("a", "u64"),
                    ("b", "u64"),
                    ("c", "u64"),
                    ("d", "u64"),
                    ("e", "u64"),
                    ("value", "MaybeToken64"),
                    ("tail", "u64"),
                ],
            )],
        )
        parameters = (
            enum_transport.plan_x86_64_sysv_nominal_enum_transport(
                target_ir
            )["functions"][0]["parameters"]
        )
        value = next(item for item in parameters if item["name"] == "value")
        tail = next(item for item in parameters if item["name"] == "tail")
        self.assertEqual(value["transport"]["kind"], "stack")
        self.assertEqual(
            value["transport"]["reason"],
            "register_exhaustion",
        )
        self.assertEqual(value["transport"]["size_bytes"], 16)
        self.assertEqual(
            tail["transport"],
            {"kind": "registers", "registers": ["r9"]},
        )

    def test_explicit_planner_contains_no_machine_emission_claims(self):
        target_ir = _target_ir(
            "Token",
            [{"name": "value", "type": "u32"}],
            "MaybeToken",
            [_function(
                "echo",
                [("value", "MaybeToken")],
                return_type="MaybeToken",
            )],
        )
        rendered = repr(
            enum_transport.plan_x86_64_sysv_nominal_enum_transport(
                target_ir
            )
        )
        for forbidden in (
            "mov ",
            "call ",
            "ret ",
            "assembly",
            "opcode",
            "payload_extract",
            "enum_construct",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_central_transport_remains_closed_until_h2e2c2(self):
        target_ir = _target_ir(
            "Token",
            [{"name": "value", "type": "u32"}],
            "MaybeToken",
            [_function(
                "echo",
                [("value", "MaybeToken")],
                return_type="MaybeToken",
            )],
        )
        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "nominal payload enum transport waits for M16.4h2e2c",
        ):
            aggregate_transport.plan_x86_64_sysv_aggregate_transport(
                target_ir
            )

    def test_compiler_and_tools_h2e2c1_layers_remain_identical(self):
        relative = (
            Path("sotlas_compile")
            / "_machine_x86_64_enum_transport.py"
        )
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
