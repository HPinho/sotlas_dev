"""Tests for backend-neutral DEVICE synchronization fences."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_device_sync_package"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        PACKAGE_DIR / "__init__.py",
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sotlas_compile = _load_canonical_package()
device_ownership = importlib.import_module(
    f"{sotlas_compile.__name__}.device_ownership"
)
device_sync = importlib.import_module(f"{sotlas_compile.__name__}.device_sync")
typed_ast = importlib.import_module(f"{sotlas_compile.__name__}.typed_ast")

DeviceTransferState = device_ownership.DeviceTransferState
complete_device_transfer = device_ownership.complete_device_transfer
open_device_completion = device_ownership.open_device_completion
OwnershipDomain = typed_ast.OwnershipDomain
OwnershipDomainGraph = typed_ast.OwnershipDomainGraph
OwnershipDomainTransition = typed_ast.OwnershipDomainTransition
Phase1SemanticError = typed_ast.Phase1SemanticError
SemanticType = typed_ast.SemanticType
VarState = typed_ast.VarState
DeviceSyncState = device_sync.DeviceSyncState
consume_device_sync = device_sync.consume_device_sync
plan_device_sync = device_sync.plan_device_sync
plan_synced_reacquisitions = device_sync.plan_synced_reacquisitions

TOKEN = SemanticType("Token")


def _submission(binding: str, point_id: str) -> OwnershipDomainTransition:
    return OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=OwnershipDomain.EXCLUSIVE,
        target=OwnershipDomain.DEVICE,
        source_state=VarState.LIVE,
        operation="handover",
        function="submit_pair",
        point_id=point_id,
    )


def _completed(binding: str, submit: str, complete: str):
    graph = OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=(_submission(binding, submit),),
    )
    token = open_device_completion(
        graph, function="submit_pair", binding=binding
    )
    return complete_device_transfer(token, point_id=complete)


class SotlasDeviceSyncTests(unittest.TestCase):
    def completed_pair(self):
        return (
            _completed("left", "handover@3:5", "completion@8:1"),
            _completed("right", "handover@4:5", "completion@8:2"),
        )

    def test_fence_requires_all_tokens_completed(self):
        left, right = self.completed_pair()
        submitted = replace(right, state=DeviceTransferState.SUBMITTED,
                            completion_point_id=None)
        with self.assertRaisesRegex(Phase1SemanticError, "requires COMPLETED"):
            plan_device_sync(
                (left, submitted),
                function="submit_pair",
                queue="queue0",
                point_id="sync@10:1",
            )

    def test_fence_covers_exact_completed_submission_set(self):
        tokens = self.completed_pair()
        fence = plan_device_sync(
            tokens,
            function="submit_pair",
            queue="queue0",
            point_id="sync@10:1",
        )
        self.assertIs(fence.state, DeviceSyncState.SYNCHRONIZED)
        self.assertEqual(
            fence.submission_point_ids,
            ("handover@3:5", "handover@4:5"),
        )
        self.assertEqual(
            fence.completion_point_ids,
            ("completion@8:1", "completion@8:2"),
        )

    def test_sync_rejects_duplicate_submission_identity(self):
        left, right = self.completed_pair()
        duplicate = replace(
            right,
            submission_point_id=left.submission_point_id,
        )
        with self.assertRaisesRegex(Phase1SemanticError, "duplicate submission"):
            plan_device_sync(
                (left, duplicate),
                function="submit_pair",
                queue="queue0",
                point_id="sync@10:1",
            )

    def test_sync_point_cannot_alias_submit_or_completion(self):
        tokens = self.completed_pair()
        for point in ("handover@3:5", "completion@8:2"):
            with self.subTest(point=point):
                with self.assertRaisesRegex(Phase1SemanticError, "must be distinct"):
                    plan_device_sync(
                        tokens,
                        function="submit_pair",
                        queue="queue0",
                        point_id=point,
                    )

    def test_batch_reacquisition_requires_exact_fence_coverage(self):
        tokens = self.completed_pair()
        fence = plan_device_sync(
            tokens,
            function="submit_pair",
            queue="queue0",
            point_id="sync@10:1",
        )
        with self.assertRaisesRegex(Phase1SemanticError, "exact token set"):
            plan_synced_reacquisitions(
                tuple(reversed(tokens)),
                fence,
                point_ids=("reacquire@11:1", "reacquire@11:2"),
            )

    def test_batch_reacquisition_is_one_point_per_token(self):
        tokens = self.completed_pair()
        fence = plan_device_sync(
            tokens,
            function="submit_pair",
            queue="queue0",
            point_id="sync@10:1",
        )
        with self.assertRaisesRegex(Phase1SemanticError, "one point per token"):
            plan_synced_reacquisitions(
                tokens,
                fence,
                point_ids=("reacquire@11:1",),
            )
        with self.assertRaisesRegex(Phase1SemanticError, "must be unique"):
            plan_synced_reacquisitions(
                tokens,
                fence,
                point_ids=("reacquire@11:1", "reacquire@11:1"),
            )

    def test_synchronized_batch_consumes_fence_and_reacquires_all(self):
        tokens = self.completed_pair()
        fence = plan_device_sync(
            tokens,
            function="submit_pair",
            queue="queue0",
            point_id="sync@10:1",
        )
        batch = plan_synced_reacquisitions(
            tokens,
            fence,
            point_ids=("reacquire@11:1", "reacquire@11:2"),
        )
        result = consume_device_sync(tokens, batch)
        self.assertIs(result.fence.state, DeviceSyncState.CONSUMED)
        self.assertTrue(
            all(token.state is DeviceTransferState.REACQUIRED for token in result.tokens)
        )
        self.assertEqual(
            tuple(token.reacquisition_point_id for token in result.tokens),
            ("reacquire@11:1", "reacquire@11:2"),
        )


if __name__ == "__main__":
    unittest.main()
