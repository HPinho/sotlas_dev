"""Acyclic CFG coverage for the Sotlas-owned x86-64 backend."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_machine_cfg_canonical_compile"


def _load_backend():
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
    backend = importlib.import_module(f"{_CANONICAL_PACKAGE}.machine_x86_64")
    if Path(backend.__file__).resolve().parent != COMPILER_PACKAGE_DIR.resolve():
        raise RuntimeError("machine backend did not load from compiler/sotlas_compile")
    return backend


_BACKEND = _load_backend()
MachineBackendError = _BACKEND.MachineBackendError
compile_source_to_x86_64_sysv_assembly = (
    _BACKEND.compile_source_to_x86_64_sysv_assembly
)
emit_x86_64_sysv_assembly = _BACKEND.emit_x86_64_sysv_assembly


def _conditional_return_module(*, condition_type: str = "bool") -> dict:
    return {
        "schema": "sotlas.target-ir.v1",
        "stage": "pre_selection",
        "module": "machine_cfg",
        "functions": [{
            "name": "choose",
            "parameters": [
                {"name": "condition", "type": condition_type},
                {"name": "left", "type": "u32"},
                {"name": "right", "type": "u32"},
            ],
            "return_type": "u32",
            "blocks": [
                {
                    "label": "entry.with-punctuation",
                    "instructions": [{
                        "op": "cond_branch",
                        "operands": ["condition"],
                        "targets": ["then-block", "else-block"],
                        "attributes": {},
                    }],
                },
                {
                    "label": "then-block",
                    "instructions": [{
                        "op": "return", "operands": ["left"], "attributes": {}
                    }],
                },
                {
                    "label": "else-block",
                    "instructions": [{
                        "op": "return", "operands": ["right"], "attributes": {}
                    }],
                },
            ],
        }],
        "limitations": [],
    }


class SotlasX8664MachineCFGTests(unittest.TestCase):
    def test_conditional_branch_uses_safe_deterministic_local_labels(self):
        assembly = emit_x86_64_sysv_assembly(_conditional_return_module())

        self.assertIn(".Lchoose_bb0:", assembly)
        self.assertIn(".Lchoose_bb1:", assembly)
        self.assertIn(".Lchoose_bb2:", assembly)
        self.assertIn("test al, al", assembly)
        self.assertIn("jne .Lchoose_bb1", assembly)
        self.assertIn("jmp .Lchoose_bb2", assembly)
        self.assertNotIn("entry.with-punctuation:", assembly)
        self.assertNotIn("then-block:", assembly)

    def test_conditional_branch_requires_canonical_bool_condition(self):
        with self.assertRaisesRegex(
            MachineBackendError,
            "cond_branch condition must have type 'bool'",
        ):
            emit_x86_64_sysv_assembly(
                _conditional_return_module(condition_type="u32")
            )

    def test_phi_stays_fail_closed_until_edge_copy_lowering_exists(self):
        target_ir = {
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
        with self.assertRaisesRegex(
            MachineBackendError,
            "phi lowering waits for the edge-copy milestone",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_acyclic_cfg_allows_non_topological_block_layout(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "acyclic_layout",
            "functions": [{
                "name": "forward_only",
                "parameters": [{"name": "value", "type": "u32"}],
                "return_type": "u32",
                "blocks": [
                    {"label": "entry", "instructions": [
                        {"op": "branch", "targets": ["middle"]}
                    ]},
                    {"label": "exit", "instructions": [
                        {"op": "return", "operands": ["value"]}
                    ]},
                    {"label": "middle", "instructions": [
                        {"op": "branch", "targets": ["exit"]}
                    ]},
                ],
            }],
            "limitations": [],
        }
        assembly = emit_x86_64_sysv_assembly(target_ir)
        self.assertIn("jmp .Lforward_only_bb2", assembly)
        self.assertIn("jmp .Lforward_only_bb1", assembly)

    def test_backedge_stays_fail_closed_until_loop_milestone(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "stage": "pre_selection",
            "module": "loop_cfg",
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
            "CFG backedges/loops wait for the loop milestone",
        ):
            emit_x86_64_sysv_assembly(target_ir)

    def test_source_if_comparison_reaches_native_cfg_selection(self):
        source = """
module test::machine_cfg_source;
fn choose(left: u32, right: u32) -> u32 {
    if left < right { return left; }
    return right;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_cfg_source.sotlas"
        )
        self.assertIn(".local choose", assembly)
        self.assertNotIn(".globl choose", assembly)
        self.assertIn("cmp eax, ecx", assembly)
        self.assertIn("setb al", assembly)
        self.assertIn("test al, al", assembly)
        self.assertIn("jne .Lchoose_bb", assembly)
        self.assertIn("jmp .Lchoose_bb", assembly)
        self.assertGreaterEqual(assembly.count("ret"), 2)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "x86-64 SysV execution gate is Linux-specific",
    )
    def test_linux_e2e_executes_source_conditional_cfg(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("native C compiler is required for x86-64 CFG execution gate")

        source = """
module test::machine_cfg_e2e;
pub fn choose(left: u32, right: u32) -> u32 {
    if left < right { return left; }
    return right;
}
"""
        assembly = compile_source_to_x86_64_sysv_assembly(
            source, "machine_cfg_e2e.sotlas"
        )

        with tempfile.TemporaryDirectory(prefix="sotlas_machine_cfg_x86_64_") as temp:
            directory = Path(temp)
            asm_path = directory / "machine_cfg.s"
            caller_path = directory / "caller.c"
            executable = directory / "machine_cfg_e2e"
            asm_path.write_text(assembly, encoding="utf-8")
            caller_path.write_text(
                """
#include <stdint.h>
extern uint32_t choose(uint32_t left, uint32_t right);
int main(void) {
    if (choose(10u, 20u) != 10u) return 1;
    if (choose(20u, 10u) != 10u) return 2;
    if (choose(20u, 20u) != 20u) return 3;
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
