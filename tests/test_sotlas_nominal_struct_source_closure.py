"""M16.4h1c2 source-to-SIR nominal struct declaration closure gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_nominal_struct_source_compile"


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
target_ir_addressing = importlib.import_module(f"{_PACKAGE}.target_ir_addressing")
struct_layout = importlib.import_module(f"{_PACKAGE}.struct_layout")


_SOURCE = """module test::nominal_struct_source;
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


_TRANSITIVE_SOURCE = """module test::nominal_struct_transitive;
sole struct Token {
    value: u32;
}
struct Envelope {
    token: Token;
    count: u32;
}
struct Vault {
    envelope: Envelope;
    flag: u8;
}
pub fn read_flag(ptr: *mut Vault) -> u8 {
    unsafe { return ptr.flag; }
}
"""


_UNUSED_SOURCE = """module test::nominal_struct_unused;
sole struct Token {
    value: u32;
}
struct UnusedEnvelope {
    token: Token;
    count: u32;
}
struct Plain {
    value: u32;
}
pub fn read_plain(ptr: *mut Plain) -> u32 {
    unsafe { return ptr.value; }
}
"""


def _checked_module(source: str):
    checked = package.analyze_source_phase1(
        source,
        filename="<nominal-struct-source>",
    )
    result, _ = canonical_sir.build_canonical_checked_ownership_sir(checked)
    return checked, result.module


def _layout_signature(module):
    return {
        layout.name: tuple(
            (field.name, field.type_name, field.representation)
            for field in layout.fields
        )
        for layout in tuple(getattr(module, "struct_layouts", ()) or ())
    }


class SotlasNominalStructSourceClosureTests(unittest.TestCase):
    def test_source_lowering_closes_used_layout_over_nominal_dependency(self):
        _, module = _checked_module(_SOURCE)

        self.assertEqual(tuple(module.unlowered_functions), ())
        layouts = _layout_signature(module)
        self.assertEqual(set(layouts), {"Envelope", "Token"})
        self.assertEqual(
            layouts["Envelope"],
            (
                ("token", "Token", "nominal_struct"),
                ("count", "u32", "scalar"),
            ),
        )
        self.assertEqual(
            layouts["Token"],
            (("value", "u32", "scalar"),),
        )

    def test_target_ir_receives_complete_nominal_declaration_closure(self):
        _, module = _checked_module(_SOURCE)

        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)

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

    def test_transitive_nominal_dependencies_are_closed_recursively(self):
        _, module = _checked_module(_TRANSITIVE_SOURCE)

        layouts = _layout_signature(module)
        self.assertEqual(set(layouts), {"Vault", "Envelope", "Token"})
        self.assertEqual(
            layouts["Vault"],
            (
                ("envelope", "Envelope", "nominal_struct"),
                ("flag", "u8", "scalar"),
            ),
        )
        self.assertEqual(
            layouts["Envelope"][0],
            ("token", "Token", "nominal_struct"),
        )

    def test_unused_nominal_structs_do_not_pollute_canonical_sir(self):
        _, module = _checked_module(_UNUSED_SOURCE)

        layouts = _layout_signature(module)
        self.assertEqual(set(layouts), {"Plain"})
        self.assertEqual(
            layouts["Plain"],
            (("value", "u32", "scalar"),),
        )

    def test_complete_nominal_closure_is_accepted_by_address_validation(self):
        _, module = _checked_module(_SOURCE)
        target_ir = target_ir_calls.lower_sir_to_typed_target_ir(module)

        self.assertIsNone(
            target_ir_addressing.validate_target_ir_addressing(target_ir)
        )

    def test_nominal_source_scope_does_not_leak_after_generation(self):
        checked, _ = _checked_module(_SOURCE)
        envelope = next(
            item
            for item in checked.parsed_module.structs
            if item.name == "Envelope"
        )

        with self.assertRaisesRegex(
            struct_layout.StructLayoutError,
            "outside the M16.4h1c1 scalar/nominal declaration contract",
        ):
            struct_layout.make_struct_layout_decl(
                envelope,
                lambda item: getattr(item, "name", ""),
            )

    def test_compiler_and_tools_layers_remain_identical(self):
        for relative in (
            Path("sotlas_compile") / "local_addressing.py",
            Path("sotlas_compile") / "struct_layout.py",
        ):
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
                str(relative),
            )


if __name__ == "__main__":
    unittest.main()
