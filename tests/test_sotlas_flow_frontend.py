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
        explanation = package.explain_sir_flow_causality(
            checked_sir.module, "Home", "profile", "page"
        )
        self.assertEqual(
            [
                (step.producer_stage, step.consumer_stage,
                 step.producer_function, step.consumer_function,
                 step.argument_name, step.type_name)
                for step in explanation.steps
            ],
            [("profile", "page", "load_profile", "render", "profile", "i32")],
        )
        with self.assertRaisesRegex(package.CausalityError, "no causal dependency path"):
            package.explain_sir_flow_causality(
                checked_sir.module, "Home", "page", "profile"
            )
        impact = package.analyze_flow_stage_unavailability(plan, "profile")
        self.assertEqual(impact.affected_stages, ("profile", "page"))
        self.assertEqual(impact.unaffected_stages, ("posts",))
        self.assertEqual(
            impact.affected_dependencies,
            (("profile", "page"), ("posts", "page")),
        )
        sir_impact = package.analyze_sir_flow_stage_unavailability(
            checked_sir.module, "Home", "profile"
        )
        self.assertEqual(sir_impact, impact)
        authority_sir = package.build_canonical_checked_authority_sir(checked)
        self.assertEqual(authority_sir.module.flow_plans, checked_sir.module.flow_plans)
        with self.assertRaisesRegex(
            package.SotlasBootstrapError,
            "C11 backend does not lower source Flow declarations yet",
        ):
            package.compile_source(source)

    def test_typed_source_flow_executes_checked_stages_in_dependency_order(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
    stage posts = load_posts;
    stage page = render after profile, posts;
}
"""))
        plan = checked.flows[0]
        observed = []

        def load_profile():
            observed.append("profile")
            return 10

        def load_posts():
            observed.append("posts")
            return 7

        def render(profile, posts):
            observed.append(("page", profile, posts))
            return profile + posts

        result = package.execute_typed_flow(
            plan,
            {
                "profile": load_profile,
                "posts": load_posts,
                "page": render,
            },
        )
        self.assertEqual(result.output("page"), 17)
        self.assertEqual(observed, ["profile", "posts", ("page", 10, 7)])

    def test_source_call_causality_explains_calls_outside_flow(self):
        source = """
