"""Import-isolation and mirror gates for the M16.4b2 local-address bridge."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


class SotlasLocalAddressingImportIsolationTests(unittest.TestCase):
    def test_lightweight_fact_module_does_not_eagerly_import_generator(self):
        package_name = "_sotlas_local_addressing_isolated"
        module_name = f"{package_name}.local_addressing"
        generator_name = f"{package_name}.local_addressing_generator"

        for name in (module_name, generator_name, package_name):
            sys.modules.pop(name, None)
        package = types.ModuleType(package_name)
        package.__path__ = [str(COMPILER_PACKAGE_DIR)]
        package.__package__ = package_name
        sys.modules[package_name] = package
        try:
            module = importlib.import_module(module_name)
            self.assertTrue(hasattr(module, "LocalAddressFact"))
            self.assertTrue(hasattr(module, "attach_target_ir_local_addresses"))
            self.assertTrue(hasattr(module, "make_local_addressing_generator"))
            self.assertNotIn(generator_name, sys.modules)
        finally:
            for name in (generator_name, module_name, package_name):
                sys.modules.pop(name, None)

    def test_compiler_and_tools_local_addressing_layers_are_byte_identical(self):
        for relative in (
            "local_addressing.py",
            "local_addressing_generator.py",
            "canonical_sir.py",
            "target_ir_calls.py",
        ):
            compiler_path = ROOT / "compiler" / "sotlas_compile" / relative
            tools_path = ROOT / "tools" / "sotlas_compile" / relative
            self.assertEqual(
                compiler_path.read_bytes(),
                tools_path.read_bytes(),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
