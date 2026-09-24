"""Tests for graph-derived DEVICE frontend/runtime -> SIR correspondence."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE_DIR = ROOT / "compiler" / "sotlas_compile"
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_compile_package():
    name = "sotlas_device_frontend_runtime_sir_compile_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        COMPILE_DIR / "__init__.py",
        submodule_search_locations=[str(COMPILE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_backend_package():
    name = "sotlas_device_frontend_runtime_sir_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


compile_package = _load_compile_package()
typed_ast = importlib.import_module(f"{compile_package.__name__}.typed_ast")
lifecycle = importlib.import_module(f"{compile_package.__name__}.device_lifecycle")
runtime_semantics = importlib.import_module(
    f"{compile_package.__name__}.device_runtime_semantics"
)
backend_package = _load_backend_package()
sir = importlib.import_module(f"{backend_package.__name__}.sir")
frontend_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_frontend_runtime"
)
device_sir = importlib.import_module(f"{backend_package.__name__}.sir.device")
device_sync_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_sync"
)

OwnershipDomain = typed_ast.OwnershipDomain
OwnershipDomainGraph = typed_ast.OwnershipDomainGraph
OwnershipDomainTransition = typed_ast.OwnershipDomainTransition
SemanticType = typed_ast.SemanticType
VarState = typed_ast.VarState
DeviceLifecycleSourcePoints = lifecycle.DeviceLifecycleSourcePoints
DeviceRuntimeSIRValueBinding = frontend_sir.DeviceRuntimeSIRValueBinding
DeviceFrontendRuntimeSIRError = frontend_sir.DeviceFrontendRuntimeSIRError
lower_device_frontend_runtime_to_sir = frontend_sir.lower_device_frontend_runtime_to_sir

TOKEN = SemanticType("Token")


def _submission(binding: str, point_id: str):
    return OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=OwnershipDomain.EXCLUSIVE,
        target=OwnershipDomain.DEVICE,
        source_state=VarState.LIVE,
        operation="handover",
        function="submit_pair",
        point_id=point_id,
    )


def _frontend_plan():
    graph = OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=(
            _submission("left", "handover@3:5"),
            _submission("right", "handover@4:5"),
        ),
    )
    return runtime_semantics.plan_device_runtime_from_graph(
        graph,
        function="submit_pair",
        queue="queue0",
        points=DeviceLifecycleSourcePoints(
            completion_point_ids=("completion@8:1", "completion@8:2"),
            synchronization_point_id="sync@10:1",
            reacquisition_point_ids=("reacquire@11:1", "reacquire@11:2"),
        ),
    )


def _values():
    return (
        DeviceRuntimeSIRValueBinding(
            "left",
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("host_left", "Token"),
        ),
        DeviceRuntimeSIRValueBinding(
            "right",
            sir.SIRValue("device_right", "Token"),
            sir.SIRValue("host_right", "Token"),
        ),
    )


class SotlasDeviceFrontendRuntimeSIRTests(unittest.TestCase):
    def test_graph_derived_runtime_plan_lowers_to_exact_sir_lifecycle(self):
        plan = lower_device_frontend_runtime_to_sir(_frontend_plan(), _values())

        self.assertEqual(plan.bindings, ("left", "right"))
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
        self.assertEqual(len(plan.sir.instructions), 5)
        self.assertTrue(
            all(
                isinstance(inst, device_sir.DeviceCompletionInst)
                for inst in plan.sir.instructions[:2]
            )
        )
        self.assertIsInstance(
            plan.sir.instructions[2], device_sync_sir.DeviceSyncFenceInst
        )
        self.assertTrue(
            all(
                isinstance(inst, device_sir.DeviceReacquisitionInst)
                for inst in plan.sir.instructions[3:]
            )
        )
        self.assertEqual(
            plan.bridge.sir_point_ids,
            (
                "completion@8:1",
                "completion@8:2",
                "sync@10:1",
                "reacquire@11:1",
                "reacquire@11:2",
            ),
        )

    def test_bridge_rejects_semantic_binding_reordering(self):
        values = _values()
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "mapping order diverges"
        ):
            lower_device_frontend_runtime_to_sir(
                _frontend_plan(), tuple(reversed(values))
            )

    def test_bridge_requires_one_mapping_per_owner(self):
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "one value mapping per owner"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), _values()[:1])

    def test_bridge_rejects_same_source_and_destination_value(self):
        values = list(_values())
        values[0] = DeviceRuntimeSIRValueBinding(
            "left",
            sir.SIRValue("same", "Token"),
            sir.SIRValue("same", "Token"),
        )
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "source and destination must be distinct"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), values)

    def test_bridge_rejects_duplicate_source_or_destination_values(self):
        values = list(_values())
        values[1] = DeviceRuntimeSIRValueBinding(
            "right",
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("host_right", "Token"),
        )
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "source values must be unique"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), values)

        values = list(_values())
        values[1] = DeviceRuntimeSIRValueBinding(
            "right",
            sir.SIRValue("device_right", "Token"),
            sir.SIRValue("host_left", "Token"),
        )
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "destination values must be unique"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), values)

    def test_bridge_rejects_runtime_identity_drift_after_frontend_planning(self):
        frontend = _frontend_plan()
        broken = replace(frontend, runtime=replace(frontend.runtime, queue="queue1"))
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "queue identity"
        ):
            lower_device_frontend_runtime_to_sir(broken, _values())


if __name__ == "__main__":
    unittest.main()
