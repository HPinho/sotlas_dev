"""Phase 6: canonical Flow dependency graph semantics."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_flow_graph():
    package = "sotlas_flow_graph_package"
    if package not in sys.modules:
        package_spec = importlib.util.spec_from_file_location(
            package,
            PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(PACKAGE_DIR)],
        )
        assert package_spec is not None and package_spec.loader is not None
        package_module = importlib.util.module_from_spec(package_spec)
        sys.modules[package] = package_module
        package_spec.loader.exec_module(package_module)
    module_name = f"{package}.flow_graph"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, PACKAGE_DIR / "flow_graph.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


flow = _load_flow_graph()


class SotlasFlowGraphTests(unittest.TestCase):
    def test_independent_nodes_share_a_stable_parallel_stage(self):
        plan = flow.certify_flow_graph(
            tuple(flow.FlowNode(name) for name in (
                "profile", "avatar", "posts", "render"
            )),
            (
                flow.FlowDependency("profile", "render"),
                flow.FlowDependency("avatar", "render"),
                flow.FlowDependency("posts", "render"),
            ),
        )
        self.assertEqual(
            plan.parallel_stages,
            (("profile", "avatar", "posts"), ("render",)),
        )

    def test_ready_node_tie_breaking_uses_source_order(self):
        plan = flow.certify_flow_graph(
            tuple(flow.FlowNode(name) for name in ("later", "first", "join")),
            (
                flow.FlowDependency("later", "join"),
                flow.FlowDependency("first", "join"),
            ),
        )
        self.assertEqual(plan.parallel_stages[0], ("later", "first"))

    def test_cycle_is_rejected_with_involved_nodes(self):
        with self.assertRaisesRegex(
            flow.FlowGraphError,
            "cycle involving: first, second",
        ):
            flow.certify_flow_graph(
                (flow.FlowNode("first"), flow.FlowNode("second")),
                (
                    flow.FlowDependency("first", "second"),
                    flow.FlowDependency("second", "first"),
                ),
            )

    def test_unknown_endpoints_and_duplicate_dependencies_are_rejected(self):
        nodes = (flow.FlowNode("first"),)
        with self.assertRaisesRegex(
            flow.FlowGraphError, "unknown consumer 'missing'"
        ):
            flow.certify_flow_graph(
                nodes, (flow.FlowDependency("first", "missing"),)
            )
        with self.assertRaisesRegex(
            flow.FlowGraphError, "repeats dependency first -> second"
        ):
            flow.certify_flow_graph(
                (flow.FlowNode("first"), flow.FlowNode("second")),
                (
                    flow.FlowDependency("first", "second"),
                    flow.FlowDependency("first", "second"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
