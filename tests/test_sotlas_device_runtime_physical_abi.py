"""Tests for concrete-backend DEVICE physical ABI declarations."""
from dataclasses import replace
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_physical_abi_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


backend_package = _load_backend_package()
device_runtime_calls = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_calls"
)
device_runtime_lowering = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_lowering"
)
device_runtime_physical_abi = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_physical_abi"
)


def _call_plan():
    call = device_runtime_calls.DeviceRuntimeCallRequirement
    return device_runtime_calls.DeviceRuntimeCallRequirementPlan(
        abi_name="sotlas.device.reference",
        abi_version=1,
        function="submit_pair",
        queue="queue0",
        calls=(
            call("submit", "handover@3:5", "device_submit", "left", ()),
            call("submit", "handover@4:5", "device_submit", "right", ()),
            call(
                "complete",
                "completion@8:1",
                "device_complete",
                "left",
                ("handover@3:5",),
            ),
            call(
                "complete",
                "completion@8:2",
                "device_complete",
                "right",
                ("handover@4:5",),
            ),
            call(
                "synchronize",
                "sync@10:1",
                "device_sync",
                None,
                ("completion@8:1", "completion@8:2"),
            ),
            call(
                "reacquire",
                "reacquire@11:1",
                "device_reacquire",
                "left",
                ("sync@10:1",),
            ),
            call(
                "reacquire",
                "reacquire@11:2",
                "device_reacquire",
                "right",
                ("sync@10:1",),
            ),
        ),
    )


def _logical_plan():
    return device_runtime_lowering.plan_device_runtime_lowering(_call_plan())


def _physical_contract():
    role = device_runtime_lowering.DeviceRuntimeABIValueRole
    parameter = device_runtime_physical_abi.DeviceRuntimePhysicalParameter
    result = device_runtime_physical_abi.DeviceRuntimePhysicalResult
    transport = device_runtime_physical_abi.DeviceRuntimeResultTransport
    operation = device_runtime_physical_abi.DeviceRuntimePhysicalOperationABI
    return device_runtime_physical_abi.DeviceRuntimePhysicalABIContract(
        abi_name="sotlas.device.reference",
        abi_version=1,
        backend="reference-test-backend",
        calling_convention="reference-cc",
        operations=(
            operation(
                operation="submit",
                parameters=(
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.HOST_OWNER, "opaque.host_owner"),
                ),
                results=(
                    result(
                        role.DEVICE_OWNER,
                        "opaque.device_owner",
                        transport.OUT_PARAMETER,
                    ),
                    result(
                        role.SUBMISSION,
                        "opaque.submission",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                operation="complete",
                parameters=(
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.SUBMISSION, "opaque.submission"),
                ),
                results=(
                    result(
                        role.COMPLETION,
                        "opaque.completion",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                operation="synchronize",
                parameters=(
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.COMPLETION_SET, "opaque.completion_set"),
                ),
                results=(
                    result(
                        role.SYNC_FENCE,
                        "opaque.sync_fence",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
            operation(
                operation="reacquire",
                parameters=(
                    parameter(role.QUEUE, "opaque.queue"),
                    parameter(role.DEVICE_OWNER, "opaque.device_owner"),
                    parameter(role.SYNC_FENCE, "opaque.sync_fence"),
                ),
                results=(
                    result(
                        role.HOST_OWNER,
                        "opaque.host_owner",
                        transport.RETURN_VALUE,
                    ),
                ),
            ),
        ),
    )


class SotlasDeviceRuntimePhysicalABITests(unittest.TestCase):
    def test_physical_contract_binds_without_emitting_calls(self):
        logical = _logical_plan()
        contract = _physical_contract()
        bound = device_runtime_physical_abi.bind_device_runtime_physical_abi(
            logical, contract
        )

        self.assertEqual(bound.abi_name, logical.abi_name)
        self.assertEqual(bound.abi_version, logical.abi_version)
        self.assertEqual(bound.backend, "reference-test-backend")
        self.assertEqual(bound.calling_convention, "reference-cc")
        self.assertEqual(bound.point_ids, logical.point_ids)
        self.assertEqual(len(bound.calls), len(logical.calls))
        self.assertEqual(bound.calls[0].physical.operation, "submit")
        self.assertEqual(
            bound.calls[0].physical.results[0].transport,
            device_runtime_physical_abi.DeviceRuntimeResultTransport.OUT_PARAMETER,
        )

    def test_physical_contract_rejects_name_or_version_drift(self):
        logical = _logical_plan()
        contract = _physical_contract()
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "name diverges",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical, replace(contract, abi_name="other")
            )
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "version diverges",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical, replace(contract, abi_version=2)
            )

    def test_physical_contract_rejects_missing_or_extra_operation(self):
        logical = _logical_plan()
        contract = _physical_contract()
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "exact logical operation set",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical, replace(contract, operations=contract.operations[:-1])
            )

        extra = replace(contract.operations[-1], operation="poll")
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "exact logical operation set",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical, replace(contract, operations=contract.operations + (extra,))
            )

    def test_physical_contract_rejects_duplicate_operation(self):
        logical = _logical_plan()
        contract = _physical_contract()
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "more than once",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical,
                replace(
                    contract,
                    operations=contract.operations + (contract.operations[0],),
                ),
            )

    def test_physical_contract_rejects_parameter_role_reordering(self):
        logical = _logical_plan()
        contract = _physical_contract()
        submit = contract.operations[0]
        broken_submit = replace(
            submit,
            parameters=tuple(reversed(submit.parameters)),
        )
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "parameter roles diverge",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical,
                replace(
                    contract,
                    operations=(broken_submit,) + contract.operations[1:],
                ),
            )

    def test_physical_contract_rejects_result_role_loss(self):
        logical = _logical_plan()
        contract = _physical_contract()
        submit = contract.operations[0]
        broken_submit = replace(submit, results=submit.results[1:])
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "result roles diverge",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical,
                replace(
                    contract,
                    operations=(broken_submit,) + contract.operations[1:],
                ),
            )

    def test_physical_contract_rejects_empty_physical_type(self):
        logical = _logical_plan()
        contract = _physical_contract()
        complete = contract.operations[1]
        broken_parameter = replace(complete.parameters[0], type_name="")
        broken_complete = replace(
            complete,
            parameters=(broken_parameter,) + complete.parameters[1:],
        )
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "parameter type requires",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical,
                replace(
                    contract,
                    operations=(
                        contract.operations[0],
                        broken_complete,
                        *contract.operations[2:],
                    ),
                ),
            )

    def test_physical_contract_rejects_multiple_direct_return_values(self):
        logical = _logical_plan()
        contract = _physical_contract()
        submit = contract.operations[0]
        transport = device_runtime_physical_abi.DeviceRuntimeResultTransport
        broken_submit = replace(
            submit,
            results=tuple(
                replace(result, transport=transport.RETURN_VALUE)
                for result in submit.results
            ),
        )
        with self.assertRaisesRegex(
            device_runtime_physical_abi.DeviceRuntimePhysicalABIError,
            "multiple direct return values",
        ):
            device_runtime_physical_abi.bind_device_runtime_physical_abi(
                logical,
                replace(
                    contract,
                    operations=(broken_submit,) + contract.operations[1:],
                ),
            )


if __name__ == "__main__":
    unittest.main()
