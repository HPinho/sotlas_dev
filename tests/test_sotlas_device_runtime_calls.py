"""Tests for backend-neutral DEVICE runtime call requirements."""
from dataclasses import replace
from pathlib import Path
import importlib
import importlib.util
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE_DIR = ROOT / "compiler" / "sotlas_compile"
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_compile_package():
    name = "sotlas_device_runtime_calls_compile_package"
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
    name = "sotlas_device_runtime_calls_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


compile_package = _load_compile_package()
device_ownership = importlib.import_module(
    f"{compile_package.__name__}.device_ownership"
)
device_sync = importlib.import_module(f"{compile_package.__name__}.device_sync")
device_runtime_abi = importlib.import_module(
    f"{compile_package.__name__}.device_runtime_abi"
)
typed_ast = importlib.import_module(f"{compile_package.__name__}.typed_ast")
backend_package = _load_backend_package()
sir = importlib.import_module(f"{backend_package.__name__}.sir")
device_sync_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_sync"
)
device_runtime_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime"
)
device_runtime_calls = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_calls"
)

TOKEN = typed_ast.SemanticType("Token")


def _submission(binding: str, point_id: str):
    return typed_ast.OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=typed_ast.OwnershipDomain.EXCLUSIVE,
        target=typed_ast.OwnershipDomain.DEVICE,
        source_state=typed_ast.VarState.LIVE,
        operation="handover",
        function="submit_pair",
        point_id=point_id,
    )


def _completed(binding: str, submit: str, complete: str):
    graph = typed_ast.OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=(_submission(binding, submit),),
    )
    token = device_ownership.open_device_completion(
        graph, function="submit_pair", binding=binding
    )
    return device_ownership.complete_device_transfer(token, point_id=complete)


def _validated_bound_plans():
    tokens = (
        _completed("left", "handover@3:5", "completion@8:1"),
        _completed("right", "handover@4:5", "completion@8:2"),
    )
    fence = device_sync.plan_device_sync(
        tokens,
        function="submit_pair",
        queue="queue0",
        point_id="sync@10:1",
    )
    batch = device_sync.plan_synced_reacquisitions(
        tokens,
        fence,
        point_ids=("reacquire@11:1", "reacquire@11:2"),
    )
    runtime_plan = device_runtime_abi.plan_device_runtime_requirements(tokens, batch)
    sir_plan = device_sync_sir.lower_device_sync_batch(
        batch,
        tokens,
        (
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("device_right", "Token"),
        ),
        (
            sir.SIRValue("host_left", "Token"),
            sir.SIRValue("host_right", "Token"),
        ),
    )
    bridge = device_runtime_sir.validate_device_runtime_sir_plan(
        sir_plan, runtime_plan
    )
    contract = device_runtime_abi.DeviceRuntimeABIContract(
        name="sotlas.device.reference",
        version=1,
        symbols=(
            device_runtime_abi.DeviceRuntimeABISymbol(
                device_runtime_abi.DeviceRuntimeOperation.SUBMIT,
                "sotlas_device_submit",
            ),
            device_runtime_abi.DeviceRuntimeABISymbol(
                device_runtime_abi.DeviceRuntimeOperation.COMPLETE,
                "sotlas_device_complete",
            ),
            device_runtime_abi.DeviceRuntimeABISymbol(
                device_runtime_abi.DeviceRuntimeOperation.SYNCHRONIZE,
                "sotlas_device_sync",
            ),
            device_runtime_abi.DeviceRuntimeABISymbol(
                device_runtime_abi.DeviceRuntimeOperation.REACQUIRE,
                "sotlas_device_reacquire",
            ),
        ),
    )
    bound = device_runtime_abi.bind_device_runtime_abi(runtime_plan, contract)
    return bridge, bound


class SotlasDeviceRuntimeCallPlanTests(unittest.TestCase):
    def test_call_plan_freezes_exact_bound_lifecycle_without_execution(self):
        bridge, bound = _validated_bound_plans()
        plan = device_runtime_calls.plan_bound_device_runtime_calls(bridge, bound)

        self.assertEqual(plan.abi_name, "sotlas.device.reference")
        self.assertEqual(plan.abi_version, 1)
        self.assertEqual(plan.function, "submit_pair")
        self.assertEqual(plan.queue, "queue0")
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
        self.assertEqual(
            tuple(call.operation for call in plan.calls),
            (
                "submit",
                "submit",
                "complete",
                "complete",
                "synchronize",
                "reacquire",
                "reacquire",
            ),
        )
        self.assertEqual(plan.calls[0].symbol, "sotlas_device_submit")
        self.assertEqual(plan.calls[4].symbol, "sotlas_device_sync")
        self.assertEqual(plan.calls[5].depends_on, ("sync@10:1",))

    def test_call_plan_rejects_reordered_bound_requirements(self):
        bridge, bound = _validated_bound_plans()
        entries = list(bound.requirements)
        entries[0], entries[1] = entries[1], entries[0]
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "point order diverges",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, requirements=tuple(entries))
            )

    def test_call_plan_rejects_symbol_drift_within_operation(self):
        bridge, bound = _validated_bound_plans()
        entries = list(bound.requirements)
        entries[1] = replace(entries[1], symbol="other_submit")
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "symbol drifts within one operation",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, requirements=tuple(entries))
            )

    def test_call_plan_rejects_one_symbol_reused_across_operations(self):
        bridge, bound = _validated_bound_plans()
        entries = list(bound.requirements)
        entries[2] = replace(entries[2], symbol="sotlas_device_submit")
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "reused by different operations",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, requirements=tuple(entries))
            )

    def test_call_plan_rejects_dependency_drift_after_abi_binding(self):
        bridge, bound = _validated_bound_plans()
        entries = list(bound.requirements)
        requirement = replace(
            entries[2].requirement,
            depends_on=("handover@4:5",),
        )
        entries[2] = replace(entries[2], requirement=requirement)
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "dependency graph diverges",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, requirements=tuple(entries))
            )

    def test_call_plan_rejects_binding_drift_after_abi_binding(self):
        bridge, bound = _validated_bound_plans()
        entries = list(bound.requirements)
        requirement = replace(entries[2].requirement, binding="right")
        entries[2] = replace(entries[2], requirement=requirement)
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "completion binding diverges",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, requirements=tuple(entries))
            )

    def test_call_plan_rejects_corrupted_bridge_even_if_bound_plan_is_valid(self):
        bridge, bound = _validated_bound_plans()
        broken = replace(
            bridge,
            runtime_point_ids=(
                "handover@4:5",
                "handover@3:5",
                *bridge.runtime_point_ids[2:],
            ),
        )
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "runtime point order is internally inconsistent",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(broken, bound)

    def test_call_plan_rejects_bound_function_queue_or_version_drift(self):
        bridge, bound = _validated_bound_plans()
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "crosses function identity",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, function="other")
            )
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "crosses queue identity",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, queue="queue1")
            )
        with self.assertRaisesRegex(
            device_runtime_calls.DeviceRuntimeCallPlanError,
            "version must remain a positive integer",
        ):
            device_runtime_calls.plan_bound_device_runtime_calls(
                bridge, replace(bound, abi_version=0)
            )


if __name__ == "__main__":
    unittest.main()
