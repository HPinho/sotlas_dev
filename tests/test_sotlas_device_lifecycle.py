"""Tests for DEVICE lifecycle derivation from the canonical ownership graph."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_device_lifecycle_package"
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


sotlas_compile = _load_canonical_package()
typed_ast = importlib.import_module(f"{sotlas_compile.__name__}.typed_ast")
device_ownership = importlib.import_module(
    f"{sotlas_compile.__name__}.device_ownership"
)
device_sync = importlib.import_module(f"{sotlas_compile.__name__}.device_sync")
device_lifecycle = importlib.import_module(
    f"{sotlas_compile.__name__}.device_lifecycle"
)

OwnershipDomain = typed_ast.OwnershipDomain
OwnershipDomainGraph = typed_ast.OwnershipDomainGraph
OwnershipDomainTransition = typed_ast.OwnershipDomainTransition
Phase1SemanticError = typed_ast.Phase1SemanticError
SemanticType = typed_ast.SemanticType
VarState = typed_ast.VarState
DeviceTransferState = device_ownership.DeviceTransferState
DeviceSyncState = device_sync.DeviceSyncState
DeviceLifecycleSourcePoints = device_lifecycle.DeviceLifecycleSourcePoints
DeviceLifecycleError = device_lifecycle.DeviceLifecycleError
plan_device_lifecycle_from_graph = device_lifecycle.plan_device_lifecycle_from_graph

TOKEN = SemanticType("Token")


def _submission(
    binding: str,
    point_id: str | None,
    *,
    function: str = "submit_pair",
    state: VarState = VarState.LIVE,
) -> OwnershipDomainTransition:
    return OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=OwnershipDomain.EXCLUSIVE,
        target=OwnershipDomain.DEVICE,
        source_state=state,
        operation="handover",
        function=function,
        point_id=point_id,
    )


def _graph(*transitions: OwnershipDomainTransition) -> OwnershipDomainGraph:
    return OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=tuple(transitions),
    )


def _points(
    *,
    completions=("completion@8:1", "completion@8:2"),
    sync="sync@10:1",
    reacquisitions=("reacquire@11:1", "reacquire@11:2"),
) -> DeviceLifecycleSourcePoints:
    return DeviceLifecycleSourcePoints(
        completion_point_ids=tuple(completions),
        synchronization_point_id=sync,
        reacquisition_point_ids=tuple(reacquisitions),
    )


class SotlasDeviceLifecycleTests(unittest.TestCase):
    def canonical_graph(self):
        return _graph(
            _submission("left", "handover@3:5"),
            _submission("ignored", "handover@99:1", function="other"),
            _submission("right", "handover@4:5"),
        )

    def test_lifecycle_is_derived_from_graph_order_without_manual_tokens(self):
        plan = plan_device_lifecycle_from_graph(
            self.canonical_graph(),
            function="submit_pair",
            queue="queue0",
            points=_points(),
        )

        self.assertEqual(plan.bindings, ("left", "right"))
        self.assertEqual(
            plan.submission_point_ids,
            ("handover@3:5", "handover@4:5"),
        )
        self.assertEqual(
            plan.completion_point_ids,
            ("completion@8:1", "completion@8:2"),
        )
        self.assertEqual(plan.fence.sync_point_id, "sync@10:1")
        self.assertEqual(
            plan.reacquisition_point_ids,
            ("reacquire@11:1", "reacquire@11:2"),
        )
        self.assertEqual(
            plan.point_ids,
            (
                "handover@3:5",
                "handover@4:5",
                "completion@8:1",
                "completion@8:2",
                "sync@10:1",
                "reacquire@11:1",
                "reacquire@11:2",
            ),
        )
        self.assertTrue(
            all(
                token.state is DeviceTransferState.COMPLETED
                for token in plan.completed_tokens
            )
        )
        self.assertIs(plan.fence.state, DeviceSyncState.SYNCHRONIZED)
        self.assertIs(plan.result.fence.state, DeviceSyncState.CONSUMED)
        self.assertTrue(
            all(
                token.state is DeviceTransferState.REACQUIRED
                for token in plan.result.tokens
            )
        )

    def test_lifecycle_requires_canonical_submission_for_requested_function(self):
        with self.assertRaisesRegex(DeviceLifecycleError, "no canonical"):
            plan_device_lifecycle_from_graph(
                _graph(_submission("left", "handover@3:5", function="other")),
                function="submit_pair",
                queue="queue0",
                points=DeviceLifecycleSourcePoints(
                    ("completion@8:1",),
                    "sync@10:1",
                    ("reacquire@11:1",),
                ),
            )

    def test_lifecycle_rejects_duplicate_submission_binding(self):
        graph = _graph(
            _submission("buffer", "handover@3:5"),
            _submission("buffer", "handover@4:5"),
        )
        with self.assertRaisesRegex(DeviceLifecycleError, "duplicate submission binding"):
            plan_device_lifecycle_from_graph(
                graph,
                function="submit_pair",
                queue="queue0",
                points=_points(),
            )

    def test_lifecycle_rejects_duplicate_or_missing_submission_identity(self):
        duplicate = _graph(
            _submission("left", "handover@3:5"),
            _submission("right", "handover@3:5"),
        )
        with self.assertRaisesRegex(DeviceLifecycleError, "duplicate submission point"):
            plan_device_lifecycle_from_graph(
                duplicate,
                function="submit_pair",
                queue="queue0",
                points=_points(),
            )

        missing = _graph(_submission("left", None))
        with self.assertRaisesRegex(DeviceLifecycleError, "submission point requires"):
            plan_device_lifecycle_from_graph(
                missing,
                function="submit_pair",
                queue="queue0",
                points=DeviceLifecycleSourcePoints(
                    ("completion@8:1",),
                    "sync@10:1",
                    ("reacquire@11:1",),
                ),
            )

    def test_lifecycle_rejects_submission_not_live(self):
        graph = _graph(
            _submission("left", "handover@3:5", state=VarState.MOVED),
        )
        with self.assertRaisesRegex(DeviceLifecycleError, "must originate LIVE"):
            plan_device_lifecycle_from_graph(
                graph,
                function="submit_pair",
                queue="queue0",
                points=DeviceLifecycleSourcePoints(
                    ("completion@8:1",),
                    "sync@10:1",
                    ("reacquire@11:1",),
                ),
            )

    def test_lifecycle_requires_one_completion_and_reacquisition_per_submission(self):
        graph = self.canonical_graph()
        with self.assertRaisesRegex(DeviceLifecycleError, "one completion point"):
            plan_device_lifecycle_from_graph(
                graph,
                function="submit_pair",
                queue="queue0",
                points=_points(completions=("completion@8:1",)),
            )
        with self.assertRaisesRegex(DeviceLifecycleError, "one reacquisition point"):
            plan_device_lifecycle_from_graph(
                graph,
                function="submit_pair",
                queue="queue0",
                points=_points(reacquisitions=("reacquire@11:1",)),
            )

    def test_lifecycle_requires_all_source_points_globally_unique(self):
        graph = self.canonical_graph()
        cases = (
            _points(completions=("handover@3:5", "completion@8:2")),
            _points(sync="completion@8:1"),
            _points(reacquisitions=("reacquire@11:1", "reacquire@11:1")),
        )
        for points in cases:
            with self.subTest(points=points):
                with self.assertRaisesRegex(DeviceLifecycleError, "globally unique"):
                    plan_device_lifecycle_from_graph(
                        graph,
                        function="submit_pair",
                        queue="queue0",
                        points=points,
                    )

    def test_lifecycle_rejects_empty_function_queue_or_event_point(self):
        graph = self.canonical_graph()
        with self.assertRaisesRegex(DeviceLifecycleError, "function requires"):
            plan_device_lifecycle_from_graph(
                graph, function="", queue="queue0", points=_points()
            )
        with self.assertRaisesRegex(DeviceLifecycleError, "queue requires"):
            plan_device_lifecycle_from_graph(
                graph, function="submit_pair", queue="", points=_points()
            )
        with self.assertRaisesRegex(DeviceLifecycleError, "completion point requires"):
            plan_device_lifecycle_from_graph(
                graph,
                function="submit_pair",
                queue="queue0",
                points=_points(completions=("", "completion@8:2")),
            )

    def test_lifecycle_rejects_noncanonical_input_objects(self):
        with self.assertRaisesRegex(DeviceLifecycleError, "canonical OwnershipDomainGraph"):
            plan_device_lifecycle_from_graph(  # type: ignore[arg-type]
                object(),
                function="submit_pair",
                queue="queue0",
                points=_points(),
            )
        with self.assertRaisesRegex(DeviceLifecycleError, "source-stable lifecycle points"):
            plan_device_lifecycle_from_graph(
                self.canonical_graph(),
                function="submit_pair",
                queue="queue0",
                points=object(),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
