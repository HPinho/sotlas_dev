"""Regression guards for the recovered Phase-2 ownership baseline.

These tests intentionally protect semantic surface area that must not disappear
as a side effect of compiler/bootstrap refactors. They do not certify Phase 2;
they only make destructive simplifications visible in CI.
"""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


typed_ast = _load(
    "sotlas_phase2_regression_typed_ast",
    ROOT / "compiler" / "sotlas_compile" / "typed_ast.py",
)
sir_instructions = _load(
    "sotlas_phase2_regression_sir_instructions",
    ROOT / "compiler" / "sotlas" / "sir" / "instructions.py",
)


class Phase2RegressionGuardTests(unittest.TestCase):
    def test_canonical_ownership_domain_vocabulary_is_preserved(self):
        expected = {
            "exclusive",
            "shared",
            "region",
            "device",
            "external",
            "island",
            "whisper",
            "direct",
        }
        actual = {domain.value for domain in typed_ast.OwnershipDomain}
        self.assertTrue(
            expected <= actual,
            f"Phase-2 ownership domains disappeared: {sorted(expected - actual)}",
        )

    def test_phase2_semantic_graph_and_shared_accounting_are_preserved(self):
        required = (
            "OwnershipDomainGraph",
            "OwnershipDomainTransition",
            "SharedOwnershipAccount",
            "TypedShareExpression",
            "plan_ownership_domain_transition",
            "apply_shared_transition",
            "build_typed_share_expression",
        )
        missing = [name for name in required if not hasattr(typed_ast, name)]
        self.assertEqual(missing, [], f"Phase-2 semantic API disappeared: {missing}")

    def test_ownership_sir_contract_is_preserved(self):
        required = (
            "OwnershipDomainPointInst",
            "OwnershipDomainTransferInst",
            "WhisperBorrowInst",
            "DirectAccessInst",
            "SharedOwnershipPointInst",
            "ShareInst",
            "RetainInst",
            "ReleaseInst",
            "DestroyInst",
            "DeferUseInst",
            "CompareInst",
            "PhiInst",
        )
        missing = [name for name in required if not hasattr(sir_instructions, name)]
        self.assertEqual(missing, [], f"Ownership SIR surface disappeared: {missing}")


if __name__ == "__main__":
    unittest.main()
