"""Tests for backend-neutral DEVICE completion and reacquisition semantics."""
from dataclasses import replace
import unittest

from sotlas_compile.device_ownership import (
    DeviceTransferState,
    complete_device_transfer,
    mark_device_reacquired,
    open_device_completion,
    plan_device_reacquisition,
)
from sotlas_compile.typed_ast import (
    OwnershipDomain,
    OwnershipDomainGraph,
    OwnershipDomainTransition,
    Phase1SemanticError,
    SemanticType,
    VarState,
)


TOKEN = SemanticType("Token")


def _submission(
    *,
    function: str = "submit",
    binding: str = "buffer",
    point_id: str | None = "handover@3:5",
    state: VarState = VarState.LIVE,
) -> OwnershipDomainTransition:
    return OwnershipDomainTransition(
        binding=binding,
        type=TOKEN,
        source=OwnershipDomain.EXCLUSIVE,
        target=OwnershipDomain.DEVICE,
        source_state=state,
        operation="handover",
        function=function,
        point_id=point_id,
    )


def _graph(*transitions: OwnershipDomainTransition) -> OwnershipDomainGraph:
    return OwnershipDomainGraph(
        nodes=(),
        transfers=(),
        planned_transitions=tuple(transitions),
    )


class SotlasDeviceCompletionTests(unittest.TestCase):
    def test_completion_gates_device_reacquisition(self):
        token = open_device_completion(
            _graph(_submission()), function="submit", binding="buffer"
        )
        self.assertIs(token.state, DeviceTransferState.SUBMITTED)
        self.assertEqual(token.submission_point_id, "handover@3:5")

        completed = complete_device_transfer(
            token, point_id="completion@8:1"
        )
        self.assertIs(completed.state, DeviceTransferState.COMPLETED)

        plan = plan_device_reacquisition(
            completed, point_id="reacquire@9:1"
        )
        self.assertIs(plan.source, OwnershipDomain.DEVICE)
        self.assertIs(plan.target, OwnershipDomain.EXCLUSIVE)
        self.assertEqual(plan.operation, "device_reacquire")
        self.assertEqual(plan.submission_point_id, "handover@3:5")
        self.assertEqual(plan.completion_point_id, "completion@8:1")

        reacquired = mark_device_reacquired(completed, plan)
        self.assertIs(reacquired.state, DeviceTransferState.REACQUIRED)
        self.assertEqual(reacquired.reacquisition_point_id, "reacquire@9:1")

    def test_reacquisition_before_completion_fails_closed(self):
        token = open_device_completion(
            _graph(_submission()), function="submit", binding="buffer"
        )
        with self.assertRaisesRegex(Phase1SemanticError, "requires COMPLETED"):
            plan_device_reacquisition(token, point_id="reacquire@9:1")

    def test_completion_requires_canonical_device_submission(self):
        with self.assertRaisesRegex(Phase1SemanticError, "no canonical submission"):
            open_device_completion(_graph(), function="submit", binding="buffer")

    def test_ambiguous_device_submissions_fail_closed(self):
        graph = _graph(
            _submission(point_id="handover@3:5"),
            _submission(point_id="handover@4:5"),
        )
        with self.assertRaisesRegex(Phase1SemanticError, "ambiguous"):
            open_device_completion(graph, function="submit", binding="buffer")

    def test_device_submission_requires_live_source_and_stable_point(self):
        with self.assertRaisesRegex(Phase1SemanticError, "must originate LIVE"):
            open_device_completion(
                _graph(_submission(state=VarState.MOVED)),
                function="submit",
                binding="buffer",
            )
        with self.assertRaisesRegex(Phase1SemanticError, "source-stable point"):
            open_device_completion(
                _graph(_submission(point_id=None)),
                function="submit",
                binding="buffer",
            )

    def test_completion_is_single_use_and_points_cannot_alias(self):
        token = open_device_completion(
            _graph(_submission()), function="submit", binding="buffer"
        )
        with self.assertRaisesRegex(Phase1SemanticError, "must be distinct"):
            complete_device_transfer(token, point_id="handover@3:5")

        completed = complete_device_transfer(token, point_id="completion@8:1")
        with self.assertRaisesRegex(Phase1SemanticError, "requires SUBMITTED"):
            complete_device_transfer(completed, point_id="completion@8:2")
        with self.assertRaisesRegex(Phase1SemanticError, "must be distinct"):
            plan_device_reacquisition(completed, point_id="completion@8:1")

    def test_reacquisition_plan_must_match_completion_token(self):
        token = open_device_completion(
            _graph(_submission()), function="submit", binding="buffer"
        )
        completed = complete_device_transfer(token, point_id="completion@8:1")
        plan = plan_device_reacquisition(
            completed, point_id="reacquire@9:1"
        )
        mismatched = replace(plan, binding="other")
        with self.assertRaisesRegex(Phase1SemanticError, "does not match"):
            mark_device_reacquired(completed, mismatched)


if __name__ == "__main__":
    unittest.main()
