"""M16.4h2d1 explicit Target IR ownership projection for enum payloads."""
from __future__ import annotations

import copy
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2d1_compile"


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
h2d = importlib.import_module(f"{_PACKAGE}.aggregate_ownership_h2d")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")


_SOURCE = """module test::owned_enum_payload_h2d1;
sole struct Token {
    value: u32;
}
struct Envelope {
    token: Token;
    count: u32;
}
enum MaybeToken {
    None = 0,
    Some(Token),
}
fn noop() -> void { return; }
"""


class SotlasOwnedEnumPayloadH2D1Tests(unittest.TestCase):
    def _checked_sir(self):
        checked = package.analyze_source_phase1(
            _SOURCE,
            filename="<owned-enum-payload-h2d1>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
            checked
        )
        return checked_sir

    def test_explicit_bridge_is_idempotent_after_h2d2_auto_projection(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(
            checked_sir.module
        )

        before = copy.deepcopy(
            tuple(target_ir.get("aggregate_ownership_facts", ()) or ())
        )
        self.assertTrue(
            any(item.get("kind") == "enum_payload" for item in before)
        )

        h2d.attach_target_ir_enum_payload_ownership(
            target_ir,
            checked_sir.module,
        )

        self.assertEqual(
            tuple(target_ir.get("aggregate_ownership_facts", ()) or ()),
            before,
        )
        enum_facts = [
            item
            for item in target_ir["aggregate_ownership_facts"]
            if item.get("kind") == "enum_payload"
        ]
        self.assertEqual(
            enum_facts,
            [{
                "kind": "enum_payload",
                "enum": "MaybeToken",
                "variant": "Some",
                "payload_type": "Token",
                "domain": "exclusive",
                "storage": "by_value",
            }],
        )

    def test_projection_has_no_physical_runtime_or_abi_claims(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(
            checked_sir.module
        )
        h2d.attach_target_ir_enum_payload_ownership(
            target_ir,
            checked_sir.module,
        )

        fact = next(
            item
            for item in target_ir["aggregate_ownership_facts"]
            if item.get("kind") == "enum_payload"
        )
        forbidden = {
            "offset_bytes",
            "size_bytes",
            "alignment_bytes",
            "payload_offset_bytes",
            "payload_size_bytes",
            "payload_alignment_bytes",
            "abi_class",
            "register_class",
            "cleanup",
            "drop",
            "move",
            "destroy",
        }
        self.assertFalse(forbidden & set(fact))

    def test_bridge_is_idempotent(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(
            checked_sir.module
        )

        h2d.attach_target_ir_enum_payload_ownership(
            target_ir,
            checked_sir.module,
        )
        first = copy.deepcopy(target_ir["aggregate_ownership_facts"])
        h2d.attach_target_ir_enum_payload_ownership(
            target_ir,
            checked_sir.module,
        )
        self.assertEqual(target_ir["aggregate_ownership_facts"], first)

    def test_nominal_payload_mismatch_remains_fail_closed(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(
            checked_sir.module
        )
        some = next(
            item
            for item in target_ir["nominal_enum_payloads"]["MaybeToken"]["variants"]
            if item["name"] == "Some"
        )
        some["payload_type"] = "WrongToken"

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "ownership fact does not match a nominal Target IR payload",
        ):
            h2d.attach_target_ir_enum_payload_ownership(
                target_ir,
                checked_sir.module,
            )

    def test_conflicting_preexisting_projection_fails_closed(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(
            checked_sir.module
        )
        target_ir["aggregate_ownership_facts"] = [{
            "kind": "enum_payload",
            "enum": "MaybeToken",
            "variant": "Some",
            "payload_type": "WrongToken",
            "domain": "exclusive",
            "storage": "by_value",
        }]

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "already contains conflicting aggregate ownership facts",
        ):
            h2d.attach_target_ir_enum_payload_ownership(
                target_ir,
                checked_sir.module,
            )

    def test_compiler_and_tools_h2d_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "aggregate_ownership_h2d.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
