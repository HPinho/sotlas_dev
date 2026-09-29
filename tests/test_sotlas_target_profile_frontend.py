"""Canonical execution-profile coverage for the production Sotlas frontend."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

import sotlas_compile
from sotlas_compile import bootstrap


class SotlasTargetProfileFrontendTests(unittest.TestCase):
    def test_implicit_profile_remains_native_for_existing_sources(self):
        module = bootstrap.parse("module app::implicit; fn main() -> u8 { return 0; }")
        plan = sotlas_compile.plan_target_profile(module)
        self.assertEqual(plan.profile, "native")
        self.assertFalse(plan.explicit)
        self.assertFalse(plan.is_freestanding)
        self.assertFalse(module.is_barecore)

    def test_canonical_barecore_profile_is_a_semantic_module_fact(self):
        source = """// kernel target selected before the module
target barecore;
module kernel::profile;
fn entry() -> u8 { return 0; }
"""
        module = bootstrap.parse(source, filename="<barecore-profile>")
        plan = sotlas_compile.plan_target_profile(module)
        self.assertEqual(plan.profile, "barecore")
        self.assertTrue(plan.explicit)
        self.assertTrue(plan.is_freestanding)
        self.assertEqual(plan.spelling, "target barecore;")
        self.assertEqual(module.target_profile, "barecore")
        self.assertTrue(module.is_barecore)
        self.assertEqual(module.source, source)

    def test_transitional_barecore_spelling_maps_to_same_profile(self):
        module = bootstrap.parse(
            "barecore;\nmodule kernel::legacy_profile;\nfn entry() -> u8 { return 0; }\n"
        )
        plan = sotlas_compile.plan_target_profile(module)
        self.assertEqual(plan.profile, "barecore")
        self.assertEqual(plan.spelling, "barecore;")
        self.assertTrue(module.is_barecore)

    def test_explicit_native_profile_is_preserved(self):
        module = bootstrap.parse(
            "target native;\nmodule app::native_profile;\nfn main() -> u8 { return 0; }\n"
        )
        plan = sotlas_compile.plan_target_profile(module)
        self.assertEqual(plan.profile, "native")
        self.assertTrue(plan.explicit)
        self.assertTrue(plan.is_native)
        self.assertFalse(module.is_barecore)

    def test_native_c11_behavior_remains_unchanged(self):
        source = "target native;\nmodule app::native_codegen;\nfn main() -> u8 { return 0; }\n"
        c_source = bootstrap.compile_source(source)
        self.assertNotIn("SOTLAS_TARGET_BARECORE_FREESTANDING", c_source)
        self.assertIn("uint8_t main(void)", c_source)

    def test_web_profile_is_parsed_but_c11_fails_closed(self):
        source = "target web;\nmodule app::web_profile;\nfn main() -> u8 { return 0; }\n"
        module = bootstrap.parse(source)
        self.assertTrue(sotlas_compile.plan_target_profile(module).is_web)
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "C11 backend does not lower target web yet",
        ):
            bootstrap.compile_source(source)

    def test_barecore_c11_emits_freestanding_scalar_module(self):
        source = (
            "target barecore;\n"
            "module kernel::gate;\n"
            "@export\n@system\n"
            "pub fn entry(value: u64) -> u64 { return value + 1; }\n"
        )
        c_source = bootstrap.compile_source(source, filename="<barecore-c11>")
        self.assertTrue(
            c_source.startswith("/* SOTLAS_TARGET_BARECORE_FREESTANDING */")
        )
        self.assertIn("uint64_t entry(uint64_t value)", c_source)
        for marker in (
            "#include <stdlib.h>", "malloc(", "calloc(", "realloc(",
            "free(", "abort(", "printf(", "fprintf(", "fopen(",
            "pthread_", "exit(",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, c_source)

    def test_transitional_barecore_spelling_uses_same_freestanding_backend(self):
        source = "barecore;\nmodule kernel::legacy_codegen;\nfn entry() -> u8 { return 0; }\n"
        c_source = bootstrap.compile_source(source)
        self.assertTrue(
            c_source.startswith("/* SOTLAS_TARGET_BARECORE_FREESTANDING */")
        )

    def test_barecore_rejects_features_that_emit_hosted_runtime_calls(self):
        source = """target barecore;
module kernel::hosted_contract;
fn guarded(value: u32) -> u32
    requires value != 0
{
    return value;
}
"""
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "barecore C11 requires freestanding runtime semantics",
        ):
            bootstrap.compile_source(source, filename="<barecore-hosted-contract>")

    def test_unknown_and_duplicate_profiles_are_rejected(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "target profile não suportado: firmware",
        ):
            bootstrap.parse(
                "target firmware;\nmodule kernel::bad_profile;\n"
            )

        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "target profile duplicado",
        ):
            bootstrap.parse(
                "target barecore;\ntarget native;\nmodule kernel::duplicate;\n"
            )

    def test_profile_masking_preserves_diagnostic_line_numbers(self):
        source = (
            "target barecore;\n"
            "module kernel::diagnostic;\n"
            "fn bad() -> u8 { return missing; }\n"
        )
        module = bootstrap.parse(source, filename="<profile-diagnostic>")
        with self.assertRaises(bootstrap.SotlasBootstrapError) as context:
            bootstrap.check(module)
        self.assertEqual(context.exception.line, 3)
        self.assertIn("missing", str(context.exception))

    def test_compiler_and_tools_target_profile_contracts_remain_identical(self):
        compiler_contract = (
            ROOT / "compiler" / "sotlas_compile" / "target_profile.py"
        ).read_text(encoding="utf-8")
        tools_contract = (
            ROOT / "tools" / "sotlas_compile" / "target_profile.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(compiler_contract, tools_contract)

        for package_root in ("compiler", "tools"):
            init_source = (
                ROOT / package_root / "sotlas_compile" / "__init__.py"
            ).read_text(encoding="utf-8")
            self.assertIn("_install_target_profile(bootstrap)", init_source)
            self.assertIn("plan_target_profile", init_source)


if __name__ == "__main__":
    unittest.main()
