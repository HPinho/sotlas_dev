"""Fail-closed tests for the reference C11 DEVICE declaration boundary."""
from dataclasses import replace
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_c11_failclosed_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


backend_package = _load_backend_package()
lowering = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_lowering"
)
physical = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_physical_abi"
)
c11 = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11")


def _bound_plan():
    requirement = lowering.DeviceRuntimeLoweringRequirement
    signatures = lowering.CANONICAL_DEVICE_RUNTIME_SIGNATURES
    symbols = c11.CANONICAL_C11_DEVICE_SYMBOLS
    logical = lowering.DeviceRuntimeLoweringPlan(
        abi_name=c11.REFERENCE_C11_DEVICE_ABI_NAME,
        abi_version=c11.REFERENCE_C11_DEVICE_ABI_VERSION,
        function="submit_one",
        queue="queue0",
        calls=(
            requirement(
                "submit",
                "handover@1:1",
                symbols["submit"],
                "buffer",
                (),
                signatures["submit"],
            ),
            requirement(
                "complete",
                "completion@2:1",
                symbols["complete"],
                "buffer",
                ("handover@1:1",),
                signatures["complete"],
            ),
            requirement(
                "synchronize",
                "sync@3:1",
                symbols["synchronize"],
                None,
                ("completion@2:1",),
                signatures["synchronize"],
            ),
            requirement(
                "reacquire",
                "reacquire@4:1",
                symbols["reacquire"],
                "buffer",
                ("sync@3:1",),
                signatures["reacquire"],
            ),
        ),
    )
    return physical.bind_device_runtime_physical_abi(
        logical,
        c11.reference_c11_device_runtime_contract(),
    )


class SotlasDeviceRuntimeC11FailClosedTests(unittest.TestCase):
    def test_rejects_operation_reordering_after_physical_binding(self):
        bound = _bound_plan()
        calls = list(bound.calls)
        calls[1], calls[2] = calls[2], calls[1]
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "operation order"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calls=tuple(calls))
            )

    def test_rejects_completion_dependency_drift_after_physical_binding(self):
        bound = _bound_plan()
        complete = bound.calls[1]
        broken = replace(
            complete,
            logical=replace(complete.logical, depends_on=("other-submit",)),
        )
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "completion dependency"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calls=(bound.calls[0], broken, *bound.calls[2:]))
            )

    def test_rejects_completion_binding_drift_after_physical_binding(self):
        bound = _bound_plan()
        complete = bound.calls[1]
        broken = replace(
            complete,
            logical=replace(complete.logical, binding="other-buffer"),
        )
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "completion binding"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calls=(bound.calls[0], broken, *bound.calls[2:]))
            )

    def test_rejects_sync_dependency_drift_after_physical_binding(self):
        bound = _bound_plan()
        sync = bound.calls[2]
        broken = replace(
            sync,
            logical=replace(sync.logical, depends_on=("handover@1:1",)),
        )
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "synchronization dependencies"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calls=(*bound.calls[:2], broken, bound.calls[3]))
            )

    def test_rejects_reacquisition_dependency_or_binding_drift(self):
        bound = _bound_plan()
        reacquire = bound.calls[3]
        wrong_dependency = replace(
            reacquire,
            logical=replace(reacquire.logical, depends_on=("completion@2:1",)),
        )
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "reacquisition dependency"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calls=(*bound.calls[:3], wrong_dependency))
            )

        wrong_binding = replace(
            reacquire,
            logical=replace(reacquire.logical, binding="other-buffer"),
        )
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "reacquisition binding"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calls=(*bound.calls[:3], wrong_binding))
            )


if __name__ == "__main__":
    unittest.main()
