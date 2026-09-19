"""Public opt-in Phase-1 pipeline integration tests."""
import unittest

import sotlas_compile


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
    let value: bool = 1;
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
