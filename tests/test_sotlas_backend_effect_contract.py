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


class BackendEffectContractTests(unittest.TestCase):
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
