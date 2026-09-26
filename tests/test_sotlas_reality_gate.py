"""Reality gates for prototype SIR and the canonical production path."""
import ast
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))


class SotlasRealityGateTests(unittest.TestCase):
    def test_package_metadata_matches_runtime_version_and_maturity(self):
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        setup = (ROOT / "setup.py").read_text(encoding="utf-8")
        package = (ROOT / "compiler" / "sotlas" / "__init__.py").read_text(
            encoding="utf-8"
        )
        version = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
        self.assertIsNotNone(version)
        self.assertIn(f'version="{version.group(1)}"', setup)
        self.assertIn(f'SOTLAS_VERSION = "{version.group(1)}"', package)
        self.assertIn("Development Status :: 3 - Alpha", project)
        self.assertNotIn("Development Status :: 4 - Beta", project)

    def test_historical_audit_does_not_claim_current_support(self):
        audit = (ROOT / "docs" / "sotlas_v1_audit_and_roadmap.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Historical design note", audit.split("---", 1)[0])
        self.assertIn("prototype SIR is not the production lowering path", audit)

    def test_numbered_examples_match_experimental_manifest(self):
        root = ROOT / "examples"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        entries = manifest["examples"]
        numbered = {path.name for path in root.iterdir()
                    if path.is_dir() and path.name[:2].isdigit()}
        self.assertEqual({item["id"] for item in entries}, numbered)
        self.assertTrue(all(item["status"] == "EXPERIMENTAL" for item in entries))
        self.assertTrue(all((ROOT / item["entry"]).exists() for item in entries))

    def test_public_readmes_use_current_checkout_and_label_sir_prototype(self):
        for name in ("README.md", "README.pt-BR.md"):
            readme = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("git clone https://github.com/HPinho/sotlas_dev.git", readme)
            self.assertNotIn("github.com/Sotlas/sotlas.git", readme)
            self.assertIn("SIR protótipo" if "pt-BR" in name else "prototype SIR", readme)

    def test_public_snippet_inventory_has_valid_status_and_existing_documents(self):
        inventory = json.loads(
            (ROOT / "docs" / "public_snippets.json").read_text(encoding="utf-8")
        )
        allowed = set(inventory["policy"])
        self.assertTrue(inventory["snippets"])
        ids = set()
        for snippet in inventory["snippets"]:
            with self.subTest(snippet=snippet["id"]):
                self.assertNotIn(snippet["id"], ids)
                ids.add(snippet["id"])
                self.assertIn(snippet["status"], allowed)
                self.assertTrue((ROOT / snippet["document"]).is_file())
                self.assertTrue(snippet["verification"])
                if snippet["status"] == "RUNNABLE":
                    self.assertTrue(snippet["source"])
                    self.assertTrue((ROOT / snippet["source"]).is_file())
        quickstart = next(
            item for item in inventory["snippets"]
            if item["id"] == "quickstart-numbered-example"
        )
        self.assertEqual(quickstart["status"], "RUNNABLE")

    def test_quickstarts_point_to_checked_in_source_and_c11_emission(self):
        for name in ("README.md", "README.pt-BR.md"):
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            self.assertIn("--emit-c", text)
            self.assertIn("experimental", text)
            self.assertIn("examples/01_hello_systems/main.sotlas", text)
            self.assertNotIn("#298", text)
        quickstart = (ROOT / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
        self.assertIn("examples/01_hello_systems/main.sotlas", quickstart)
        self.assertIn("SPEC_SOTLAS_1.0.md", quickstart)
        self.assertNotIn("file:///e:/LangSotlas", quickstart)

    def test_identical_compiler_tool_mirrors_do_not_drift(self):
        compiler = ROOT / "compiler"
        tools = ROOT / "tools"
        reviewed_differences = {
            Path("sotlas/cli.py"),
            Path("sotlas/__init__.py"),
            Path("sotlas/sir/instructions.py"),
            Path("sotlas_compile/bootstrap.py"),
            Path("sotlas_compile/language_safety.py"),
            Path("sotlas_compile/__init__.py"),
        }
        paired = {
            path.relative_to(compiler)
            for path in compiler.rglob("*.py")
            if (tools / path.relative_to(compiler)).is_file()
        }
        self.assertTrue(reviewed_differences <= paired)
        for relative in paired - reviewed_differences:
            self.assertEqual(
                (compiler / relative).read_bytes(),
                (tools / relative).read_bytes(),
                f"compiler/tools mirror drift: {relative}",
            )

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
        normalized = " ".join(status.split())
        self.assertIn("Status: CERTIFIED", status)
        self.assertIn("Maturity: ISOLATED_PHASE1", status)
        self.assertIn(
            "not a claim of full language production support",
            normalized,
        )
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
