"""Executable scheduler contracts for certified Flow dependency graphs."""
from __future__ import annotations

from pathlib import Path
import sys
from threading import Barrier, Event, Thread
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile import (  # noqa: E402
    FlowCancelledError,
    FlowDependency,
    FlowExecutionError,
    FlowNode,
    certify_flow_graph,
    execute_flow,
)


class SotlasFlowRuntimeTests(unittest.TestCase):
    def test_ready_nodes_run_concurrently_and_receive_only_direct_inputs(self):
        plan = certify_flow_graph(
            tuple(FlowNode(name) for name in ("left", "right", "join")),
            (
                FlowDependency("left", "join"),
                FlowDependency("right", "join"),
            ),
        )
        rendezvous = Barrier(2)

        def make_source(value):
            def run(inputs):
                self.assertEqual(dict(inputs), {})
                rendezvous.wait(timeout=2)
                return value
            return run

        def join(inputs):
            self.assertEqual(tuple(inputs), ("left", "right"))
            with self.assertRaises(TypeError):
                inputs["extra"] = 3
            return inputs["left"] + inputs["right"]

        result = execute_flow(
            plan,
            {"left": make_source(20), "right": make_source(22), "join": join},
            max_workers=2,
        )
        self.assertEqual(tuple(result.outputs), ("left", "right", "join"))
        self.assertEqual(result.output("join"), 42)
        with self.assertRaises(TypeError):
            result.outputs["left"] = 0

    def test_failed_stage_joins_peers_and_never_starts_downstream(self):
        plan = certify_flow_graph(
            tuple(FlowNode(name) for name in ("bad", "peer", "next")),
            (
                FlowDependency("bad", "next"),
                FlowDependency("peer", "next"),
            ),
        )
        peer_finished = Event()
        downstream_started = Event()

        def bad(_inputs):
            time.sleep(0.02)
            raise ValueError("broken stage")

        def peer(_inputs):
            time.sleep(0.04)
            peer_finished.set()
            return 1

        def next_action(_inputs):
            downstream_started.set()
            return None

        with self.assertRaises(FlowExecutionError) as caught:
            execute_flow(
                plan,
                {"bad": bad, "peer": peer, "next": next_action},
                max_workers=2,
            )
        self.assertEqual(caught.exception.node, "bad")
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertTrue(peer_finished.is_set())
        self.assertFalse(downstream_started.is_set())

    def test_pre_cancelled_flow_does_not_start_a_task(self):
        plan = certify_flow_graph((FlowNode("work"),), ())
        cancelled = Event()
        cancelled.set()
        started = Event()
        with self.assertRaises(FlowCancelledError):
            execute_flow(
                plan,
                {"work": lambda _inputs: started.set()},
                cancel_event=cancelled,
            )
        self.assertFalse(started.is_set())

    def test_cancellation_during_final_stage_joins_running_action(self):
        plan = certify_flow_graph((FlowNode("work"),), ())
        cancelled = Event()
        started = Event()
        finished = Event()

        def action(_inputs):
            started.set()
            time.sleep(0.05)
            finished.set()

        canceller = Thread(target=lambda: (started.wait(1), cancelled.set()))
        canceller.start()
        with self.assertRaises(FlowCancelledError):
            execute_flow(plan, {"work": action}, cancel_event=cancelled)
        canceller.join(timeout=1)
        self.assertFalse(canceller.is_alive())
        self.assertTrue(finished.is_set())

    def test_cooperative_action_receives_cancel_signal_and_stops(self):
        plan = certify_flow_graph((FlowNode("work"),), ())
        cancelled = Event()
        started = Event()
        finished = Event()

        def action(_inputs, token):
            started.set()
            self.assertTrue(token.wait(1))
            finished.set()

        canceller = Thread(target=lambda: (started.wait(1), cancelled.set()))
        canceller.start()
        with self.assertRaises(FlowCancelledError):
            execute_flow(
                plan,
                {"work": action},
                cancel_event=cancelled,
                cooperative=True,
            )
        canceller.join(timeout=1)
        self.assertFalse(canceller.is_alive())
        self.assertTrue(finished.is_set())

    def test_cooperative_peer_stops_after_stage_failure(self):
        plan = certify_flow_graph(
            (FlowNode("bad"), FlowNode("peer")), ()
        )
        rendezvous = Barrier(2)
        peer_stopped = Event()

        def bad(_inputs, _token):
            rendezvous.wait(timeout=1)
            raise ValueError("broken stage")

        def peer(_inputs, token):
            rendezvous.wait(timeout=1)
            self.assertTrue(token.wait(1))
            peer_stopped.set()

        with self.assertRaises(FlowExecutionError) as caught:
            execute_flow(
                plan,
                {"bad": bad, "peer": peer},
                max_workers=2,
                cooperative=True,
            )
        self.assertEqual(caught.exception.node, "bad")
        self.assertTrue(peer_stopped.is_set())

    def test_multiple_task_failures_report_first_declared_node(self):
        plan = certify_flow_graph(
            (FlowNode("earlier"), FlowNode("later")), ()
        )
        rendezvous = Barrier(2)

        def fail(name, delay):
            def run(_inputs):
                rendezvous.wait(timeout=2)
                time.sleep(delay)
                raise ValueError(name)
            return run

        with self.assertRaises(FlowExecutionError) as caught:
            execute_flow(
                plan,
                {"earlier": fail("earlier", 0.04),
                 "later": fail("later", 0.005)},
                max_workers=2,
            )
        self.assertEqual(caught.exception.node, "earlier")

    def test_action_set_and_forged_schedule_are_rejected(self):
        plan = certify_flow_graph(
            (FlowNode("first"), FlowNode("second")),
            (FlowDependency("first", "second"),),
        )
        with self.assertRaisesRegex(ValueError, "missing="):
            execute_flow(plan, {"first": lambda _inputs: None})
        forged = type(plan)(plan.nodes, plan.dependencies, (("second",), ("first",)))
        with self.assertRaisesRegex(ValueError, "canonical stage order"):
            execute_flow(
                forged,
                {"first": lambda _inputs: None, "second": lambda _inputs: None},
            )


if __name__ == "__main__":
    unittest.main()
