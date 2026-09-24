"""Tests for canonical ownership graph -> DEVICE runtime DAG derivation."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_device_runtime_semantics_package"
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
lifecycle = importlib.import_module(f"{sotlas_compile.__name__}.device_lifecycle")
runtime_abi = importlib.import_module(f"{sotlas_compile.__name__}.device_runtime_abi")
runtime_semantics = importlib.import_module(
    f"{sotlas_compile.__name__}.device_runtime_semantics"
)

OwnershipDomain = typed_ast.OwnershipDomain
OwnershipDomainGraph = typed_ast.OwnershipDomainGraph
OwnershipDomainTransition = typed_ast.OwnershipDomainTransition
SemanticType = typed_ast.SemanticType
VarState = typed_ast.VarState
DeviceLifecycleSourcePoints = lifecycle.DeviceLifecycleSourcePoints
DeviceRuntimeOperation = runtime_abi.DeviceRuntimeOperation
plan_device_runtime_from_graph = runtime_semantics.plan_device_runtime_from_graph

TOKEN = SemanticType("Token")


def _submission(binding: str, point_id: str, *, function="submit_one"):
    return OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=OwnershipDomain.EXCLUSIVE,
        target=OwnershipDomain.DEVICE,
        source_state=VarState.LIVE,
        operation="handover",
        function=function,
        point_id=point_id,
    )


def _graph():
    return OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=(
            _submission("buffer", "handover@3:5"),
            _submission("ignored", "handover@9:9", function="other"),
        ),
    )


def _points():
    return DeviceLifecycleSourcePoints(
        completion_point_ids=("completion@8:1",),
        synchronization_point_id="sync@10:1",
        reacquisition_point_ids=("reacquire@11:1",),
    )


class SotlasDeviceRuntimeSemanticsTests(unittest.TestCase):
    def test_runtime_dag_is_derived_from_same_graph_lifecycle(self):
        plan = plan_device_runtime_from_graph(
            _graph(), function="submit_one", queue="queue0", points=_points()
        )
        self.assertEqual(plan.bindings, ("buffer",))
        self.assertEqual(plan.runtime.function, plan.lifecycle.function)
        self.assertEqual(plan.runtime.queue, plan.lifecycle.queue)
        self.assertEqual(plan.runtime.point_ids, plan.lifecycle.point_ids)
        self.assertEqual(
            tuple(item.operation for item in plan.runtime.requirements),
            (
                DeviceRuntimeOperation.SUBMIT,
                DeviceRuntimeOperation.COMPLETE,
                DeviceRuntimeOperation.SYNCHRONIZE,
                DeviceRuntimeOperation.REACQUIRE,
            ),
        )
        self.assertEqual(
            tuple(
                item.binding
                for item in plan.runtime.requirements_for(DeviceRuntimeOperation.SUBMIT)
            ),
            ("buffer",),
        )
        self.assertEqual(
            plan.runtime.requirements_for(DeviceRuntimeOperation.SYNCHRONIZE)[0].depends_on,
            ("completion@8:1",),
        )

    def test_runtime_dag_preserves_submission_completion_and_sync_dependencies(self):
        plan = plan_device_runtime_from_graph(
            _graph(), function="submit_one", queue="queue0", points=_points()
        )
        complete = plan.runtime.requirements_for(DeviceRuntimeOperation.COMPLETE)
        reacquire = plan.runtime.requirements_for(DeviceRuntimeOperation.REACQUIRE)
        self.assertEqual(complete[0].depends_on, ("handover@3:5",))
        self.assertEqual(reacquire[0].depends_on, ("sync@10:1",))

    def test_runtime_semantic_plan_is_immutable_and_source_stable(self):
        plan = plan_device_runtime_from_graph(
            _graph(), function="submit_one", queue="queue0", points=_points()
        )
        self.assertEqual(
            plan.point_ids,
            (
                "handover@3:5",
                "completion@8:1",
                "sync@10:1",
                "reacquire@11:1",
            ),
        )
        with self.assertRaises(Exception):
            plan.runtime = None  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