module test::source_call_causality;
fn parse(value: i32) -> i32 { return value; }
fn decode(raw: i32) -> i32 { return parse(raw); }
fn entry(input: i32) -> i32 { return decode(input); }
        """
        checked = package.analyze_source_phase1(source)
        explanation = package.explain_source_call_causality(
            checked, "entry", "parse"
        )
        self.assertEqual(
            [
                (step.caller_function, step.callee_function,
                 step.argument_count, step.callee_parameters)
                for step in explanation.steps
            ],
            [
                ("entry", "decode", 1, ("raw",)),
                ("decode", "parse", 1, ("value",)),
            ],
        )
        self.assertTrue(all(step.line > 0 and step.column > 0 for step in explanation.steps))
        self.assertEqual(explanation.steps[0].caller_effects, ())
        with self.assertRaisesRegex(package.CausalityError, "no source call path"):
            package.explain_source_call_causality(checked, "parse", "entry")

    def test_causality_rejects_missing_stages_and_disconnected_paths(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
    stage posts = load_posts;
    stage page = render after profile, posts;
}
"""))
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        with self.assertRaisesRegex(package.CausalityError, "unknown Flow stage"):
            package.explain_sir_flow_causality(sir.module, "Home", "missing", "page")
        with self.assertRaisesRegex(package.CausalityError, "no causal dependency path"):
            package.explain_sir_flow_causality(sir.module, "Home", "profile", "posts")
        with self.assertRaisesRegex(package.CausalityError, "no unique checked Flow plan"):
            package.explain_sir_flow_causality(sir.module, "Missing", "profile", "page")

    def test_counterfactual_reports_structural_recovery_candidates(self):
        source = """
module test::counterfactual_recovery;
fn load_profile() -> i32 { return 1; }
fn load_backup() -> i32 { return 2; }
fn render(profile: i32) -> i32 { return profile; }
fn render_backup(profile: i32) -> i32 { return profile + 1; }
flow Home {
    stage profile = load_profile;
    stage page = render after profile;
}
flow Backup {
    stage backup = load_backup;
    stage page = render_backup after backup;
}
"""
        checked = package.analyze_source_phase1(source)
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        options = package.analyze_sir_flow_recovery_options(
            sir.module, "Home", "profile", "page"
        )
        self.assertEqual(options.impact.affected_stages, ("profile", "page"))
        self.assertEqual(len(options.candidates), 1)
        candidate = options.candidates[0]
        self.assertEqual(
            (candidate.flow, candidate.stage, candidate.function, candidate.result_type),
            ("Backup", "page", "render_backup", "i32"),
        )
        self.assertEqual(candidate.effects, ())
        self.assertEqual(candidate.effects_added, ())
        self.assertEqual(candidate.effects_removed, ())
        self.assertFalse(candidate.semantic_equivalence_verified)

    def test_counterfactual_rejects_unknown_stage_and_noncanonical_graph(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
    stage page = render after profile;
}
""").replace(
            "fn render(profile: i32, posts: i32) -> i32 { return profile + posts; }",
            "fn render(profile: i32) -> i32 { return profile; }",
        ))
        plan = checked.flows[0]
        with self.assertRaisesRegex(package.CounterfactualError, "unknown Flow stage"):
            package.analyze_flow_stage_unavailability(plan, "absent")
        bad_graph = replace(plan.graph, parallel_stages=(("page",), ("profile",)))
        with self.assertRaisesRegex(package.CounterfactualError, "not in canonical"):
            package.analyze_flow_stage_unavailability(replace(plan, graph=bad_graph), "profile")
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        with self.assertRaisesRegex(package.CounterfactualError, "no unique checked Flow plan"):
            package.analyze_sir_flow_stage_unavailability(sir.module, "Missing", "profile")
        plan_sir = sir.module.flow_plans[0]
        sir.module.flow_plans = (replace(
            plan_sir, parallel_stages=(("page",), ("profile",))
        ),)
        with self.assertRaisesRegex(package.CounterfactualError, "parallel stages are not canonical"):
            package.analyze_sir_flow_stage_unavailability(sir.module, "Home", "profile")

    def test_transaction_effect_audit_requires_explicit_reversibility_policy(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
}
"""))
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        original = sir.module.flow_plans[0]
        sir_function = next(
            function for function in sir.module.functions
            if function.name == "load_profile"
        )
        sir_function.source_effect_summary = replace(
            sir_function.source_effect_summary,
            direct_effects=("io",), transitive_effects=("io",),
        )
        sir.module.flow_plans = (replace(
            original,
            stages=(replace(original.stages[0], effects=("io",)),),
        ),)

        unclassified = package.analyze_sir_flow_transaction_effects(
            sir.module, "Home", {}
        )
        self.assertFalse(unclassified.rollback_policy_satisfied)
        self.assertIn("effect io has no transaction policy", unclassified.blockers[0])

        irreversible = package.analyze_sir_flow_transaction_effects(
            sir.module, "Home", {"io": "irreversible"}
        )
        self.assertFalse(irreversible.rollback_policy_satisfied)
        self.assertEqual(irreversible.effects[0].classification, "irreversible")

        compensatable = package.analyze_sir_flow_transaction_effects(
            sir.module, "Home", {"io": "compensatable"},
            {"io": "load_posts"},
        )
        self.assertTrue(compensatable.rollback_policy_satisfied)
        self.assertEqual(compensatable.effects[0].compensation, "load_posts")
        self.assertEqual(compensatable.compensation_stage_order, (("profile",),))

        no_handler = package.analyze_sir_flow_transaction_effects(
            sir.module, "Home", {"io": "compensatable"}
        )
        self.assertFalse(no_handler.rollback_policy_satisfied)
        self.assertIn("requires a compensation handler", no_handler.blockers[0])

        with self.assertRaisesRegex(package.TransactionError, "absent from the Flow"):
            package.analyze_sir_flow_transaction_effects(
                sir.module, "Home", {"network": "reversible"}
            )

    def test_transaction_audit_orders_compensation_by_reverse_flow_layers(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
    stage posts = load_posts;
    stage page = render after profile, posts;
}
"""))
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        plan = sir.module.flow_plans[0]
        for function in sir.module.functions:
            if function.name in {"load_profile", "load_posts", "render"}:
                function.source_effect_summary = replace(
                    function.source_effect_summary,
                    direct_effects=("io",), transitive_effects=("io",),
                )
        sir.module.flow_plans = (replace(
            plan,
            stages=tuple(replace(stage, effects=("io",)) for stage in plan.stages),
        ),)
        audit = package.analyze_sir_flow_transaction_effects(
            sir.module,
            "Home",
            {"io": "compensatable"},
            {"io": "load_profile"},
        )
        self.assertTrue(audit.rollback_policy_satisfied)
        self.assertEqual(
            audit.compensation_stage_order,
            (("page",), ("profile", "posts")),
        )

    def test_sir_flow_validator_reconciles_signatures_edges_effects_and_schedule(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
    stage page = render after profile;
}
""").replace(
            "fn render(profile: i32, posts: i32) -> i32 { return profile + posts; }",
            "fn render(profile: i32) -> i32 { return profile; }",
        ))
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        self.assertEqual(
            package.validate_sir_flow_plans(sir.module), sir.module.flow_plans
        )
        plan = sir.module.flow_plans[0]
        page = plan.stages[1]
        bad_argument = replace(page.arguments[0], type_name="u32")
        bad_page = replace(page, arguments=(bad_argument,))
        sir.module.flow_plans = (replace(
            plan, stages=(plan.stages[0], bad_page)
        ),)
        with self.assertRaisesRegex(package.FlowSIRError, "argument differs from SIR parameter"):
            package.validate_sir_flow_plans(sir.module)
        with self.assertRaisesRegex(package.CausalityError, "invalid canonical SIR Flow plan"):
            package.explain_sir_flow_causality(sir.module, "Home", "profile", "page")
        with self.assertRaisesRegex(package.CounterfactualError, "invalid canonical SIR Flow plan"):
            package.analyze_sir_flow_stage_unavailability(sir.module, "Home", "profile")
        with self.assertRaisesRegex(package.TransactionError, "invalid canonical SIR Flow plan"):
            package.analyze_sir_flow_transaction_effects(sir.module, "Home", {})

    def test_intent_selects_preferred_eligible_flow_and_explains_fallbacks(self):
        source = """
module test::intent;
fn cached() -> i32 { return 1; }
fn local() -> i32 { return 2; }
flow Cached { stage value = cached; }
flow Local { stage value = local; }
"""
        checked = package.analyze_source_phase1(source)
        sir, _ = package.build_canonical_checked_ownership_sir(checked)
        cached_function = next(
            function for function in sir.module.functions
            if function.name == "cached"
        )
        cached_function.source_effect_summary = replace(
            cached_function.source_effect_summary,
            direct_effects=("system",), transitive_effects=("system",),
        )
        cached_plan = sir.module.flow_plans[0]
        cached_stage = cached_plan.stages[0]
        sir.module.flow_plans = (replace(
            cached_plan,
            stages=(replace(cached_stage, effects=("system",)),),
        ), sir.module.flow_plans[1])

        selected = package.plan_sir_intent(
            sir.module, "LoadValue", prefer=("Cached",), fallback=("Local",),
            forbidden_effects=("system",),
        )
        self.assertEqual(selected.selected_flow, "Local")
        self.assertFalse(selected.inspection[0].eligible)
        self.assertIn("forbidden effects: system", selected.inspection[0].reasons[0])
        self.assertEqual(
            selected.guarantees,
            ("forbidden_effects_absent", "all_selected_flow_stages_available"),
        )
        execution = package.execute_sir_intent(
            checked, sir.module, selected, {"value": lambda: 42}
        )
        self.assertEqual(execution.selected_flow, "Local")
        self.assertEqual(execution.execution.output("value"), 42)
        with self.assertRaisesRegex(package.IntentError, "differs from the canonical"):
            package.execute_sir_intent(
                checked,
                sir.module,
                replace(selected, selected_flow="Cached"),
                {"value": lambda: 42},
            )

        preferred = package.plan_sir_intent(
            sir.module, "LoadValue", prefer=("Cached",), fallback=("Local",)
        )
        self.assertEqual(preferred.selected_flow, "Cached")
        unavailable = package.plan_sir_intent(
            sir.module, "LoadValue", prefer=("Cached",), fallback=("Local",),
            unavailable_stages={"Cached": ("value",), "Local": ("value",)},
        )
        self.assertIsNone(unavailable.selected_flow)
        self.assertEqual(unavailable.guarantees, ())
        with self.assertRaisesRegex(package.IntentError, "unknown stages"):
            package.plan_sir_intent(
                sir.module, "LoadValue", prefer=("Cached",),
                unavailable_stages={"Cached": ("missing",)},
            )

    def test_typed_flow_runtime_rejects_dependency_tampering_before_execution(self):
        checked = package.analyze_source_phase1(self._source("""
flow Home {
    stage profile = load_profile;
    stage page = render after profile;
}
""").replace(
            "fn render(profile: i32, posts: i32) -> i32 { return profile + posts; }",
            "fn render(profile: i32) -> i32 { return profile; }",
        ))
        plan = checked.flows[0]
        page = next(stage for stage in plan.stages if stage.name == "page")
        tampered = replace(page, dependencies=())
        bad_plan = replace(
            plan,
            stages=tuple(tampered if stage.name == "page" else stage
                         for stage in plan.stages),
        )
        called = []
        with self.assertRaisesRegex(ValueError, "dependencies differ"):
            package.execute_typed_flow(
                bad_plan,
                {"profile": lambda: 1, "page": lambda value: called.append(value)},
            )
        self.assertEqual(called, [])

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
