from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas.device_provider_runtime import (
    DeviceProviderContractError,
    DeviceProviderFailure,
    DeviceProviderTimeout,
    execute_device_provider_plan,
)
from sotlas.device_runtime_c11 import (
    CANONICAL_C11_DEVICE_SYMBOLS,
    reference_c11_device_runtime_contract,
)
from sotlas.sir.device_runtime_lowering import (
    CANONICAL_DEVICE_RUNTIME_SIGNATURES,
    DeviceRuntimeLoweringPlan,
    DeviceRuntimeLoweringRequirement,
)
from sotlas.sir.device_runtime_physical_abi import bind_device_runtime_physical_abi


def _requirement(operation, point_id, binding, dependencies):
    return DeviceRuntimeLoweringRequirement(
        operation=operation,
        point_id=point_id,
        symbol=CANONICAL_C11_DEVICE_SYMBOLS[operation],
        binding=binding,
        depends_on=dependencies,
        signature=CANONICAL_DEVICE_RUNTIME_SIGNATURES[operation],
    )


def _bound_plan():
    contract = reference_c11_device_runtime_contract()
    logical = DeviceRuntimeLoweringPlan(
        abi_name=contract.abi_name,
        abi_version=contract.abi_version,
        function="device_kernel",
        queue="queue0",
        calls=(
            _requirement("submit", "submit:a", "a", ()),
            _requirement("submit", "submit:b", "b", ()),
            _requirement("complete", "complete:a", "a", ("submit:a",)),
            _requirement("complete", "complete:b", "b", ("submit:b",)),
            _requirement(
                "synchronize", "sync:all", None, ("complete:a", "complete:b")
            ),
            _requirement("reacquire", "reacquire:a", "a", ("sync:all",)),
            _requirement("reacquire", "reacquire:b", "b", ("sync:all",)),
        ),
    )
    return bind_device_runtime_physical_abi(logical, contract)


class RecordingProvider:
    name = "recording-provider"

    def __init__(self, *, timeout_point=None, failure_point=None, bad_submit=False):
        self.timeout_point = timeout_point
        self.failure_point = failure_point
        self.bad_submit = bad_submit
        self.events = []

    def _before(self, operation, point_id):
        self.events.append((operation, point_id))
        if point_id == self.timeout_point:
            raise TimeoutError(point_id)
        if point_id == self.failure_point:
            raise RuntimeError(point_id)

    def submit(self, *, queue, binding, point_id):
        self._before("submit", point_id)
        if self.bad_submit:
            return None
        return (f"device:{binding}", f"submission:{binding}")

    def complete(self, *, queue, submission, binding, point_id, timeout_ms):
        self._before("complete", point_id)
        return f"completion:{binding}:{timeout_ms}"

    def synchronize(self, *, queue, completions, point_id, timeout_ms):
        self._before("synchronize", point_id)
        return f"fence:{len(completions)}:{timeout_ms}"

    def reacquire(self, *, queue, device_owner, fence, binding, point_id):
        self._before("reacquire", point_id)
        return f"host:{binding}"


class SotlasDeviceProviderRuntimeTests(unittest.TestCase):
    def test_success_preserves_canonical_points_and_reacquires_after_fence(self):
        provider = RecordingProvider()
        plan = _bound_plan()
        result = execute_device_provider_plan(plan, provider, timeout_ms=25)

        self.assertEqual(result.provider, "recording-provider")
        self.assertEqual(result.function, "device_kernel")
        self.assertEqual(result.queue, "queue0")
        self.assertEqual(result.point_ids, plan.point_ids)
        self.assertEqual(
            provider.events,
            [
                ("submit", "submit:a"),
                ("submit", "submit:b"),
                ("complete", "complete:a"),
                ("complete", "complete:b"),
                ("synchronize", "sync:all"),
                ("reacquire", "reacquire:a"),
                ("reacquire", "reacquire:b"),
            ],
        )
        self.assertEqual(result.fence.completion_point_ids, ("complete:a", "complete:b"))
        self.assertEqual(
            tuple(item.fence_point_id for item in result.reacquisitions),
            ("sync:all", "sync:all"),
        )

    def test_completion_timeout_stops_before_sync_and_reacquire(self):
        provider = RecordingProvider(timeout_point="complete:b")
        with self.assertRaises(DeviceProviderTimeout) as caught:
            execute_device_provider_plan(_bound_plan(), provider, timeout_ms=5)
        self.assertEqual(caught.exception.operation, "complete")
        self.assertEqual(caught.exception.point_id, "complete:b")
        self.assertNotIn(("synchronize", "sync:all"), provider.events)
        self.assertFalse(any(op == "reacquire" for op, _ in provider.events))

    def test_sync_failure_never_returns_ownership_to_host(self):
        provider = RecordingProvider(failure_point="sync:all")
        with self.assertRaises(DeviceProviderFailure) as caught:
            execute_device_provider_plan(_bound_plan(), provider)
        self.assertEqual(caught.exception.operation, "synchronize")
        self.assertEqual(caught.exception.point_id, "sync:all")
        self.assertFalse(any(op == "reacquire" for op, _ in provider.events))

    def test_provider_results_and_timeout_configuration_fail_closed(self):
        with self.assertRaisesRegex(
            DeviceProviderContractError,
            r"submit must return \(device_owner, submission\)",
        ):
            execute_device_provider_plan(_bound_plan(), RecordingProvider(bad_submit=True))
        with self.assertRaisesRegex(DeviceProviderContractError, "non-negative"):
            execute_device_provider_plan(_bound_plan(), RecordingProvider(), timeout_ms=-1)

    def test_reordered_bound_plan_is_rejected_before_provider_execution(self):
        plan = _bound_plan()
        calls = list(plan.calls)
        calls[0], calls[2] = calls[2], calls[0]
        mutated = replace(plan, calls=tuple(calls))
        provider = RecordingProvider()
        with self.assertRaisesRegex(DeviceProviderContractError, "canonical lifecycle order"):
            execute_device_provider_plan(mutated, provider)
        self.assertEqual(provider.events, [])

    def test_compatibility_mirror_is_byte_identical(self):
        canonical = ROOT / "compiler" / "sotlas" / "device_provider_runtime.py"
        mirror = ROOT / "tools" / "sotlas" / "device_provider_runtime.py"
        self.assertEqual(canonical.read_bytes(), mirror.read_bytes())


if __name__ == "__main__":
    unittest.main()
