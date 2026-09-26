from __future__ import annotations

import unittest

from sotlas.sir import (
    BackendEffectContract,
    CallInst,
    EffectInferencePass,
    SIRFunction,
    SIRModule,
    SIRPassManager,
    validate_backend_effects,
)
from sotlas.codegen_llvm import CodegenLLVM
from sotlas.codegen_c import CodegenC
from sotlas.lexer import Lexer
from sotlas.parser import Parser


class BackendEffectContractTests(unittest.TestCase):
    def _ast(self):
        source = """module test::backend_effect_contract;
pub fn pure() -> void { return; }
pub fn reader() -> void { return; }
pub fn opaque() -> void { return; }
"""
        return Parser(Lexer(source, "<backend-effect-contract>").tokenize()).parse()

    def _module(self):
        module = SIRModule("backend_effects")
        pure = SIRFunction("pure", [], "void")
        pure.add_block("entry")
        module.add_function(pure)
        reader = SIRFunction("reader", [], "void")
        reader.add_block("entry").add(CallInst(callee="io_read", arguments=[]))
        module.add_function(reader)
        opaque = SIRFunction("opaque", [], "void")
        opaque.add_block("entry").add(CallInst(callee="foreign_api", arguments=[]))
        module.add_function(opaque)
        return module

    def test_contract_accepts_allowed_effects_and_rejects_other_functions(self):
        module = self._module()
        result = SIRPassManager().validate_backend_effects(
            module,
            BackendEffectContract("sandbox", frozenset({"io"})),
        )
        self.assertEqual(
            [(item.function, item.accepted, item.rejected_effects) for item in result],
            [
                ("pure", True, ()),
                ("reader", True, ()),
                ("opaque", False, ("unknown_call",)),
            ],
        )

    def test_contract_reports_effects_in_canonical_order(self):
        module = self._module()
        self.assertTrue(EffectInferencePass().run(module).success)
        result = validate_backend_effects(
            module, BackendEffectContract("pure", frozenset())
        )
        self.assertEqual(result[1].rejected_effects, ("io",))
        self.assertEqual(result[2].rejected_effects, ("unknown_call",))

    def test_contract_rejects_unknown_capabilities(self):
        with self.assertRaisesRegex(ValueError, "unknown effects"):
            BackendEffectContract("bad", frozenset({"magic"}))

    def test_llvm_emission_enforces_explicit_backend_effect_contract(self):
        module = self._module()
        with self.assertRaisesRegex(ValueError, "reader: io; opaque: unknown_call"):
            CodegenLLVM(
                module,
                effect_contract=BackendEffectContract("pure", frozenset()),
            ).emit()

        ir = CodegenLLVM(
            module,
            effect_contract=BackendEffectContract(
                "io-host", frozenset({"io", "unknown_call"}),
                allow_unknown_calls=True,
            ),
        ).emit()
        self.assertIn("define void @reader()", ir)

    def test_llvm_emission_rejects_invalid_effect_contract_input(self):
        with self.assertRaisesRegex(TypeError, "BackendEffectContract"):
            CodegenLLVM(self._module(), effect_contract=object()).emit()

    def test_llvm_emission_applies_default_target_contract(self):
        module = self._module()
        with self.assertRaisesRegex(ValueError, "reader: io; opaque: unknown_call"):
            CodegenLLVM(module).emit()

    def test_llvm_emission_requires_inferred_effect_summaries(self):
        module = SIRModule("incomplete_effects")
        function = SIRFunction("work", [], "void")
        function.add_block("entry")
        module.add_function(function)
        self.assertNotIn("work", module.effect_summaries)
        # An empty SIR function has no effectful instructions, but inference is
        # still required and must create a pure summary before LLVM lowering.
        ir = CodegenLLVM(module).emit()
        self.assertIn("define void @work()", ir)
        self.assertEqual(module.effect_summaries["work"].transitive_effects, ())

    def test_c11_emission_enforces_explicit_backend_effect_contract(self):
        module = self._module()
        with self.assertRaisesRegex(ValueError, "reader: io; opaque: unknown_call"):
            CodegenC(
                self._ast(),
                sir_module=module,
                effect_contract=BackendEffectContract("pure-c11", frozenset()),
            ).emit()

        output = CodegenC(
            self._ast(),
            sir_module=module,
            effect_contract=BackendEffectContract(
                "host-c11",
                frozenset({"io", "unknown_call"}),
                allow_unknown_calls=True,
            ),
        ).emit()
        self.assertIn("pure", output)

    def test_c11_contract_rejects_sir_from_a_different_function_set(self):
        module = self._module()
        module.add_function(SIRFunction("unmatched", [], "void"))
        with self.assertRaisesRegex(ValueError, "unmatched SIR functions: unmatched"):
            CodegenC(
                self._ast(),
                sir_module=module,
                effect_contract=BackendEffectContract("host-c11", frozenset()),
            ).emit()

    def test_c11_contract_requires_sir_evidence_and_rejects_invalid_contract(self):
        with self.assertRaisesRegex(TypeError, "requires the canonical SIRModule"):
            CodegenC(self._ast(), effect_contract=BackendEffectContract("pure", frozenset()))
        with self.assertRaisesRegex(TypeError, "BackendEffectContract"):
            CodegenC(self._ast(), sir_module=self._module(), effect_contract=object())

    def test_sir_dump_keeps_per_function_effect_evidence(self):
        module = self._module()
        result = EffectInferencePass().run(module)
        self.assertTrue(result.success, result.errors)
        self.assertTrue(module.effect_summaries)
        dump = module.dump()
        self.assertIn("effects @reader: inferred=[io]", dump)
        self.assertIn("unresolved=[foreign_api]", dump)


if __name__ == "__main__":
    unittest.main()
