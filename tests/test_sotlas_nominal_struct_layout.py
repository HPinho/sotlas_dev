"""M16.4h1c1 nominal by-value struct declaration gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_nominal_struct_layout_compile"


def _load_compiler_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


sotlas_compile = _load_compiler_package()
_struct_layout = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.struct_layout"
)


_SOURCE = """module test::nominal_struct_layout;
sole struct Token { value: u32; }
struct Envelope {
    token: Token;
    count: u32;
}
fn noop() -> void { return; }
"""


def _render(type_info) -> str:
    name = getattr(type_info, "name", None)
    if not isinstance(name, str) or not name:
        raise ValueError("test type has no canonical name")
    if bool(getattr(type_info, "pointer", False)):
        return f"{name}*"
    if bool(getattr(type_info, "is_reference", False)):
        return f"&{name}"
    if bool(getattr(type_info, "is_array", False)):
        return f"[{name}]"
    return name


class SotlasNominalStructLayoutTests(unittest.TestCase):
    def _declarations(self):
        checked = sotlas_compile.analyze_source_phase1(
            _SOURCE, filename="<nominal-struct-layout>"
        )
        parsed = {item.name: item for item in checked.parsed_module.structs}
        names = frozenset(item.name for item in checked.semantic.typed_module.structs)
        token = _struct_layout.make_struct_layout_decl(
            parsed["Token"],
            _render,
            nominal_struct_names=names,
        )
        envelope = _struct_layout.make_struct_layout_decl(
            parsed["Envelope"],
            _render,
            nominal_struct_names=names,
        )
        return token, envelope

    def test_direct_known_struct_field_keeps_nominal_identity(self):
        token, envelope = self._declarations()

        self.assertEqual(
            [(field.name, field.type_name, field.representation) for field in token.fields],
            [("value", "u32", "scalar")],
        )
        self.assertEqual(
            [(field.name, field.type_name, field.representation) for field in envelope.fields],
            [
                ("token", "Token", "nominal_struct"),
                ("count", "u32", "scalar"),
            ],
        )

    def test_target_ir_preserves_nominal_field_without_physical_claims(self):
        token, envelope = self._declarations()
        sir_module = SimpleNamespace(struct_layouts=())
        _struct_layout.attach_sir_struct_layout(sir_module, token)
        _struct_layout.attach_sir_struct_layout(sir_module, envelope)
        target_ir = {"schema": "sotlas.target-ir.v1", "functions": []}

        _struct_layout.attach_target_ir_struct_layouts(target_ir, sir_module)

        self.assertEqual(
            target_ir["struct_layouts"],
            [
                {
                    "name": "Envelope",
                    "fields": [
                        {
                            "name": "token",
                            "type": "Token",
                            "representation": "nominal_struct",
                        },
                        {"name": "count", "type": "u32"},
                    ],
                },
                {
                    "name": "Token",
                    "fields": [{"name": "value", "type": "u32"}],
                },
            ],
        )
        nominal = target_ir["struct_layouts"][0]["fields"][0]
        for forbidden in (
            "offset_bytes",
            "size_bytes",
            "alignment_bytes",
            "abi_class",
            "register_class",
        ):
            self.assertNotIn(forbidden, nominal)

    def test_nominal_reference_requires_declared_struct_layout(self):
        _, envelope = self._declarations()
        sir_module = SimpleNamespace(struct_layouts=(envelope,))
        target_ir = {"schema": "sotlas.target-ir.v1", "functions": []}

        with self.assertRaisesRegex(
            _struct_layout.StructLayoutError,
            "references undeclared nominal struct 'Token'",
        ):
            _struct_layout.attach_target_ir_struct_layouts(target_ir, sir_module)

    def test_unknown_nominal_type_stays_fail_closed(self):
        checked = sotlas_compile.analyze_source_phase1(_SOURCE)
        envelope = next(
            item for item in checked.parsed_module.structs
            if item.name == "Envelope"
        )
        with self.assertRaisesRegex(
            _struct_layout.StructLayoutError,
            "outside the M16.4h1c1 scalar/nominal declaration contract",
        ):
            _struct_layout.make_struct_layout_decl(
                envelope,
                _render,
                nominal_struct_names={"Envelope"},
            )

    def test_direct_self_recursive_nominal_field_is_rejected(self):
        direct_type = SimpleNamespace(
            name="Loop",
            pointer=False,
            is_reference=False,
            is_array=False,
        )
        recursive = SimpleNamespace(
            name="Loop",
            fields=(SimpleNamespace(
                name="next",
                type=direct_type,
                bit_width=None,
            ),),
        )
        with self.assertRaisesRegex(
            _struct_layout.StructLayoutError,
            "cannot contain itself directly by value",
        ):
            _struct_layout.make_struct_layout_decl(
                recursive,
                _render,
                nominal_struct_names={"Loop"},
            )

    def test_mutual_by_value_nominal_cycle_is_rejected_before_target_ir(self):
        field_a = _struct_layout.StructFieldDecl(
            "b", "B", representation="nominal_struct"
        )
        field_b = _struct_layout.StructFieldDecl(
            "a", "A", representation="nominal_struct"
        )
        sir_module = SimpleNamespace(struct_layouts=(
            _struct_layout.StructLayoutDecl("A", (field_a,)),
            _struct_layout.StructLayoutDecl("B", (field_b,)),
        ))
        target_ir = {"schema": "sotlas.target-ir.v1", "functions": []}

        with self.assertRaisesRegex(
            _struct_layout.StructLayoutError,
            "by-value cycle",
        ):
            _struct_layout.attach_target_ir_struct_layouts(target_ir, sir_module)

    def test_compiler_and_tools_struct_layout_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "struct_layout.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
