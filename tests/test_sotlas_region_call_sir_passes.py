"""SIR optimization passes must preserve REGION call-transfer facts."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.sir import (
    CallInst,
    RegionCallTransferInst,
    ReturnInst,
    SIRFunction,
    SIRModule,
    SIRValue,
)
from sotlas.sir.passes import (
    BranchFoldingPass,
    DeadCodeEliminationPass,
    RedundantLoadPass,
)


class SotlasRegionCallSIRPassTests(unittest.TestCase):
    @staticmethod
    def _module():
        module = SIRModule(name="region_call_passes")
        function = SIRFunction(name="run", parameters=[], return_type="void")
        block = function.add_block("0")
        marker = RegionCallTransferInst(
            operation="call_transfer",
            source_name="token",
            destination_name="consume.token",
            point_id="call@5:5",
            source=SIRValue("token", "Token"),
            callee="consume",
            parameter="token",
            argument_index=0,
            source_domain="region",
            target_domain="region",
        )
        call = CallInst(callee="consume", arguments=[SIRValue("token", "Token")])
        block.add(marker)
        block.add(call)
        block.add(ReturnInst())
        module.add_function(function)
        return module, marker, call

    def test_core_optimization_passes_preserve_region_call_fact_and_order(self):
        module, marker, call = self._module()
        for pass_type in (
            DeadCodeEliminationPass,
            BranchFoldingPass,
            RedundantLoadPass,
        ):
            with self.subTest(pass_name=pass_type.__name__):
                result = pass_type().run(module)
                self.assertTrue(result.success, result.errors)
                instructions = module.functions[0].blocks[0].instructions
                self.assertIn(marker, instructions)
                self.assertIn(call, instructions)
                self.assertLess(instructions.index(marker), instructions.index(call))


if __name__ == "__main__":
    unittest.main()
