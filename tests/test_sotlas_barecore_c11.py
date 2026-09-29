"""Exercise the canonical freestanding C11 boundary for target barecore."""
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


HOSTED_HEADERS = (
    "#include <stdint.h>",
    "#include <stddef.h>",
    "#include <stdbool.h>",
    "#include <stdlib.h>",
    "#include <stdio.h>",
    "#include <string.h>",
    "#include <pthread.h>",
)


class SotlasBarecoreC11Tests(unittest.TestCase):
    def test_barecore_emits_self_contained_freestanding_abi_types(self):
        source = """
target barecore;
module kernel::freestanding;

@export
pub fn answer() -> u64 {
    return 42;
}
"""
        generated = sotlas_compile.compile_source(
            source, filename="<barecore-c11>"
        )
        self.assertIn("SOTLAS_BARECORE_ABI_TYPES", generated)
        self.assertIn("typedef __UINT64_TYPE__ uint64_t;", generated)
        self.assertIn("uint64_t answer(void)", generated)
        for header in HOSTED_HEADERS:
            with self.subTest(header=header):
                self.assertNotIn(header, generated)

    def test_native_target_keeps_hosted_preamble_for_compatibility(self):
        generated = sotlas_compile.compile_source(
            "target native;\n"
            "module app::hosted;\n"
            "pub fn answer() -> u64 { return 42; }\n",
            filename="<native-c11>",
        )
        self.assertIn("#include <stdint.h>", generated)
        self.assertNotIn("SOTLAS_BARECORE_ABI_TYPES", generated)

    def test_web_target_fails_closed_at_c11_backend(self):
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            "target web cannot be lowered by the C11 backend",
        ):
            sotlas_compile.compile_source(
                "target web;\n"
                "module web::app;\n"
                "pub fn answer() -> u64 { return 42; }\n",
                filename="<web-c11>",
            )

    def test_barecore_without_preamble_does_not_inject_hosted_headers(self):
        module = bootstrap.parse(
            "target barecore;\n"
            "module kernel::unit;\n"
            "pub fn answer() -> u64 { return 42; }\n",
            filename="<barecore-unit>",
        )
        bootstrap.check(module)
        generated = bootstrap.emit_c(module, include_preamble=False)
        self.assertNotIn("SOTLAS_BARECORE_ABI_TYPES", generated)
        for header in HOSTED_HEADERS:
            self.assertNotIn(header, generated)

    def test_barecore_public_header_is_freestanding(self):
        module = bootstrap.parse(
            "target barecore;\n"
            "module kernel::abi;\n"
            "@export\n"
            "pub fn answer() -> u64 { return 42; }\n",
            filename="<barecore-header>",
        )
        header = bootstrap.emit_header(module)
        self.assertIn("SOTLAS_BARECORE_ABI_TYPES", header)
        self.assertIn("uint64_t answer(void);", header)
        for hosted in HOSTED_HEADERS:
            self.assertNotIn(hosted, header)

    def test_c11_target_enforcement_is_outermost_public_boundary(self):
        self.assertTrue(bootstrap._TARGET_PROFILE_C11_INSTALLED)
        module = bootstrap.parse(
            "target barecore;\n"
            "module kernel::boundary;\n"
            "pub fn answer() -> u64 { return 42; }\n",
            filename="<barecore-boundary>",
        )
        generated = bootstrap.emit_c(module)
        self.assertNotIn("#include <stdlib.h>", generated)


if __name__ == "__main__":
    unittest.main()
