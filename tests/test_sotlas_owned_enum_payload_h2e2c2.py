"""M16.4h2e2c2 central SysV transport for nominal payload enums."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2e2c2_compile"


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


package = _load_package()
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")
aggregate_transport = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_aggregate_transport"
)
enum_transport = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_enum_transport"
)
aggregate_abi = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_aggregate_abi"
)


_SOURCE = """module test::owned_enum_payload_h2e2c2;
sole struct Token {
    value: u32;
}
enum MaybeToken {
    None = 0,
    Some(Token),
}
pub fn read_value(ptr: *mut Token) -> u32 {
    unsafe { return ptr.value; }
}
"""


def _target_ir_from_source():
    checked = package.analyze_source_phase1(
        _SOURCE,
        filename="<owned-enum-payload-h2e2c2>",
    )
    checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
        checked
    )
    return target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)


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
        "struct_layouts": [{"name": struct_name, "fields": fields}],
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


class SotlasOwnedEnumPayloadH2E2C2Tests(unittest.TestCase):
    def test_source_derived_enum_roundtrip_uses_central_argument_and_return_abi(self):
        target_ir = _target_ir_from_source()
        target_ir["functions"] = [
            _function(
                "echo",
                [("value", "MaybeToken")],
                return_type="MaybeToken",
            )
        ]

        plan = aggregate_transport.plan_x86_64_sysv_aggregate_transport(
            target_ir
        )
        function = plan["functions"][0]
        self.assertEqual(function["parameters"][0]["kind"], "enum")
        self.assertEqual(function["parameters"][0]["classes"], ["INTEGER"])
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rdi"]},
        )
        self.assertFalse(function["sret"])
        self.assertEqual(
            function["return"]["transport"],
            {"kind": "registers", "registers": ["rax"]},
        )

    def test_sixteen_byte_enum_uses_register_pairs_centrally(self):
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
        function = aggregate_transport.plan_x86_64_sysv_aggregate_transport(
            target_ir
        )["functions"][0]
        self.assertEqual(
            function["parameters"][0]["transport"],
            {"kind": "registers", "registers": ["rdi", "rsi"]},
        )
        self.assertEqual(
            function["return"]["transport"],
            {"kind": "registers", "registers": ["rax", "rdx"]},
        )

    def test_memory_enum_uses_stack_and_sret_in_central_plan(self):
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
        function = aggregate_transport.plan_x86_64_sysv_aggregate_transport(
            target_ir
        )["functions"][0]
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

    def test_register_exhaustion_spills_the_whole_enum_without_partial_use(self):
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
        parameters = aggregate_transport.plan_x86_64_sysv_aggregate_transport(
            target_ir
        )["functions"][0]["parameters"]
        value = next(item for item in parameters if item["name"] == "value")
        tail = next(item for item in parameters if item["name"] == "tail")
        self.assertEqual(value["transport"]["kind"], "stack")
        self.assertEqual(value["transport"]["reason"], "register_exhaustion")
        self.assertEqual(value["transport"]["size_bytes"], 16)
        self.assertEqual(
            tail["transport"],
            {"kind": "registers", "registers": ["r9"]},
        )

    def test_central_and_explicit_enum_planners_agree_on_enum_only_functions(self):
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
        central = aggregate_transport.plan_x86_64_sysv_aggregate_transport(
            target_ir
        )["functions"][0]
        explicit = enum_transport.plan_x86_64_sysv_nominal_enum_transport(
            target_ir
        )["functions"][0]
        self.assertEqual(central["sret"], explicit["sret"])
        self.assertEqual(
            [item["transport"] for item in central["parameters"]],
            [item["transport"] for item in explicit["parameters"]],
        )
        self.assertEqual(
            central["return"]["transport"],
            explicit["return"]["transport"],
        )

    def test_unsupported_payload_classes_remain_fail_closed(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "struct_layouts": [{
                "name": "Token",
                "fields": [{"name": "value", "type": "u32"}],
            }],
            "nominal_enum_payloads": {
                "MaybeFloat": {
                    "tag_type": "u32",
                    "storage": "tagged_union",
                    "variants": [
                        {"name": "None", "discriminant": 0},
                        {
                            "name": "Some",
                            "discriminant": 1,
                            "payload_type": "Token",
                            "payload_representation": "nominal_struct",
                        },
                        {
                            "name": "Float",
                            "discriminant": 2,
                            "payload_type": "f64",
                            "payload_representation": "scalar",
                        },
                    ],
                },
            },
            "functions": [],
        }
        with self.assertRaisesRegex(
            aggregate_transport._core.MachineBackendError,
            "SSE/other payload classes wait for a later slice",
        ):
            aggregate_abi.classify_x86_64_sysv_aggregates(target_ir)

    def test_transport_plan_does_not_claim_machine_emission(self):
        target_ir = _target_ir_from_source()
        target_ir["functions"] = [
            _function(
                "echo",
                [("value", "MaybeToken")],
                return_type="MaybeToken",
            )
        ]
        rendered = repr(
            aggregate_transport.plan_x86_64_sysv_aggregate_transport(
                target_ir
            )
        )
        for forbidden in ("assembly", "opcode", "payload_extract", "enum_construct"):
            self.assertNotIn(forbidden, rendered)

    def test_compiler_and_tools_transport_modules_remain_identical(self):
        relative = Path("sotlas_compile") / "_machine_x86_64_aggregate_transport.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_bytes(),
            (ROOT / "tools" / relative).read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
