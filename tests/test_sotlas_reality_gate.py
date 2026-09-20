"""Reality gates for prototype SIR and the canonical production path."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))


class SotlasRealityGateTests(unittest.TestCase):
    def test_sir_dump_declares_prototype_status(self):
        instructions = (
            ROOT / "compiler" / "sotlas" / "sir" / "instructions.py"
        ).read_text(encoding="utf-8")
        self.assertIn("SIR PROTOTYPE — NOT THE PRODUCTION LOWERING PATH", instructions)

    def test_sir_generator_does_not_claim_complete_body_lowering(self):
        generator = (
            ROOT / "compiler" / "sotlas" / "sir" / "generator.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Emite retorno padrão", generator)
        self.assertNotIn("production lowering", generator.lower())

    def test_public_production_entrypoint_is_bootstrap_not_sir(self):
        package = (
            ROOT / "compiler" / "sotlas_compile" / "__init__.py"
        ).read_text(encoding="utf-8")
        self.assertIn("compile_source = bootstrap.compile_source", package)
        self.assertNotIn("SIRGenerator", package)
        self.assertNotIn("CodegenLLVM", package)
        self.assertNotIn("from .compiler import", package)
        self.assertIn("from .errors import SotlasError", package)


    def test_canonical_bootstrap_has_no_product_or_cq_compatibility_names(self):
        for path in (
            ROOT / "compiler" / "sotlas_compile" / "bootstrap.py",
            ROOT / "tools" / "sotlas_compile" / "bootstrap.py",
        ):
            source = path.read_text(encoding="utf-8").lower()
            for forbidden in (
                "baken", "libbkn", "projeto-bkn", "cq01error",
                ".cq", ".cqh", "vortexc",
            ):
                self.assertNotIn(forbidden, source, f"{forbidden} leaked into {path}")

    def test_x86_inline_assembly_uses_platform_c_symbol_spelling(self):
        intrinsics = (
            ROOT / "compiler" / "sotlas_compile" / "x86_intrinsics.py"
        ).read_text(encoding="utf-8")
        self.assertIn("#define SOTLAS_ASM_CSYM(name)", intrinsics)
        self.assertIn("__APPLE__", intrinsics)
        self.assertIn(
            "SOTLAS_ASM_CSYM(sotlas_x86_exception_dispatch)",
            intrinsics,
        )
        self.assertIn(
            "SOTLAS_ASM_CSYM(sotlas_x86_irq_dispatch)",
            intrinsics,
        )
        self.assertIn(
            "SOTLAS_ASM_CSYM(sotlas_x86_scheduler_thread_exit)",
            intrinsics,
        )

    def test_sir_status_document_records_required_gate(self):
        status = (ROOT / "docs" / "sir-status.md").read_text(encoding="utf-8")
        self.assertIn("Maturity: PROTOTYPE", status)
        self.assertIn("ownership/move facts", status)
        self.assertIn("effects and system capabilities", status)
        self.assertIn("state/typestate transitions", status)
        self.assertIn("causal/flow dependencies", status)


    def test_phase1_semantic_core_status_records_certification_scope(self):
        status = (
            ROOT / "docs" / "phase1-semantic-core-status.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Status: CERTIFIED", status)
        self.assertIn("Maturity: ISOLATED_PHASE1", status)
        self.assertIn("not a claim of full language production support", status)
        self.assertIn("bootstrap.check", status)
        self.assertIn("Typed AST", status)
        self.assertIn("ownership", status)

    def test_phase1_semantic_core_maturity_does_not_regress(self):
        source = (
            ROOT / "compiler" / "sotlas_compile" / "typed_ast.py"
        ).read_text(encoding="utf-8")
        self.assertIn('MATURITY = "ISOLATED_PHASE1"', source)
        self.assertNotIn("DECLARATIONS_ONLY", source)
        self.assertIn("maturity: str = MATURITY", source)

    def test_phase1_legacy_assignable_is_not_in_semantic_use(self):
        path = ROOT / "compiler" / "sotlas_compile" / "bootstrap.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "assignable"
        ]
        self.assertEqual(
            calls,
            [],
            "legacy assignable() must not re-enter certified Phase-1 semantics",
        )


if __name__ == "__main__":
    unittest.main()