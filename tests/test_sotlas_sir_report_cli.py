from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class SotlasSIRReportCliTests(unittest.TestCase):
    def _run_report(self, source: str, command: str = "sir-report", extra=()):
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
                *extra,
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

    def _load_target_ir(self):
        module_path = ROOT / "compiler" / "sotlas_compile" / "target_ir.py"
        spec = importlib.util.spec_from_file_location(
            "sotlas_test_target_ir", module_path
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

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

    def test_target_ir_report_preserves_checked_handover_after_move_call(self):
        result = self._run_report(
            """module test;
sole struct Token { value: u32; }
fn discard(token: Token) -> void { return; }
fn transfer(source: Token, destination: Token) -> void {
    discard(move destination);
    handover source to destination;
    return;
}
fn quarantine_source(source: Token, temporary: Token) -> void {
    discard(move temporary);
    quarantine source;
    return;
}
""",
            "target-ir-report",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        function = next(
            item for item in report["functions"] if item["name"] == "transfer"
        )
        operations = [
            instruction
            for block in function["blocks"]
            for instruction in block["instructions"]
        ]
        transfer = next(
            item for item in operations
            if item["op"] == "semantic.ownership_transfer"
        )
        self.assertEqual(transfer["attributes"]["operation"], "handover")
        self.assertEqual(
            transfer["attributes"]["point_id"].split("@")[0], "handover"
        )
        self.assertEqual(transfer["operands"], ["source", "destination"])
        quarantine_fn = next(
            item for item in report["functions"]
            if item["name"] == "quarantine_source"
        )
        quarantine_operations = [
            instruction
            for block in quarantine_fn["blocks"]
            for instruction in block["instructions"]
        ]
        quarantine = next(
            item for item in quarantine_operations
            if item["op"] == "semantic.ownership_transfer"
        )
        self.assertEqual(quarantine["attributes"]["operation"], "quarantine")
        self.assertTrue(
            quarantine["attributes"]["point_id"].startswith("quarantine@")
        )
        self.assertEqual(quarantine["operands"], ["source"])

    def test_register_allocation_preview_reports_intervals_and_spills(self):
        result = self._run_report(
            """module test::registers;
pub fn sum(left: u32, right: u32) -> u32 { return left + right; }
""",
            "register-allocation-report",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "sotlas.register-allocation-preview.v1")
        self.assertEqual(report["algorithm"], "linear_scan_straight_line")
        self.assertEqual(report["functions"][0]["spill_slots"], 0)
        values = {item["value"]: item for item in report["functions"][0]["intervals"]}
        self.assertIn("left", values)
        self.assertIn("right", values)
        self.assertEqual(values["left"]["location"]["kind"], "register")

        constrained = self._run_report(
            """module test::register_pressure;
pub fn sum(left: u32, right: u32) -> u32 { return left + right; }
""",
            "register-allocation-report",
            ("--registers", "1"),
        )
        self.assertEqual(constrained.returncode, 0, constrained.stderr)
        constrained_report = json.loads(constrained.stdout)
        self.assertGreater(constrained_report["functions"][0]["spill_slots"], 0)

    def test_register_allocation_preview_rejects_cfg_and_bad_register_count(self):
        source = """module test::registers_cfg;
pub fn choose(flag: bool, yes: u32, no: u32) -> u32 {
    return if flag { yes } else { no };
}
"""
        cfg = self._run_report(source, "register-allocation-report")
        self.assertNotEqual(cfg.returncode, 0)
        self.assertIn("one straight-line block", cfg.stderr)

        bad_count = self._run_report(
            "module test::registers_bad; pub fn value(x: u32) -> u32 { return x; }",
            "register-allocation-report",
            ("--registers", "0"),
        )
        self.assertNotEqual(bad_count.returncode, 0)
        self.assertIn("positive integer", bad_count.stderr)

    def test_stack_layout_preview_aligns_scalar_locals_and_rejects_bad_alignment(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "functions": [{
                "name": "sizes",
                "blocks": [{"instructions": [
                    {"op": "alloc_stack", "result": "small_slot", "type": "u8",
                     "attributes": {"source_name": "small"}},
                    {"op": "alloc_stack", "result": "middle_slot", "type": "u32",
                     "attributes": {"source_name": "middle"}},
                    {"op": "alloc_stack", "result": "wide_slot", "type": "u64",
                     "attributes": {"source_name": "wide"}},
                ]}],
            }],
        }
        report = self._load_target_ir().layout_target_ir_stack(target_ir)
        self.assertEqual(report["schema"], "sotlas.stack-layout-preview.v1")
        function = report["functions"][0]
        by_name = {slot["source_name"]: slot for slot in function["slots"]}
        self.assertEqual(by_name["small"]["offset_bytes"], 0)
        self.assertEqual(by_name["middle"]["offset_bytes"], 4)
        self.assertEqual(by_name["wide"]["offset_bytes"], 8)
        self.assertEqual(function["raw_size_bytes"], 16)
        self.assertEqual(function["frame_size_bytes"], 16)

        source = """module test::stack_layout;
pub fn sum(left: u32, right: u32) -> u32 { return left + right; }
"""
        result = self._run_report(source, "stack-layout-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        invalid = self._run_report(source, "stack-layout-report", ("--alignment", "3"))
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("power of two", invalid.stderr)

    def test_target_ir_liveness_respects_phi_predecessor_edges(self):
        source = """module test::liveness;
pub fn choose(flag: bool, yes: u32, no: u32) -> u32 {
    return if flag { yes } else { no };
}
"""
        result = self._run_report(source, "target-ir-liveness-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "sotlas.target-ir-liveness.v1")
        self.assertEqual(
            report["analysis"], "backward_dataflow_with_phi_edge_uses"
        )
        target_ir = json.loads(self._run_report(source, "target-ir-report").stdout)
        function = report["functions"][0]
        target_function = target_ir["functions"][0]
        block_liveness = {block["label"]: block for block in function["blocks"]}
        entry = function["blocks"][0]
        self.assertIn("flag", entry["live_in"])
        phi = next(
            instruction
            for block in target_function["blocks"]
            for instruction in block["instructions"]
            if instruction["op"] == "phi"
        )
        for incoming in phi["incoming"]:
            self.assertIn(
                incoming["value"], block_liveness[incoming["block"]]["live_out"]
            )

    def test_target_ir_liveness_converges_across_loop_backedges(self):
        target_ir = {
            "schema": "sotlas.target-ir.v1",
            "functions": [{
                "name": "iterate",
                "parameters": [
                    {"name": "flag", "type": "bool"},
                    {"name": "start", "type": "u32"},
                    {"name": "step", "type": "u32"},
                ],
                "blocks": [
                    {"label": "entry", "instructions": [
                        {"op": "cond_branch", "operands": ["flag"],
                         "targets": ["loop", "exit"]},
                    ]},
                    {"label": "loop", "instructions": [
                        {"op": "phi", "result": "current", "type": "u32",
                         "incoming": [
                             {"block": "entry", "value": "start"},
                             {"block": "loop", "value": "next"},
                         ]},
                        {"op": "add", "result": "next", "type": "u32",
                         "operands": ["current", "step"]},
                        {"op": "branch", "targets": ["loop"]},
                    ]},
                    {"label": "exit", "instructions": [
                        {"op": "return", "operands": ["start"]},
                    ]},
                ],
            }],
        }
        report = self._load_target_ir().analyze_target_ir_liveness(target_ir)
        blocks = {item["label"]: item for item in report["functions"][0]["blocks"]}
        self.assertIn("start", blocks["entry"]["live_out"])
        self.assertIn("next", blocks["loop"]["live_out"])
        self.assertIn("step", blocks["loop"]["live_in"])

    def test_target_ir_lowerer_preserves_handover_domains_and_source_point(self):
        sys.path.insert(0, str(ROOT / "compiler"))
        try:
            from sotlas_compile.canonical_sir import load_canonical_sir
        finally:
            sys.path.remove(str(ROOT / "compiler"))
        lower_sir_to_target_ir = self._load_target_ir().lower_sir_to_target_ir

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
        target_ir = self._load_target_ir()
        TargetIRLoweringError = target_ir.TargetIRLoweringError
        lower_sir_to_target_ir = target_ir.lower_sir_to_target_ir

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

    def test_target_ir_lowerer_rejects_invalid_phi_predecessors_and_types(self):
        target_ir = self._load_target_ir()
        lower = target_ir.lower_sir_to_target_ir
        value = lambda name, type_name: SimpleNamespace(
            name=name, type_name=type_name
        )
        instruction = lambda kind, **attributes: type(
            kind, (), attributes
        )()

        def module_with_phi(incoming, right_type="u32"):
            condition = value("condition", "bool")
            left_value = value("left_value", "u32")
            right_value = value("right_value", right_type)
            result = value("joined", "u32")
            blocks = [
                SimpleNamespace(label="entry", instructions=[
                    instruction(
                        "CondBranchInst", condition=condition,
                        true_block="left", false_block="right",
                    ),
                ]),
                SimpleNamespace(label="left", instructions=[
                    instruction(
                        "ConstantIntInst", result=left_value, value=1,
                    ),
                    instruction("BranchInst", target_block="merge"),
                ]),
                SimpleNamespace(label="right", instructions=[
                    instruction(
                        "ConstantIntInst", result=right_value, value=2,
                    ),
                    instruction("BranchInst", target_block="merge"),
                ]),
                SimpleNamespace(label="merge", instructions=[
                    instruction(
                        "PhiInst", result=result, incoming=incoming(
                            left_value, right_value
                        ),
                    ),
                    instruction("ReturnInst", value=result),
                ]),
            ]
            function = SimpleNamespace(
                name="choose", parameters=[condition], return_type="u32",
                blocks=blocks,
            )
            return SimpleNamespace(name="test", functions=[function])

        with self.assertRaisesRegex(
            target_ir.TargetIRLoweringError, "do not match CFG predecessors"
        ):
            lower(module_with_phi(lambda left, right: [(left, "left")]))

        with self.assertRaisesRegex(
            target_ir.TargetIRLoweringError, "different type"
        ):
            lower(module_with_phi(
                lambda left, right: [(left, "left"), (right, "right")],
                right_type="u64",
            ))

        condition = value("condition", "bool")
        branch_value = value("branch_value", "u32")
        escaping_use = SimpleNamespace(
            name="escape", return_type="u32", parameters=[condition],
            blocks=[
                SimpleNamespace(label="entry", instructions=[
                    instruction(
                        "CondBranchInst", condition=condition,
                        true_block="left", false_block="right",
                    ),
                ]),
                SimpleNamespace(label="left", instructions=[
                    instruction(
                        "ConstantIntInst", result=branch_value, value=1,
                    ),
                    instruction("BranchInst", target_block="merge"),
                ]),
                SimpleNamespace(label="right", instructions=[
                    instruction("BranchInst", target_block="merge"),
                ]),
                SimpleNamespace(label="merge", instructions=[
                    instruction("ReturnInst", value=branch_value),
                ]),
            ],
        )
        with self.assertRaisesRegex(
            target_ir.TargetIRLoweringError, "dominance"
        ):
            lower(SimpleNamespace(name="test", functions=[escaping_use]))


if __name__ == "__main__":
    unittest.main()
