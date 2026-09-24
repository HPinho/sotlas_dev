"""Tests for backend-neutral REGION lifetime topology."""
from pathlib import Path
import importlib.util
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_lifetime_package"
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


package = _load_package()
typed_ast = __import__(f"{package.__name__}.typed_ast", fromlist=["*"])
region_lifetime = __import__(f"{package.__name__}.region_lifetime", fromlist=["*"])

Domain = typed_ast.OwnershipDomain
State = typed_ast.VarState
Graph = typed_ast.OwnershipDomainGraph
Node = typed_ast.OwnershipDomainNode
Transfer = typed_ast.OwnershipDomainTransfer
Whisper = typed_ast.OwnershipWhisperBorrow
Direct = typed_ast.OwnershipDirectAccess
RegionLifetimeError = region_lifetime.RegionLifetimeError
build_plan = region_lifetime.build_region_lifetime_plan

TYPE = SimpleNamespace(name="Token")
OTHER_TYPE = SimpleNamespace(name="Other")


def _node(binding: str, *, domain=Domain.REGION, type_info=TYPE, state=State.LIVE):
    return Node("run", binding, type_info, domain, state)


def _handover(
    source: str = "left",
    destination: str | None = "right",
    *,
    point: str = "handover@10:5",
    source_domain=Domain.REGION,
    target_domain=Domain.REGION,
    destination_domain=Domain.REGION,
):
    return Transfer(
        function="run",
        binding=source,
        domain=Domain.REGION,
        via="handover",
        destination=destination,
        point_id=point,
        source_domain=source_domain,
        target_domain=target_domain,
        destination_domain=destination_domain,
    )


def _whisper(source: str = "left", point: str = "whisper@8:5"):
    return Whisper(
        "run", "observe", "token", source, TYPE, Domain.REGION, point
    )


def _direct(source: str = "right", point: str = "direct@12:5"):
    return Direct(
        "run", "inspect", "token", source, TYPE, Domain.REGION, point
    )


def _graph(*, nodes=None, transfers=(), whispers=(), directs=()):
    return Graph(
        nodes=tuple(nodes if nodes is not None else (_node("left"), _node("right"))),
        transfers=tuple(transfers),
        whisper_borrows=tuple(whispers),
        direct_accesses=tuple(directs),
    )


class SotlasRegionLifetimeTests(unittest.TestCase):
    def test_plan_collects_region_owners_transfer_and_call_scoped_borrows(self):
        graph = _graph(
            transfers=(_handover(),),
            whispers=(_whisper(),),
            directs=(_direct(),),
        )
        plan = build_plan(graph, function="run")

        self.assertEqual(plan.bindings, ("left", "right"))
        self.assertEqual(len(plan.transfers), 1)
        self.assertEqual(plan.transfers[0].source, "left")
        self.assertEqual(plan.transfers[0].destination, "right")
        self.assertFalse(plan.transfers[0].terminal)
        self.assertEqual(
            tuple((item.source, item.mode, item.scope) for item in plan.borrows),
            (("left", "whisper", "call"), ("right", "direct", "call")),
        )
        self.assertEqual(
            plan.point_ids,
            ("handover@10:5", "whisper@8:5", "direct@12:5"),
        )

    def test_terminal_region_move_is_preserved_without_inventing_destination(self):
        terminal = Transfer(
            function="run",
            binding="left",
            domain=Domain.REGION,
            via="return",
            destination=None,
            point_id="return@20:5",
            source_domain=Domain.REGION,
            target_domain=Domain.REGION,
            destination_domain=None,
        )
        plan = build_plan(_graph(transfers=(terminal,)), function="run")
        self.assertTrue(plan.transfers[0].terminal)
        self.assertIsNone(plan.transfers[0].destination)

    def test_region_handover_requires_explicit_region_destination(self):
        with self.assertRaisesRegex(RegionLifetimeError, "explicit destination"):
            build_plan(_graph(transfers=(_handover(destination=None),)), function="run")

    def test_region_transfer_rejects_cross_domain_drift(self):
        broken = _handover(
            target_domain=Domain.DEVICE,
            destination_domain=Domain.DEVICE,
        )
        with self.assertRaisesRegex(RegionLifetimeError, "non-region target domain"):
            build_plan(_graph(transfers=(broken,)), function="run")

    def test_region_transfer_rejects_destination_type_drift(self):
        nodes = (_node("left"), _node("right", type_info=OTHER_TYPE))
        with self.assertRaisesRegex(RegionLifetimeError, "types diverged"):
            build_plan(
                _graph(nodes=nodes, transfers=(_handover(),)),
                function="run",
            )

    def test_region_borrow_requires_matching_region_owner_node(self):
        nodes = (_node("left", domain=Domain.EXCLUSIVE), _node("right"))
        with self.assertRaisesRegex(RegionLifetimeError, "no REGION owner node"):
            build_plan(
                _graph(nodes=nodes, whispers=(_whisper(),)),
                function="run",
            )

    def test_region_lifetime_points_are_globally_unique(self):
        with self.assertRaisesRegex(RegionLifetimeError, "duplicate REGION lifetime point"):
            build_plan(
                _graph(
                    transfers=(_handover(point="point@1:1"),),
                    whispers=(_whisper(point="point@1:1"),),
                ),
                function="run",
            )

    def test_plan_is_function_scoped(self):
        other = Node("other", "outside", TYPE, Domain.REGION, State.LIVE)
        graph = Graph(
            nodes=(_node("left"), other),
            transfers=(),
        )
        plan = build_plan(graph, function="run")
        self.assertEqual(plan.bindings, ("left",))
        self.assertEqual(plan.transfers, ())
        self.assertEqual(plan.borrows, ())

    def test_noncanonical_graph_is_rejected(self):
        with self.assertRaisesRegex(RegionLifetimeError, "canonical OwnershipDomainGraph"):
            build_plan(object(), function="run")


if __name__ == "__main__":
    unittest.main()
