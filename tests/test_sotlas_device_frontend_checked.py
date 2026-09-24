"""Integration tests from real Phase-1 source to DEVICE runtime semantics."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_device_checked_frontend_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sotlas_compile = _load_canonical_package()
try:
    importlib.import_module("sotlas.sir")
except ImportError:
    compiler_dir = str(ROOT / "compiler")
    if compiler_dir not in sys.path:
        sys.path.insert(0, compiler_dir)

lifecycle = importlib.import_module(f"{sotlas_compile.__name__}.device_lifecycle")
frontend = importlib.import_module(f"{sotlas_compile.__name__}.device_frontend")
runtime_abi = importlib.import_module(f"{sotlas_compile.__name__}.device_runtime_abi")

DeviceLifecycleSourcePoints = lifecycle.DeviceLifecycleSourcePoints
DeviceRuntimeOperation = runtime_abi.DeviceRuntimeOperation
plan_checked_device_runtime = frontend.plan_checked_device_runtime


SINGLE_SOURCE = """module test::device_checked_frontend;
sole struct Buffer { value: u32; }
fn accept_device(buffer: device Buffer) -> void { return; }
fn submit(cpu: Buffer, slot: device Buffer) -> void {
    accept_device(move slot);
    handover cpu to slot;
    return;
}
"""

SEQUENTIAL_SOURCE = """module test::device_checked_frontend_sequential;
sole struct Buffer { value: u32; }
fn accept_device(buffer: device Buffer) -> void { return; }
fn submit(cpu_a: Buffer, cpu_b: Buffer,
          device_a: device Buffer, device_b: device Buffer) -> void {
    accept_device(move device_a);
    accept_device(move device_b);
    handover cpu_a to device_a;
    handover cpu_b to device_b;
    return;
}
"""

BRANCH_SOURCE = """module test::device_checked_frontend_branch;
sole struct Buffer { value: u32; }
fn accept_device(buffer: device Buffer) -> void { return; }
fn submit(flag: bool, cpu_a: Buffer, cpu_b: Buffer,
          device_a: device Buffer, device_b: device Buffer) -> void {
    if flag {
        accept_device(move device_a);
        handover cpu_a to device_a;
        return;
    } else {
        accept_device(move device_b);
        handover cpu_b to device_b;
        return;
    }
}
"""


class SotlasDeviceCheckedFrontendTests(unittest.TestCase):
    def test_real_phase1_source_drives_device_runtime_dag(self):
        checked = sotlas_compile.analyze_source_phase1(
            SINGLE_SOURCE,
            filename="<device-checked-frontend>",
        )
        plan = plan_checked_device_runtime(
            checked,
            function="submit",
            queue="queue0",
            points=DeviceLifecycleSourcePoints(
                completion_point_ids=("completion@test:1",),
                synchronization_point_id="sync@test:1",
                reacquisition_point_ids=("reacquire@test:1",),
            ),
        )
        self.assertIs(plan.graph, checked.semantic.ownership_domains)
        self.assertIsNone(plan.coexecution_certificate)
        self.assertEqual(plan.bindings, ("cpu",))
        self.assertEqual(plan.function, "submit")
        self.assertEqual(plan.queue, "queue0")
        self.assertTrue(plan.point_ids[0].startswith("handover@"))
        self.assertEqual(
            plan.point_ids[1:],
            ("completion@test:1", "sync@test:1", "reacquire@test:1"),
        )
        self.assertEqual(
            tuple(item.operation for item in plan.runtime.runtime.requirements),
            (
                DeviceRuntimeOperation.SUBMIT,
                DeviceRuntimeOperation.COMPLETE,
                DeviceRuntimeOperation.SYNCHRONIZE,
                DeviceRuntimeOperation.REACQUIRE,
            ),
        )

    def test_real_sequential_multi_owner_source_is_auto_certified(self):
        checked = sotlas_compile.analyze_source_phase1(
            SEQUENTIAL_SOURCE,
            filename="<device-checked-frontend-sequential>",
        )
        plan = plan_checked_device_runtime(
            checked,
            function="submit",
            queue="queue0",
            points=DeviceLifecycleSourcePoints(
                completion_point_ids=("completion@test:1", "completion@test:2"),
                synchronization_point_id="sync@test:1",
                reacquisition_point_ids=("reacquire@test:1", "reacquire@test:2"),
            ),
        )
        self.assertIsNotNone(plan.coexecution_certificate)
        self.assertEqual(plan.bindings, ("cpu_a", "cpu_b"))
        self.assertEqual(
            tuple(item.operation for item in plan.runtime.runtime.requirements),
            (
                DeviceRuntimeOperation.SUBMIT,
                DeviceRuntimeOperation.SUBMIT,
                DeviceRuntimeOperation.COMPLETE,
                DeviceRuntimeOperation.COMPLETE,
                DeviceRuntimeOperation.SYNCHRONIZE,
                DeviceRuntimeOperation.REACQUIRE,
                DeviceRuntimeOperation.REACQUIRE,
            ),
        )
        self.assertEqual(
            tuple(item.binding for item in plan.runtime.runtime.requirements[:2]),
            ("cpu_a", "cpu_b"),
        )

    def test_real_branch_source_remains_fail_closed_when_coexecution_cannot_be_proved(self):
        checked = sotlas_compile.analyze_source_phase1(
            BRANCH_SOURCE,
            filename="<device-checked-frontend-branch>",
        )
        with self.assertRaisesRegex(
            frontend.DeviceFrontendPlanError,
            "cannot prove submission co-execution",
        ):
            plan_checked_device_runtime(
                checked,
                function="submit",
                queue="queue0",
                points=DeviceLifecycleSourcePoints(
                    completion_point_ids=("completion@test:1", "completion@test:2"),
                    synchronization_point_id="sync@test:1",
                    reacquisition_point_ids=("reacquire@test:1", "reacquire@test:2"),
                ),
            )

    def test_checked_entrypoint_rejects_non_checked_objects(self):
        with self.assertRaisesRegex(
            frontend.DeviceFrontendPlanError,
            "Phase1CheckedModule semantic snapshot",
        ):
            plan_checked_device_runtime(
                object(),
                function="submit",
                queue="queue0",
                points=DeviceLifecycleSourcePoints(
                    completion_point_ids=("completion@test:1",),
                    synchronization_point_id="sync@test:1",
                    reacquisition_point_ids=("reacquire@test:1",),
                ),
            )


if __name__ == "__main__":
    unittest.main()
