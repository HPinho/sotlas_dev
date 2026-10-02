"""M16.4g1c3a aggregate-aware x86-64 outgoing slice call gates."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_aggregate_call_emit_compile"


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
_call_emit = importlib.import_module(
    f"{_CANONICAL_PACKAGE}._machine_x86_64_aggregate_call_emit"
)
_core = importlib.import_module(f"{_CANONICAL_PACKAGE}._machine_x86_64_core")


def _function(name, parameters, instructions):
    return {
        "name": name,
        "parameters": [
            {"name": parameter_name, "type": parameter_type}
            for parameter_name, parameter_type in parameters
        ],
        "return_type": "void",
        "blocks": [{
            "label": "0",
            "instructions": instructions,
        }],
    }


def _call(callee, operands):
    return {
        "op": "call",
        "operands": list(operands),
        "attributes": {"callee": callee},
    }


def _return():
    return {"op": "return", "operands": [], "attributes": {}}


def _slice_view(function_name, *, data="values__data", length="values__len"):
    return {
        "function": function_name,
        "name": "values",
        "logical_type": "&[u32]",
        "element_type": "u32",
        "mutable": False,
        "data": data,
        "length": length,
        "representation": "pointer_length",
        "source_point_id": "slice_view@1:1",
    }


def _target_ir(functions, slice_views):
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "aggregate_call_emit",
        "functions": functions,
        "slice_views": slice_views,
        "limitations": [],
    }


def _call_window(assembly: str, callee: str) -> str:
    marker = f"    call {callee}"
    end = assembly.index(marker) + len(marker)
    start = assembly.rfind("    sub rsp,", 0, end)
    if start < 0:
        raise AssertionError("call setup was not found")
    return assembly[start:end]


class SotlasX8664AggregateOutgoingCallTests(unittest.TestCase):
    def test_slice_call_uses_two_planned_integer_registers(self):
        callee = _function(
            "read",
            [
                ("values__data", "u32*"),
                ("values__len", "usize"),
                ("tail", "u64"),
            ],
            [_return()],
        )
        caller = _function(
            "invoke",
            [("data", "u32*"), ("length", "usize"), ("tail", "u64")],
            [_call("read", ["data", "length", "tail"]), _return()],
        )
        target_ir = _target_ir(
            [caller, callee],
            [_slice_view("read")],
        )

        assembly = _emit.emit_x86_64_sysv_assembly(target_ir)
        window = _call_window(assembly, "read")

        self.assertIn("    sub rsp, 16", window)
        self.assertIn("    mov rdi, rax", window)
        self.assertIn("    mov rsi, rax", window)
        self.assertIn("    mov rdx, rax", window)
        self.assertNotIn("    mov QWORD PTR [rsp], rax", window)
        self.assertLess(window.index("    mov rdi, rax"), window.index("    mov rsi, rax"))
        self.assertLess(window.index("    mov rsi, rax"), window.index("    mov rdx, rax"))

    def test_register_exhaustion_rolls_whole_outgoing_slice_to_stack(self):
        callee_parameters = [
            ("a", "u64"),
            ("b", "u64"),
            ("c", "u64"),
            ("d", "u64"),
            ("e", "u64"),
            ("values__data", "u32*"),
            ("values__len", "usize"),
            ("tail", "u64"),
        ]
        caller_parameters = [
            ("ca", "u64"),
            ("cb", "u64"),
            ("cc", "u64"),
            ("cd", "u64"),
            ("ce", "u64"),
            ("data", "u32*"),
            ("length", "usize"),
            ("ctail", "u64"),
        ]
        callee = _function("pressure", callee_parameters, [_return()])
        caller = _function(
            "invoke_pressure",
            caller_parameters,
            [
                _call(
                    "pressure",
                    ["ca", "cb", "cc", "cd", "ce", "data", "length", "ctail"],
                ),
                _return(),
            ],
        )
        target_ir = _target_ir(
            [caller, callee],
            [_slice_view("pressure")],
        )

        assembly = _emit.emit_x86_64_sysv_assembly(target_ir)
        window = _call_window(assembly, "pressure")

        self.assertIn("    sub rsp, 32", window)
        self.assertIn("    mov QWORD PTR [rsp], rax", window)
        self.assertIn("    mov QWORD PTR [rsp+8], rax", window)
        self.assertIn("    mov QWORD PTR [rsp+16], r10", window)
        self.assertIn("    mov QWORD PTR [rsp+24], r11", window)
        self.assertEqual(window.count("    mov r9, rax"), 1)
        self.assertLess(
            window.index("    mov QWORD PTR [rsp], rax"),
            window.index("    mov r9, rax"),
        )

    def test_scalar_call_inside_slice_module_keeps_legacy_emitter(self):
        scalar = _function(
            "scalar",
            [("value", "u64")],
            [_return()],
        )
        slice_owner = _function(
            "slice_owner",
            [("values__data", "u32*"), ("values__len", "usize")],
            [_return()],
        )
        caller = _function(
            "invoke_scalar",
            [("value", "u64")],
            [_call("scalar", ["value"]), _return()],
        )
        target_ir = _target_ir(
            [caller, scalar, slice_owner],
            [_slice_view("slice_owner")],
        )

        assembly = _emit.emit_x86_64_sysv_assembly(target_ir)
        window = _call_window(assembly, "scalar")

        self.assertIn("    sub rsp, 16", window)
        self.assertIn("    mov rdi, rax", window)
        self.assertNotIn("    mov QWORD PTR [rsp], rax", window)

    def test_sret_outgoing_call_remains_fail_closed(self):
        lines = []
        caller = _function("caller", [], [_return()])
        callee = {
            "name": "make_large",
            "parameters": [],
            "return_type": "Large",
            "blocks": [{"label": "0", "instructions": [_return()]}],
        }
        instruction = {
            "op": "call",
            "operands": [],
            "result": "result",
            "type": "Large",
            "attributes": {"callee": "make_large"},
        }
        with self.assertRaisesRegex(
            _core.MachineBackendError,
            "sret direct-call emission waits for M16.4g1c3b",
        ):
            _call_emit.emit_aggregate_direct_call(
                lines,
                caller=caller,
                instruction=instruction,
                locations={},
                caller_value_types={},
                callee_function=callee,
                callee_plan={
                    "abi_transport": {
                        "sret": True,
                        "parameters": [],
                        "return": {
                            "kind": "struct",
                            "logical_type": "Large",
                            "transport": {
                                "kind": "indirect",
                                "sret_register": "rdi",
                                "returns_pointer_in": "rax",
                            },
                        },
                    }
                },
            )

    def test_compiler_and_tools_outgoing_call_layers_remain_identical(self):
        for filename in (
            "_machine_x86_64_aggregate_call_emit.py",
            "_machine_x86_64_call_emit.py",
        ):
            relative = Path("sotlas_compile") / filename
            self.assertEqual(
                (ROOT / "compiler" / relative).read_text(encoding="utf-8"),
                (ROOT / "tools" / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
