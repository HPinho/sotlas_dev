"""Link the compiler-generated DEVICE ABI declarations to the reference provider."""
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
SOTLAS_DIR = ROOT / "compiler" / "sotlas"
RUNTIME_DIR = ROOT / "runtime"
REFERENCE_RUNTIME_C = RUNTIME_DIR / "device_reference.c"


def _load_backend_package():
    name = "sotlas_device_reference_abi_link_backend_package"
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


def _host_c_compiler() -> str:
    compiler = shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise unittest.SkipTest("host GCC/Clang not available")
    return compiler


def _generated_declarations() -> str:
    signatures = lowering.CANONICAL_DEVICE_RUNTIME_SIGNATURES
    symbols = c11.CANONICAL_C11_DEVICE_SYMBOLS
    requirement = lowering.DeviceRuntimeLoweringRequirement
    logical = lowering.DeviceRuntimeLoweringPlan(
        abi_name=c11.REFERENCE_C11_DEVICE_ABI_NAME,
        abi_version=c11.REFERENCE_C11_DEVICE_ABI_VERSION,
        function="submit_one",
        queue="queue0",
        calls=(
            requirement(
                "submit", "handover@1:1", symbols["submit"], "buffer", (),
                signatures["submit"],
            ),
            requirement(
                "complete", "completion@2:1", symbols["complete"], "buffer",
                ("handover@1:1",), signatures["complete"],
            ),
            requirement(
                "synchronize", "sync@3:1", symbols["synchronize"], None,
                ("completion@2:1",), signatures["synchronize"],
            ),
            requirement(
                "reacquire", "reacquire@4:1", symbols["reacquire"], "buffer",
                ("sync@3:1",), signatures["reacquire"],
            ),
        ),
    )
    bound = physical.bind_device_runtime_physical_abi(
        logical,
        c11.reference_c11_device_runtime_contract(),
    )
    return c11.plan_reference_c11_device_runtime(bound).render_declarations()


class SotlasDeviceReferenceABILinkTests(unittest.TestCase):
    def test_generated_declarations_call_repository_reference_provider(self):
        declarations = _generated_declarations()
        source = declarations + r'''
/* Diagnostics are provider-only and intentionally outside the DEVICE ABI. */
extern void sotlas_device_reference_reset(void);
extern int sotlas_device_reference_last_status(void);
extern int sotlas_device_reference_fence_consumed(sotlas_device_fence_t fence);

int main(void) {
    sotlas_device_queue_t queue = (sotlas_device_queue_t)5u;
    uintptr_t device_address = 0;
    size_t device_extent = 0;
    uintptr_t host_address = 0;
    size_t host_extent = 0;
    sotlas_device_submission_t submission;
    sotlas_device_completion_t completion;
    sotlas_device_fence_t fence;

    sotlas_device_reference_reset();
    submission = sotlas_device_submit(
        queue, (uintptr_t)0x4000u, (size_t)256u,
        &device_address, &device_extent
    );
    if (submission == 0 || sotlas_device_reference_last_status() != 0) return 1;
    completion = sotlas_device_complete(queue, submission);
    if (completion == 0 || sotlas_device_reference_last_status() != 0) return 2;
    fence = sotlas_device_sync(queue, &completion, (size_t)1u);
    if (fence == 0 || sotlas_device_reference_last_status() != 0) return 3;
    sotlas_device_reacquire(
        queue, device_address, device_extent, fence,
        &host_address, &host_extent
    );
    if (sotlas_device_reference_last_status() != 0) return 4;
    if (host_address != (uintptr_t)0x4000u || host_extent != (size_t)256u) return 5;
    if (!sotlas_device_reference_fence_consumed(fence)) return 6;
    return 0;
}
'''
        compiler = _host_c_compiler()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            main_c = temp / "main.c"
            executable = temp / ("device_abi_link.exe" if sys.platform == "win32" else "device_abi_link")
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
            self.assertEqual(compiled.returncode, 0, compiled.stderr or compiled.stdout)
            executed = subprocess.run(
                [str(executable)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)


if __name__ == "__main__":
    unittest.main()
