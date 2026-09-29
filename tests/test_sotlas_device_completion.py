"""Tests for backend-neutral DEVICE completion and reacquisition semantics."""
from dataclasses import replace
import importlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    """Load compiler/sotlas_compile without legacy tools-package hijacking."""
    name = "sotlas_device_completion_package"
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
typed_ast = importlib.import_module(f"{sotlas_compile.__name__}.typed_ast")

DeviceTransferState = device_ownership.DeviceTransferState
apply_device_reacquisition = device_ownership.apply_device_reacquisition
complete_device_transfer = device_ownership.complete_device_transfer
mark_device_reacquired = device_ownership.mark_device_reacquired
open_device_completion = device_ownership.open_device_completion
plan_device_reacquisition = device_ownership.plan_device_reacquisition
OwnershipBinding = typed_ast.OwnershipBinding
OwnershipDomain = typed_ast.OwnershipDomain
OwnershipDomainGraph = typed_ast.OwnershipDomainGraph
OwnershipDomainTransfer = typed_ast.OwnershipDomainTransfer
OwnershipDomainTransition = typed_ast.OwnershipDomainTransition
OwnershipEnv = typed_ast.OwnershipEnv
Phase1SemanticError = typed_ast.Phase1SemanticError
SemanticType = typed_ast.SemanticType
VarState = typed_ast.VarState

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


def _handover_edge(
    transition: OwnershipDomainTransition,
    *,
    destination: str = "device_buffer",
) -> OwnershipDomainTransfer:
    return OwnershipDomainTransfer(
        function=transition.function or "submit",
        binding=transition.binding,
        domain=OwnershipDomain.EXCLUSIVE,
        via="handover",
        destination=destination,
        point_id=transition.point_id,
        source_domain=OwnershipDomain.EXCLUSIVE,
        target_domain=OwnershipDomain.DEVICE,
        destination_domain=OwnershipDomain.DEVICE,
    )


def _graph(*transitions: OwnershipDomainTransition) -> OwnershipDomainGraph:
    return OwnershipDomainGraph(
        nodes=(),
        transfers=tuple(
            _handover_edge(transition, destination=f"device_buffer_{index}")
            for index, transition in enumerate(transitions)
        ),
        planned_transitions=tuple(transitions),
    )


def _lifecycle():
    submission = _submission()
    graph = OwnershipDomainGraph(
        nodes=(),
        transfers=(_handover_edge(submission),),
        planned_transitions=(submission,),
    )
    token = open_device_completion(
        graph, function="submit", binding="buffer"
    )
    completed = complete_device_transfer(token, point_id="completion@8:1")
    plan = plan_device_reacquisition(completed, point_id="reacquire@9:1")
    reacquired = mark_device_reacquired(completed, plan)
    return token, completed, plan, reacquired


