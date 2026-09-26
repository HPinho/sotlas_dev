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


if __name__ == "__main__":
    unittest.main()
