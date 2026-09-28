"""Regression guard for canonical SIR class identity across dynamic package loads."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SotlasCanonicalSIRIdentityTests(unittest.TestCase):
    def _run_isolated(self, source: str) -> None:
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(source)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "isolated canonical-SIR identity probe failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    def test_compiler_and_tools_aliases_share_one_canonical_sir(self):
        self._run_isolated(
            r'''
            import importlib
            import importlib.util
            from pathlib import Path
            import sys

            root = Path.cwd()

            def load_package(name, directory):
                spec = importlib.util.spec_from_file_location(
                    name,
                    directory / "__init__.py",
                    submodule_search_locations=[str(directory)],
                )
                assert spec is not None and spec.loader is not None
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
                return module

            compiler_package = load_package(
                "sotlas_canonical_identity_compiler",
                root / "compiler" / "sotlas_compile",
            )
            tools_package = load_package(
                "sotlas_canonical_identity_tools",
                root / "tools" / "sotlas_compile",
            )
            compiler_bridge = importlib.import_module(
                f"{compiler_package.__name__}.canonical_sir"
            )
            tools_bridge = importlib.import_module(
                f"{tools_package.__name__}.canonical_sir"
            )

            compiler_sir = compiler_bridge.load_canonical_sir()
            tools_sir = tools_bridge.load_canonical_sir()

            assert compiler_sir is tools_sir
            expected = root / "compiler" / "sotlas" / "sir" / "__init__.py"
            assert Path(compiler_sir.__file__).resolve() == expected.resolve()
            assert compiler_sir.__name__ == "_sotlas_compiler_canonical_sir"

            for name in (
                "SIRValue",
                "SIRInstruction",
                "OwnershipDomainPointInst",
                "OwnershipDomainTransferInst",
                "SIRBasicBlock",
                "SIRFunction",
                "SIRModule",
                "CheckedOwnershipSIR",
            ):
                assert getattr(compiler_sir, name) is getattr(tools_sir, name), name
            '''
        )

    def test_legacy_public_sotlas_sir_cannot_poison_canonical_identity(self):
        self._run_isolated(
            r'''
            import importlib
            import importlib.util
            from pathlib import Path
            import sys

            root = Path.cwd()
            sys.path.insert(0, str(root / "tools"))
            legacy_sir = importlib.import_module("sotlas.sir")

            package_dir = root / "compiler" / "sotlas_compile"
            package_name = "sotlas_canonical_identity_after_legacy"
            spec = importlib.util.spec_from_file_location(
                package_name,
                package_dir / "__init__.py",
                submodule_search_locations=[str(package_dir)],
            )
            assert spec is not None and spec.loader is not None
            package = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = package
            spec.loader.exec_module(package)

            bridge = importlib.import_module(f"{package_name}.canonical_sir")
            canonical_sir = bridge.load_canonical_sir()

            expected = root / "compiler" / "sotlas" / "sir" / "__init__.py"
            assert Path(canonical_sir.__file__).resolve() == expected.resolve()
            assert canonical_sir is not legacy_sir
            assert canonical_sir.SIRValue is not legacy_sir.SIRValue
            assert canonical_sir.SIRModule is not legacy_sir.SIRModule
            assert canonical_sir.SIRValue.__module__.startswith(
                "_sotlas_compiler_canonical_sir."
            )
            '''
        )


if __name__ == "__main__":
    unittest.main()
