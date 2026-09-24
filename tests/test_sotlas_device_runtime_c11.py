"""Tests for declaration-only reference C11 DEVICE runtime lowering."""
from dataclasses import replace
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_c11_backend_package"
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


def _logical_plan():
    requirement = lowering.DeviceRuntimeLoweringRequirement
    signatures = lowering.CANONICAL_DEVICE_RUNTIME_SIGNATURES
    symbols = c11.CANONICAL_C11_DEVICE_SYMBOLS
    return lowering.DeviceRuntimeLoweringPlan(
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


def _bound_plan():
    logical = _logical_plan()
    return physical.bind_device_runtime_physical_abi(
        logical,
        c11.reference_c11_device_runtime_contract(),
    )


class SotlasDeviceRuntimeC11Tests(unittest.TestCase):
    def test_reference_contract_freezes_expected_physical_shapes(self):
        contract = c11.reference_c11_device_runtime_contract()
        self.assertEqual(contract.backend, "c11-reference")
        self.assertEqual(contract.calling_convention, "c")
        self.assertEqual(
            tuple(operation.operation for operation in contract.operations),
            ("submit", "complete", "synchronize", "reacquire"),
        )
        sync = contract.operations[2]
        self.assertEqual(
            tuple((parameter.role.value, parameter.component) for parameter in sync.parameters),
            (("queue", None), ("completion_set", "data"), ("completion_set", "count")),
        )

    def test_c11_plan_renders_declarations_without_call_emission(self):
        plan = c11.plan_reference_c11_device_runtime(_bound_plan())
        self.assertEqual(plan.point_ids, _logical_plan().point_ids)
        self.assertEqual(
            plan.render_declarations(),
            "#include <stddef.h>\n"
            "#include <stdint.h>\n"
            "\n"
            "typedef uintptr_t sotlas_device_queue_t;\n"
            "typedef uintptr_t sotlas_device_submission_t;\n"
            "typedef uintptr_t sotlas_device_completion_t;\n"
            "typedef uintptr_t sotlas_device_fence_t;\n"
            "\n"
            "sotlas_device_submission_t sotlas_device_submit("
            "sotlas_device_queue_t queue, uintptr_t host_address, size_t host_extent, "
            "uintptr_t * out_device_address, size_t * out_device_extent);\n"
            "sotlas_device_completion_t sotlas_device_complete("
            "sotlas_device_queue_t queue, sotlas_device_submission_t submission);\n"
            "sotlas_device_fence_t sotlas_device_sync("
            "sotlas_device_queue_t queue, const sotlas_device_completion_t * completions, "
            "size_t completion_count);\n"
            "void sotlas_device_reacquire("
            "sotlas_device_queue_t queue, uintptr_t device_address, size_t device_extent, "
            "sotlas_device_fence_t fence, uintptr_t * out_host_address, "
            "size_t * out_host_extent);\n",
        )

    def test_c11_plan_preserves_physical_operand_map_per_lifecycle_point(self):
        plan = c11.plan_reference_c11_device_runtime(_bound_plan())
        submit, complete, sync, reacquire = plan.calls

        self.assertEqual(submit.point_id, "handover@1:1")
        self.assertEqual(
            tuple(slot.name for slot in submit.inputs),
            ("queue", "host_address", "host_extent"),
        )
        self.assertEqual(
            tuple(slot.name for slot in submit.outputs),
            ("out_device_address", "out_device_extent"),
        )
        self.assertEqual(submit.direct_result.name, "submission")

        self.assertEqual(complete.direct_result.name, "completion")
        self.assertEqual(
            tuple(slot.name for slot in sync.inputs),
            ("queue", "completions", "completion_count"),
        )
        self.assertEqual(sync.direct_result.name, "fence")

        self.assertIsNone(reacquire.direct_result)
        self.assertEqual(
            tuple(slot.name for slot in reacquire.outputs),
            ("out_host_address", "out_host_extent"),
        )

    def test_c11_plan_rejects_backend_or_calling_convention_drift(self):
        bound = _bound_plan()
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "backend identity"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, backend="other-c11")
            )
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "calling convention"):
            c11.plan_reference_c11_device_runtime(
                replace(bound, calling_convention="other")
            )

    def test_c11_plan_rejects_symbol_drift_after_physical_binding(self):
        bound = _bound_plan()
        first = bound.calls[0]
        broken_logical = replace(first.logical, symbol="other_submit")
        broken_first = replace(first, logical=broken_logical)
        broken = replace(bound, calls=(broken_first,) + bound.calls[1:])
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "symbol diverges"):
            c11.plan_reference_c11_device_runtime(broken)

    def test_c11_plan_rejects_physical_layout_drift_after_binding(self):
        bound = _bound_plan()
        first = bound.calls[0]
        parameters = list(first.physical.parameters)
        parameters[1] = replace(parameters[1], type_name="uint64_t")
        broken_physical = replace(first.physical, parameters=tuple(parameters))
        broken_first = replace(first, physical=broken_physical)
        broken = replace(bound, calls=(broken_first,) + bound.calls[1:])
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "physical ABI diverges"):
            c11.plan_reference_c11_device_runtime(broken)

    def test_c11_plan_rejects_duplicate_lifecycle_identity(self):
        bound = _bound_plan()
        second = bound.calls[1]
        broken_second = replace(
            second,
            logical=replace(second.logical, point_id=bound.calls[0].logical.point_id),
        )
        broken = replace(bound, calls=(bound.calls[0], broken_second, *bound.calls[2:]))
        with self.assertRaisesRegex(c11.DeviceRuntimeC11ABIError, "globally unique"):
            c11.plan_reference_c11_device_runtime(broken)


if __name__ == "__main__":
    unittest.main()
