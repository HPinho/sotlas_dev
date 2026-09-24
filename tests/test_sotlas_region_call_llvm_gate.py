"""LLVM must fail closed on REGION interprocedural ownership facts."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.codegen_llvm import CodegenLLVM
from sotlas.sir import (
    RegionCallTransferInst,
    SIRFunction,
    SIRModule,
    SIRValue,
)


class SotlasRegionCallLLVMGateTests(unittest.TestCase):
    @staticmethod
    def _module_with(instruction):
        module = SIRModule(name="region_call_llvm_gate")
        function = SIRFunction(name="main", parameters=[], return_type="void")
        block = function.add_block("0")
        block.add(instruction)
        module.add_function(function)
        return module

    def test_public_region_call_transfer_is_rejected_without_backend_abi(self):
        instruction = RegionCallTransferInst(
            operation="call_transfer",
            source_name="token",
            destination_name="consume.token",
            point_id="call@4:5",
            source=SIRValue("token", "Token"),
            callee="consume",
            parameter="token",
            argument_index=0,
            source_domain="region",
            target_domain="region",
        )
        with self.assertRaisesRegex(
            ValueError,
            "does not lower REGION call-transfer facts",
        ):
            CodegenLLVM(self._module_with(instruction)).emit()

    def test_private_namespace_shape_is_also_rejected_by_name(self):
        ForeignRegionCallTransferInst = type("RegionCallTransferInst", (), {})
        with self.assertRaisesRegex(
            ValueError,
            "does not lower REGION call-transfer facts",
        ):
            CodegenLLVM(
                self._module_with(ForeignRegionCallTransferInst())
            ).emit()


if __name__ == "__main__":
    unittest.main()
