"""Native conformance tests for the repository DEVICE reference runtime.

The provider under runtime/device_reference.c is a deterministic software state
machine. These tests prove ABI/link/runtime sequencing only; they do not claim
DMA, GPU, driver or physical device support.
"""
import importlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE_DIR = ROOT / "compiler" / "sotlas_compile"
SOTLAS_DIR = ROOT / "compiler" / "sotlas"
RUNTIME_DIR = ROOT / "runtime"
REFERENCE_RUNTIME_C = RUNTIME_DIR / "device_reference.c"


def _host_c_compiler() -> str:
    resolved = shutil.which("gcc") or shutil.which("clang")
    if resolved is None:
        raise unittest.SkipTest("host GCC/Clang not available")
    return resolved


def _compile_and_run(source: str) -> subprocess.CompletedProcess[str]:
    compiler = _host_c_compiler()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        main_c = temp / "main.c"
        executable = temp / ("device_reference_test.exe" if sys.platform == "win32" else "device_reference_test")
        main_c.write_text(source, encoding="utf-8")
        compiled = subprocess.run(
            [
                compiler,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(main_c),
                str(REFERENCE_RUNTIME_C),
                "-I",
                str(RUNTIME_DIR),
                "-o",
                str(executable),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if compiled.returncode != 0:
            raise AssertionError(compiled.stderr or compiled.stdout)
        return subprocess.run(
            [str(executable)],
            text=True,
            capture_output=True,
            check=False,
        )


def _load_compile_package():
    name = "sotlas_device_reference_runtime_compile_package"
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
    name = "sotlas_device_reference_runtime_backend_package"
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
frontend_sir = importlib.import_module(f"{backend_package.__name__}.sir.device_frontend_runtime")
runtime_calls = importlib.import_module(f"{backend_package.__name__}.sir.device_runtime_calls")
runtime_lowering = importlib.import_module(f"{backend_package.__name__}.sir.device_runtime_lowering")
c11 = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11")
c11_materialize = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11_materialize")
c11_pipeline = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11_pipeline")


SOURCE = """module test::device_reference_runtime;
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


def _artifact():
    checked = compile_package.analyze_source_phase1(
        SOURCE,
        filename="<device-reference-runtime>",
    )
    checked_runtime = frontend.plan_checked_device_runtime(
        checked,
        function="submit",
        queue="queue0",
        points=lifecycle.DeviceLifecycleSourcePoints(
            completion_point_ids=("completion@test:1", "completion@test:2"),
            synchronization_point_id="sync@test:1",
            reacquisition_point_ids=("reacquire@test:1", "reacquire@test:2"),
        ),
    )
    sir_plan = frontend_sir.lower_device_frontend_runtime_to_sir(
        checked_runtime.runtime,
        (
            frontend_sir.DeviceRuntimeSIRValueBinding(
                "cpu_a",
                sir.SIRValue("device_cpu_a", "Buffer"),
                sir.SIRValue("host_cpu_a", "Buffer"),
            ),
            frontend_sir.DeviceRuntimeSIRValueBinding(
                "cpu_b",
                sir.SIRValue("device_cpu_b", "Buffer"),
                sir.SIRValue("host_cpu_b", "Buffer"),
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
    bound = runtime_abi.bind_device_runtime_abi(checked_runtime.runtime.runtime, contract)
    call_plan = runtime_calls.plan_bound_device_runtime_calls(sir_plan.bridge, bound)
    logical = runtime_lowering.plan_device_runtime_lowering(call_plan)
    artifact = c11_pipeline.lower_device_runtime_plan_to_reference_c11(
        logical,
        queue_identifier="device_queue",
        host_owners=(
            c11_materialize.C11DeviceOwnerSource("cpu_a", "host_a_address", "host_a_extent"),
            c11_materialize.C11DeviceOwnerSource("cpu_b", "host_b_address", "host_b_extent"),
        ),
        include_standard_headers=False,
    )
    return checked_runtime, artifact


class SotlasDeviceReferenceRuntimeTests(unittest.TestCase):
    def test_generated_two_owner_artifact_links_and_executes_reference_runtime(self):
        checked_runtime, artifact = _artifact()
        self.assertEqual(artifact.point_ids, checked_runtime.point_ids)
        result_a, result_b = artifact.host_results
        source = f'''#include "device_reference.h"

int main(void) {{
    sotlas_device_queue_t device_queue = (sotlas_device_queue_t)7u;
    uintptr_t host_a_address = (uintptr_t)0x1000u;
    size_t host_a_extent = (size_t)64u;
    uintptr_t host_b_address = (uintptr_t)0x2000u;
    size_t host_b_extent = (size_t)128u;

    sotlas_device_reference_reset();
{artifact.body_source}
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_OK) return 1;
    if ({result_a.address_identifier} != host_a_address) return 2;
    if ({result_a.extent_identifier} != host_a_extent) return 3;
    if ({result_b.address_identifier} != host_b_address) return 4;
    if ({result_b.extent_identifier} != host_b_extent) return 5;
    if (!sotlas_device_reference_fence_consumed(__sotlas_device_sync_fence)) return 6;
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_OK) return 7;
    return 0;
}}
'''
        executed = _compile_and_run(source)
        self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)

    def test_reference_runtime_rejects_invalid_lifecycle_sequences(self):
        source = r'''#include "device_reference.h"

int main(void) {
    uintptr_t device_address = 0;
    size_t device_extent = 0;
    uintptr_t host_address = 0;
    size_t host_extent = 0;
    sotlas_device_submission_t submission;
    sotlas_device_completion_t completion;
    sotlas_device_completion_t duplicate[2];
    sotlas_device_fence_t fence;

    sotlas_device_reference_reset();
    if (sotlas_device_complete((sotlas_device_queue_t)1u, (sotlas_device_submission_t)99u) != 0) return 10;
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_UNKNOWN_SUBMISSION) return 11;

    submission = sotlas_device_submit(
        (sotlas_device_queue_t)1u,
        (uintptr_t)0x1234u,
        (size_t)32u,
        &device_address,
        &device_extent
    );
    if (submission == 0) return 12;
    if (sotlas_device_complete((sotlas_device_queue_t)2u, submission) != 0) return 13;
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_QUEUE_MISMATCH) return 14;

    completion = sotlas_device_complete((sotlas_device_queue_t)1u, submission);
    if (completion == 0) return 15;
    duplicate[0] = completion;
    duplicate[1] = completion;
    if (sotlas_device_sync((sotlas_device_queue_t)1u, duplicate, (size_t)2u) != 0) return 16;
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_DUPLICATE_COMPLETION) return 17;

    fence = sotlas_device_sync((sotlas_device_queue_t)1u, &completion, (size_t)1u);
    if (fence == 0) return 18;
    sotlas_device_reacquire(
        (sotlas_device_queue_t)1u,
        (uintptr_t)0x9999u,
        device_extent,
        fence,
        &host_address,
        &host_extent
    );
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_OWNER_NOT_IN_FENCE) return 19;

    sotlas_device_reacquire(
        (sotlas_device_queue_t)1u,
        device_address,
        device_extent,
        fence,
        &host_address,
        &host_extent
    );
    if (sotlas_device_reference_last_status() != SOTLAS_DEVICE_REFERENCE_OK) return 20;
    if (host_address != (uintptr_t)0x1234u || host_extent != (size_t)32u) return 21;
    if (!sotlas_device_reference_fence_consumed(fence)) return 22;
    return 0;
}
'''
        executed = _compile_and_run(source)
        self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)


if __name__ == "__main__":
    unittest.main()
