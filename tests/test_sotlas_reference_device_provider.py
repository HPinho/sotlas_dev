from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas.device_provider_runtime import execute_device_provider_plan
from sotlas.device_runtime_c11 import (
    CANONICAL_C11_DEVICE_SYMBOLS,
    reference_c11_device_runtime_contract,
)
from sotlas.reference_device_provider import (
    ReferenceDeviceProvider,
    ReferenceHostOwner,
)
from sotlas.sir.device_runtime_lowering import (
    CANONICAL_DEVICE_RUNTIME_SIGNATURES,
    DeviceRuntimeLoweringPlan,
    DeviceRuntimeLoweringRequirement,
)
from sotlas.sir.device_runtime_physical_abi import bind_device_runtime_physical_abi


def _req(operation, point, binding, dependencies):
    return DeviceRuntimeLoweringRequirement(
        operation=operation,
        point_id=point,
        symbol=CANONICAL_C11_DEVICE_SYMBOLS[operation],
        binding=binding,
        depends_on=dependencies,
        signature=CANONICAL_DEVICE_RUNTIME_SIGNATURES[operation],
    )


def _plan():
    contract = reference_c11_device_runtime_contract()
    logical = DeviceRuntimeLoweringPlan(
        abi_name=contract.abi_name,
        abi_version=contract.abi_version,
        function="reference_kernel",
        queue="queue0",
        calls=(
            _req("submit", "submit:buffer", "buffer", ()),
            _req("complete", "complete:buffer", "buffer", ("submit:buffer",)),
            _req("synchronize", "sync:buffer", None, ("complete:buffer",)),
            _req("reacquire", "reacquire:buffer", "buffer", ("sync:buffer",)),
        ),
    )
    return bind_device_runtime_physical_abi(logical, contract)


class SotlasReferenceDeviceProviderTests(unittest.TestCase):
    def test_reference_provider_executes_generation_safe_lifecycle(self):
        result = execute_device_provider_plan(_plan(), ReferenceDeviceProvider())
        self.assertEqual(
            result.point_ids,
            ("submit:buffer", "complete:buffer", "sync:buffer", "reacquire:buffer"),
        )
        self.assertEqual(len(result.reacquisitions), 1)
        host = result.reacquisitions[0].host_owner
        self.assertIsInstance(host, ReferenceHostOwner)
        self.assertEqual(host.binding, "buffer")
        self.assertEqual(host.generation, 1)

    def test_reference_provider_rejects_cross_queue_and_token_reuse(self):
        provider = ReferenceDeviceProvider()
        owner, submission = provider.submit(
            queue="q0", binding="buffer", point_id="submit:buffer"
        )
        completion = provider.complete(
            queue="q0",
            submission=submission,
            binding="buffer",
            point_id="complete:buffer",
            timeout_ms=None,
        )
        fence = provider.synchronize(
            queue="q0",
            completions=(completion,),
            point_id="sync:buffer",
            timeout_ms=None,
        )
        provider.reacquire(
            queue="q0",
            device_owner=owner,
            fence=fence,
            binding="buffer",
            point_id="reacquire:buffer",
        )
        with self.assertRaisesRegex(RuntimeError, "reacquired"):
            provider.reacquire(
                queue="q0",
                device_owner=owner,
                fence=fence,
                binding="buffer",
                point_id="reacquire:again",
            )
        with self.assertRaisesRegex(RuntimeError, "queue identity changed"):
            provider.submit(queue="q1", binding="other", point_id="submit:other")

    def test_compatibility_mirror_is_byte_identical(self):
        canonical = ROOT / "compiler" / "sotlas" / "reference_device_provider.py"
        mirror = ROOT / "tools" / "sotlas" / "reference_device_provider.py"
        self.assertEqual(canonical.read_bytes(), mirror.read_bytes())


if __name__ == "__main__":
    unittest.main()
