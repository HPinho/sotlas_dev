"""M16.4h2e1 x86-64 SysV physical layout planning for nominal tagged unions."""
from __future__ import annotations

import copy
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_PACKAGE = "_sotlas_owned_enum_payload_h2e1_compile"


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
enum_layout = importlib.import_module(
    f"{_PACKAGE}._machine_x86_64_enum_layout"
)


_SOURCE = """module test::owned_enum_payload_h2e1;
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
        filename="<owned-enum-payload-h2e1>",
    )
    checked_sir, _ = canonical_sir.build_canonical_checked_ownership_sir(
        checked
    )
    return target_ir_calls.lower_sir_to_typed_target_ir(
        checked_sir.module
    )


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
                        "name": "Small",
                        "discriminant": 1,
                        "payload_type": "u32",
                        "payload_representation": "scalar",
                    },
                    {
                        "name": "Some",
                        "discriminant": 2,
                        "payload_type": "Wide",
                        "payload_representation": "nominal_struct",
                    },
                ],
            },
        },
        "functions": [],
    }


class SotlasOwnedEnumPayloadH2E1Tests(unittest.TestCase):
    def test_source_target_ir_derives_nominal_tagged_union_layout(self):
        target_ir = _target_ir_from_source()
        before = copy.deepcopy(target_ir)

        layouts = enum_layout.plan_x86_64_sysv_nominal_enum_layouts(
            target_ir
        )
        maybe = layouts["MaybeToken"]

        self.assertEqual(maybe["tag_offset_bytes"], 0)
        self.assertEqual(maybe["tag_size_bytes"], 4)
        self.assertEqual(maybe["tag_alignment_bytes"], 4)
        self.assertEqual(maybe["payload_offset_bytes"], 4)
        self.assertEqual(maybe["payload_size_bytes"], 4)
        self.assertEqual(maybe["payload_alignment_bytes"], 4)
        self.assertEqual(maybe["size_bytes"], 8)
        self.assertEqual(maybe["alignment_bytes"], 4)

        some = maybe["variants"]["Some"]
        self.assertEqual(some["payload_type"], "Token")
        self.assertEqual(
            some["payload_representation"],
            "nominal_struct",
        )
        self.assertEqual(some["payload_offset_bytes"], 4)
        self.assertEqual(some["payload_size_bytes"], 4)
        self.assertEqual(some["payload_alignment_bytes"], 4)
        self.assertEqual(target_ir, before)

    def test_payload_slot_uses_max_size_and_alignment_across_variants(self):
        layouts = enum_layout.plan_x86_64_sysv_nominal_enum_layouts(
            _wide_target_ir()
        )
        maybe = layouts["MaybeWide"]

        self.assertEqual(maybe["payload_offset_bytes"], 8)
        self.assertEqual(maybe["payload_size_bytes"], 16)
        self.assertEqual(maybe["payload_alignment_bytes"], 8)
        self.assertEqual(maybe["size_bytes"], 24)
        self.assertEqual(maybe["alignment_bytes"], 8)
        self.assertEqual(
            maybe["variants"]["Small"]["payload_offset_bytes"],
            8,
        )
        self.assertEqual(
            maybe["variants"]["Small"]["payload_size_bytes"],
            4,
        )
        self.assertEqual(
            maybe["variants"]["Some"]["payload_size_bytes"],
            16,
        )

    def test_missing_nominal_struct_layout_fails_closed(self):
        target_ir = _wide_target_ir()
        target_ir["struct_layouts"] = []

        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "has no physical struct layout",
        ):
            enum_layout.plan_x86_64_sysv_nominal_enum_layouts(
                target_ir
            )

    def test_logical_target_ir_still_cannot_smuggle_physical_layout(self):
        target_ir = _wide_target_ir()
        target_ir["nominal_enum_payloads"]["MaybeWide"][
            "size_bytes"
        ] = 24

        with self.assertRaisesRegex(
            machine.MachineBackendError,
            "rejected logical payload facts",
        ):
            enum_layout.plan_x86_64_sysv_nominal_enum_layouts(
                target_ir
            )

    def test_planner_does_not_open_call_abi_or_runtime_ownership(self):
        planned = enum_layout.plan_x86_64_sysv_nominal_enum_layouts(
            _target_ir_from_source()
        )["MaybeToken"]

        forbidden = {
            "abi_class",
            "register_class",
            "argument_registers",
            "return_registers",
            "sret",
            "cleanup",
            "drop",
            "move",
            "destroy",
        }
        self.assertFalse(forbidden & set(planned))

    def test_compiler_and_tools_h2e1_layers_remain_identical(self):
        relative = Path("sotlas_compile") / "_machine_x86_64_enum_layout.py"
        self.assertEqual(
            (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
            (ROOT / "tools" / relative).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
