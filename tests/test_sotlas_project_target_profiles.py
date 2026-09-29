"""Target-profile propagation across canonical Sotlas projects."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_DIR = ROOT / "compiler"
if str(COMPILER_DIR) not in sys.path:
    sys.path.insert(0, str(COMPILER_DIR))

from sotlas_compile import bootstrap


class SotlasProjectTargetProfileTests(unittest.TestCase):
    def _project(self, helper_header: str = ""):
        temporary = tempfile.TemporaryDirectory(prefix="sotlas-target-project-")
        root = Path(temporary.name)
        (root / "core").mkdir(parents=True)
        (root / "kernel").mkdir(parents=True)
        helper = root / "core" / "helper.sotlas"
        helper.write_text(
            f"{helper_header}"
            "module core::helper;\n"
            "pub fn helper() -> u64 { return 7; }\n",
            encoding="utf-8",
        )
        entry = root / "kernel" / "main.sotlas"
        entry.write_text(
            "target barecore;\n"
            "module kernel::main;\n"
            "import core::helper::*;\n"
            "@export\n"
            "pub fn kernel_main() -> u64 { return helper(); }\n",
            encoding="utf-8",
        )
        return temporary, entry

    def test_unannotated_dependencies_inherit_barecore_root_profile(self):
        temporary, entry = self._project()
        self.addCleanup(temporary.cleanup)
        modules = bootstrap.compile_project(entry)
        profiles = {module.name: module.target_profile for module in modules}
        self.assertEqual(profiles["kernel::main"], "barecore")
        self.assertEqual(profiles["core::helper"], "barecore")
        helper = next(module for module in modules if module.name == "core::helper")
        self.assertFalse(helper.target_profile_explicit)
        self.assertTrue(helper.is_barecore)

    def test_explicit_cross_profile_dependency_fails_closed(self):
        temporary, entry = self._project("target native;\n")
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "target profile mismatch",
        ):
            bootstrap.compile_project(entry)

    def test_barecore_project_emission_uses_one_freestanding_preamble(self):
        temporary, entry = self._project()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "build" / "kernel.c"
        bootstrap.emit_c_project(entry, output)
        generated = output.read_text(encoding="utf-8")
        self.assertEqual(generated.count("SOTLAS_BARECORE_ABI_TYPES"), 2)
        # one occurrence is the #ifndef and one is its #define in one preamble
        self.assertNotIn("#include <stdint.h>", generated)
        self.assertNotIn("#include <stddef.h>", generated)
        self.assertNotIn("#include <stdbool.h>", generated)
        self.assertNotIn("#include <stdlib.h>", generated)
        self.assertIn("uint64_t kernel_main(void)", generated)
        self.assertIn("uint64_t helper(void)", generated)

    def test_matching_explicit_dependency_profile_is_accepted(self):
        temporary, entry = self._project("target barecore;\n")
        self.addCleanup(temporary.cleanup)
        modules = bootstrap.compile_project(entry)
        self.assertTrue(all(module.is_barecore for module in modules))


if __name__ == "__main__":
    unittest.main()
