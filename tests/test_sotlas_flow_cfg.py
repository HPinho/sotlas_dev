from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

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
    "sotlas_flow_cfg_test_package", ROOT / "compiler" / "sotlas_compile"
)
tools_package = _load_package(
    "sotlas_flow_cfg_tools_test_package", ROOT / "tools" / "sotlas_compile"
)


class SotlasFlowCFGTests(unittest.TestCase):
    def _serial_source(self) -> str:
        return """
module test::flow_cfg;
fn load() -> u32 { return 7u32; }
fn relay(value: u32) -> u32 { return value; }
fn finish(value: u32) -> u32 { return value; }
flow Serial {
    stage raw = load;
    stage copied = relay after raw;
    stage final = finish after copied;
}
"""

    def _serial_module(self):
        checked = package.analyze_source_phase1(self._serial_source())
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        return checked_sir.module

    def test_serial_flow_lowers_to_real_sir_call_cfg(self):
        sir_module = self._serial_module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")

        self.assertEqual(cfg.function_name, "__sotlas_flow_Serial")
        self.assertEqual(cfg.final_stage, "final")
        self.assertEqual(cfg.result_type, "u32")
        self.assertEqual(tuple(cfg.function.parameters), ())
        self.assertEqual(len(cfg.function.blocks), 1)
        block = cfg.function.blocks[0]
        self.assertEqual(block.label, "entry")

        calls = block.instructions[:-1]
        self.assertEqual(
            [instruction.callee for instruction in calls],
            ["load", "relay", "finish"],
        )
        self.assertEqual(calls[0].arguments, [])
        self.assertEqual(
            [value.name for value in calls[1].arguments],
            ["flow_Serial_raw_result"],
        )
        self.assertEqual(
            [value.name for value in calls[2].arguments],
            ["flow_Serial_copied_result"],
        )
        self.assertEqual(
            [point.stage_name for point in cfg.calls],
            ["raw", "copied", "final"],
        )
        self.assertEqual(cfg.calls[1].argument_stages, ("raw",))
        self.assertEqual(cfg.calls[2].argument_stages, ("copied",))

        terminator = block.instructions[-1]
        self.assertEqual(type(terminator).__name__, "ReturnInst")
        self.assertEqual(terminator.value.name, "flow_Serial_final_result")
        self.assertIs(package.validate_serial_flow_cfg(sir_module, cfg), cfg)

    def test_serial_cfg_rejects_tampered_callee_before_backend(self):
        sir_module = self._serial_module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")
        cfg.function.blocks[0].instructions[1].callee = "load"
        with self.assertRaisesRegex(
            package.FlowCFGError, "executable callee facts changed"
        ):
            package.validate_serial_flow_cfg(sir_module, cfg)

    def test_serial_cfg_rejects_tampered_argument_provenance(self):
        sir_module = self._serial_module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")
        call = cfg.function.blocks[0].instructions[2]
        call.arguments = [cfg.function.blocks[0].instructions[0].result]
        with self.assertRaisesRegex(
            package.FlowCFGError, "executable argument provenance changed"
        ):
            package.validate_serial_flow_cfg(sir_module, cfg)

    def test_serial_cfg_rejects_tampered_external_call_identity(self):
        sir_module = self._serial_module()
        cfg = package.lower_serial_flow_to_cfg(sir_module, "Serial")
        tampered_call = replace(cfg.calls[1], stage_name="raw")
        tampered = replace(
            cfg,
            calls=(cfg.calls[0], tampered_call, cfg.calls[2]),
        )
        with self.assertRaisesRegex(
            package.FlowCFGError, "call identity diverges"
        ):
            package.validate_serial_flow_cfg(sir_module, tampered)

    def test_nominal_values_remain_fail_closed_until_ownership_integration(self):
        sir_module = self._serial_module()
        functions = {function.name: function for function in sir_module.functions}
        functions["load"].return_type = "Token"
        functions["relay"].parameters[0].type_name = "Token"
        functions["relay"].return_type = "Token"
        functions["finish"].parameters[0].type_name = "Token"
        functions["finish"].return_type = "Token"

        plan = sir_module.flow_plans[0]
        raw, copied, final = plan.stages
        copied_arg = copied.arguments[0]
        final_arg = final.arguments[0]
        raw = replace(raw, result_type="Token")
        copied = replace(
            copied,
            result_type="Token",
            arguments=(replace(
                copied_arg,
                type_name="Token",
                value=replace(copied_arg.value, type_name="Token"),
            ),),
        )
        final = replace(
            final,
            result_type="Token",
            arguments=(replace(
                final_arg,
                type_name="Token",
                value=replace(final_arg.value, type_name="Token"),
            ),),
        )
        sir_module.flow_plans = (replace(
            plan,
            stages=(raw, copied, final),
        ),)

        # The declarative plan is internally coherent, but ordinary nominal SSA
        # copying is not a substitute for Flow/Ownership integration.
        package.validate_sir_flow_plans(sir_module)
        with self.assertRaisesRegex(
            package.FlowCFGError,
            r"does not yet integrate ownership/lifetime semantics for type 'Token'",
        ):
            package.lower_serial_flow_to_cfg(sir_module, "Serial")

    def test_parallel_flow_remains_fail_closed_in_executable_cfg_subset(self):
        source = """
module test::flow_cfg_parallel;
fn left() -> u32 { return 1u32; }
fn right() -> u32 { return 2u32; }
fn combine(a: u32, b: u32) -> u32 { return a + b; }
flow Parallel {
    stage a = left;
    stage b = right;
    stage total = combine after a, b;
}
"""
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        with self.assertRaisesRegex(
            package.FlowCFGError, "not strictly serial"
        ):
            package.lower_serial_flow_to_cfg(checked_sir.module, "Parallel")

    def test_compat_package_exports_serial_flow_cfg_api(self):
        self.assertTrue(callable(tools_package.lower_serial_flow_to_cfg))
        self.assertTrue(callable(tools_package.validate_serial_flow_cfg))
        self.assertTrue(hasattr(tools_package, "FlowCFGError"))


if __name__ == "__main__":
    unittest.main()
