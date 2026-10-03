"""CLI coverage for direct assembly-to-object output from the machine backend."""
from __future__ import annotations

from contextlib import redirect_stderr
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from sotlas import cli


class SotlasMachineObjectCliTests(unittest.TestCase):
    def test_machine_backend_emits_object_by_assembling_its_own_output(self):
        with tempfile.TemporaryDirectory(prefix="sotlas-machine-object-") as temp:
            root = Path(temp)
            source = root / "answer.sotlas"
            output = root / "answer.o"
            source.write_text(
                "module test::machine_object;\npub fn answer() -> u32 { return 42u32; }\n",
                encoding="utf-8",
            )
            assembler_result = subprocess.CompletedProcess([], 0, "", "")
            machine_module = ModuleType("sotlas_compile.machine_x86_64")
            machine_module.MachineBackendError = ValueError
            machine_module.compile_source_to_x86_64_sysv_assembly = lambda *_: (
                ".intel_syntax noprefix\n.text\n"
            )
            stderr = io.StringIO()
            with (
                patch.dict(
                    sys.modules,
                    {
                        "sotlas_compile.machine_x86_64": machine_module,
                        "compiler.sotlas_compile.machine_x86_64": machine_module,
                    },
                ),
                patch.object(
                    sys,
                    "argv",
                    [
                        "sotlas", "compile", str(source), "--backend", "sotlas-x86_64",
                        "--emit-obj", "-o", str(output), "--cc", "clang",
                        "--target", "x86_64-freestanding",
                    ],
                ),
                patch("sotlas.cli.subprocess.run", return_value=assembler_result) as run,
                redirect_stderr(stderr),
            ):
                self.assertEqual(cli.main(), 0, stderr.getvalue())

            command = run.call_args.args[0]
            self.assertEqual(
                command,
                [
                    "clang", "-target", "x86_64-unknown-none-elf", "-x",
                    "assembler", "-c", "-o", str(output), "-",
                ],
            )
            self.assertEqual(run.call_args.kwargs["input"], ".intel_syntax noprefix\n.text\n")
            self.assertTrue(output.parent.is_dir())


if __name__ == "__main__":
    unittest.main()
