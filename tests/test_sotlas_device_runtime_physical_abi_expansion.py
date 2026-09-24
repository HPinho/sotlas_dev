"""Regression tests for logical-role expansion in DEVICE physical ABIs."""
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_physical_expansion_backend_package"
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


def _logical_plan():
    requirement = lowering.DeviceRuntimeLoweringRequirement
    signatures = lowering.CANONICAL_DEVICE_RUNTIME_SIGNATURES
    return lowering.DeviceRuntimeLoweringPlan(
        abi_name="sotlas.device.reference",
        abi_version=1,
        function="submit_one",
        queue="queue0",
        calls=(
            requirement(
                "submit",
                "handover@1:1",
                "device_submit",
                "buffer",
                (),
                signatures["submit"],
            ),
            requirement(
                "complete",
                "completion@2:1",
                "device_complete",
                "buffer",
                ("handover@1:1",),
                signatures["complete"],
            ),
            requirement(
                "synchronize",
                "sync@3:1",
                "device_sync",
                None,
                ("completion@2:1",),
                signatures["synchronize"],
            ),
            requirement(
                "reacquire",
                "reacquire@4:1",
                "device_reacquire",
                "buffer",
                ("sync@3:1",),
                signatures["reacquire"],
            ),
        ),
    )


def _expanded_contract(*, duplicate_completion_component: bool = False):
    role = lowering.DeviceRuntimeABIValueRole
    parameter = physical.DeviceRuntimePhysicalParameter
    result = physical.DeviceRuntimePhysicalResult
    transport = physical.DeviceRuntimeResultTransport
    operation = physical.DeviceRuntimePhysicalOperationABI
    second_completion_component = "data" if duplicate_completion_component else "count"

    return physical.DeviceRuntimePhysicalABIContract(
        abi_name="sotlas.device.reference",
        abi_version=1,
        backend="reference-test-backend",
        calling_convention="reference-cc",
        operations=(
            operation(
                "submit",
                (
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.HOST_OWNER, "uintptr_t", "address"),
                    parameter(role.HOST_OWNER, "uintptr_t", "extent"),
                ),
                (
                    result(
                        role.DEVICE_OWNER,
                        "uintptr_t",
                        transport.OUT_PARAMETER,
                        "address",
                    ),
                    result(
                        role.DEVICE_OWNER,
                        "uintptr_t",
                        transport.OUT_PARAMETER,
                        "extent",
                    ),
                    result(
                        role.SUBMISSION,
                        "opaque.submission",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                "complete",
                (
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.SUBMISSION, "opaque.submission"),
                ),
                (
                    result(
                        role.COMPLETION,
                        "opaque.completion",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                "synchronize",
                (
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(
                        role.COMPLETION_SET,
                        "opaque.completion_ptr",
                        "data",
                    ),
                    parameter(
                        role.COMPLETION_SET,
                        "usize",
                        second_completion_component,
                    ),
                ),
                (
                    result(
                        role.SYNC_FENCE,
                        "opaque.sync_fence",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                "reacquire",
                (
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.DEVICE_OWNER, "uintptr_t", "address"),
                    parameter(role.DEVICE_OWNER, "uintptr_t", "extent"),
                    parameter(role.SYNC_FENCE, "opaque.sync_fence"),
                ),
                (
                    result(
                        role.HOST_OWNER,
                        "opaque.host_owner",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
        ),
    )


class SotlasDevicePhysicalABIExpansionTests(unittest.TestCase):
    def test_logical_role_can_expand_to_adjacent_named_physical_components(self):
        bound = physical.bind_device_runtime_physical_abi(
            _logical_plan(), _expanded_contract()
        )

        sync = bound.calls[2].physical
        self.assertEqual(
            tuple(parameter.component for parameter in sync.parameters),
            (None, "data", "count"),
        )
        self.assertEqual(
            tuple(parameter.role for parameter in sync.parameters[1:]),
            (
                lowering.DeviceRuntimeABIValueRole.COMPLETION_SET,
                lowering.DeviceRuntimeABIValueRole.COMPLETION_SET,
            ),
        )
        submit = bound.calls[0].physical
        self.assertEqual(
            tuple(result.component for result in submit.results[:2]),
            ("address", "extent"),
        )

    def test_expanded_role_requires_unique_component_names(self):
        with self.assertRaisesRegex(
            physical.DeviceRuntimePhysicalABIError,
            "components must be unique",
        ):
            physical.bind_device_runtime_physical_abi(
                _logical_plan(),
                _expanded_contract(duplicate_completion_component=True),
            )

    def test_expanded_role_components_cannot_be_empty(self):
        contract = _expanded_contract()
        sync = contract.operations[2]
        broken_parameter = physical.DeviceRuntimePhysicalParameter(
            role=lowering.DeviceRuntimeABIValueRole.COMPLETION_SET,
            type_name="usize",
            component="",
        )
        broken_sync = physical.DeviceRuntimePhysicalOperationABI(
            operation=sync.operation,
            parameters=sync.parameters[:-1] + (broken_parameter,),
            results=sync.results,
        )
        broken = physical.DeviceRuntimePhysicalABIContract(
            abi_name=contract.abi_name,
            abi_version=contract.abi_version,
            backend=contract.backend,
            calling_convention=contract.calling_convention,
            operations=contract.operations[:2] + (broken_sync,) + contract.operations[3:],
        )
        with self.assertRaisesRegex(
            physical.DeviceRuntimePhysicalABIError,
            "component requires a non-empty identity",
        ):
            physical.bind_device_runtime_physical_abi(_logical_plan(), broken)


if __name__ == "__main__":
    unittest.main()
