"""End-to-end semantic proof from real Sotlas source to reference C11 DEVICE artifact.

This test intentionally stops at the reference C11 artifact.  It proves the
compiler chain, not a hardware runtime or driver implementation.
"""
import importlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE_DIR = ROOT / "compiler" / "sotlas_compile"
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_compile_package():
    name = "sotlas_device_checked_c11_compile_package"
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
    name = "sotlas_device_checked_c11_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


compile_package = _load_compile_package()
try:
    importlib.import_module("sotlas.sir")
except ImportError:
    compiler_dir = str(ROOT / "compiler")
    if compiler_dir not in sys.path:
        sys.path.insert(0, compiler_dir)

lifecycle = importlib.import_module(f"{compile_package.__name__}.device_lifecycle")
frontend = importlib.import_module(f"{compile_package.__name__}.device_frontend")
runtime_abi = importlib.import_module(f"{compile_package.__name__}.device_runtime_abi")

backend_package = _load_backend_package()
sir = importlib.import_module(f"{backend_package.__name__}.sir")
frontend_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_frontend_runtime"
)
runtime_calls = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_calls"
)
runtime_lowering = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime_lowering"
)
c11 = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11")
c11_materialize = importlib.import_module(
    f"{backend_package.__name__}.device_runtime_c11_materialize"
)
c11_pipeline = importlib.import_module(
    f"{backend_package.__name__}.device_runtime_c11_pipeline"
)

SOURCE = """module test::device_checked_c11;
sole struct Buffer { value: u32; }
fn accept_device(buffer: device Buffer) -> void { return; }
fn submit(cpu: Buffer, slot: device Buffer) -> void {
    accept_device(move slot);
    handover cpu to slot;
    return;
}
"""


class SotlasDeviceCheckedC11PipelineTests(unittest.TestCase):
    def test_real_source_reaches_reference_c11_without_rebuilding_semantics(self):
        checked = compile_package.analyze_source_phase1(
            SOURCE,
            filename="<device-checked-c11>",
        )
        checked_runtime = frontend.plan_checked_device_runtime(
            checked,
            function="submit",
            queue="queue0",
            points=lifecycle.DeviceLifecycleSourcePoints(
                completion_point_ids=("completion@test:1",),
                synchronization_point_id="sync@test:1",
                reacquisition_point_ids=("reacquire@test:1",),
            ),
        )

        sir_plan = frontend_sir.lower_device_frontend_runtime_to_sir(
            checked_runtime.runtime,
            (
                frontend_sir.DeviceRuntimeSIRValueBinding(
                    "cpu",
                    sir.SIRValue("device_cpu", "Buffer"),
                    sir.SIRValue("host_cpu", "Buffer"),
                ),
            ),
        )

        contract = runtime_abi.DeviceRuntimeABIContract(
            name=c11.REFERENCE_C11_DEVICE_ABI_NAME,
            version=c11.REFERENCE_C11_DEVICE_ABI_VERSION,
            symbols=tuple(
                runtime_abi.DeviceRuntimeABISymbol(operation, symbol)
                for operation, symbol in (
                    (runtime_abi.DeviceRuntimeOperation.SUBMIT, c11.CANONICAL_C11_DEVICE_SYMBOLS["submit"]),
                    (runtime_abi.DeviceRuntimeOperation.COMPLETE, c11.CANONICAL_C11_DEVICE_SYMBOLS["complete"]),
                    (runtime_abi.DeviceRuntimeOperation.SYNCHRONIZE, c11.CANONICAL_C11_DEVICE_SYMBOLS["synchronize"]),
                    (runtime_abi.DeviceRuntimeOperation.REACQUIRE, c11.CANONICAL_C11_DEVICE_SYMBOLS["reacquire"]),
                )
            ),
        )
        bound = runtime_abi.bind_device_runtime_abi(
            checked_runtime.runtime.runtime,
            contract,
        )
        call_plan = runtime_calls.plan_bound_device_runtime_calls(
            sir_plan.bridge,
            bound,
        )
        logical = runtime_lowering.plan_device_runtime_lowering(call_plan)
        artifact = c11_pipeline.lower_device_runtime_plan_to_reference_c11(
            logical,
            queue_identifier="device_queue",
            host_owners=(
                c11_materialize.C11DeviceOwnerSource(
                    binding="cpu",
                    address_identifier="host_address",
                    extent_identifier="host_extent",
                ),
            ),
            include_standard_headers=False,
        )

        self.assertEqual(artifact.abi_name, c11.REFERENCE_C11_DEVICE_ABI_NAME)
        self.assertEqual(artifact.abi_version, c11.REFERENCE_C11_DEVICE_ABI_VERSION)
        self.assertEqual(artifact.function, "submit")
        self.assertEqual(artifact.queue, "queue0")
        self.assertNotIn("#include", artifact.declaration_source)
        self.assertIn("sotlas_device_submit", artifact.declaration_source)
        self.assertEqual(tuple(item.binding for item in artifact.host_results), ("cpu",))

        body = artifact.body_source
        submit_index = body.index("sotlas_device_submit(")
        complete_index = body.index("sotlas_device_complete(")
        sync_index = body.index("sotlas_device_sync(")
        reacquire_index = body.index("sotlas_device_reacquire(")
        self.assertLess(submit_index, complete_index)
        self.assertLess(complete_index, sync_index)
        self.assertLess(sync_index, reacquire_index)
        self.assertIn("host_address", body)
        self.assertIn("host_extent", body)
        self.assertEqual(
            artifact.emission.point_ids,
            checked_runtime.point_ids,
        )


if __name__ == "__main__":
    unittest.main()
