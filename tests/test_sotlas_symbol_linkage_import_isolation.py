"""Regression gate for symbol-linkage import isolation."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_PACKAGE_DIR = ROOT / "tools" / "sotlas_compile"


class SotlasSymbolLinkageImportIsolationTests(unittest.TestCase):
    def test_tools_package_loads_without_target_ir_module(self):
        script = textwrap.dedent(
            f"""
            import importlib.util
            from pathlib import Path
            import sys

            package_dir = Path({str(TOOLS_PACKAGE_DIR)!r})
            package_name = "_sotlas_linkage_isolated_tools"
            spec = importlib.util.spec_from_file_location(
                package_name,
                package_dir / "__init__.py",
                submodule_search_locations=[str(package_dir)],
            )
            assert spec is not None and spec.loader is not None
            package = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = package
            spec.loader.exec_module(package)

            linkage = __import__(
                package_name + ".symbol_linkage",
                fromlist=["SourceSymbolLinkage"],
            )
            fact = linkage.SourceSymbolLinkage(
                symbol="helper",
                linkage="internal",
                source_visibility="private",
                abi_export=False,
            )
            assert fact.linkage == "internal"
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"isolated tools package import failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
