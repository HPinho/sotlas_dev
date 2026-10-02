"""M16.4h2c1 explicit nominal enum payload representation contract."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2c1_compile"


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
canonical_sir = importlib.import_module(f"{_PACKAGE}.canonical_sir")
nominal = importlib.import_module(f"{_PACKAGE}.enum_nominal_payloads")

_SOURCE = """module test::owned_enum_payload_h2c1;
sole struct Token { value: u32; }
enum MaybeToken { None = 0, Some(Token), }
enum MaybeCount { None = 0, Some(u32), }
fn noop() -> void { return; }
"""


class SotlasOwnedEnumPayloadH2C1Tests(unittest.TestCase):
    def _checked(self):
        return package.analyze_source_phase1(_SOURCE, filename="<owned-enum-payload-h2c1>")

    def test_checked_typed_ast_yields_nominal_payload_declaration(self):
        facts = nominal.collect_nominal_enum_payload_facts(self._checked().semantic.typed_module)
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual((fact.enum_name, fact.tag_type, fact.storage), ("MaybeToken", "u32", "tagged_union"))
        self.assertEqual(
            tuple((v.name, v.discriminant, v.payload_type, v.payload_representation) for v in fact.variants),
            (("None", 0, None, None), ("Some", 1, "Token", "nominal_struct")),
        )

    def test_scalar_only_enum_is_not_reclassified_as_nominal(self):
        facts = nominal.collect_nominal_enum_payload_facts(self._checked().semantic.typed_module)
        self.assertNotIn("MaybeCount", {fact.enum_name for fact in facts})

    def test_explicit_sir_bridge_does_not_mutate_ownership_facts(self):
        checked = self._checked()
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        before = tuple(checked_sir.module.aggregate_ownership_facts)
        facts = nominal.attach_checked_nominal_enum_payloads(checked.semantic, checked_sir.module)
        self.assertEqual(tuple(checked_sir.module.aggregate_ownership_facts), before)
        self.assertEqual(tuple(checked_sir.module.nominal_enum_payload_facts), facts)

    def test_explicit_target_ir_sidecar_has_no_physical_claims(self):
        checked = self._checked()
        checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
        nominal.attach_checked_nominal_enum_payloads(checked.semantic, checked_sir.module)
        target_ir = {"schema": "sotlas.target-ir.v1", "functions": []}
        nominal.attach_target_ir_nominal_enum_payloads(target_ir, checked_sir.module)
        declaration = target_ir["nominal_enum_payloads"]["MaybeToken"]
        some = next(item for item in declaration["variants"] if item["name"] == "Some")
        self.assertEqual(some["payload_type"], "Token")
        self.assertEqual(some["payload_representation"], "nominal_struct")
        forbidden = {
            "size_bytes", "alignment_bytes", "offset_bytes", "payload_offset_bytes",
            "payload_size_bytes", "payload_alignment_bytes", "abi_class", "register_class",
        }
        self.assertFalse(forbidden & set(declaration))
        self.assertFalse(forbidden & set(some))

    def test_target_ir_sidecar_rejects_physical_layout_injection(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "nominal_enum_payloads": {
                "MaybeToken": {
                    "tag_type": "u32", "storage": "tagged_union", "size_bytes": 16,
                    "variants": [
                        {"name": "None", "discriminant": 0},
                        {"name": "Some", "discriminant": 1, "payload_type": "Token", "payload_representation": "nominal_struct"},
                    ],
                }
            },
        }
        with self.assertRaisesRegex(nominal.NominalEnumPayloadError, "cannot carry physical layout or ABI metadata"):
            nominal.validate_target_ir_nominal_enum_payloads(target_ir)

    def test_compiler_and_tools_h2c1_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "enum_nominal_payloads.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
