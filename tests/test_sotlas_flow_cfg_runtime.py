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
        summary = sir_module.effect_summaries["load"]
        effectful = replace(
            summary,
            direct_effects=("io",),
            transitive_effects=("io",),
        )
        sir_module.effect_summaries["load"] = effectful
        load.source_effect_summary = effectful
        plan = sir_module.flow_plans[0]
        raw = plan.stages[0]
        sir_module.flow_plans = (replace(
            plan,
            stages=(replace(raw, effects=("io",)), *plan.stages[1:]),
        ),)

        # The declarative plan and summary still agree, so the execution-specific
        # purity gate—not a malformed-plan shortcut—must reject it.
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
