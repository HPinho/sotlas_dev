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


def _frontend_plan():
    graph = OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=(
            OwnershipDomainTransition(
                binding="buffer",
                type=TOKEN,
                source=OwnershipDomain.EXCLUSIVE,
                target=OwnershipDomain.DEVICE,
                source_state=VarState.LIVE,
                operation="handover",
                function="submit_one",
                point_id="handover@3:5",
            ),
        ),
    )
    return runtime_semantics.plan_device_runtime_from_graph(
        graph,
        function="submit_one",
        queue="queue0",
        points=DeviceLifecycleSourcePoints(
            completion_point_ids=("completion@8:1",),
            synchronization_point_id="sync@10:1",
            reacquisition_point_ids=("reacquire@11:1",),
        ),
    )


def _values():
    return (
        DeviceRuntimeSIRValueBinding(
            "buffer",
            sir.SIRValue("device_buffer", "Token"),
            sir.SIRValue("host_buffer", "Token"),
        ),
    )


class SotlasDeviceFrontendRuntimeSIRTests(unittest.TestCase):
    def test_graph_derived_runtime_plan_lowers_to_exact_sir_lifecycle(self):
        plan = lower_device_frontend_runtime_to_sir(_frontend_plan(), _values())
        self.assertEqual(plan.bindings, ("buffer",))
        self.assertEqual(
            plan.point_ids,
            (
                "handover@3:5",
                "completion@8:1",
                "sync@10:1",
                "reacquire@11:1",
            ),
        )
        self.assertEqual(len(plan.sir.instructions), 3)
        self.assertIsInstance(plan.sir.instructions[0], device_sir.DeviceCompletionInst)
        self.assertIsInstance(plan.sir.instructions[1], device_sync_sir.DeviceSyncFenceInst)
        self.assertIsInstance(plan.sir.instructions[2], device_sir.DeviceReacquisitionInst)
        self.assertEqual(
            plan.bridge.sir_point_ids,
            ("completion@8:1", "sync@10:1", "reacquire@11:1"),
        )

    def test_bridge_rejects_semantic_binding_mismatch(self):
        values = (
            DeviceRuntimeSIRValueBinding(
                "other",
                sir.SIRValue("device_buffer", "Token"),
                sir.SIRValue("host_buffer", "Token"),
            ),
        )
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "mapping order diverges"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), values)

    def test_bridge_requires_exactly_one_mapping_per_owner(self):
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "at least one owner mapping"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), ())
        extra = _values() + (
            DeviceRuntimeSIRValueBinding(
                "extra",
                sir.SIRValue("device_extra", "Token"),
                sir.SIRValue("host_extra", "Token"),
            ),
        )
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "one value mapping per owner"
        ):
            lower_device_frontend_runtime_to_sir(_frontend_plan(), extra)

    def test_bridge_rejects_same_source_and_destination_value(self):
        values = (
            DeviceRuntimeSIRValueBinding(
                "buffer",
                sir.SIRValue("same", "Token"),
                sir.SIRValue("same", "Token"),
            ),
        )
        with self.assertRaisesRegex(
            DeviceFrontendRuntimeSIRError, "source and destination must be distinct"
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
