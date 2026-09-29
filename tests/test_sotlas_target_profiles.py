"""Contract tests for canonical Sotlas target-profile parsing."""
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
from sotlas_compile.target_profile import (
    TARGET_BARECORE,
    TARGET_NATIVE,
    TARGET_WEB,
    target_profile_of,
)


class SotlasTargetProfileTests(unittest.TestCase):
    def parse(self, header: str):
        return bootstrap.parse(
            f"{header}module target::contract;\n"
            "pub fn answer() -> u32 { return 42; }\n",
            filename="<target-profile>",
        )

    def test_default_target_remains_native_for_compatibility(self):
        module = self.parse("")
        self.assertEqual(module.target_profile, "native")
        self.assertIs(module.target_profile_facts, TARGET_NATIVE)
        self.assertFalse(module.target_profile_explicit)
        self.assertFalse(module.is_barecore)
        self.assertIs(target_profile_of(module), TARGET_NATIVE)

    def test_canonical_barecore_target_is_freestanding(self):
        module = self.parse("target barecore;\n")
        self.assertEqual(module.target_profile, "barecore")
        self.assertIs(module.target_profile_facts, TARGET_BARECORE)
        self.assertTrue(module.target_profile_explicit)
        self.assertTrue(module.is_barecore)

    def test_transitional_barecore_header_remains_compatible(self):
        module = self.parse("barecore;\n")
        self.assertIs(module.target_profile_facts, TARGET_BARECORE)
        self.assertTrue(module.is_barecore)

    def test_native_and_web_profiles_are_recorded_without_source_reinspection(self):
        native = self.parse("target native;\n")
        web = self.parse("target web;\n")
        self.assertIs(native.target_profile_facts, TARGET_NATIVE)
        self.assertIs(web.target_profile_facts, TARGET_WEB)
        self.assertFalse(native.is_barecore)
        self.assertFalse(web.is_barecore)

    def test_unknown_profile_fails_closed(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "unsupported target profile 'quantum'",
        ):
            self.parse("target quantum;\n")

    def test_missing_profile_name_fails_closed(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "target profile name expected",
        ):
            self.parse("target ;\n")

    def test_duplicate_profile_header_is_rejected_before_module(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "target profile may be declared only once",
        ):
            self.parse("target barecore;\ntarget native;\n")

    def test_target_words_remain_contextual_identifiers_outside_header(self):
        module = bootstrap.parse(
            "module target::names;\n"
            "fn native(web: u32) -> u32 { return web; }\n",
            filename="<contextual-target-words>",
        )
        self.assertEqual(module.functions[0].name, "native")
        self.assertEqual(module.functions[0].params[0][0], "web")

    def test_real_kernel_header_is_parsed_by_canonical_frontend(self):
        kernel = (
            ROOT / "bootstrap" / "sotlas" / "kernel" / "main.sotlas"
        ).read_text(encoding="utf-8")
        module = bootstrap.parse(kernel, filename="bootstrap/sotlas/kernel/main.sotlas")
        self.assertEqual(module.name, "kernel::minimal")
        self.assertTrue(module.is_barecore)

    def test_target_extension_is_installed_on_public_pipeline(self):
        self.assertIs(sotlas_compile.bootstrap, bootstrap)
        self.assertTrue(bootstrap._TARGET_PROFILE_FRONTEND_INSTALLED)


if __name__ == "__main__":
    unittest.main()
