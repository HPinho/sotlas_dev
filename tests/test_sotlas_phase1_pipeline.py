"""Public opt-in Phase-1 pipeline integration tests."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    """Load the production package under a unique test name.

    Some legacy tests prepend ROOT/tools to sys.path, where a compatibility
    package with the same top-level name exists. Loading by explicit package
    path keeps this integration test pinned to compiler/sotlas_compile without
    mutating or depending on global test discovery order.
    """
    name = "sotlas_phase1_public_package"
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


class SotlasPhase1PipelineTests(unittest.TestCase):
    def test_public_phase1_pipeline_is_explicit_and_preserves_bootstrap_check(self):
        source = """module test::phase1_public;
sole struct Token { value: u32; }

fn read(t: Token) -> u32 {
    return t.value;
}
"""
        check_before = sotlas_compile.bootstrap.check
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-public>"
        )
        self.assertIs(sotlas_compile.bootstrap.check, check_before)
        self.assertEqual(result.semantic.maturity, "ISOLATED_PHASE1")
        self.assertEqual(result.semantic.typed_module.structs[0].name, "Token")
        self.assertEqual(result.semantic.bodies[0].name, "read")

    def test_public_phase1_pipeline_reuses_canonical_parse_and_check(self):
        source = """module test::phase1_public_invalid;
fn main() -> void {
    let value: i64 = 1;
    value = true;
    return;
}
"""
        with self.assertRaises(sotlas_compile.SotlasBootstrapError):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-public-invalid>"
            )

    def test_normal_package_import_does_not_auto_attach_phase1_state(self):
        source = """module test::phase1_no_side_effect;
fn main() -> void { return; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<phase1-no-side-effect>"
        )
        sotlas_compile.bootstrap.check(parsed)
        self.assertFalse(hasattr(parsed, "typed_ast"))
        self.assertFalse(hasattr(parsed, "phase1"))


if __name__ == "__main__":
    unittest.main()