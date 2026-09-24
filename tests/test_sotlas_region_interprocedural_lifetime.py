"""Compose local, call, CFG and return REGION lifetime proofs."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_interprocedural_lifetime_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = _load_package()
interprocedural = importlib.import_module(
    f"{package.__name__}.region_interprocedural"
)


SOURCE = """module app::region_interprocedural;
sole struct Token { value: u32; }
fn pass(token: region Token) -> region Token {
    return token;
}
fn consume(token: region Token) -> void { return; }
fn run(first: region Token, second: region Token) -> void {
    consume(move first);
    consume(move second);
    return;
}
"""


class SotlasRegionInterproceduralLifetimeTests(unittest.TestCase):
    def test_checked_module_composes_local_calls_cfg_and_returns(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-interprocedural>"
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)

        run = plan.function("run")
        self.assertEqual(run.local.function, "run")
        self.assertEqual(tuple(item.binding for item in run.calls), ("first", "second"))
        self.assertEqual(len({item.point_id for item in run.calls}), 2)
        self.assertEqual(
            tuple((item.callee, item.parameter) for item in run.calls),
            (("consume", "token"), ("consume", "token")),
        )
        self.assertEqual(
            sorted((item.source, item.via) for item in run.local.transfers),
            [("first", "call:consume"), ("second", "call:consume")],
        )

        self.assertEqual(
            tuple((item.function, item.point_id, item.callee) for item in plan.call_cfg.points),
            tuple((item.function, item.point_id, item.callee) for item in run.calls),
        )
        self.assertEqual(len(plan.call_cfg.relations), 1)
        relation = plan.call_cfg.relations[0]
        self.assertEqual(relation.function, "run")
        self.assertEqual(relation.relation, "ordered_path")
        self.assertEqual(
            (relation.first_point_id, relation.second_point_id),
            tuple(item.point_id for item in run.calls),
        )

        call_points = plan.call_points("run")
        self.assertEqual(
            tuple(item.point_id for item in call_points),
            tuple(item.point_id for item in run.calls),
        )
        first_point = plan.call_point("run", run.calls[0].point_id)
        self.assertEqual((first_point.callee, first_point.argument_indices), ("consume", (0,)))

        call_relations = plan.call_relations("run")
        self.assertEqual(call_relations, (relation,))
        resolved_relation = plan.call_relation(
            "run",
            run.calls[0].point_id,
            run.calls[1].point_id,
        )
        self.assertEqual(resolved_relation.relation, "ordered_path")

        summary = plan.call_path_summary("run")
        first_call = run.calls[0].point_id
        second_call = run.calls[1].point_id
        self.assertEqual(summary.function, "run")
        self.assertEqual(summary.point_ids, (first_call, second_call))
        self.assertEqual(summary.ordered_relations, (relation,))
        self.assertEqual(summary.path_disjoint_relations, ())
        self.assertEqual(summary.root_point_ids, (first_call,))
        self.assertEqual(summary.terminal_point_ids, (second_call,))
        self.assertEqual(summary.ordered_successors(first_call), (second_call,))
        self.assertEqual(summary.ordered_successors(second_call), ())
        self.assertEqual(summary.ordered_predecessors(first_call), ())
        self.assertEqual(summary.ordered_predecessors(second_call), (first_call,))

        passed = plan.function("pass")
        self.assertEqual(
            tuple((item.source, item.via) for item in passed.local.transfers),
            (("token", "return"),),
        )
        self.assertEqual(
            tuple((item.function, item.binding) for item in plan.returns.transfers),
            (("pass", "token"),),
        )

    def test_region_parameter_function_without_transfer_remains_present(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-interprocedural-callee>"
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)
        consume = plan.function("consume")
        self.assertEqual(consume.local.bindings, ("token",))
        self.assertEqual(consume.local.transfers, ())
        self.assertEqual(consume.calls, ())
        self.assertEqual(plan.call_points("consume"), ())
        self.assertEqual(plan.call_relations("consume"), ())

        summary = plan.call_path_summary("consume")
        self.assertEqual(summary.point_ids, ())
        self.assertEqual(summary.ordered_relations, ())
        self.assertEqual(summary.path_disjoint_relations, ())
        self.assertEqual(summary.root_point_ids, ())
        self.assertEqual(summary.terminal_point_ids, ())

    def test_missing_call_point_and_relation_fail_closed(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-interprocedural-query-errors>"
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)
        run = plan.function("run")

        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "exactly one call point",
        ):
            plan.call_point("run", "call@missing")

        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "exactly one call relation",
        ):
            plan.call_relation(
                "run",
                run.calls[1].point_id,
                run.calls[0].point_id,
            )

        summary = plan.call_path_summary("run")
        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "known call point",
        ):
            summary.ordered_successors("call@missing")
        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "known call point",
        ):
            summary.ordered_predecessors("call@missing")

    def test_call_path_summary_rejects_unknown_relation_kind(self):
        checked = package.analyze_source_phase1(
            SOURCE, filename="<region-interprocedural-summary-tamper>"
        )
        plan = interprocedural.plan_checked_region_interprocedural(checked)
        relation = plan.call_cfg.relations[0]
        forged_relation = replace(relation, relation="unknown")
        forged_cfg = replace(plan.call_cfg, relations=(forged_relation,))
        forged_plan = replace(plan, call_cfg=forged_cfg)

        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "unknown relation",
        ):
            forged_plan.call_path_summary("run")

    def test_non_checked_module_is_rejected(self):
        with self.assertRaisesRegex(
            interprocedural.RegionInterproceduralLifetimeError,
            "Phase1CheckedModule",
        ):
            interprocedural.plan_checked_region_interprocedural(object())


if __name__ == "__main__":
    unittest.main()
