from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class SotlasSIRReportCliTests(unittest.TestCase):
    def _run_report(self, source: str, command: str = "sir-report"):
        temp = tempfile.TemporaryDirectory(prefix="sotlas_sir_report_")
        self.addCleanup(temp.cleanup)
        source_path = Path(temp.name) / "report.sotlas"
        source_path.write_text(source, encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            (str(ROOT / "compiler"), str(ROOT / "tools"),
             environment.get("PYTHONPATH", ""))
        )
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "compiler" / "sotlas" / "cli.py"),
                command,
                str(source_path),
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

    def test_sir_report_is_deterministic_and_summarizes_checked_module(self):
        source = """module test::sir_report;
fn load() -> u32 { return 4u32; }
fn identity(value: u32) -> u32 { return value; }
flow Calculate {
    stage input = load;
    stage output = identity after input;
}
"""
        first = self._run_report(source)
        second = self._run_report(source)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema"], "sotlas.sir-report.v1")
        self.assertEqual(report["representation"], "canonical_checked_subset")
        self.assertEqual(report["module"], "test::sir_report")
        self.assertEqual([item["name"] for item in report["functions"]], ["load", "identity"])
        self.assertEqual(report["flows"], ["Calculate"])
        self.assertEqual(report["summary"]["function_count"], 2)
        self.assertGreater(report["summary"]["block_count"], 0)
        self.assertGreater(report["summary"]["instruction_count"], 0)

    def test_sir_report_rejects_invalid_source_without_partial_json(self):
        result = self._run_report(
            "module test::sir_report_bad; fn broken() -> i32 { return missing; }"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("sir report", result.stderr)

    def test_target_ir_report_is_deterministic_and_preserves_typed_operations(self):
        source = """module test::target_ir;
pub fn sum(left: u32, right: u32) -> u32 { return left + right; }
"""
        first = self._run_report(source, "target-ir-report")
        second = self._run_report(source, "target-ir-report")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema"], "sotlas.target-ir.v1")
        self.assertEqual(report["stage"], "pre_selection")
        function = report["functions"][0]
        self.assertEqual(function["name"], "sum")
        operations = [
            instruction["op"]
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        self.assertIn("add", operations)
        self.assertIn("return", operations)
        self.assertTrue(report["limitations"])

    def test_target_ir_report_preserves_structured_control_flow_and_phi_values(self):
        result = self._run_report(
            """module test::target_ir_cfg;
pub fn choose(flag: bool, yes: u32, no: u32) -> u32 {
    return if flag { yes } else { no };
}
""",
            "target-ir-report",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        blocks = report["functions"][0]["blocks"]
        operations = [
            instruction
            for block in blocks
            for instruction in block["instructions"]
        ]
        self.assertIn("cond_branch", [item["op"] for item in operations])
        phi = next(item for item in operations if item["op"] == "phi")
        self.assertEqual(phi["type"], "u32")
        self.assertEqual(len(phi["incoming"]), 2)
        incoming_blocks = {item["block"] for item in phi["incoming"]}
        self.assertEqual(len(incoming_blocks), 2)
        self.assertTrue(incoming_blocks.issubset({block["label"] for block in blocks}))

    def test_target_ir_report_preserves_verified_direct_borrow_facts(self):
        result = self._run_report(
            """module test::target_ir_bad;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn caller(token: Token) -> void { inspect(&token); return; }
""",
            "target-ir-report",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        operations = [
            instruction
            for function in report["functions"]
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        borrow = next(item for item in operations if item["op"] == "semantic.direct_borrow")
        self.assertTrue(borrow["semantic_only"])
        self.assertEqual(borrow["attributes"]["callee"], "inspect")

    def test_target_ir_lowerer_preserves_handover_domains_and_source_point(self):
        sys.path.insert(0, str(ROOT / "compiler"))
        try:
            from sotlas_compile.canonical_sir import load_canonical_sir
            from sotlas_compile.target_ir import lower_sir_to_target_ir
        finally:
            sys.path.remove(str(ROOT / "compiler"))

        sir = load_canonical_sir()
        source = sir.SIRValue("source", "Token")
        destination = sir.SIRValue("destination", "Token")
        module = sir.SIRModule("test::target_ir_handover")
        function = sir.SIRFunction(
            "transfer", [source, destination], "void"
        )
        block = function.add_block("entry")
        block.add(sir.OwnershipDomainTransferInst(
            operation="handover",
            source=source,
            source_domain="exclusive",
            target_domain="exclusive",
            destination=destination,
            point_id="handover@7:5",
        ))
        block.add(sir.ReturnInst())
        module.add_function(function)

        report = lower_sir_to_target_ir(module)
        transfer = report["functions"][0]["blocks"][0]["instructions"][0]
        self.assertEqual(transfer["op"], "semantic.ownership_transfer")
        self.assertTrue(transfer["semantic_only"])
        self.assertEqual(transfer["operands"], ["source", "destination"])
        self.assertEqual(transfer["attributes"]["source_domain"], "exclusive")
        self.assertEqual(transfer["attributes"]["target_domain"], "exclusive")
        self.assertEqual(transfer["attributes"]["point_id"], "handover@7:5")

    def test_target_ir_lowerer_rejects_unknown_sir_operations(self):
        sys.path.insert(0, str(ROOT / "compiler"))
        try:
            from sotlas_compile.target_ir import (
                TargetIRLoweringError,
                lower_sir_to_target_ir,
            )
        finally:
            sys.path.remove(str(ROOT / "compiler"))

        class UnsupportedInstruction:
            pass

        module = SimpleNamespace(
            name="invalid",
            functions=[SimpleNamespace(
                name="function",
                parameters=[],
                return_type="void",
                blocks=[SimpleNamespace(
                    label="entry",
                    instructions=[UnsupportedInstruction()],
                )],
            )],
        )
        with self.assertRaisesRegex(
            TargetIRLoweringError, "does not lower UnsupportedInstruction"
        ):
            lower_sir_to_target_ir(module)


if __name__ == "__main__":
    unittest.main()
