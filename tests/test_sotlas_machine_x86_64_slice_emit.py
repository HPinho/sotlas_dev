"""M16.4f3c x86-64 checked slice indexing emission gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_slice_machine_emit_compile"


def _load_compiler_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            COMPILER_PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(COMPILER_PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


_load_compiler_package()
_emit = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_call_emit"
)
_slice_emit = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_slice_emit"
)
_core = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_core")


def _target_ir(element_type="u32", *, can_eliminate=False):
    data_type = f"{element_type}*"
    function = {
        "name": "read",
        "parameters": [
            {"name": "values__data", "type": data_type},
            {"name": "values__len", "type": "usize"},
            {"name": "index", "type": "usize"},
        ],
        "return_type": element_type,
        "blocks": [{
            "label": "0",
            "instructions": [
                {
                    "op": "bounds_check",
                    "operands": ["index", "values__len"],
                    "attributes": {"can_eliminate": can_eliminate},
                },
                {
                    "op": "slice_address",
                    "result": "element_ptr",
                    "type": data_type,
                    "operands": ["values__data", "index", "values__len"],
                    "attributes": {
                        "element_type": element_type,
                        "bounds_policy": "checked",
                        "source_point_id": "slice_address@1:1",
                    },
                },
                {
                    "op": "load",
                    "result": "value",
                    "type": element_type,
                    "operands": ["element_ptr"],
                    "attributes": {},
                },
                {
                    "op": "return",
                    "operands": ["value"],
                    "attributes": {},
                },
            ],
        }],
    }
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "slice_machine_emit",
        "functions": [function],
        "slice_views": [{
            "function": "read",
            "name": "values",
            "logical_type": f"&[{element_type}]",
            "element_type": element_type,
            "mutable": False,
            "data": "values__data",
            "length": "values__len",
            "representation": "pointer_length",
            "source_point_id": "slice_view@1:1",
        }],
        "limitations": [],
    }


class SotlasX8664SliceMachineEmissionTests(unittest.TestCase):
    def test_checked_u32_slice_index_emits_trap_and_scaled_address(self):
        assembly = _emit.emit_x86_64_sysv_assembly(_target_ir("u32"))
        self.assertIn("    cmp rcx, rdx", assembly)
        self.assertIn("    jb 1f", assembly)
        self.assertIn("    ud2", assembly)
        self.assertIn("    lea rax, [rcx+rdx*4]", assembly)

    def test_u8_slice_uses_unit_stride(self):
        assembly = _emit.emit_x86_64_sysv_assembly(_target_ir("u8"))
        self.assertIn("    lea rax, [rcx+rdx]", assembly)
        self.assertNotIn("rdx*1", assembly)

    def test_can_eliminate_is_not_silently_treated_as_already_eliminated(self):
        assembly = _emit.emit_x86_64_sysv_assembly(
            _target_ir("u32", can_eliminate=True)
        )
        self.assertIn("    cmp rcx, rdx", assembly)
        self.assertIn("    ud2", assembly)

    def test_slice_address_without_dominating_bounds_check_is_rejected(self):
        target_ir = _target_ir()
        instructions = target_ir["functions"][0]["blocks"][0]["instructions"]
        instructions.pop(0)
        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "dominating bounds proof",
        ):
            _slice_emit.validate_slice_indexing_machine_contract(target_ir)

    def test_slice_address_without_matching_slice_view_is_rejected(self):
        target_ir = _target_ir()
        target_ir["slice_views"] = []
        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "matching slice view",
        ):
            _slice_emit.validate_slice_indexing_machine_contract(target_ir)

    def test_slice_length_must_remain_usize(self):
        target_ir = _target_ir()
        target_ir["functions"][0]["parameters"][1]["type"] = "u64"
        with self.assertRaises(_core.MachineBackendError):
            _emit.emit_x86_64_sysv_assembly(target_ir)

    def test_compiler_and_tools_slice_machine_layers_remain_identical(self):
        for filename in (
            "_machine_x86_64_slice_emit.py",
            "_machine_x86_64_call_emit.py",
        ):
            relative = Path("sotlas_compile") / filename
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
