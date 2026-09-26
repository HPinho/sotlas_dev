from __future__ import annotations

import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
PACKAGE_NAME = "sotlas_flow_frontend_test_package"
SPEC = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    PACKAGE_DIR / "__init__.py",
    submodule_search_locations=[str(PACKAGE_DIR)],
)
assert SPEC is not None and SPEC.loader is not None
package = importlib.util.module_from_spec(SPEC)
sys.modules[PACKAGE_NAME] = package
SPEC.loader.exec_module(package)

TOOLS_PACKAGE_DIR = ROOT / "tools" / "sotlas_compile"
TOOLS_PACKAGE_NAME = "sotlas_flow_frontend_compat_package"
TOOLS_SPEC = importlib.util.spec_from_file_location(
    TOOLS_PACKAGE_NAME,
    TOOLS_PACKAGE_DIR / "__init__.py",
    submodule_search_locations=[str(TOOLS_PACKAGE_DIR)],
)
assert TOOLS_SPEC is not None and TOOLS_SPEC.loader is not None
tools_package = importlib.util.module_from_spec(TOOLS_SPEC)
sys.modules[TOOLS_PACKAGE_NAME] = tools_package
TOOLS_SPEC.loader.exec_module(tools_package)


class SotlasFlowFrontendTests(unittest.TestCase):
    def _source(self, flow: str) -> str:
        return f"""
module test::flow_frontend;
fn load_profile() -> i32 {{ return 1; }}
fn load_posts() -> i32 {{ return 2; }}
fn render(profile: i32, posts: i32) -> i32 {{ return profile + posts; }}
{flow}
"""

    def test_flow_source_builds_certified_typed_dependency_plan(self):
        source = self._source("""
flow Home {
    stage profile = load_profile;
    stage posts = load_posts;
    stage page = render after profile, posts;
}
""")
        checked = package.analyze_source_phase1(source)
        self.assertEqual(len(checked.flows), 1)
        plan = checked.flows[0]
        self.assertEqual(
            tuple(node.name for node in plan.graph.nodes),
            ("profile", "posts", "page"),
        )
        self.assertEqual(
            [(edge.producer, edge.consumer) for edge in plan.graph.dependencies],
            [("profile", "page"), ("posts", "page")],
        )
        page = next(stage for stage in plan.stages if stage.name == "page")
        self.assertEqual(page.dependencies, ("profile", "posts"))
        self.assertEqual(tuple(t.name for t in page.input_types), ("i32", "i32"))
        self.assertEqual(page.result_type.name, "i32")
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        sir_plan = checked_sir.module.flow_plans[0]
        self.assertEqual(sir_plan.name, "Home")
        self.assertEqual(sir_plan.parallel_stages, (("profile", "posts"), ("page",)))
        lowered_page = next(stage for stage in sir_plan.stages if stage.name == "page")
        self.assertEqual(lowered_page.function, "render")
        self.assertEqual(
            [
                (argument.parameter_index, argument.parameter_name,
                 argument.value.producer_stage, argument.value.producer_function,
                 argument.type_name)
                for argument in lowered_page.arguments
            ],
            [
                (0, "profile", "profile", "load_profile", "i32"),
                (1, "posts", "posts", "load_posts", "i32"),
            ],
        )
        sir_dump = checked_sir.module.dump()
        self.assertIn("sir_flow @Home", sir_dump)
        self.assertIn("parallel_stage 0 = [%profile, %posts]", sir_dump)
        self.assertIn("parallel_stage 1 = [%page]", sir_dump)
        self.assertIn(
            "flow_stage %page = call @render(%profile.result, %posts.result)",
            sir_dump,
        )
        authority_sir = package.build_canonical_checked_authority_sir(checked)
        self.assertEqual(authority_sir.module.flow_plans, checked_sir.module.flow_plans)
        with self.assertRaisesRegex(
            package.SotlasBootstrapError,
            "C11 backend does not lower source Flow declarations yet",
        ):
            package.compile_source(source)

    def test_flow_sir_lowering_rejects_tampered_checked_type_facts(self):
        source = self._source("""
flow Home {
    stage profile = load_profile;
    stage page = render after profile;
}
""").replace(
            "fn render(profile: i32, posts: i32) -> i32 { return profile + posts; }",
            "fn render(profile: i32) -> i32 { return profile; }",
        )
        checked = package.analyze_source_phase1(source)
        checked_sir, _ = package.build_canonical_checked_ownership_sir(checked)
        plan = checked.flows[0]
        page = next(stage for stage in plan.stages if stage.name == "page")
        tampered_page = replace(page, input_types=(package.bootstrap.Type("u32"),))
        tampered_plan = replace(
            plan,
            stages=tuple(
                tampered_page if stage.name == "page" else stage
                for stage in plan.stages
            ),
        )
        with self.assertRaisesRegex(
            package.FlowSIRError, "checked input type changed"
        ):
            package.lower_typed_flows_to_sir(
                (tampered_plan,), checked.parsed_module, checked_sir.module
            )

    def test_flow_source_rejects_unknown_stage_function_and_dependency(self):
        for flow, diagnostic in (
            ("flow Broken { stage x = missing; }", "unknown function 'missing'"),
            ("flow Broken { stage x = load_profile after absent; }", "unknown producer 'absent'"),
        ):
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaisesRegex(package.SotlasBootstrapError, diagnostic):
                    package.compile_source(self._source(flow))

    def test_flow_source_rejects_cycles_and_dependency_type_mismatch(self):
        cyclic = self._source("""
flow Broken {
    stage profile = load_profile after page;
    stage posts = load_posts;
    stage page = render after profile, posts;
}
""")
        with self.assertRaisesRegex(package.SotlasBootstrapError, "cycle"):
            package.compile_source(cyclic)

        mismatch = self._source("""
flow Broken {
    stage profile = load_profile;
    stage posts = load_posts;
    stage page = render after profile, posts;
}
        """).replace(
            "fn render(profile: i32, posts: i32) -> i32 { return profile + posts; }",
            "fn render(profile: u32, posts: i32) -> i32 { return posts; }",
        )
        with self.assertRaisesRegex(package.SotlasBootstrapError, "type does not match"):
            package.compile_source(mismatch)

    def test_compatibility_frontend_parses_and_fails_closed_in_c11(self):
        source = self._source("""
flow Home {
    stage profile = load_profile;
}
""")
        module = tools_package.bootstrap.parse(source)
        tools_package.bootstrap.check(module)
        self.assertEqual(len(module.typed_flows), 1)
        with self.assertRaisesRegex(
            tools_package.SotlasBootstrapError,
            "C11 backend does not lower source Flow declarations yet",
        ):
            tools_package.compile_source(source)


if __name__ == "__main__":
    unittest.main()
