"""Pin the real kernel bootstrap to the canonical freestanding Sotlas profile."""
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

        # The real-kernel spelling must be recognized by the single production
        # frontend as the same semantic target as `target barecore;`.
        module = bootstrap.parse(
            "barecore;\nmodule kernel::profile; fn marker() -> void {}",
            filename="<kernel-profile>",
        )
        plan = sotlas_compile.plan_target_profile(module)
        self.assertTrue(plan.is_barecore)
        self.assertTrue(plan.is_freestanding)
        self.assertEqual(module.target_profile, "barecore")
        self.assertTrue(module.is_barecore)

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
