"""Public production API for strict Phase-3 Authority SIR."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_production_package():
    name = "sotlas_authority_public_api_package"
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


package = _load_production_package()


SOURCE = """module app::authority_public_api;
@system(pci.config)
fn configure_pci() -> void { return; }
@system(pci.config)
fn boot() -> void {
    configure_pci();
    return;
}
"""


class SotlasAuthorityPublicAPITests(unittest.TestCase):
    def test_public_package_exports_strict_authority_sir_builder(self):
        self.assertIn("CheckedAuthoritySIR", package.__all__)
        self.assertIn("build_canonical_checked_authority_sir", package.__all__)
        self.assertTrue(hasattr(package, "CheckedAuthoritySIR"))
        self.assertTrue(hasattr(package, "build_canonical_checked_authority_sir"))

    def test_public_builder_runs_checked_authority_pipeline_end_to_end(self):
        checked = package.analyze_source_phase1(
            SOURCE,
            filename="<authority-public-api>",
        )
        result = package.build_canonical_checked_authority_sir(checked)

        self.assertIsInstance(result, package.CheckedAuthoritySIR)
        self.assertTrue(result.authority_safety.success)
        self.assertEqual(
            result.authority_certificate.function("boot").capabilities,
            ("pci.config",),
        )
        self.assertEqual(
            result.authority_certificate.calls_from("boot")[0].sir_call_count,
            1,
        )


if __name__ == "__main__":
    unittest.main()
