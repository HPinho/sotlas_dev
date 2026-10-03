"""M16.4h2e2a explicit ABI classification for nominal payload enums."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2e2a_compile"


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
machine = importlib.import_module(f"{_PACKAGE}.machine_x86_64")
enum_abi = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_enum_abi"
)
aggregate_abi = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_aggregate_abi"
)


_SOURCE = """module test::owned_enum_payload_h2e2a;
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
        filename="<owned-enum-payload-h2e2a>",
    )
    checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
        checked
    )
    return target_ir_calls.lower_sir_to_typed_target_ir(
        checked_sir.module
    )


def _u64_nominal_target_ir():
    return {
        "schema": "sotlas.target-ir.v1",
        "struct_layouts": [{
            "name": "Token64",
            "fields": [{"name": "value", "type": "u64"}],
        }],
        "nominal_enum_payloads": {
            "MaybeToken64": {
                "tag_type": "u32",
                "storage": "tagged_union",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {
                        "name": "Some",
                        "discriminant": 1,
                        "payload_type": "Token64",
                        "payload_representation": "nominal_struct",
                    },
                ],
            },
        },
        "functions": [],
    }


def _wide_target_ir():
    return {
        "schema": "sotlas.target-ir.v1",
        "struct_layouts": [{
            "name": "Wide",
            "fields": [
                {"name": "head", "type": "u8"},
                {"name": "wide", "type": "u64"},
            ],
        }],
        "nominal_enum_payloads": {
            "MaybeWide": {
                "tag_type": "u32",
                "storage": "tagged_union",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {
                        "name": "Some",
                        "discriminant": 1,
                        "payload_type": "Wide",
                        "payload_representation": "nominal_struct",
                    },
                ],
            },
        },
        "functions": [],
    }


def _mixed_float_target_ir():
    return {
        "schema": "sotlas.target-ir.v1",
        "struct_layouts": [{
            "name": "Token",
            "fields": [{"name": "value", "type": "u32"}],
        }],
        "nominal_enum_payloads": {
            "MaybeMixed": {
                "tag_type": "u32",
                "storage": "tagged_union",
                "variants": [
                    {"name": "None", "discriminant": 0},
                    {
                        "name": "Float",
                        "discriminant": 1,
                        "payload_type": "f64",
                        "payload_representation": "scalar",
                    },
                    {
                        "name": "Some",
                        "discriminant": 2,
                        "payload_type": "Token",
                        "payload_representation": "nominal_struct",
                    },
                ],
            },
        },
        "functions": [],
    }


class SotlasOwnedEnumPayloadH2E2ATests(unittest.TestCase):
    def test_source_maybe_token_classifies_as_one_integer_eightbyte(self):
        plan = enum_abi.classify_x86_64_sysv_nominal_enums(
            _target_ir_from_source()
        )
        self.assertEqual(plan["schema"], "sotlas.nominal-enum-abi.x86_64-sysv.v1")
        self.assertEqual(len(plan["aggregates"]), 1)

        maybe = plan["aggregates"][0]
        self.assertEqual(maybe["kind"], "enum")
        self.assertEqual(maybe["name"], "MaybeToken")
        self.assertEqual(maybe["storage"], "tagged_union")
        self.assertEqual(maybe["size_bytes"], 8)
        self.assertEqual(maybe["alignment_bytes"], 4)
        self.assertEqual(maybe["classes"], ["INTEGER"])
        self.assertEqual(maybe["tag_offset_bytes"], 0)
        self.assertEqual(maybe["payload_offset_bytes"], 4)
        self.assertNotIn("transport", maybe)
        self.assertNotIn("registers", maybe)
        self.assertNotIn("sret", maybe)

    def test_sixteen_byte_enum_uses_two_integer_eightbytes(self):
        plan = enum_abi.classify_x86_64_sysv_nominal_enums(
            _u64_nominal_target_ir()
        )
        maybe = plan["aggregates"][0]
        self.assertEqual(maybe["size_bytes"], 16)
        self.assertEqual(maybe["alignment_bytes"], 8)
        self.assertEqual(maybe["classes"], ["INTEGER", "INTEGER"])

    def test_enum_larger_than_two_eightbytes_is_memory_class(self):
        plan = enum_abi.classify_x86_64_sysv_nominal_enums(
            _wide_target_ir()
        )
        maybe = plan["aggregates"][0]
        self.assertEqual(maybe["size_bytes"], 24)
        self.assertEqual(maybe["alignment_bytes"], 8)
        self.assertEqual(maybe["classes"], ["MEMORY"])

    def test_sse_payload_mix_remains_fail_closed(self):
        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "SSE/other payload classes wait for a later slice",
        ):
            enum_abi.classify_x86_64_sysv_nominal_enums(
                _mixed_float_target_ir()
            )

    def test_central_aggregate_classifier_is_not_opened_by_h2e2a(self):
        target_ir = _target_ir_from_source()
        classified = aggregate_abi.classify_x86_64_sysv_aggregates(target_ir)
        self.assertFalse(
            any(
                item.get("kind") == "enum"
                and item.get("name") == "MaybeToken"
                for item in classified["aggregates"]
            )
        )

    def test_compiler_and_tools_h2e2a_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "_machine_x86_64_enum_abi.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
