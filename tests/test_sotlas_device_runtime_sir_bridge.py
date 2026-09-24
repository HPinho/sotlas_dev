"""Tests for the fail-closed DEVICE runtime-requirement/SIR bridge."""
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
    name = "sotlas_device_runtime_sir_bridge_compile_package"
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
    name = "sotlas_device_runtime_sir_bridge_backend_package"
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
device_runtime_abi = importlib.import_module(
    f"{compile_package.__name__}.device_runtime_abi"
)
typed_ast = importlib.import_module(f"{compile_package.__name__}.typed_ast")
backend_package = _load_sotlas_backend_package()
sir = importlib.import_module(f"{backend_package.__name__}.sir")
device_sync_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_sync"
)
device_runtime_sir = importlib.import_module(
    f"{backend_package.__name__}.sir.device_runtime"
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


def _plans():
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
    runtime_plan = device_runtime_abi.plan_device_runtime_requirements(tokens, batch)
    sir_plan = device_sync_sir.lower_device_sync_batch(
        batch,
        tokens,
        (
            sir.SIRValue("device_left", "Token"),
            sir.SIRValue("device_right", "Token"),
        ),
        (
            sir.SIRValue("host_left", "Token"),
            sir.SIRValue("host_right", "Token"),
        ),
    )
    return runtime_plan, sir_plan


class SotlasDeviceRuntimeSIRBridgeTests(unittest.TestCase):
    def test_bridge_freezes_exact_runtime_and_sir_lifecycle_identity(self):
        runtime_plan, sir_plan = _plans()
        bridge = device_runtime_sir.validate_device_runtime_sir_plan(
            sir_plan, runtime_plan
        )

        self.assertEqual(bridge.function, "submit_pair")
        self.assertEqual(bridge.queue, "queue0")
        self.assertEqual(
            bridge.runtime_point_ids,
            (
                "handover@3:5",
                "handover@4:5",
                "completion@8:1",
                "completion@8:2",
                "sync@10:1",
                "reacquire@11:1",
                "reacquire@11:2",
            ),
        )
        self.assertEqual(
            bridge.sir_point_ids,
            (
                "completion@8:1",
                "completion@8:2",
                "sync@10:1",
                "reacquire@11:1",
                "reacquire@11:2",
            ),
        )
        self.assertEqual(
            bridge.submission_point_ids,
            ("handover@3:5", "handover@4:5"),
        )
        self.assertEqual(
            bridge.completion_point_ids,
            ("completion@8:1", "completion@8:2"),
        )
        self.assertEqual(bridge.synchronization_point_id, "sync@10:1")
        self.assertEqual(
            bridge.reacquisition_point_ids,
            ("reacquire@11:1", "reacquire@11:2"),
        )

    def test_bridge_rejects_reordered_sir_even_when_instruction_types_match(self):
        runtime_plan, sir_plan = _plans()
        instructions = sir_plan.instructions
        reordered = replace(
            sir_plan,
            instructions=(
                instructions[1],
                instructions[0],
                instructions[2],
                instructions[3],
                instructions[4],
            ),
        )
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "point order diverges",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                reordered, runtime_plan
            )

    def test_bridge_rejects_runtime_dependency_drift(self):
        runtime_plan, sir_plan = _plans()
        requirements = list(runtime_plan.requirements)
        requirements[2] = replace(
            requirements[2], depends_on=("handover@4:5",)
        )
        drifted = replace(runtime_plan, requirements=tuple(requirements))

        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "completion dependency diverges",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                sir_plan, drifted
            )

    def test_bridge_rejects_sir_fence_function_queue_or_coverage_drift(self):
        runtime_plan, sir_plan = _plans()
        instructions = sir_plan.instructions
        fence = instructions[2]

        wrong_queue = replace(fence, queue="queue1")
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "crosses queue identity",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(
                    sir_plan,
                    instructions=(
                        instructions[0], instructions[1], wrong_queue,
                        instructions[3], instructions[4],
                    ),
                ),
                runtime_plan,
            )

        wrong_function = replace(fence, source_name="other")
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "crosses function identity",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(
                    sir_plan,
                    instructions=(
                        instructions[0], instructions[1], wrong_function,
                        instructions[3], instructions[4],
                    ),
                ),
                runtime_plan,
            )

        wrong_coverage = replace(
            fence,
            submission_point_ids=("handover@4:5", "handover@3:5"),
        )
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "lost exact submission coverage",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(
                    sir_plan,
                    instructions=(
                        instructions[0], instructions[1], wrong_coverage,
                        instructions[3], instructions[4],
                    ),
                ),
                runtime_plan,
            )

    def test_bridge_rejects_lost_submission_or_completion_identity(self):
        runtime_plan, sir_plan = _plans()
        instructions = sir_plan.instructions

        lost_submit = replace(
            instructions[0], submission_point_id="handover@other"
        )
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "completion lost its submission identity",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(
                    sir_plan,
                    instructions=(
                        lost_submit, instructions[1], instructions[2],
                        instructions[3], instructions[4],
                    ),
                ),
                runtime_plan,
            )

        lost_completion = replace(
            instructions[3], completion_point_id="completion@other"
        )
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "reacquisition lost its completion identity",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(
                    sir_plan,
                    instructions=(
                        instructions[0], instructions[1], instructions[2],
                        lost_completion, instructions[4],
                    ),
                ),
                runtime_plan,
            )

    def test_bridge_rejects_missing_extra_or_wrong_domain_sir_facts(self):
        runtime_plan, sir_plan = _plans()
        instructions = sir_plan.instructions

        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "exact completion/fence/reacquisition set",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(sir_plan, instructions=instructions[:-1]),
                runtime_plan,
            )

        wrong_domain = replace(instructions[3], target_domain="shared")
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "must remain DEVICE -> EXCLUSIVE",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                replace(
                    sir_plan,
                    instructions=(
                        instructions[0], instructions[1], instructions[2],
                        wrong_domain, instructions[4],
                    ),
                ),
                runtime_plan,
            )

    def test_bridge_revalidates_runtime_plan_instead_of_trusting_planner(self):
        runtime_plan, sir_plan = _plans()
        requirements = list(runtime_plan.requirements)
        requirements[0] = replace(
            requirements[0],
            point_id=requirements[1].point_id,
        )
        duplicate_points = replace(
            runtime_plan, requirements=tuple(requirements)
        )
        with self.assertRaisesRegex(
            device_runtime_sir.DeviceRuntimeSIRBridgeError,
            "globally unique runtime point ids",
        ):
            device_runtime_sir.validate_device_runtime_sir_plan(
                sir_plan, duplicate_points
            )


if __name__ == "__main__":
    unittest.main()
