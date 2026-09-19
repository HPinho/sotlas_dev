"""Reality gates for prototype SIR and the canonical production path."""
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

    def test_baken_compatibility_adapter_is_not_imported_by_production_package(self):
        package = (
            ROOT / "compiler" / "sotlas_compile" / "__init__.py"
        ).read_text(encoding="utf-8")
        compatibility = (
            ROOT / "compiler" / "sotlas_compile" / "compiler.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("from .compiler import", package)
        self.assertIn('root / "kernel"', compatibility)
        self.assertIn('root / "libbkn"', compatibility)

    def test_canonical_safety_policy_has_no_baken_specific_names(self):
        safety = (
            ROOT / "compiler" / "sotlas_compile" / "language_safety.py"
        ).read_text(encoding="utf-8")
        package = (
            ROOT / "compiler" / "sotlas_compile" / "__init__.py"
        ).read_text(encoding="utf-8")
        compat = (
            ROOT / "compiler" / "sotlas_compile" / "baken_compat.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("baken_", safety.lower())
        self.assertNotIn("baken_compat", package)
        self.assertIn("baken_get_font_alpha", compat)

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


if __name__ == "__main__":
    unittest.main()