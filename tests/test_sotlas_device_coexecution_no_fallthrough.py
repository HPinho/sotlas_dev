"""Regression guard: SIR block list order is not an implicit CFG edge."""
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIR_DIR = ROOT / "compiler" / "sotlas" / "sir"


def _load_sir_package():
    name = "sotlas_device_coexecution_no_fallthrough_package"
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


def _transfer(binding: str, point: str):
    return instructions.OwnershipDomainTransferInst(
        operation="handover",
        source=instructions.SIRValue(binding, "Buffer"),
        source_domain="exclusive",
        target_domain="device",
        destination=instructions.SIRValue(f"device_{binding}", "Buffer"),
        point_id=point,
    )


class SotlasDeviceCoexecutionNoFallthroughTests(unittest.TestCase):
    def test_adjacent_blocks_without_branch_do_not_prove_coexecution(self):
        function = instructions.SIRFunction("submit", [], "void")
        first = function.add_block("first")
        first.add(_transfer("left", "handover@1:1"))
        # Deliberately no BranchInst here. Physical list adjacency is not CFG.
        second = function.add_block("second")
        second.add(_transfer("right", "handover@2:1"))
        second.add(instructions.ReturnInst())
        module = instructions.SIRModule("device_no_fallthrough")
        module.add_function(function)

        with self.assertRaisesRegex(
            coexec.DeviceCoexecutionError,
            "not co-executable",
        ):
            coexec.certify_device_submission_coexecution(
                module,
                function="submit",
                point_ids=("handover@1:1", "handover@2:1"),
            )


if __name__ == "__main__":
    unittest.main()
