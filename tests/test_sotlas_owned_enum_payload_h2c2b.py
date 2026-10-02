"""M16.4h2c2b logical nominal enum payload projection into full Target IR."""
from __future__ import annotations

import copy
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2c2b_compile"


def _load_package():
    package = sys.modules.get(_PACKAGE)
    if package is not None:
        return package
    spec = importlib.util.spec_from_file_location(
        _PACKAGE, PACKAGE_DIR / "__init__.py",
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
bridge = importlib.import_module(f"{_PACKAGE}.aggregate_ownership_h2c2b")
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")
target_ir_calls = importlib.import_module(f"{_PACKAGE}.target_ir_calls")

_SOURCE = """module test::owned_enum_payload_h2c2b;
sole struct Token { value: u32; }
enum MaybeToken { None = 0, Some(Token), }
fn noop() -> void { return; }
"""


class SotlasOwnedEnumPayloadH2C2BTests(unittest.TestCase):
    def _checked_sir(self):
        checked = package.analyze_source_phase1(
            _SOURCE,
            filename="<owned-enum-payload-h2c2b>",
        )
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        return checked_sir

    def test_full_target_ir_preserves_nominal_payload_without_projecting_enum_ownership(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)

        declaration = target_ir["nominal_enum_payloads"]["MaybeToken"]
        some = next(item for item in declaration["variants"] if item["name"] == "Some")
        self.assertEqual(some["payload_type"], "Token")
        self.assertEqual(some["payload_representation"], "nominal_struct")
        self.assertNotIn("size_bytes", declaration)
        self.assertNotIn("payload_offset_bytes", some)
        self.assertFalse(
            any(
                item.get("kind") == "enum_payload"
                for item in tuple(target_ir.get("aggregate_ownership_facts", ()) or ())
            )
        )

    def test_enum_ownership_requires_matching_nominal_payload_identity(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)
        tampered = copy.deepcopy(target_ir)
        some = next(
            item
            for item in tampered["nominal_enum_payloads"]["MaybeToken"]["variants"]
            if item["name"] == "Some"
        )
        some["payload_type"] = "WrongToken"

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "ownership fact does not match a nominal Target IR payload",
        ):
            bridge.attach_target_ir_aggregate_ownership_with_nominal_enums(
                tampered,
                checked_sir.module,
            )

    def test_enum_ownership_requires_nominal_sidecar_presence(self):
        checked_sir = self._checked_sir()
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(checked_sir.module)
        target_ir.pop("nominal_enum_payloads")

        with self.assertRaisesRegex(
            aggregate.AggregateOwnershipError,
            "ownership fact does not match a nominal Target IR payload",
        ):
            bridge.attach_target_ir_aggregate_ownership_with_nominal_enums(
                target_ir,
                checked_sir.module,
            )

    def test_compiler_and_tools_h2c2b_layers_remain_identical(self):
        for relative in (
            Path("sotlas_compile") / "aggregate_ownership_h2c2b.py",
            Path("sotlas_compile") / "target_ir_calls.py",
        ):
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
