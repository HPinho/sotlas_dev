from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sotlas import cli


class _AssemblyToolchain:
    def __init__(self):
        self.calls = []

    def compile_source_to_native(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return Path(args[2])


class SotlasAssemblyCliTests(unittest.TestCase):
    def test_emit_asm_routes_directly_to_llvm_without_c11(self):
        toolchain = _AssemblyToolchain()
        with tempfile.TemporaryDirectory(prefix="sotlas_asm_cli_") as temp:
            source = Path(temp) / "answer.sotlas"
            source.write_text(
                "module test::asm_cli; fn answer() -> u32 { return 42u32; }",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                source=str(source), target="host", cpu_feature=[],
                emit_asm=True, output=None, backend="llvm",
            )
            with (
                patch("sotlas.llvm_toolchain.default_toolchain", toolchain),
                patch.object(cli, "compile_source", side_effect=AssertionError("C11 path used")),
                patch("builtins.print"),
            ):
                result = cli._run_compile(args)
        self.assertEqual(result, 0)
        self.assertEqual(len(toolchain.calls), 1)
        call_args, call_kwargs = toolchain.calls[0]
        self.assertEqual(call_args[2].suffix, ".s")
        self.assertEqual(call_kwargs["emit_type"], "asm")
        self.assertEqual(call_kwargs["backend"], "llvm")


if __name__ == "__main__":
    unittest.main()
