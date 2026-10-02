"""M16.4h1d Target IR aggregate ownership sidecar gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_aggregate_ownership_target_ir_compile"


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
aggregate = importlib.import_module(f"{_PACKAGE}.aggregate_ownership")
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")
target_ir_addressing = importlib.import_module(f"{_PACKAGE}.target_ir_addressing")


_SOURCE = """module test::aggregate_ownership_target_ir;
sole struct Token {
    value: u32;
}
struct Envelope {
    token: Token;
    count: u32;
}
pub fn read_count(ptr: *mut Envelope) -> u32 {
    unsafe { return ptr.count; }
}
"""


_UNUSED_SOURCE = """module test::aggregate_ownership_target_ir_unused;
sole struct Token {
    value: u32;
}
struct Envelope {
    token: Token;
    count: u32;
}
fn noop() -> void { return; }
"""


def _checked(source: str):
    checked = package.analyze_source_phase1(
        source,
        filename="<aggregate-ownership-target-ir>",
    )
    result, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
    return result.module


class SotlasAggregateOwnershipTargetIRTests(unittest.TestCase):
    def test_materialized_owned_field_reaches_target_ir_without_physical_claims(self):
        module = _checked(_SOURCE)
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)

        self.assertEqual(
            target_ir["aggregate_ownership_facts"],
            [{
                "kind": "struct_field",
                "struct": "Envelope",
                "field": "token",
                "field_type": "Token",
                "domain": "exclusive",
                "storage": "by_value",
            }],
        )
        fact = target_ir["aggregate_ownership_facts"][0]
        for forbidden in (
            "offset_bytes",
            "size_bytes",
            "alignment_bytes",
            "abi_class",
            "register_class",
            "cleanup",
            "drop",
            "move",
        ):
            self.assertNotIn(forbidden, fact)

        envelope = next(
            item for item in target_ir["struct_layouts"]
            if item["name"] == "Envelope"
        )
        token = next(
            item for item in envelope["fields"]
            if item["name"] == "token"
        )
        self.assertEqual(token["type"], "Token")
        self.assertEqual(token["representation"], "nominal_struct")
        self.assertIsNone(
            target_ir_addressing.validate_target_ir_addressing(target_ir)
        )

    def test_unused_owned_struct_fact_does_not_pollute_usage_driven_target_ir(self):
        module = _checked(_UNUSED_SOURCE)
        self.assertEqual(
            tuple(
                (
                    fact.struct_name,
                    fact.field_name,
                    fact.field_type,
                    fact.domain,
                    fact.storage,
                )
                for fact in module.aggregate_ownership_facts
            ),
            (("Envelope", "token", "Token", "exclusive", "by_value"),),
        )

        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)

        self.assertNotIn("struct_layouts", target_ir)
        self.assertNotIn("aggregate_ownership_facts", target_ir)

    def test_target_ir_layout_mismatch_with_ownership_fact_fails_closed(self):
        module = _checked(_SOURCE)
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)
        target_ir.pop("aggregate_ownership_facts")

        envelope = next(
            item for item in target_ir["struct_layouts"]
            if item["name"] == "Envelope"
        )
        token = next(
            item for item in envelope["fields"]
            if item["name"] == "token"
        )
        token["representation"] = "scalar"

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "does not match a nominal Target IR field",
        ):
            aggregate.attach_target_ir_aggregate_ownership(
                target_ir,
                module,
            )

    def test_missing_nominal_dependency_for_owned_field_fails_closed(self):
        module = _checked(_SOURCE)
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)
        target_ir.pop("aggregate_ownership_facts")
        target_ir["struct_layouts"] = [
            item for item in target_ir["struct_layouts"]
            if item["name"] != "Token"
        ]

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "is not declared in Target IR",
        ):
            aggregate.attach_target_ir_aggregate_ownership(
                target_ir,
                module,
            )

    def test_conflicting_existing_target_ir_sidecar_fails_closed(self):
        module = _checked(_SOURCE)
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)
        target_ir["aggregate_ownership_facts"] = [{"contradictory": True}]

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "conflicting aggregate ownership facts",
        ):
            aggregate.attach_target_ir_aggregate_ownership(
                target_ir,
                module,
            )

    def test_compiler_and_tools_layers_remain_identical(self):
        for relative in (
            Path("sotlas_compile") / "aggregate_ownership.py",
            Path("sotlas_compile") / "target_ir_calls.py",
        ):
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
                str(relative),
            )


if __name__ == "__main__":
    unittest.main()
