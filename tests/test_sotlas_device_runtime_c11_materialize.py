"""Tests for non-executable C11 DEVICE operand materialization."""
from dataclasses import replace
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_c11_materialize_backend_package"
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
materialize = importlib.import_module(
    f"{backend_package.__name__}.device_runtime_c11_materialize"
)


def _logical_plan():
    requirement = lowering.DeviceRuntimeLoweringRequirement
    signatures = lowering.CANONICAL_DEVICE_RUNTIME_SIGNATURES
    symbols = c11.CANONICAL_C11_DEVICE_SYMBOLS
    return lowering.DeviceRuntimeLoweringPlan(
        abi_name=c11.REFERENCE_C11_DEVICE_ABI_NAME,
        abi_version=c11.REFERENCE_C11_DEVICE_ABI_VERSION,
        function="submit_pair",
        queue="queue0",
        calls=(
            requirement(
                "submit", "handover@1:1", symbols["submit"], "left", (), signatures["submit"]
            ),
            requirement(
                "submit", "handover@1:2", symbols["submit"], "right", (), signatures["submit"]
            ),
            requirement(
                "complete", "completion@2:1", symbols["complete"], "left",
                ("handover@1:1",), signatures["complete"]
            ),
            requirement(
                "complete", "completion@2:2", symbols["complete"], "right",
                ("handover@1:2",), signatures["complete"]
            ),
            requirement(
                "synchronize", "sync@3:1", symbols["synchronize"], None,
                ("completion@2:1", "completion@2:2"), signatures["synchronize"]
            ),
            requirement(
                "reacquire", "reacquire@4:1", symbols["reacquire"], "left",
                ("sync@3:1",), signatures["reacquire"]
            ),
            requirement(
                "reacquire", "reacquire@4:2", symbols["reacquire"], "right",
                ("sync@3:1",), signatures["reacquire"]
            ),
        ),
    )


def _plans():
    bound = physical.bind_device_runtime_physical_abi(
        _logical_plan(), c11.reference_c11_device_runtime_contract()
    )
    declarations = c11.plan_reference_c11_device_runtime(bound)
    return bound, declarations


def _sources():
    source = materialize.C11DeviceOwnerSource
    return (
        source("left", "left_address", "left_extent"),
        source("right", "right_address", "right_extent"),
    )


class SotlasDeviceRuntimeC11MaterializationTests(unittest.TestCase):
    def test_materializes_storage_and_operands_without_emitting_calls(self):
        bound, declarations = _plans()
        plan = materialize.materialize_reference_c11_device_runtime(
            declarations,
            bound,
            queue_identifier="device_queue",
            host_owners=_sources(),
        )

        self.assertEqual(plan.point_ids, declarations.point_ids)
        self.assertEqual(plan.queue_identifier, "device_queue")
        self.assertIn(
            "sotlas_device_submission_t __sotlas_device_submission_0;",
            plan.storage_declarations,
        )
        self.assertIn(
            "sotlas_device_fence_t __sotlas_device_sync_fence;",
            plan.storage_declarations,
        )

        first_submit = plan.calls[0]
        self.assertEqual(
            first_submit.arguments,
            (
                "device_queue",
                "left_address",
                "left_extent",
                "&__sotlas_device_owner_0_address",
                "&__sotlas_device_owner_0_extent",
            ),
        )
        self.assertEqual(
            first_submit.direct_result_target,
            "__sotlas_device_submission_0",
        )

        sync = plan.calls[4]
        self.assertEqual(
            sync.prelude,
            (
                "sotlas_device_completion_t __sotlas_device_completions[2] = { "
                "__sotlas_device_completion_0, __sotlas_device_completion_1 };",
            ),
        )
        self.assertEqual(
            sync.arguments,
            ("device_queue", "__sotlas_device_completions", "(size_t)2"),
        )
        self.assertEqual(sync.direct_result_target, "__sotlas_device_sync_fence")

        last_reacquire = plan.calls[-1]
        self.assertIsNone(last_reacquire.direct_result_target)
        self.assertEqual(
            last_reacquire.arguments,
            (
                "device_queue",
                "__sotlas_device_owner_1_address",
                "__sotlas_device_owner_1_extent",
                "__sotlas_device_sync_fence",
                "&__sotlas_host_owner_1_address",
                "&__sotlas_host_owner_1_extent",
            ),
        )
        self.assertEqual(
            tuple(result.binding for result in plan.host_results),
            ("left", "right"),
        )

    def test_materialization_accepts_owner_sources_in_any_input_order(self):
        bound, declarations = _plans()
        plan = materialize.materialize_reference_c11_device_runtime(
            declarations,
            bound,
            queue_identifier="device_queue",
            host_owners=tuple(reversed(_sources())),
        )
        self.assertEqual(plan.calls[0].arguments[1:3], ("left_address", "left_extent"))
        self.assertEqual(plan.calls[1].arguments[1:3], ("right_address", "right_extent"))

    def test_materialization_requires_exact_owner_coverage(self):
        bound, declarations = _plans()
        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "exactly cover submitted bindings",
        ):
            materialize.materialize_reference_c11_device_runtime(
                declarations,
                bound,
                queue_identifier="device_queue",
                host_owners=_sources()[:1],
            )
        extra = materialize.C11DeviceOwnerSource("extra", "extra_address", "extra_extent")
        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "exactly cover submitted bindings",
        ):
            materialize.materialize_reference_c11_device_runtime(
                declarations,
                bound,
                queue_identifier="device_queue",
                host_owners=_sources() + (extra,),
            )

    def test_materialization_rejects_unsafe_or_duplicate_c_identifiers(self):
        bound, declarations = _plans()
        bad = (
            materialize.C11DeviceOwnerSource("left", "left-address", "left_extent"),
            _sources()[1],
        )
        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "safe C11 identifier",
        ):
            materialize.materialize_reference_c11_device_runtime(
                declarations,
                bound,
                queue_identifier="device_queue",
                host_owners=bad,
            )

        duplicate = (
            materialize.C11DeviceOwnerSource("left", "same_value", "left_extent"),
            materialize.C11DeviceOwnerSource("right", "same_value", "right_extent"),
        )
        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "globally unique",
        ):
            materialize.materialize_reference_c11_device_runtime(
                declarations,
                bound,
                queue_identifier="device_queue",
                host_owners=duplicate,
            )

        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "safe C11 identifier",
        ):
            materialize.materialize_reference_c11_device_runtime(
                declarations,
                bound,
                queue_identifier="return",
                host_owners=_sources(),
            )

    def test_materialization_rejects_declaration_physical_plan_drift(self):
        bound, declarations = _plans()
        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "do not share one identity",
        ):
            materialize.materialize_reference_c11_device_runtime(
                replace(declarations, queue="other_queue"),
                bound,
                queue_identifier="device_queue",
                host_owners=_sources(),
            )

        calls = list(declarations.calls)
        calls[0] = replace(calls[0], symbol="other_submit")
        with self.assertRaisesRegex(
            materialize.DeviceRuntimeC11MaterializationError,
            "declaration call diverges",
        ):
            materialize.materialize_reference_c11_device_runtime(
                replace(declarations, calls=tuple(calls)),
                bound,
                queue_identifier="device_queue",
                host_owners=_sources(),
            )


if __name__ == "__main__":
    unittest.main()
