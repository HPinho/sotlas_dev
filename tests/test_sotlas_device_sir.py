"""SIR tests for completion-gated DEVICE ownership."""
from pathlib import Path
import importlib
import importlib.util
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILE_DIR = ROOT / "compiler" / "sotlas_compile"
SOTLAS_DIR = ROOT / "compiler" / "sotlas"


def _load_compile_package():
    name = "sotlas_device_sir_compile_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        COMPILE_DIR / "__init__.py",
        submodule_search_locations=[str(COMPILE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_sotlas_backend_package():
    """Create a canonical package root without executing public __init__.py."""
    name = "sotlas_device_sir_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


compile_package = _load_compile_package()
device_semantics = importlib.import_module(
    f"{compile_package.__name__}.device_ownership"
)
typed_ast = importlib.import_module(f"{compile_package.__name__}.typed_ast")
backend_package = _load_sotlas_backend_package()
sir = importlib.import_module(f"{backend_package.__name__}.sir")
codegen_llvm = importlib.import_module(
    f"{backend_package.__name__}.codegen_llvm"
)


def _completed_lifecycle():
    semantic_type = typed_ast.SemanticType("Token")
    submission = typed_ast.OwnershipDomainTransition(
        binding="buffer",
        type=semantic_type,
        source=typed_ast.OwnershipDomain.EXCLUSIVE,
        target=typed_ast.OwnershipDomain.DEVICE,
        source_state=typed_ast.VarState.LIVE,
        operation="handover",
        function="submit",
        point_id="handover@3:5",
    )
    graph = typed_ast.OwnershipDomainGraph(
        nodes=(), transfers=(), planned_transitions=(submission,)
    )
    token = device_semantics.open_device_completion(
        graph, function="submit", binding="buffer"
    )
    completed = device_semantics.complete_device_transfer(
        token, point_id="completion@8:1"
    )
    plan = device_semantics.plan_device_reacquisition(
        completed, point_id="reacquire@9:1"
    )
    reacquired = device_semantics.mark_device_reacquired(completed, plan)
    return completed, plan, reacquired


class SotlasDeviceSIRTests(unittest.TestCase):
    def test_completed_device_lifecycle_preserves_all_source_identities(self):
        _, plan, reacquired = _completed_lifecycle()
        source = sir.SIRValue("device_buffer", "Token")
        destination = sir.SIRValue("host_buffer", "Token")

        lowered = sir.lower_device_lifecycle(
            reacquired, plan, source, destination
        )
        self.assertEqual(len(lowered.instructions), 2)
        completion, reacquisition = lowered.instructions

        self.assertIsInstance(completion, sir.DeviceCompletionInst)
        self.assertIsInstance(completion, sir.OwnershipDomainPointInst)
        self.assertEqual(completion.submission_point_id, "handover@3:5")
        self.assertEqual(completion.point_id, "completion@8:1")

        self.assertIsInstance(reacquisition, sir.DeviceReacquisitionInst)
        self.assertIsInstance(reacquisition, sir.OwnershipDomainTransferInst)
        self.assertEqual(reacquisition.submission_point_id, "handover@3:5")
        self.assertEqual(reacquisition.completion_point_id, "completion@8:1")
        self.assertEqual(reacquisition.point_id, "reacquire@9:1")
        self.assertEqual(reacquisition.source_domain, "device")
        self.assertEqual(reacquisition.target_domain, "exclusive")

        rendered = "\n".join(str(inst) for inst in lowered.instructions)
        self.assertIn("handover@3:5", rendered)
        self.assertIn("completion@8:1", rendered)
        self.assertIn("reacquire@9:1", rendered)

    def test_device_sir_rejects_incomplete_semantic_proof(self):
        completed, plan, _ = _completed_lifecycle()
        source = sir.SIRValue("device_buffer", "Token")
        destination = sir.SIRValue("host_buffer", "Token")

        with self.assertRaisesRegex(
            sir.DeviceSIRLoweringError, "requires REACQUIRED"
        ):
            sir.lower_device_lifecycle(completed, plan, source, destination)

        with self.assertRaisesRegex(
            sir.DeviceSIRLoweringError, "has type 'Wrong'"
        ):
            sir.lower_device_reacquisition(
                plan,
                sir.SIRValue("device_buffer", "Wrong"),
                destination,
            )

    def test_device_sir_rejects_mismatched_reacquisition_identity(self):
        _, plan, reacquired = _completed_lifecycle()
        source = sir.SIRValue("device_buffer", "Token")
        destination = sir.SIRValue("host_buffer", "Token")
        mismatched = type(plan)(
            function=plan.function,
            binding=plan.binding,
            type=plan.type,
            source=plan.source,
            target=plan.target,
            submission_point_id=plan.submission_point_id,
            completion_point_id=plan.completion_point_id,
            reacquisition_point_id="reacquire@99:1",
            operation=plan.operation,
        )
        with self.assertRaisesRegex(
            sir.DeviceSIRLoweringError, "different identities"
        ):
            sir.lower_device_lifecycle(
                reacquired, mismatched, source, destination
            )

    def test_llvm_remains_fail_closed_for_device_completion_runtime(self):
        _, plan, reacquired = _completed_lifecycle()
        source = sir.SIRValue("device_buffer", "Token")
        destination = sir.SIRValue("host_buffer", "Token")
        lowered = sir.lower_device_lifecycle(
            reacquired, plan, source, destination
        )

        expectations = (
            (lowered.instructions[0], "DeviceCompletionInst"),
            (lowered.instructions[1], "device_reacquire ownership transfer"),
        )
        for instruction, error_text in expectations:
            with self.subTest(instruction=type(instruction).__name__):
                module = sir.SIRModule("device_fail_closed")
                function = sir.SIRFunction("probe", [], "void")
                block = function.add_block("0")
                block.add(instruction)
                block.add(sir.ReturnInst())
                module.add_function(function)
                with self.assertRaisesRegex(ValueError, error_text):
                    codegen_llvm.CodegenLLVM(module).emit()


if __name__ == "__main__":
    unittest.main()
