"""SIR tests for synchronized DEVICE ownership batches."""
from dataclasses import replace
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
    name = "sotlas_device_sync_sir_compile_package"
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
    name = "sotlas_device_sync_sir_backend_package"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(SOTLAS_DIR)]
        package.__package__ = name
        sys.modules[name] = package
    return sys.modules[name]


compile_package = _load_compile_package()
device_ownership = importlib.import_module(
    f"{compile_package.__name__}.device_ownership"
)
device_sync = importlib.import_module(f"{compile_package.__name__}.device_sync")
typed_ast = importlib.import_module(f"{compile_package.__name__}.typed_ast")
backend_package = _load_sotlas_backend_package()
sir = importlib.import_module(f"{backend_package.__name__}.sir")
device_sir = importlib.import_module(f"{backend_package.__name__}.sir.device")
device_sync_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_sync"
)
codegen_llvm = importlib.import_module(
    f"{backend_package.__name__}.codegen_llvm"
)


TOKEN = typed_ast.SemanticType("Token")


def _submission(binding: str, point_id: str):
    return typed_ast.OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=typed_ast.OwnershipDomain.EXCLUSIVE,
        target=typed_ast.OwnershipDomain.DEVICE,
        source_state=typed_ast.VarState.LIVE,
        operation="handover",
        function="submit_pair",
        point_id=point_id,
    )


def _completed(binding: str, submit: str, complete: str):
    graph = typed_ast.OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=(_submission(binding, submit),),
    )
    token = device_ownership.open_device_completion(
        graph, function="submit_pair", binding=binding
    )
    return device_ownership.complete_device_transfer(token, point_id=complete)


def _synchronized_batch():
    tokens = (
        _completed("left", "handover@3:5", "completion@8:1"),
        _completed("right", "handover@4:5", "completion@8:2"),
    )
    fence = device_sync.plan_device_sync(
        tokens,
        function="submit_pair",
        queue="queue0",
        point_id="sync@10:1",
    )
    batch = device_sync.plan_synced_reacquisitions(
        tokens,
        fence,
        point_ids=("reacquire@11:1", "reacquire@11:2"),
    )
    return tokens, batch


class SotlasDeviceSyncSIRTests(unittest.TestCase):
    def test_sync_batch_lowers_completion_fence_then_reacquisition(self):
        tokens, batch = _synchronized_batch()
        sources = (
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("device_right", "Token"),
        )
        destinations = (
            sir.SIRValue("host_left", "Token"),
            sir.SIRValue("host_right", "Token"),
        )

        lowered = device_sync_sir.lower_device_sync_batch(
            batch, tokens, sources, destinations
        )
        self.assertEqual(len(lowered.instructions), 5)
        first_completion, second_completion, fence, left_reacquire, right_reacquire = (
            lowered.instructions
        )

        self.assertIsInstance(first_completion, device_sir.DeviceCompletionInst)
        self.assertIsInstance(second_completion, device_sir.DeviceCompletionInst)
        self.assertIsInstance(fence, device_sync_sir.DeviceSyncFenceInst)
        self.assertIsInstance(fence, sir.OwnershipDomainPointInst)
        self.assertIsInstance(left_reacquire, device_sir.DeviceReacquisitionInst)
        self.assertIsInstance(right_reacquire, device_sir.DeviceReacquisitionInst)

        self.assertEqual(fence.source_name, "submit_pair")
        self.assertEqual(fence.queue, "queue0")
        self.assertEqual(fence.point_id, "sync@10:1")
        self.assertEqual(
            fence.submission_point_ids,
            ("handover@3:5", "handover@4:5"),
        )
        self.assertEqual(
            fence.completion_point_ids,
            ("completion@8:1", "completion@8:2"),
        )
        self.assertEqual(first_completion.point_id, "completion@8:1")
        self.assertEqual(second_completion.point_id, "completion@8:2")
        self.assertEqual(left_reacquire.point_id, "reacquire@11:1")
        self.assertEqual(right_reacquire.point_id, "reacquire@11:2")

        rendered = "\n".join(str(inst) for inst in lowered.instructions)
        self.assertLess(rendered.index("completion@8:1"), rendered.index("sync@10:1"))
        self.assertLess(rendered.index("sync@10:1"), rendered.index("reacquire@11:1"))

    def test_sync_sir_rejects_noncompleted_or_reordered_token_set(self):
        tokens, batch = _synchronized_batch()
        sources = (
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("device_right", "Token"),
        )
        destinations = (
            sir.SIRValue("host_left", "Token"),
            sir.SIRValue("host_right", "Token"),
        )

        with self.assertRaisesRegex(
            device_sync_sir.DeviceSyncSIRLoweringError,
            "exact token identities",
        ):
            device_sync_sir.lower_device_sync_batch(
                batch, tuple(reversed(tokens)), sources, destinations
            )

        submitted = replace(
            tokens[1],
            state=device_ownership.DeviceTransferState.SUBMITTED,
        )
        with self.assertRaisesRegex(
            device_sync_sir.DeviceSyncSIRLoweringError,
            "requires COMPLETED tokens",
        ):
            device_sync_sir.lower_device_sync_batch(
                batch, (tokens[0], submitted), sources, destinations
            )

    def test_sync_sir_rejects_consumed_fence_and_type_mismatch(self):
        tokens, batch = _synchronized_batch()
        sources = (
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("device_right", "Token"),
        )
        destinations = (
            sir.SIRValue("host_left", "Token"),
            sir.SIRValue("host_right", "Token"),
        )

        consumed_fence = replace(
            batch.fence, state=device_sync.DeviceSyncState.CONSUMED
        )
        consumed_batch = replace(batch, fence=consumed_fence)
        with self.assertRaisesRegex(
            device_sync_sir.DeviceSyncSIRLoweringError,
            "requires SYNCHRONIZED",
        ):
            device_sync_sir.lower_device_sync_batch(
                consumed_batch, tokens, sources, destinations
            )

        bad_sources = (
            sir.SIRValue("device_left", "Wrong"),
            sources[1],
        )
        with self.assertRaisesRegex(
            device_sir.DeviceSIRLoweringError,
            "has type 'Wrong'",
        ):
            device_sync_sir.lower_device_sync_batch(
                batch, tokens, bad_sources, destinations
            )

    def test_llvm_remains_fail_closed_for_device_sync_fence(self):
        tokens, batch = _synchronized_batch()
        fence = device_sync_sir.lower_device_sync_fence(batch.fence)
        module = sir.SIRModule("device_sync_fail_closed")
        function = sir.SIRFunction("probe", [], "void")
        block = function.add_block("0")
        block.add(fence)
        block.add(sir.ReturnInst())
        module.add_function(function)

        with self.assertRaisesRegex(ValueError, "DeviceSyncFenceInst"):
            codegen_llvm.CodegenLLVM(module).emit()


if __name__ == "__main__":
    unittest.main()