class SotlasDeviceCompletionTests(unittest.TestCase):
    def test_completion_gates_device_reacquisition(self):
        token, completed, plan, reacquired = _lifecycle()
        self.assertIs(token.state, DeviceTransferState.SUBMITTED)
        self.assertEqual(token.submission_point_id, "handover@3:5")
        self.assertEqual(token.device_binding, "device_buffer")
        self.assertIs(completed.state, DeviceTransferState.COMPLETED)

        self.assertIs(plan.source, OwnershipDomain.DEVICE)
        self.assertIs(plan.target, OwnershipDomain.EXCLUSIVE)
        self.assertEqual(plan.operation, "device_reacquire")
        self.assertEqual(plan.device_binding, "device_buffer")
        self.assertEqual(plan.submission_point_id, "handover@3:5")
        self.assertEqual(plan.completion_point_id, "completion@8:1")

        self.assertIs(reacquired.state, DeviceTransferState.REACQUIRED)
        self.assertEqual(reacquired.reacquisition_point_id, "reacquire@9:1")

    def test_reacquisition_before_completion_fails_closed(self):
        token, _, _, _ = _lifecycle()
        with self.assertRaisesRegex(Phase1SemanticError, "requires COMPLETED"):
            plan_device_reacquisition(token, point_id="reacquire@9:1")

    def test_completion_requires_canonical_device_submission(self):
        with self.assertRaisesRegex(Phase1SemanticError, "no canonical submission"):
            open_device_completion(
                OwnershipDomainGraph(nodes=(), transfers=()),
                function="submit",
                binding="buffer",
            )

    def test_completion_requires_matching_canonical_handover_edge(self):
        submission = _submission()
        graph = OwnershipDomainGraph(
            nodes=(), transfers=(), planned_transitions=(submission,)
        )
        with self.assertRaisesRegex(Phase1SemanticError, "canonical handover edge"):
            open_device_completion(graph, function="submit", binding="buffer")

        wrong_edge = replace(
            _handover_edge(submission),
            destination_domain=OwnershipDomain.EXCLUSIVE,
        )
        graph = OwnershipDomainGraph(
            nodes=(), transfers=(wrong_edge,), planned_transitions=(submission,)
        )
        with self.assertRaisesRegex(Phase1SemanticError, "canonical handover edge"):
            open_device_completion(graph, function="submit", binding="buffer")

    def test_ambiguous_device_submissions_fail_closed(self):
        graph = _graph(
            _submission(point_id="handover@3:5"),
            _submission(point_id="handover@4:5"),
        )
        with self.assertRaisesRegex(Phase1SemanticError, "ambiguous"):
            open_device_completion(graph, function="submit", binding="buffer")

    def test_device_submission_requires_live_source_and_stable_point(self):
        moved = _submission(state=VarState.MOVED)
        with self.assertRaisesRegex(Phase1SemanticError, "must originate LIVE"):
            open_device_completion(
                OwnershipDomainGraph(
                    nodes=(),
                    transfers=(_handover_edge(moved),),
                    planned_transitions=(moved,),
                ),
                function="submit",
                binding="buffer",
            )
        unstamped = _submission(point_id=None)
        with self.assertRaisesRegex(Phase1SemanticError, "source-stable point"):
            open_device_completion(
                OwnershipDomainGraph(
                    nodes=(),
                    transfers=(_handover_edge(unstamped),),
                    planned_transitions=(unstamped,),
                ),
                function="submit",
                binding="buffer",
            )

    def test_completion_is_single_use_and_points_cannot_alias(self):
        token, completed, _, _ = _lifecycle()
        with self.assertRaisesRegex(Phase1SemanticError, "must be distinct"):
            complete_device_transfer(token, point_id="handover@3:5")
        with self.assertRaisesRegex(Phase1SemanticError, "requires SUBMITTED"):
            complete_device_transfer(completed, point_id="completion@8:2")
        with self.assertRaisesRegex(Phase1SemanticError, "must be distinct"):
            plan_device_reacquisition(completed, point_id="completion@8:1")

    def test_reacquisition_plan_must_match_completion_token(self):
        _, completed, plan, _ = _lifecycle()
        for mismatched in (
            replace(plan, binding="other"),
            replace(plan, device_binding="other_device"),
        ):
            with self.subTest(mismatched=mismatched):
                with self.assertRaisesRegex(Phase1SemanticError, "does not match"):
                    mark_device_reacquired(completed, mismatched)

    def test_reacquisition_rearms_moved_exclusive_owner_and_consumes_device_owner(self):
        _, _, plan, reacquired = _lifecycle()
        env = OwnershipEnv((
            OwnershipBinding(
                "device_buffer", TOKEN, VarState.LIVE, OwnershipDomain.DEVICE
            ),
            OwnershipBinding(
                "host_buffer", TOKEN, VarState.MOVED, OwnershipDomain.EXCLUSIVE
            ),
        ))
        applied = apply_device_reacquisition(
            env, reacquired, plan, destination="host_buffer"
        )
        self.assertIs(applied.state_of("device_buffer"), VarState.MOVED)
        self.assertIs(applied.domain_of("device_buffer"), OwnershipDomain.DEVICE)
        self.assertIs(applied.state_of("host_buffer"), VarState.LIVE)
        self.assertIs(applied.domain_of("host_buffer"), OwnershipDomain.EXCLUSIVE)

    def test_reacquisition_env_application_fails_closed_on_invalid_slots(self):
        _, completed, plan, reacquired = _lifecycle()
        valid = OwnershipEnv((
            OwnershipBinding(
                "device_buffer", TOKEN, VarState.LIVE, OwnershipDomain.DEVICE
            ),
            OwnershipBinding(
                "host_buffer", TOKEN, VarState.MOVED, OwnershipDomain.EXCLUSIVE
            ),
        ))
        with self.assertRaisesRegex(Phase1SemanticError, "requires REACQUIRED"):
            apply_device_reacquisition(
                valid, completed, plan, destination="host_buffer"
            )

        live_destination = OwnershipEnv((
            OwnershipBinding(
                "device_buffer", TOKEN, VarState.LIVE, OwnershipDomain.DEVICE
            ),
            OwnershipBinding(
                "host_buffer", TOKEN, VarState.LIVE, OwnershipDomain.EXCLUSIVE
            ),
        ))
        with self.assertRaisesRegex(Phase1SemanticError, "moved EXCLUSIVE"):
            apply_device_reacquisition(
                live_destination, reacquired, plan, destination="host_buffer"
            )

        moved_device = OwnershipEnv((
            OwnershipBinding(
                "device_buffer", TOKEN, VarState.MOVED, OwnershipDomain.DEVICE
            ),
            OwnershipBinding(
                "host_buffer", TOKEN, VarState.MOVED, OwnershipDomain.EXCLUSIVE
            ),
        ))
        with self.assertRaisesRegex(Phase1SemanticError, "live DEVICE"):
            apply_device_reacquisition(
                moved_device, reacquired, plan, destination="host_buffer"
            )


if __name__ == "__main__":
    unittest.main()
