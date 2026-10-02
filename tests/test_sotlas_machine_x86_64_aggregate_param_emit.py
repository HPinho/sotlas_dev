"""M16.4g1c2 aggregate-aware x86-64 incoming parameter emission gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_aggregate_param_emit_compile"


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
_param_emit = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_aggregate_param_emit"
)
_core = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_core")


def _function(name, parameters):
    return {
        "name": name,
        "parameters": [
            {"name": parameter_name, "type": parameter_type}
            for parameter_name, parameter_type in parameters
        ],
        "return_type": "void",
        "blocks": [{
            "label": "0",
            "instructions": [
                {"op": "return", "operands": [], "attributes": {}}
            ],
        }],
    }


def _target_ir(function, *, slice_name=None, data=None, length=None, element_type="u32"):
    target_ir = {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "aggregate_param_emit",
        "functions": [function],
        "limitations": [],
    }
    if slice_name is not None:
        target_ir["slice_views"] = [{
            "function": function["name"],
            "name": slice_name,
            "logical_type": f"&[{element_type}]",
            "element_type": element_type,
            "mutable": False,
            "data": data,
            "length": length,
            "representation": "pointer_length",
            "source_point_id": "slice_view@1:1",
        }]
    return target_ir


class SotlasX8664AggregateIncomingEmissionTests(unittest.TestCase):
    def test_register_slice_entry_uses_planned_sysv_register_pair(self):
        function = _function(
            "read",
            [
                ("values__data", "u32*"),
                ("values__len", "usize"),
                ("tail", "u64"),
            ],
        )
        target_ir = _target_ir(
            function,
            slice_name="values",
            data="values__data",
            length="values__len",
        )

        assembly = _emit.emit_x86_64_sysv_assembly(target_ir)

        data_load = assembly.index("    mov rax, rdi")
        len_load = assembly.index("    mov rax, rsi")
        tail_load = assembly.index("    mov rax, rdx")
        self.assertLess(data_load, len_load)
        self.assertLess(len_load, tail_load)
        self.assertNotIn("QWORD PTR [rbp+16]", assembly)

    def test_register_exhaustion_loads_whole_slice_from_stack_and_keeps_r9_for_tail(self):
        function = _function(
            "pressure",
            [
                ("a", "u64"),
                ("b", "u64"),
                ("c", "u64"),
                ("d", "u64"),
                ("e", "u64"),
                ("values__data", "u32*"),
                ("values__len", "usize"),
                ("tail", "u64"),
            ],
        )
        target_ir = _target_ir(
            function,
            slice_name="values",
            data="values__data",
            length="values__len",
        )

        assembly = _emit.emit_x86_64_sysv_assembly(target_ir)

        data_stack = assembly.index("    mov rax, QWORD PTR [rbp+16]")
        len_stack = assembly.index("    mov rax, QWORD PTR [rbp+24]")
        tail_register = assembly.index("    mov rax, r9")
        self.assertLess(data_stack, len_stack)
        self.assertLess(len_stack, tail_register)
        self.assertNotIn("QWORD PTR [rbp+32]", assembly)

    def test_legacy_scalar_entry_keeps_existing_index_based_stack_transport(self):
        function = _function(
            "legacy",
            [
                ("a", "u64"),
                ("b", "u64"),
                ("c", "u64"),
                ("d", "u64"),
                ("e", "u64"),
                ("f", "u64"),
                ("g", "u64"),
            ],
        )
        target_ir = _target_ir(function)

        assembly = _emit.emit_x86_64_sysv_assembly(target_ir)

        self.assertIn("    mov rax, rdi", assembly)
        self.assertIn("    mov rax, r9", assembly)
        self.assertIn("    mov rax, QWORD PTR [rbp+16]", assembly)

    def test_slice_module_with_direct_call_remains_fail_closed(self):
        function = _function(
            "read",
            [("values__data", "u32*"), ("values__len", "usize")],
        )
        function["blocks"][0]["instructions"].insert(
            0,
            {
                "op": "call",
                "operands": [],
                "attributes": {"callee": "read"},
            },
        )
        target_ir = _target_ir(
            function,
            slice_name="values",
            data="values__data",
            length="values__len",
        )

        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "aggregate-aware direct-call emission waits for M16.4g1c3",
        ):
            _param_emit.validate_aggregate_entry_emission_scope(target_ir)

    def test_sret_remains_fail_closed_in_entry_emitter(self):
        lines = []
        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "sret emission waits for M16.4g1c3",
        ):
            _param_emit.emit_aggregate_incoming_parameters(
                lines,
                function=_function("make", []),
                function_plan={
                    "abi_transport": {
                        "sret": True,
                        "parameters": [],
                        "return": {
                            "kind": "struct",
                            "logical_type": "Large",
                        },
                    }
                },
                locations={},
            )

    def test_compiler_and_tools_emission_layers_remain_identical(self):
        for filename in (
            "_machine_x86_64_aggregate_param_emit.py",
            "_machine_x86_64_call_emit.py",
        ):
            relative = Path("sotlas_compile") / filename
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
