from __future__ import annotations

import unittest
import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"
PACKAGE_NAME = "sotlas_source_effects_test_package"
SPEC = importlib.util.spec_from_file_location(
    PACKAGE_NAME,
    PACKAGE_DIR / "__init__.py",
    submodule_search_locations=[str(PACKAGE_DIR)],
)
assert SPEC is not None and SPEC.loader is not None
package = importlib.util.module_from_spec(SPEC)
sys.modules[PACKAGE_NAME] = package
SPEC.loader.exec_module(package)
SotlasBootstrapError = package.SotlasBootstrapError
analyze_source_effects = package.analyze_source_effects
compile_source = package.compile_source
bootstrap = package.bootstrap


class SourceEffectContractTests(unittest.TestCase):
    def test_infers_direct_and_transitive_effects_through_recursive_calls(self):
        source = """
module test::source_effects;
@effects(system)
fn outer() -> void { inner(); }
fn inner() -> void { __unknown_intrinsic(); outer(); }
"""
        module = bootstrap.parse(source, filename="effects.sotlas")
        summaries = analyze_source_effects(module, bootstrap)

        self.assertEqual(summaries["inner"].direct_effects, ("system",))
        self.assertEqual(summaries["outer"].transitive_effects, ("system",))
        compile_source(source, filename="effects.sotlas")

    def test_contract_rejects_omitted_transitive_effect(self):
        source = """
module test::source_effects;
@effects(alloc)
fn caller() -> void { __unknown_intrinsic(); }
"""
        with self.assertRaisesRegex(SotlasBootstrapError, "omits inferred effects: system"):
            compile_source(source, filename="effects.sotlas")

    def test_external_calls_require_unknown_call_contract(self):
        source = """
module test::source_effects;
fn external_call() -> void { __external_api(); }
@effects(unknown_call)
fn caller() -> void { external_call(); }
"""
        module = bootstrap.parse(source, filename="effects.sotlas")
        summaries = analyze_source_effects(module, bootstrap)
        self.assertEqual(summaries["caller"].unresolved_calls, ("__external_api",))
        source = source.replace("@effects(unknown_call)\nfn caller", "@effects(io)\nfn caller")
        with self.assertRaisesRegex(SotlasBootstrapError, "cannot prove calls"):
            compile_source(source, filename="effects.sotlas")

    def test_unknown_external_is_explicitly_permitted(self):
        source = """
module test::source_effects;
@effects(unknown_call)
fn caller() -> void { __external_api(); }
"""
        compile_source(source, filename="effects.sotlas")

    def test_unknown_and_malformed_contracts_fail_closed(self):
        for contract in ("@effects(network)", "@effects()", "@effects(io,io)"):
            with self.subTest(contract=contract):
                source = f"module test::source_effects;\n{contract}\nfn pure() -> void {{ return; }}\n"
                with self.assertRaises(SotlasBootstrapError):
                    compile_source(source, filename="effects.sotlas")

    def test_assembly_is_unsafe_and_volatile(self):
        source = """
module test::source_effects;
@effects(unsafe,volatile)
@system fn raw() -> void { asm("nop"); }
"""
        module = bootstrap.parse(source, filename="effects.sotlas")
        summary = analyze_source_effects(module, bootstrap)["raw"]
        self.assertEqual(summary.transitive_effects, ("unsafe", "volatile"))


if __name__ == "__main__":
    unittest.main()
