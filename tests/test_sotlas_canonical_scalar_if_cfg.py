"""Canonical scalar structured-if CFG lowering coverage."""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPILER_PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
_CANONICAL_PACKAGE = "_sotlas_scalar_if_cfg_canonical_compile"


def _load_compile_package():
    package = sys.modules.get(_CANONICAL_PACKAGE)
    if package is None:
        spec = importlib.util.spec_from_file_location(
            _CANONICAL_PACKAGE,
            COMPILER_PACKAGE_DIR / "__init__.py",
            submodule_search_locations=[str(COMPILER_PACKAGE_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load canonical sotlas_compile package")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_CANONICAL_PACKAGE] = package
        spec.loader.exec_module(package)
    return package


_load_compile_package()
_CANONICAL_SIR = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.canonical_sir"
)
_PHASE1 = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.phase1_pipeline"
)
_TARGET_IR = importlib.import_module(
    f"{_CANONICAL_PACKAGE}.target_ir"
)


class SotlasCanonicalScalarIfCFGTests(unittest.TestCase):
    def _checked_sir(self, source: str):
        checked = _PHASE1.analyze_source_phase1(
            source,
            filename="canonical_scalar_if_cfg.sotlas",
        )
        result, _ = _CANONICAL_SIR.build_canonical_checked_ownership_sir(
            checked
        )
        return result.module

    def test_nonvoid_if_returns_same_typed_parameters_as_real_cfg(self):
        module = self._checked_sir(
            """
module test::canonical_scalar_if_cfg;
fn choose(left: u32, right: u32) -> u32 {
    if left < right { return left; }
    return right;
}
"""
        )
        self.assertEqual(tuple(module.unlowered_functions), ())
        function = module.functions[0]
        self.assertEqual(function.return_type, "u32")
        self.assertEqual(len(function.blocks), 3)

        operations = [
            type(instruction).__name__
            for block in function.blocks
            for instruction in block.instructions
        ]
        self.assertIn("CompareInst", operations)
        self.assertIn("CondBranchInst", operations)

        returns = [
            instruction
            for block in function.blocks
            for instruction in block.instructions
            if type(instruction).__name__ == "ReturnInst"
        ]
        self.assertEqual(len(returns), 2)
        self.assertEqual(
            {item.value.name for item in returns},
            {"left", "right"},
        )

        target_ir = _TARGET_IR.lower_sir_to_target_ir(module)
        target_function = target_ir["functions"][0]
        self.assertEqual(len(target_function["blocks"]), 3)
        target_ops = [
            instruction["op"]
            for block in target_function["blocks"]
            for instruction in block["instructions"]
        ]
        self.assertIn("compare", target_ops)
        self.assertIn("cond_branch", target_ops)

    def test_nonvoid_if_else_returns_same_typed_parameters(self):
        module = self._checked_sir(
            """
module test::canonical_scalar_if_else_cfg;
fn choose(flag: bool, left: u32, right: u32) -> u32 {
    if flag { return left; } else { return right; }
}
"""
        )
        self.assertEqual(tuple(module.unlowered_functions), ())
        returns = [
            instruction
            for block in module.functions[0].blocks
            for instruction in block.instructions
            if type(instruction).__name__ == "ReturnInst"
        ]
        self.assertEqual(
            {item.value.name for item in returns},
            {"left", "right"},
        )

    def test_nonvoid_if_expression_return_remains_fail_closed(self):
        module = self._checked_sir(
            """
module test::canonical_scalar_if_reject_expression;
fn choose(left: u32, right: u32) -> u32 {
    if left < right { return left + right; }
    return right;
}
"""
        )
        self.assertEqual(tuple(module.unlowered_functions), ("choose",))


if __name__ == "__main__":
    unittest.main()
