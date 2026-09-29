"""Pin the kernel bootstrap to the explicit freestanding Sotlas profile."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sotlas.lexer import Lexer
from sotlas.parser import Parser


KERNEL = ROOT / "bootstrap" / "sotlas" / "kernel" / "main.sotlas"


def _significant_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]


class SotlasKernelFreestandingProfileContractTests(unittest.TestCase):
    def test_kernel_bootstrap_declares_barecore_before_module(self):
        text = KERNEL.read_text(encoding="utf-8")
        lines = _significant_lines(text)
        self.assertGreaterEqual(len(lines), 2)
        self.assertEqual(lines[0], "barecore;")
        self.assertEqual(lines[1], "module kernel::minimal;")

        # The profile spelling used by the real kernel must be recognized by
        # the language parser as freestanding, not merely guarded by a text test.
        source = "barecore;\nmodule kernel::profile; fn marker() -> Void {}"
        ast = Parser(Lexer(source, "<kernel-profile>").tokenize(), "<kernel-profile>").parse()
        self.assertTrue(ast.is_barecore)

    def test_kernel_entry_and_boot_frame_keep_system_abi_contract(self):
        text = KERNEL.read_text(encoding="utf-8")
        self.assertIn("@repr(C)\n@packed\npub struct BootFrame", text)
        self.assertIn(
            "@export\n@system\npub fn kernel_main(frame: *mut BootFrame) -> u64",
            text,
        )
        self.assertIn("framebuffer: *mut u32;", text)
        self.assertIn("tag: [u8; 8];", text)

    def test_kernel_bootstrap_does_not_gain_obvious_hosted_runtime_dependencies(self):
        text = KERNEL.read_text(encoding="utf-8")
        forbidden = (
            "malloc(",
            "calloc(",
            "realloc(",
            "free(",
            "printf(",
            "fprintf(",
            "fopen(",
            "pthread_",
            "std::",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
