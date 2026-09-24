"""Tests for the isolated reference C11 DEVICE backend entrypoint."""
from dataclasses import replace
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_c11_pipeline_backend_package"
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
c11 = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11")
materialize = importlib.import_module(
    f"{backend_package.__name__}.device_runtime_c11_materialize"
)
pipeline = importlib.import_module(
    f"{backend_package.__name__}.device_runtime_c11_pipeline"
)


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
            requirement("submit", "handover@1:1", symbols["submit"], "buffer", (), signatures["submit"]),
            requirement("complete", "completion@2:1", symbols["complete"], "buffer", ("handover@1:1",), signatures["complete"]),
            requirement("synchronize", "sync@3:1", symbols["synchronize"], None, ("completion@2:1",), signatures["synchronize"]),
            requirement("reacquire", "reacquire@4:1", symbols["reacquire"], "buffer", ("sync@3:1",), signatures["reacquire"]),
        ),
    )


class SotlasDeviceRuntimeC11PipelineTests(unittest.TestCase):
    def test_pipeline_builds_embed_ready_fragment_without_claiming_runtime(self):
        artifact = pipeline.lower_device_runtime_plan_to_reference_c11(
            _logical_plan(),
            queue_identifier="device_queue",
            host_owners=(
                materialize.C11DeviceOwnerSource(
                    "buffer", "host_address", "host_extent"
                ),
            ),
            include_standard_headers=False,
        )
        self.assertEqual(artifact.abi_name, "sotlas.device.reference")
        self.assertEqual(artifact.function, "submit_one")
        self.assertNotIn("#include", artifact.declaration_source)
        self.assertIn("sotlas_device_submit", artifact.declaration_source)
        self.assertIn("sotlas_device_submit(", artifact.body_source)
        self.assertIn("sotlas_device_reacquire(", artifact.body_source)
        self.assertEqual(artifact.host_results[0].binding, "buffer")
        self.assertEqual(
            artifact.emission.host_results,
            artifact.host_results,
        )

    def test_pipeline_can_render_standalone_standard_headers(self):
        artifact = pipeline.lower_device_runtime_plan_to_reference_c11(
            _logical_plan(),
            queue_identifier="device_queue",
            host_owners=(
                materialize.C11DeviceOwnerSource(
                    "buffer", "host_address", "host_extent"
                ),
            ),
            include_standard_headers=True,
        )
        self.assertTrue(
            artifact.declaration_source.startswith(
                "#include <stddef.h>\n#include <stdint.h>\n"
            )
        )

    def test_pipeline_rejects_non_plan_input(self):
        with self.assertRaisesRegex(
            pipeline.DeviceRuntimeC11PipelineError,
            "proven logical lowering plan",
        ):
            pipeline.lower_device_runtime_plan_to_reference_c11(
                object(),
                queue_identifier="device_queue",
                host_owners=(),
            )

    def test_pipeline_rejects_forged_noncanonical_lifecycle(self):
        logical = _logical_plan()
        calls = list(logical.calls)
        calls[1], calls[2] = calls[2], calls[1]
        forged = replace(logical, calls=tuple(calls))
        with self.assertRaises(ValueError):
            pipeline.lower_device_runtime_plan_to_reference_c11(
                forged,
                queue_identifier="device_queue",
                host_owners=(
                    materialize.C11DeviceOwnerSource(
                        "buffer", "host_address", "host_extent"
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
