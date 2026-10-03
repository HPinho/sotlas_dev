"""M16.4h2e2b central ABI integration for nominal payload enums."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2e2b_compile"


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
transport = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_aggregate_transport"
)


_SOURCE = """module test::owned_enum_payload_h2e2b;
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
        filename="<owned-enum-payload-h2e2b>",
    )
    checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
        checked
    )
    return target_ir_calls.lower_sir_to_typed_target_ir(
        checked_sir.module
    )


def _echo_function():
    return {
        "name": "echo",
        "parameters": [{"name": "value", "type": "MaybeToken"}],
        "return_type": "MaybeToken",
        "blocks": [{
            "label": "0",
            "instructions": [{
                "op": "return",
                "operands": ["value"],
                "attributes": {},
            }],
        }],
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


class SotlasOwnedEnumPayloadH2E2BTests(unittest.TestCase):
    def test_central_classifier_contains_certified_nominal_enum(self):
        target_ir = _target_ir_from_source()
        explicit = enum_abi.classify_x86_64_sysv_nominal_enums(target_ir)
        central = aggregate_abi.classify_x86_64_sysv_aggregates(target_ir)

        maybe = next(
            item
            for item in central["aggregates"]
            if item.get("kind") == "enum"
            and item.get("name") == "MaybeToken"
        )
        self.assertEqual(maybe, explicit["aggregates"][0])
        self.assertEqual(maybe["storage"], "tagged_union")
        self.assertEqual(maybe["size_bytes"], 8)
        self.assertEqual(maybe["alignment_bytes"], 4)
        self.assertEqual(maybe["classes"], ["INTEGER"])
        self.assertEqual(maybe["payload_offset_bytes"], 4)

    def test_central_classification_still_contains_no_transport_claims(self):
        target_ir = _target_ir_from_source()
        central = aggregate_abi.classify_x86_64_sysv_aggregates(target_ir)
        maybe = next(
            item
            for item in central["aggregates"]
            if item.get("name") == "MaybeToken"
        )
        forbidden = {
            "transport",
            "registers",
            "argument_registers",
            "return_registers",
            "sret",
            "stack_ordinal",
        }
        self.assertFalse(forbidden & set(maybe))

    def test_unused_nominal_enum_does_not_block_existing_transport(self):
        target_ir = _target_ir_from_source()
        plan = transport.plan_x86_64_sysv_aggregate_transport(target_ir)
        names = {item["name"] for item in plan["functions"]}
        self.assertIn("read_value", names)

    def test_nominal_enum_parameter_and_return_wait_for_h2e2c(self):
        target_ir = _target_ir_from_source()
        target_ir["functions"] = [_echo_function()]

        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "nominal payload enum transport waits for M16.4h2e2c",
        ):
            transport.plan_x86_64_sysv_aggregate_transport(target_ir)

    def test_sse_payload_mix_remains_fail_closed_through_central_classifier(self):
        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "SSE/other payload classes wait for a later slice",
        ):
            aggregate_abi.classify_x86_64_sysv_aggregates(
                _mixed_float_target_ir()
            )

    def test_compiler_and_tools_h2e2b_paths_remain_identical(self):
        for relative in (
            "_machine_x86_64_enum_abi.py",
            "_machine_x86_64_aggregate_abi.py",
            "_machine_x86_64_aggregate_transport.py",
        ):
            path = Path("sotlas_compile") / relative
            self.assertEqual(
                (ROOT / "compiler" / path).read_text(encoding="utf-8"),
                (ROOT / "tools" / path).read_text(encoding="utf-8"),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
