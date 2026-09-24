"""Tests for conservative DEVICE submission coexecution certificates."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIR_DIR = ROOT / "compiler" / "sotlas" / "sir"


def _load_sir_package():
    name = "sotlas_device_coexecution_sir_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        SIR_DIR / "__init__.py",
        submodule_search_locations=[str(SIR_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sir = _load_sir_package()
coexec = importlib.import_module(f"{sir.__name__}.device_coexecution")
instructions = importlib.import_module(f"{sir.__name__}.instructions")

SIRModule = instructions.SIRModule
SIRFunction = instructions.SIRFunction
SIRValue = instructions.SIRValue
OwnershipDomainTransferInst = instructions.OwnershipDomainTransferInst
BranchInst = instructions.BranchInst
CondBranchInst = instructions.CondBranchInst
ReturnInst = instructions.ReturnInst
DeviceCoexecutionError = coexec.DeviceCoexecutionError
certify = coexec.certify_device_submission_coexecution


def _transfer(binding: str, point: str):
    return OwnershipDomainTransferInst(
        operation="handover",
        source=SIRValue(binding, "Buffer"),
        source_domain="exclusive",
        target_domain="device",
        destination=SIRValue(f"device_{binding}", "Buffer"),
        point_id=point,
    )


def _module(function: SIRFunction) -> SIRModule:
    module = SIRModule("device_coexecution")
    module.add_function(function)
    return module


class SotlasDeviceCoexecutionTests(unittest.TestCase):
    def test_two_submissions_in_same_block_are_certified_in_instruction_order(self):
        function = SIRFunction("submit", [], "void")
        entry = function.add_block("entry")
        entry.add(_transfer("left", "handover@1:1"))
        entry.add(_transfer("right", "handover@2:1"))
        entry.add(ReturnInst())

        certificate = certify(
            _module(function),
            function="submit",
            point_ids=("handover@1:1", "handover@2:1"),
        )
        self.assertEqual(certificate.bindings, ("left", "right"))
        self.assertEqual(certificate.block_path, ("entry",))
        self.assertTrue(certificate.acyclic)
        self.assertLess(
            certificate.locations[0].instruction_index,
            certificate.locations[1].instruction_index,
        )

    def test_submissions_in_forward_sequential_blocks_are_certified(self):
        function = SIRFunction("submit", [], "void")
        entry = function.add_block("entry")
        entry.add(_transfer("left", "handover@1:1"))
        entry.add(BranchInst("next"))
        next_block = function.add_block("next")
        next_block.add(_transfer("right", "handover@2:1"))
        next_block.add(ReturnInst())

        certificate = certify(
            _module(function),
            function="submit",
            point_ids=("handover@1:1", "handover@2:1"),
        )
        self.assertEqual(certificate.block_path, ("entry", "next"))

    def test_mutually_exclusive_branch_submissions_are_rejected(self):
        function = SIRFunction("submit", [], "void")
        entry = function.add_block("entry")
        entry.add(
            CondBranchInst(
                condition=SIRValue("flag", "bool"),
                true_block="yes",
                false_block="no",
            )
        )
        yes = function.add_block("yes")
        yes.add(_transfer("left", "handover@1:1"))
        yes.add(ReturnInst())
        no = function.add_block("no")
        no.add(_transfer("right", "handover@2:1"))
        no.add(ReturnInst())

        with self.assertRaisesRegex(DeviceCoexecutionError, "not co-executable"):
            certify(
                _module(function),
                function="submit",
                point_ids=("handover@1:1", "handover@2:1"),
            )

    def test_multi_submission_certificate_rejects_cycles(self):
        function = SIRFunction("submit", [], "void")
        entry = function.add_block("entry")
        entry.add(_transfer("left", "handover@1:1"))
        entry.add(BranchInst("loop"))
        loop = function.add_block("loop")
        loop.add(_transfer("right", "handover@2:1"))
        loop.add(BranchInst("entry"))

        with self.assertRaisesRegex(DeviceCoexecutionError, "acyclic CFG"):
            certify(
                _module(function),
                function="submit",
                point_ids=("handover@1:1", "handover@2:1"),
            )

    def test_certificate_rejects_duplicate_placement_of_one_point(self):
        function = SIRFunction("submit", [], "void")
        entry = function.add_block("entry")
        entry.add(_transfer("left", "handover@1:1"))
        entry.add(_transfer("right", "handover@1:1"))
        entry.add(ReturnInst())

        with self.assertRaisesRegex(DeviceCoexecutionError, "placed more than once"):
            certify(
                _module(function),
                function="submit",
                point_ids=("handover@1:1",),
            )

    def test_certificate_requires_requested_source_order(self):
        function = SIRFunction("submit", [], "void")
        entry = function.add_block("entry")
        entry.add(_transfer("left", "handover@1:1"))
        entry.add(_transfer("right", "handover@2:1"))
        entry.add(ReturnInst())

        with self.assertRaisesRegex(DeviceCoexecutionError, "not ordered"):
            certify(
                _module(function),
                function="submit",
                point_ids=("handover@2:1", "handover@1:1"),
            )


if __name__ == "__main__":
    unittest.main()
