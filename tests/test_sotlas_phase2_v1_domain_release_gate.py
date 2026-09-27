"""Canonical native gates for the bounded ISLAND and HANDOVER subset."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))
from sotlas.llvm_toolchain import default_toolchain  # noqa: E402


ISLAND_HANDOVER_SOURCE = """module app::phase2_v1_island_handover;
sole struct Token { value: u32; }
static mut destroy_count: u32 = 0;

fn Token_deinit(self: *mut Token) -> void {
    unsafe { destroy_count = destroy_count + 1u32; }
}

fn consume(token: Token) -> void { return; }

fn main() -> i32 {
    let source: Token = Token { value: 41u32 };
    let destination: Token = Token { value: 9u32 };
    consume(move destination);
    quarantine source;
    handover source to destination;
    if destination.value == 41u32 && destroy_count == 1u32 { return 0; }
    return 1;
}
"""


class SotlasPhase2V1DomainReleaseGateTests(unittest.TestCase):
    def test_island_handover_executes_through_canonical_c11_with_one_drop_per_owner(self):
        compiler_available = default_toolchain.is_available() or shutil.which("gcc")
        if not compiler_available:
            self.skipTest("Clang or GCC is required for canonical ownership execution")

        with tempfile.TemporaryDirectory(prefix="sotlas-island-handover-") as temp:
            executable = Path(temp) / (
                "island_handover.exe" if os.name == "nt" else "island_handover"
            )
            default_toolchain.compile_source_to_native(
                ISLAND_HANDOVER_SOURCE,
                "app::phase2_v1_island_handover",
                executable,
                emit_type="exe",
                backend="c11",
            )
            executed = subprocess.run(
                [str(executable)], capture_output=True, text=True, check=False
            )
            self.assertEqual(executed.returncode, 0, executed.stderr or executed.stdout)


if __name__ == "__main__":
    unittest.main()
