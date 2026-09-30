"""Regression and phi-edge-copy coverage for the x86-64 machine backend."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


BASE_PATH = Path(__file__).with_name("_sotlas_machine_x86_64_cfg_baseline.py")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "_sotlas_machine_x86_64_cfg_baseline", BASE_PATH
)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError("cannot load x86-64 CFG baseline regression cases")
_BASE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE)

emit_x86_64_sysv_assembly = _BASE.emit_x86_64_sysv_assembly
MachineBackendError = _BASE.MachineBackendError


def _phi_join_module() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "phi_cfg",
        "functions": [{
            "name": "select_value",
            "parameters": [
                {"name": "condition", "type": "bool"},
                {"name": "left", "type": "u32"},
                {"name": "right", "type": "u32"},
            ],
            "return_type": "u32",
            "blocks": [
                {
                    "label": "entry",
                    "instructions": [{
                        "op": "cond_branch",
                        "operands": ["condition"],
                        "targets": ["left_path", "right_path"],
                    }],
                },
                {
                    "label": "left_path",
                    "instructions": [{"op": "branch", "targets": ["join"]}],
                },
                {
                    "label": "right_path",
                    "instructions": [{"op": "branch", "targets": ["join"]}],
                },
                {
                    "label": "join",
                    "instructions": [
                        {
                            "op": "phi",
                            "result": "selected",
                            "type": "u32",
                            "incoming": [
                                {"value": "left", "block": "left_path"},
                                {"value": "right", "block": "right_path"},
                            ],
                        },
                        {"op": "return", "operands": ["selected"]},
                    ],
                },
            ],
        }],
        "limitations": [],
    }


def _parallel_phi_module() -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "parallel_phi_cfg",
        "functions": [{
            "name": "encode_pair",
            "parameters": [
                {"name": "condition", "type": "bool"},
                {"name": "left", "type": "u32"},
                {"name": "right", "type": "u32"},
            ],
            "return_type": "u32",
            "blocks": [
                {
                    "label": "entry",
                    "instructions": [{
                        "op": "cond_branch",
                        "operands": ["condition"],
                        "targets": ["keep", "swap"],
                    }],
                },
                {"label": "keep", "instructions": [
                    {"op": "branch", "targets": ["join"]}
                ]},
                {"label": "swap", "instructions": [
                    {"op": "branch", "targets": ["join"]}
                ]},
                {
                    "label": "join",
                    "instructions": [
                        {
                            "op": "phi", "result": "first", "type": "u32",
                            "incoming": [
                                {"value": "left", "block": "keep"},
                                {"value": "right", "block": "swap"},
                            ],
                        },
                        {
                            "op": "phi", "result": "second", "type": "u32",
                            "incoming": [
                                {"value": "right", "block": "keep"},
                                {"value": "left", "block": "swap"},
                            ],
                        },
                        {
                            "op": "const_int", "result": "ten", "type": "u32",
                            "attributes": {"value": 10},
                        },
                        {
                            "op": "mul", "result": "scaled", "type": "u32",
                            "operands": ["first", "ten"],
                        },
                        {
                            "op": "add", "result": "encoded", "type": "u32",
                            "operands": ["scaled", "second"],
                        },
                        {"op": "return", "operands": ["encoded"]},
                    ],
                },
            ],
        }],
        "limitations": [],
    }


class SotlasX8664MachineCFGTests(_BASE.SotlasX8664MachineCFGTests):
    def test_phi_stays_fail_closed_until_edge_copy_lowering_exists(self):
        assembly = emit_x86_64_sysv_assembly(_phi_join_module())

        self.assertIn(".Lselect_value_bb3:", assembly)
        self.assertIn("mov QWORD PTR [rbp-", assembly)
        self.assertIn("mov rax, QWORD PTR [rbp-", assembly)
        self.assertNotIn("phi", assembly.lower())

    def test_phi_inputs_must_match_cfg_predecessors(self):
        target_ir = _phi_join_module()
        phi = target_ir["functions"][0]["blocks"][3]["instructions"][0]
        phi["incoming"] = [{"value": "left", "block": "left_path"}]

        with self.assertRaisesRegex(
            MachineBackendError,
            "inputs do not match CFG predecessors",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_parallel_phi_values_are_staged_before_join_loads(self):
        assembly = emit_x86_64_sysv_assembly(_parallel_phi_module())

        # Two private slots stage the incoming values before either phi result is
        # loaded, so a future physical-register copy cycle cannot corrupt SSA.
        self.assertGreaterEqual(assembly.count("mov QWORD PTR [rbp-"), 4)
        self.assertGreaterEqual(assembly.count("mov rax, QWORD PTR [rbp-"), 2)
        self.assertIn("imul eax, ecx", assembly)

    def test_backedge_stays_fail_closed_until_loop_milestone(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "unproven_cycle",
            "functions": [{
                "name": "loop_forever",
                "parameters": [],
                "return_type": "void",
                "blocks": [
                    {"label": "entry", "instructions": [
                        {"op": "branch", "targets": ["loop"]}
                    ]},
                    {"label": "loop", "instructions": [
                        {"op": "branch", "targets": ["loop"]}
                    ]},
                ],
            }],
            "limitations": [],
        }
        with self.assertRaisesRegex(
            MachineBackendError,
            "cyclic CFG is outside the bounded-loop machine subset",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_parallel_phi_edge_copies(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for x86-64 phi execution gate")

        assembly = emit_x86_64_sysv_assembly(_parallel_phi_module())
        with tempfile.TemporaryDirectory(prefix="sotlas_machine_phi_x86_64_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine_phi.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_phi_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdbool.h>
#include <stdint.h>
extern uint32_t encode_pair(bool condition, uint32_t left, uint32_t right);
int main(void) {
    if (encode_pair(true, 2u, 7u) != 27u) return 1;
    if (encode_pair(false, 2u, 7u) != 72u) return 2;
    return 0;
}
""",
                encoding="utf-8",
            )
            build = subprocess.run(
                [compiler, str(caller_path), str(asm_path), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
