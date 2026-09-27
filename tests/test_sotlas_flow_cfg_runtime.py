from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
from threading import Barrier
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _load_package(name: str, directory: Path):
    spec = importlib.util.spec_from_file_location(
        name,
        directory / "__init__.py",
        submodule_search_locations=[str(directory)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = _load_package(
    "sotlas_flow_cfg_runtime_test_package", ROOT / "compiler" / "sotlas_compile"
)
tools_package = _load_package(
    "sotlas_flow_cfg_runtime_tools_test_package", ROOT / "tools" / "sotlas_compile"
)


class SotlasFlowCFGRuntimeTests(unittest.TestCase):
    def _module(self):
        source = """
module test::flow_cfg_runtime;
fn load() -> u32 { return 7u32; }
fn double(value: u32) -> u32 { return value + value; }
fn finish(value: u32) -> u32 { return value; }
flow Serial {
    stage raw = load;
    stage doubled = double after raw;
    stage final = finish after doubled;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        return checked_sir.module

    def test_executes_actual_serial_call_cfg_through_scheduler(self):
        sir_module = self._module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")
        result = package.execute_serial_flow_cfg(sir_module, cfg)
        self.assertEqual(result.output("raw"), 7)
        self.assertEqual(result.output("doubled"), 14)
        self.assertEqual(result.output("final"), 14)

    def test_executes_independent_stages_concurrently_from_checked_cfg(self):
        source = """
module test::flow_cfg_parallel;
fn left() -> u32 { return 7u32; }
fn right() -> u32 { return 9u32; }
fn combine(a: u32, b: u32) -> u32 { return a + b; }
flow Parallel {
    stage left_value = left;
    stage right_value = right;
    stage total = combine after left_value, right_value;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        cfg = package.lower_flow_to_cfg(checked_sir.module, "Parallel")

        interpreter = importlib.import_module(
            "sotlas_flow_cfg_runtime_test_package.flow_interpreter"
        )
        original = interpreter._interpret_function
        independent_stage_barrier = Barrier(2)

        def synchronized_interpret(function, arguments, **kwargs):
            if function.name in {"left", "right"}:
                independent_stage_barrier.wait(timeout=5)
            return original(function, arguments, **kwargs)

        with patch.object(
            interpreter, "_interpret_function", side_effect=synchronized_interpret
        ):
            result = package.execute_flow_cfg(checked_sir.module, cfg)

        self.assertEqual(result.output("left_value"), 7)
        self.assertEqual(result.output("right_value"), 9)
        self.assertEqual(result.output("total"), 16)

    def test_executes_signed_integer_arithmetic_stages(self):
        source = """
module test::flow_cfg_signed;
fn seed() -> i32 { return 7i32; }
fn double(value: i32) -> i32 { return value + value; }
fn finish(value: i32) -> i32 { return value; }
flow SignedSerial {
    stage raw = seed;
    stage doubled = double after raw;
    stage final = finish after doubled;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        cfg = package.lower_serial_flow_to_cfg(checked_sir.module, "SignedSerial")
        result = package.execute_serial_flow_cfg(checked_sir.module, cfg)
        self.assertEqual(result.output("raw"), 7)
        self.assertEqual(result.output("doubled"), 14)
        self.assertEqual(result.output("final"), 14)

    def test_rejects_signed_overflow_before_publishing_flow_outputs(self):
        source = """
module test::flow_cfg_signed_overflow;
fn seed() -> i8 { return 100i8; }
fn double(value: i8) -> i8 { return value + value; }
flow SignedOverflow {
    stage raw = seed;
    stage doubled = double after raw;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        cfg = package.lower_serial_flow_to_cfg(checked_sir.module, "SignedOverflow")
        with self.assertRaisesRegex(
            package.FlowExecutionError, "outside the range of i8"
        ):
            package.execute_serial_flow_cfg(checked_sir.module, cfg)

    def test_executes_acyclic_stage_branches_and_phi_joins(self):
        source = """
module test::flow_cfg_branch;
fn seed() -> i32 { return 5i32; }
fn scale(value: i32) -> i32 { return value + value; }
fn equal(left: i32, right: i32) -> bool { return left == right; }
fn choose(flag: bool, yes: i32, no: i32) -> i32 {
    return if flag { yes } else { no };
}
flow Branching {
    stage base = seed;
    stage scaled = scale after base;
    stage same = equal after scaled, base;
    stage selected = choose after same, base, scaled;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        cfg = package.lower_serial_flow_to_cfg(checked_sir.module, "Branching")
        result = package.execute_serial_flow_cfg(checked_sir.module, cfg)
        self.assertEqual(result.output("base"), 5)
        self.assertEqual(result.output("scaled"), 10)
        self.assertFalse(result.output("same"))
        self.assertEqual(result.output("selected"), 10)

    def test_executes_scalar_phi_loop_in_flow_stage(self):
        source = """
module test::flow_cfg_loop;
fn seed() -> i32 { return 4i32; }
fn accumulate(limit: i32) -> i32 { return limit; }
flow Looping {
    stage bound = seed;
    stage total = accumulate after bound;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        canonical_sir = importlib.import_module(
            "sotlas_flow_cfg_runtime_test_package.canonical_sir"
        )
        sir = canonical_sir.load_canonical_sir()
        instructions = importlib.import_module(
            "_sotlas_compiler_canonical_sir.instructions"
        )
        function = next(
            item for item in checked_sir.module.functions
            if item.name == "accumulate"
        )
        function.blocks.clear()
        zero = sir.SIRValue("zero", "i32")
        one = sir.SIRValue("one", "i32")
        index = sir.SIRValue("index", "i32")
        total = sir.SIRValue("total", "i32")
        below_limit = sir.SIRValue("below_limit", "bool")
        next_index = sir.SIRValue("next_index", "i32")
        next_total = sir.SIRValue("next_total", "i32")
        entry = function.add_block("entry")
        header = function.add_block("header")
        body = function.add_block("body")
        exit_block = function.add_block("exit")
        entry.add(sir.ConstantIntInst(0, zero))
        entry.add(sir.ConstantIntInst(1, one))
        entry.add(sir.BranchInst("header"))
        header.add(sir.PhiInst(index, [(zero, "entry"), (next_index, "body")]))
        header.add(sir.PhiInst(total, [(zero, "entry"), (next_total, "body")]))
        header.add(sir.CompareInst("LT", index, function.parameters[0], below_limit))
        header.add(sir.CondBranchInst(below_limit, "body", "exit"))
        body.add(instructions.BinaryOpInst("add", index, one, next_index))
        body.add(instructions.BinaryOpInst("add", total, index, next_total))
        body.add(sir.BranchInst("header"))
        exit_block.add(sir.ReturnInst(total))

        cfg = package.lower_serial_flow_to_cfg(checked_sir.module, "Looping")
        result = package.execute_serial_flow_cfg(checked_sir.module, cfg)
        self.assertEqual(result.output("bound"), 4)
        self.assertEqual(result.output("total"), 6)

    def test_scalar_cyclic_cfg_execution_has_a_block_visit_limit(self):
        canonical_sir = importlib.import_module(
            "sotlas_flow_cfg_runtime_test_package.canonical_sir"
        )
        interpreter = importlib.import_module(
            "sotlas_flow_cfg_runtime_test_package.flow_interpreter"
        )
        sir = canonical_sir.load_canonical_sir()
        looping = sir.SIRFunction("looping", [], "i32")
        looping.add_block("entry").add(sir.BranchInst("spin"))
        looping.add_block("spin").add(sir.BranchInst("spin"))
        interpreter._validate_function_shape(looping)
        with self.assertRaisesRegex(ValueError, r"block-visit limit \(4\)"):
            interpreter._interpret_function(looping, (), max_block_visits=4)

    def test_flow_cancellation_interrupts_a_running_scalar_loop_stage(self):
        source = """
module test::flow_cfg_cancel_loop;
fn seed() -> i32 { return 4i32; }
fn spin(limit: i32) -> i32 { return limit; }
flow Spinning {
    stage bound = seed;
    stage result = spin after bound;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        canonical_sir = importlib.import_module(
            "sotlas_flow_cfg_runtime_test_package.canonical_sir"
        )
        sir = canonical_sir.load_canonical_sir()
        function = next(
            item for item in checked_sir.module.functions if item.name == "spin"
        )
        function.blocks.clear()
        function.add_block("entry").add(sir.BranchInst("spin"))
        function.add_block("spin").add(sir.BranchInst("spin"))
        cfg = package.lower_serial_flow_to_cfg(checked_sir.module, "Spinning")

        class CancelAfterReads:
            def __init__(self):
                self.reads = 0

            def is_set(self):
                self.reads += 1
                return self.reads >= 12

        with self.assertRaises(package.FlowCancelledError):
            package.execute_serial_flow_cfg(
                checked_sir.module, cfg, cancel_event=CancelAfterReads()
            )

    def test_revalidates_call_cfg_before_any_stage_execution(self):
        sir_module = self._module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")
        cfg.function.blocks[0].instructions[1].callee = "finish"
        with self.assertRaisesRegex(
            package.FlowCFGError, "executable callee facts changed"
        ):
            package.execute_serial_flow_cfg(sir_module, cfg)

    def test_rejects_effectful_stage_even_when_cfg_shape_is_valid(self):
        sir_module = self._module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")
        load = next(function for function in sir_module.functions if function.name == "load")
        summary = load.source_effect_summary
        self.assertIsNotNone(summary)
        effectful = replace(
            summary,
            direct_effects=("io",),
            transitive_effects=("io",),
        )
        load.source_effect_summary = effectful
        plan = sir_module.flow_plans[0]
        raw = plan.stages[0]
        sir_module.flow_plans = (replace(
            plan,
            stages=(replace(raw, effects=("io",)), *plan.stages[1:]),
        ),)

        # The declarative plan and source summary still agree. The runtime must
        # materialize canonical SIR effect summaries itself and reject the stage
        # because executable CFG interpretation is pure-only.
        package.validate_sir_flow_plans(sir_module)
        with self.assertRaisesRegex(
            package.FlowCFGExecutionError, "requires pure stage function 'load'"
        ):
            package.execute_serial_flow_cfg(sir_module, cfg)

    def test_tools_package_exports_cfg_runtime_api(self):
        self.assertTrue(callable(tools_package.execute_serial_flow_cfg))
        self.assertTrue(hasattr(tools_package, "FlowCFGExecutionError"))


if __name__ == "__main__":
    unittest.main()
