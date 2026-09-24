"""Tests for embedding reference DEVICE declarations in C11 preludes."""
from pathlib import Path
import importlib
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_backend_package():
    name = "sotlas_device_c11_embed_backend_package"
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
embed = importlib.import_module(f"{backend_package.__name__}.device_runtime_c11_embed")


def _declarations():
    requirement = lowering.DeviceRuntimeLoweringRequirement
    signatures = lowering.CANONICAL_DEVICE_RUNTIME_SIGNATURES
    symbols = c11.CANONICAL_C11_DEVICE_SYMBOLS
    logical = lowering.DeviceRuntimeLoweringPlan(
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
    bound = physical.bind_device_runtime_physical_abi(
        logical, c11.reference_c11_device_runtime_contract()
    )
    return c11.plan_reference_c11_device_runtime(bound)


class SotlasDeviceRuntimeC11EmbedTests(unittest.TestCase):
    def test_standalone_embedding_keeps_standard_headers(self):
        rendered = embed.render_reference_c11_device_runtime_declarations(
            _declarations(), include_standard_headers=True
        )
        self.assertTrue(rendered.startswith("#include <stddef.h>\n#include <stdint.h>\n"))
        self.assertIn("typedef uintptr_t sotlas_device_queue_t;", rendered)
        self.assertIn("sotlas_device_submit", rendered)

    def test_existing_prelude_embedding_omits_standard_headers(self):
        rendered = embed.render_reference_c11_device_runtime_declarations(
            _declarations(), include_standard_headers=False
        )
        self.assertNotIn("#include", rendered)
        self.assertTrue(rendered.startswith("typedef uintptr_t sotlas_device_queue_t;"))
        self.assertIn("sotlas_device_reacquire", rendered)


if __name__ == "__main__":
    unittest.main()
