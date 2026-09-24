"""Tests for isolated reference C11 DEVICE call emission."""
from dataclasses import replace
from pathlib import Path
import importlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_c11_emit_backend_package"
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
emit = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11_emit")


def _plans():
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
                "submit", "handover@1:1", symbols["submit"], "buffer", (), signatures["submit"]
            ),
            requirement(
                "complete", "completion@2:1", symbols["complete"], "buffer",
                ("handover@1:1",), signatures["complete"]
            ),
            requirement(
                "synchronize", "sync@3:1", symbols["synchronize"], None,
                ("completion@2:1",), signatures["synchronize"]
            ),
            requirement(
                "reacquire", "reacquire@4:1", symbols["reacquire"], "buffer",
                ("sync@3:1",), signatures["reacquire"]
            ),
        ),
    )
    bound = physical.bind_device_runtime_physical_abi(
        logical, c11.reference_c11_device_runtime_contract()
    )
    declarations = c11.plan_reference_c11_device_runtime(bound)
    materialized = materialize.materialize_reference_c11_device_runtime(
        declarations,
        bound,
        queue_identifier="device_queue",
        host_owners=(
            materialize.C11DeviceOwnerSource("buffer", "host_address", "host_extent"),
        ),
    )
    return declarations, materialized


class SotlasDeviceRuntimeC11EmissionTests(unittest.TestCase):
    def test_emits_exact_call_stream_from_materialized_plan(self):
        declarations, materialized = _plans()
        plan = emit.emit_reference_c11_device_runtime_calls(
            declarations, materialized
        )
        self.assertEqual(
            plan.call_statements,
            (
                "__sotlas_device_submission_0 = sotlas_device_submit("
                "device_queue, host_address, host_extent, "
                "&__sotlas_device_owner_0_address, &__sotlas_device_owner_0_extent);",
                "__sotlas_device_completion_0 = sotlas_device_complete("
                "device_queue, __sotlas_device_submission_0);",
                "sotlas_device_completion_t __sotlas_device_completions[1] = { "
                "__sotlas_device_completion_0 };",
                "__sotlas_device_sync_fence = sotlas_device_sync("
                "device_queue, __sotlas_device_completions, (size_t)1);",
                "sotlas_device_reacquire("
                "device_queue, __sotlas_device_owner_0_address, "
                "__sotlas_device_owner_0_extent, __sotlas_device_sync_fence, "
                "&__sotlas_host_owner_0_address, &__sotlas_host_owner_0_extent);",
            ),
        )

    def test_emitter_rejects_argument_or_prelude_injection(self):
        declarations, materialized = _plans()
        calls = list(materialized.calls)
        calls[0] = replace(
            calls[0],
            arguments=("device_queue; abort()", *calls[0].arguments[1:]),
        )
        with self.assertRaisesRegex(
            emit.DeviceRuntimeC11EmissionError, "safe subset"
        ):
            emit.emit_reference_c11_device_runtime_calls(
                declarations, replace(materialized, calls=tuple(calls))
            )

        calls = list(materialized.calls)
        calls[0] = replace(calls[0], prelude=("abort();",))
        with self.assertRaisesRegex(
            emit.DeviceRuntimeC11EmissionError, "cannot inject prelude"
        ):
            emit.emit_reference_c11_device_runtime_calls(
                declarations, replace(materialized, calls=tuple(calls))
            )

    def test_emitter_rejects_direct_result_drift(self):
        declarations, materialized = _plans()
        calls = list(materialized.calls)
        calls[0] = replace(calls[0], direct_result_target=None)
        with self.assertRaisesRegex(
            emit.DeviceRuntimeC11EmissionError, "direct runtime result"
        ):
            emit.emit_reference_c11_device_runtime_calls(
                declarations, replace(materialized, calls=tuple(calls))
            )

    def test_emitted_reference_call_stream_compiles_and_executes_with_test_runtime(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if compiler is None:
            raise unittest.SkipTest("host C compiler not available")

        declarations, materialized = _plans()
        plan = emit.emit_reference_c11_device_runtime_calls(
            declarations, materialized
        )
        host = plan.host_results[0]
        source = (
            plan.declaration_source
            + "\n"
            + "static unsigned runtime_step = 0;\n\n"
            + "sotlas_device_submission_t sotlas_device_submit(\n"
            + "    sotlas_device_queue_t queue, uintptr_t host_address, size_t host_extent,\n"
            + "    uintptr_t *out_device_address, size_t *out_device_extent) {\n"
            + "    if (runtime_step++ != 0 || queue != 7 || host_address != 100 || host_extent != 64) return 0;\n"
            + "    *out_device_address = host_address + 1000;\n"
            + "    *out_device_extent = host_extent;\n"
            + "    return 11;\n"
            + "}\n\n"
            + "sotlas_device_completion_t sotlas_device_complete(\n"
            + "    sotlas_device_queue_t queue, sotlas_device_submission_t submission) {\n"
            + "    if (runtime_step++ != 1 || queue != 7 || submission != 11) return 0;\n"
            + "    return 21;\n"
            + "}\n\n"
            + "sotlas_device_fence_t sotlas_device_sync(\n"
            + "    sotlas_device_queue_t queue, const sotlas_device_completion_t *completions,\n"
            + "    size_t completion_count) {\n"
            + "    if (runtime_step++ != 2 || queue != 7 || completion_count != 1 || completions[0] != 21) return 0;\n"
            + "    return 31;\n"
            + "}\n\n"
            + "void sotlas_device_reacquire(\n"
            + "    sotlas_device_queue_t queue, uintptr_t device_address, size_t device_extent,\n"
            + "    sotlas_device_fence_t fence, uintptr_t *out_host_address, size_t *out_host_extent) {\n"
            + "    if (runtime_step++ != 3 || queue != 7 || device_address != 1100 || device_extent != 64 || fence != 31) {\n"
            + "        *out_host_address = 0; *out_host_extent = 0; return;\n"
            + "    }\n"
            + "    *out_host_address = device_address - 1000;\n"
            + "    *out_host_extent = device_extent;\n"
            + "}\n\n"
            + "int main(void) {\n"
            + "    sotlas_device_queue_t device_queue = 7;\n"
            + "    uintptr_t host_address = 100;\n"
            + "    size_t host_extent = 64;\n"
            + plan.render_body(indent="    ")
            + f"    if (runtime_step != 4 || {host.address_identifier} != 100 || {host.extent_identifier} != 64) return 1;\n"
            + "    return 0;\n"
            + "}\n"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            c_path = Path(tmpdir) / "device_runtime_reference.c"
            exe_path = Path(tmpdir) / ("device_runtime_reference.exe" if sys.platform == "win32" else "device_runtime_reference")
            c_path.write_text(source, encoding="utf-8")
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", str(c_path), "-o", str(exe_path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            executed = subprocess.run(
                [str(exe_path)], text=True, capture_output=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)


if __name__ == "__main__":
    unittest.main()
