"""Tests for backend-neutral DEVICE runtime ABI requirements."""
from dataclasses import replace
from pathlib import Path
import importlib
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    name = "sotlas_device_runtime_abi_package"
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
device_runtime_abi = importlib.import_module(
    f"{sotlas_compile.__name__}.device_runtime_abi"
)
typed_ast = importlib.import_module(f"{sotlas_compile.__name__}.typed_ast")

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


def _batch():
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


def _valid_abi():
    operation = device_runtime_abi.DeviceRuntimeOperation
    symbol = device_runtime_abi.DeviceRuntimeABISymbol
    return device_runtime_abi.DeviceRuntimeABIContract(
        name="sotlas-device-test",
        version=1,
        symbols=(
            symbol(operation.SUBMIT, "sotlas_device_submit_v1"),
            symbol(operation.COMPLETE, "sotlas_device_complete_v1"),
            symbol(operation.SYNCHRONIZE, "sotlas_device_sync_v1"),
            symbol(operation.REACQUIRE, "sotlas_device_reacquire_v1"),
        ),
    )


class SotlasDeviceRuntimeABITests(unittest.TestCase):
    def test_runtime_requirement_dag_preserves_full_device_lifecycle(self):
        tokens, batch = _batch()
        plan = device_runtime_abi.plan_device_runtime_requirements(tokens, batch)
        operation = device_runtime_abi.DeviceRuntimeOperation

        self.assertEqual(plan.function, "submit_pair")
        self.assertEqual(plan.queue, "queue0")
        self.assertEqual(len(plan.requirements), 7)
        self.assertEqual(len(plan.requirements_for(operation.SUBMIT)), 2)
        self.assertEqual(len(plan.requirements_for(operation.COMPLETE)), 2)
        self.assertEqual(len(plan.requirements_for(operation.SYNCHRONIZE)), 1)
        self.assertEqual(len(plan.requirements_for(operation.REACQUIRE)), 2)

        submits = plan.requirements_for(operation.SUBMIT)
        completes = plan.requirements_for(operation.COMPLETE)
        sync = plan.requirements_for(operation.SYNCHRONIZE)[0]
        reacquires = plan.requirements_for(operation.REACQUIRE)

        self.assertEqual(
            tuple(item.point_id for item in submits),
            ("handover@3:5", "handover@4:5"),
        )
        self.assertEqual(completes[0].depends_on, ("handover@3:5",))
        self.assertEqual(completes[1].depends_on, ("handover@4:5",))
        self.assertEqual(
            sync.depends_on,
            ("completion@8:1", "completion@8:2"),
        )
        self.assertEqual(sync.point_id, "sync@10:1")
        self.assertEqual(reacquires[0].depends_on, ("sync@10:1",))
        self.assertEqual(reacquires[1].depends_on, ("sync@10:1",))
        self.assertEqual(
            tuple(item.point_id for item in reacquires),
            ("reacquire@11:1", "reacquire@11:2"),
        )

        # Planning ABI requirements is proof-only and must not consume semantics.
        self.assertTrue(
            all(
                token.state is device_ownership.DeviceTransferState.COMPLETED
                for token in tokens
            )
        )
        self.assertIs(batch.fence.state, device_sync.DeviceSyncState.SYNCHRONIZED)

    def test_runtime_requirements_reject_noncompleted_or_consumed_semantics(self):
        tokens, batch = _batch()
        submitted = replace(
            tokens[1], state=device_ownership.DeviceTransferState.SUBMITTED
        )
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "requires COMPLETED token",
        ):
            device_runtime_abi.plan_device_runtime_requirements(
                (tokens[0], submitted), batch
            )

        consumed = replace(
            batch,
            fence=replace(
                batch.fence, state=device_sync.DeviceSyncState.CONSUMED
            ),
        )
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "SYNCHRONIZED fence",
        ):
            device_runtime_abi.plan_device_runtime_requirements(tokens, consumed)

    def test_runtime_requirements_reject_identity_drift(self):
        tokens, batch = _batch()
        drifted = replace(tokens[1], completion_point_id="completion@other")
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "completion identity diverges",
        ):
            device_runtime_abi.plan_device_runtime_requirements(
                (tokens[0], drifted), batch
            )

        wrong_plan = replace(batch.plans[1], binding="other")
        wrong_batch = replace(batch, plans=(batch.plans[0], wrong_plan))
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "binding differ",
        ):
            device_runtime_abi.plan_device_runtime_requirements(tokens, wrong_batch)

    def test_valid_runtime_abi_binds_every_requirement_without_execution(self):
        tokens, batch = _batch()
        plan = device_runtime_abi.plan_device_runtime_requirements(tokens, batch)
        bound = device_runtime_abi.bind_device_runtime_abi(plan, _valid_abi())

        self.assertEqual(bound.abi_name, "sotlas-device-test")
        self.assertEqual(bound.abi_version, 1)
        self.assertEqual(bound.function, "submit_pair")
        self.assertEqual(bound.queue, "queue0")
        self.assertEqual(len(bound.requirements), 7)
        expected = {
            device_runtime_abi.DeviceRuntimeOperation.SUBMIT:
                "sotlas_device_submit_v1",
            device_runtime_abi.DeviceRuntimeOperation.COMPLETE:
                "sotlas_device_complete_v1",
            device_runtime_abi.DeviceRuntimeOperation.SYNCHRONIZE:
                "sotlas_device_sync_v1",
            device_runtime_abi.DeviceRuntimeOperation.REACQUIRE:
                "sotlas_device_reacquire_v1",
        }
        for item in bound.requirements:
            self.assertEqual(item.symbol, expected[item.requirement.operation])

    def test_runtime_abi_missing_operation_fails_closed(self):
        tokens, batch = _batch()
        plan = device_runtime_abi.plan_device_runtime_requirements(tokens, batch)
        contract = _valid_abi()
        without_sync = replace(
            contract,
            symbols=tuple(
                entry
                for entry in contract.symbols
                if entry.operation
                is not device_runtime_abi.DeviceRuntimeOperation.SYNCHRONIZE
            ),
        )
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "missing required operations: synchronize",
        ):
            device_runtime_abi.bind_device_runtime_abi(plan, without_sync)

    def test_runtime_abi_rejects_duplicate_operations_symbols_and_bad_version(self):
        tokens, batch = _batch()
        plan = device_runtime_abi.plan_device_runtime_requirements(tokens, batch)
        contract = _valid_abi()
        symbol = device_runtime_abi.DeviceRuntimeABISymbol
        operation = device_runtime_abi.DeviceRuntimeOperation

        duplicate_operation = replace(
            contract,
            symbols=contract.symbols
            + (symbol(operation.SUBMIT, "sotlas_device_submit_v2"),),
        )
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "submit more than once",
        ):
            device_runtime_abi.bind_device_runtime_abi(plan, duplicate_operation)

        duplicate_symbol = replace(
            contract,
            symbols=(
                symbol(operation.SUBMIT, "same_symbol"),
                symbol(operation.COMPLETE, "same_symbol"),
                symbol(operation.SYNCHRONIZE, "sync_symbol"),
                symbol(operation.REACQUIRE, "reacquire_symbol"),
            ),
        )
        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "symbols must be unique",
        ):
            device_runtime_abi.bind_device_runtime_abi(plan, duplicate_symbol)

        with self.assertRaisesRegex(
            device_runtime_abi.DeviceRuntimeABIError,
            "version must be positive",
        ):
            device_runtime_abi.bind_device_runtime_abi(
                plan, replace(contract, version=0)
            )


if __name__ == "__main__":
    unittest.main()
