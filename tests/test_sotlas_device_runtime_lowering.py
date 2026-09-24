"""Tests for the backend-neutral DEVICE runtime lowering contract."""
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
    name = "sotlas_device_runtime_lowering_compile_package"
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
    name = "sotlas_device_runtime_lowering_backend_package"
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
device_runtime_lowering = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_lowering"
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


def _call_plan():
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
    return device_runtime_calls.plan_bound_device_runtime_calls(bridge, bound)


class SotlasDeviceRuntimeLoweringTests(unittest.TestCase):
    def test_lowering_plan_freezes_logical_signatures_without_physical_abi(self):
        plan = device_runtime_lowering.plan_device_runtime_lowering(_call_plan())
        role = device_runtime_lowering.DeviceRuntimeABIValueRole

        self.assertEqual(plan.abi_name, "sotlas.device.reference")
        self.assertEqual(plan.abi_version, 1)
        self.assertEqual(plan.function, "submit_pair")
        self.assertEqual(plan.queue, "queue0")
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
        self.assertEqual(
            plan.calls[0].signature.parameters,
            (role.QUEUE, role.HOST_OWNER),
        )
        self.assertEqual(
            plan.calls[0].signature.results,
            (role.DEVICE_OWNER, role.SUBMISSION),
        )
        self.assertEqual(
            plan.calls[2].signature.parameters,
            (role.QUEUE, role.SUBMISSION),
        )
        self.assertEqual(
            plan.calls[4].signature.parameters,
            (role.QUEUE, role.COMPLETION_SET),
        )
        self.assertEqual(
            plan.calls[4].signature.results,
            (role.SYNC_FENCE,),
        )
        self.assertEqual(
            plan.calls[5].signature.parameters,
            (role.QUEUE, role.DEVICE_OWNER, role.SYNC_FENCE),
        )
        self.assertEqual(
            plan.calls[5].signature.results,
            (role.HOST_OWNER,),
        )

    def test_lowering_plan_rejects_reordered_lifecycle(self):
        call_plan = _call_plan()
        calls = list(call_plan.calls)
        calls[0], calls[2] = calls[2], calls[0]
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "operation order diverges",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

    def test_lowering_plan_rejects_duplicate_point_identity(self):
        call_plan = _call_plan()
        calls = list(call_plan.calls)
        calls[1] = replace(calls[1], point_id=calls[0].point_id)
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "point identities must remain globally unique",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

    def test_lowering_plan_rejects_completion_dependency_drift(self):
        call_plan = _call_plan()
        calls = list(call_plan.calls)
        calls[2] = replace(calls[2], depends_on=(calls[1].point_id,))
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "completion dependency diverges",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

    def test_lowering_plan_rejects_sync_dependency_or_binding_drift(self):
        call_plan = _call_plan()
        calls = list(call_plan.calls)
        calls[4] = replace(calls[4], depends_on=(calls[2].point_id,))
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "synchronization dependency set diverges",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

        calls = list(call_plan.calls)
        calls[4] = replace(calls[4], binding="left")
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "must cover the batch",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

    def test_lowering_plan_rejects_reacquisition_binding_drift(self):
        call_plan = _call_plan()
        calls = list(call_plan.calls)
        calls[5] = replace(calls[5], binding="right")
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "reacquisition binding diverges",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

    def test_lowering_plan_rejects_symbol_drift_and_cross_operation_reuse(self):
        call_plan = _call_plan()
        calls = list(call_plan.calls)
        calls[1] = replace(calls[1], symbol="other_submit")
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "symbol drifts within one operation",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

        calls = list(call_plan.calls)
        calls[2] = replace(calls[2], symbol=calls[0].symbol)
        with self.assertRaisesRegex(
            device_runtime_lowering.DeviceRuntimeLoweringPlanError,
            "reused by different operations",
        ):
            device_runtime_lowering.plan_device_runtime_lowering(
                replace(call_plan, calls=tuple(calls))
            )

    def test_lowering_plan_rejects_invalid_plan_identity(self):
        call_plan = _call_plan()
        for broken, message in (
            (replace(call_plan, abi_name=""), "ABI name"),
            (replace(call_plan, abi_version=0), "positive integer"),
            (replace(call_plan, function=""), "runtime function"),
            (replace(call_plan, queue=""), "runtime queue"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    device_runtime_lowering.DeviceRuntimeLoweringPlanError,
                    message,
                ):
                    device_runtime_lowering.plan_device_runtime_lowering(broken)


if __name__ == "__main__":
    unittest.main()
