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
analyze_source_phase1 = package.analyze_source_phase1


class SourceEffectContractTests(unittest.TestCase):
    def test_foreign_declarations_have_explicit_ffi_boundary_effect(self):
        source = '''
module test::ffi_effects;
extern "C" fn foreign_read() -> u32;
@effects(ffi,io)
extern "C" fn contracted_read() -> u32;
'''
        module = bootstrap.parse(source, filename="ffi-effects.sotlas")
        summaries = analyze_source_effects(module, bootstrap)
        self.assertEqual(
            summaries["foreign_read"].transitive_effects,
            ("ffi", "unknown_call"),
        )
        self.assertEqual(
            summaries["contracted_read"].transitive_effects,
            ("io", "ffi"),
        )

        omitted = source.replace("@effects(ffi,io)", "@effects(io)")
        with self.assertRaisesRegex(
            SotlasBootstrapError, "omits inferred effects: ffi"
        ):
            compile_source(omitted, filename="ffi-effects.sotlas")

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

    def test_c11_backend_contract_rejects_async_before_emitting_c(self):
        source = """
module test::c11_effects;
@effects(async)
fn suspended() -> void { return; }
"""
        with self.assertRaisesRegex(
            SotlasBootstrapError,
            "C11 backend effect contract rejected lowering.*async",
        ):
            compile_source(source, filename="c11-effects.sotlas")

        supported = """
module test::c11_effects;
@effects(io)
fn host_io() -> void { return; }
"""
        self.assertIn("host_io", compile_source(supported))

    def test_assembly_is_unsafe_and_volatile(self):
        source = """
module test::source_effects;
@effects(unsafe,volatile)
@system fn raw() -> void { unsafe { asm("nop"); } }
"""
        module = bootstrap.parse(source, filename="effects.sotlas")
        summary = analyze_source_effects(module, bootstrap)["raw"]
        self.assertEqual(summary.transitive_effects, ("unsafe", "volatile"))

    def test_phase1_checked_module_preserves_effect_summaries(self):
        source = """
module test::effects_phase1;
@effects(unsafe,volatile)
@system fn raw() -> void { unsafe { asm("nop"); } }
@effects(unsafe,volatile)
fn run() -> void { raw(); }
"""
        checked = analyze_source_phase1(source)
        self.assertEqual(
            checked.source_effects["run"].transitive_effects,
            ("unsafe", "volatile"),
        )
        typed = {item.name: item for item in checked.semantic.typed_module.functions}
        self.assertEqual(
            typed["raw"].effect_summary.direct_effects,
            ("unsafe", "volatile"),
        )
        self.assertEqual(
            typed["run"].effect_summary.transitive_effects,
            ("unsafe", "volatile"),
        )
        self.assertEqual(
            typed["run"].effect_summary.declared_effects,
            ("unsafe", "volatile"),
        )

    def test_checked_source_effects_are_revalidated_in_canonical_sir(self):
        source = """
module test::effects_sir;
@effects(unsafe,volatile)
@system fn raw() -> void { unsafe { asm("nop"); } }
@effects(unsafe,volatile)
fn run() -> void { raw(); }
"""
        checked = analyze_source_phase1(source)
        ownership_sir, _ = package.build_canonical_checked_ownership_sir(
            checked
        )
        sir = sys.modules["_sotlas_compiler_canonical_sir"]
        result = sir.EffectInferencePass().run(ownership_sir.module)
        self.assertTrue(result.success, result.errors)
        self.assertEqual(
            ownership_sir.module.effect_summaries["raw"].direct_effects,
            ("unsafe", "volatile"),
        )
        self.assertEqual(
            ownership_sir.module.effect_summaries["run"].transitive_effects,
            ("unsafe", "volatile"),
        )
        self.assertEqual(
            ownership_sir.module.effect_summaries["run"].declared_effects,
            ("unsafe", "volatile"),
        )


if __name__ == "__main__":
    unittest.main()
