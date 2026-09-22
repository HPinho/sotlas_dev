"""Testes unitários para o Sotlas Intermediate Representation (SIR)."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.sir import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst, BranchInst, CondBranchInst,
    OwnershipDomainPointInst, OwnershipDomainTransferInst,
    OwnershipDomainSIRPlan, place_ownership_domain_transfers,
    OwnershipFunctionSIRPlan, OwnershipModuleSIRPlan,
    apply_ownership_module_domain_transfers, apply_ownership_module_plan,
    SharedOwnershipSIRPlan,
    ShareInst, RetainInst, ReleaseInst, DestroyInst, DeferUseInst,
    lower_ownership_domain_trace,
    lower_ownership_module_analysis,
    lower_shared_ownership_trace, place_shared_return_cleanup,
    place_shared_loop_control_cleanup, place_shared_loop_backedge_cleanup,
    apply_shared_ownership_trace,
    SIRGenerator, SIRPassManager, DefiniteInitializationPass,
    SystemCapabilitySafetyPass, DeadCodeEliminationPass
)
from sotlas.lexer import Lexer
from sotlas.parser import Parser


class SotlasSIRTests(unittest.TestCase):
    def test_sir_instruction_string_representation(self):
        v0 = SIRValue("v0", "i32")
        v1 = SIRValue("v1", "i32")
        alloc = AllocStackInst("count", "i32", v0)
        store = StoreInst(v0, v1)
        load = LoadInst(v0, v1)
        call = CallInst("display_init", [v0], is_system=True)
        ret = ReturnInst(v1)

        self.assertIn("alloc_stack i32 // count", str(alloc))
        self.assertIn("store %v1: i32 to %v0: i32", str(store))
        self.assertIn("%v1: i32 = load %v0: i32", str(load))
        self.assertIn("@system call @display_init", str(call))
        self.assertIn("return %v1: i32", str(ret))

    def test_shared_ownership_sir_instruction_strings(self):
        value = SIRValue("token", "Token")
        self.assertIn("share_value", str(ShareInst(value)))
        self.assertIn("retain_value", str(RetainInst(value)))
        self.assertIn("release_value", str(ReleaseInst(value)))
        self.assertIn("destroy_value", str(DestroyInst(value)))
        self.assertIn(
            "defer@7:9",
            str(DeferUseInst(value, "defer@7:9")),
        )

    def test_ownership_domain_transfer_instruction_string(self):
        source = SIRValue("token", "Token")
        destination = SIRValue("peer", "Token")
        quarantine = OwnershipDomainTransferInst(
            "quarantine", source, "exclusive", "island"
        )
        handover = OwnershipDomainTransferInst(
            "handover", source, "island", "exclusive", destination
        )
        self.assertIn("ownership_transfer quarantine", str(quarantine))
        self.assertIn("[exclusive->island]", str(quarantine))
        self.assertIn("-> %peer: Token", str(handover))
        self.assertIn("[island->exclusive]", str(handover))

    def test_generator_emits_source_stable_ownership_domain_points(self):
        quarantine = type("Quarantine", (), {})()
        quarantine.value = SimpleNamespace(value="token")
        quarantine.destination = None
        quarantine.token = SimpleNamespace(line=5, column=5)

        handover = type("Handover", (), {})()
        handover.value = SimpleNamespace(value="token")
        handover.destination = SimpleNamespace(value="peer")
        handover.token = SimpleNamespace(line=6, column=5)

        ret = type("Return", (), {})()
        ret.token = SimpleNamespace(line=7, column=5)

        fn = SimpleNamespace(
            name="isolate",
            params=[],
            result=SimpleNamespace(name="void"),
            body=[quarantine, handover, ret],
            attributes=[],
        )
        module = SimpleNamespace(name="test", functions=[fn])

        sir = SIRGenerator().generate_from_ast(module)
        instructions = sir.functions[0].blocks[0].instructions
        points = [
            item for item in instructions
            if isinstance(item, OwnershipDomainPointInst)
        ]
        self.assertEqual(
            tuple(item.point_id for item in points),
            ("quarantine@5:5", "handover@6:5"),
        )
        self.assertEqual(points[0].source_name, "token")
        self.assertIsNone(points[0].destination_name)
        self.assertEqual(points[1].destination_name, "peer")
        self.assertIsInstance(instructions[-1], ReturnInst)
        self.assertEqual(instructions[-1].point_id, "return@7:5")

    def test_domain_transfer_placement_replaces_markers_atomically(self):
        fn = SIRFunction("isolate", [], "void")
        block = fn.add_block("0")
        block.add(
            OwnershipDomainPointInst(
                "quarantine", "token", None, "quarantine@5:5"
            )
        )
        block.add(
            OwnershipDomainPointInst(
                "handover", "token", "peer", "handover@6:5"
            )
        )
        block.add(ReturnInst(point_id="return@7:5"))

        token = SIRValue("token", "Token")
        peer = SIRValue("peer", "Token")
        plan = OwnershipDomainSIRPlan((
            OwnershipDomainTransferInst(
                "quarantine", token, "exclusive", "island"
            ),
            OwnershipDomainTransferInst(
                "handover", token, "island", "exclusive", peer
            ),
        ))

        placement = place_ownership_domain_transfers(fn, plan)

        self.assertEqual(placement.inserted_instructions, 2)
        self.assertEqual(
            tuple(type(item) for item in block.instructions),
            (
                OwnershipDomainTransferInst,
                OwnershipDomainTransferInst,
                ReturnInst,
            ),
        )
        self.assertEqual(
            block.instructions[1].destination.name, "peer"
        )

    def test_domain_transfer_placement_mismatch_is_transactional(self):
        fn = SIRFunction("isolate", [], "void")
        block = fn.add_block("0")
        marker = OwnershipDomainPointInst(
            "quarantine", "token", None, "quarantine@5:5"
        )
        block.add(marker)
        block.add(ReturnInst(point_id="return@6:5"))

        plan = OwnershipDomainSIRPlan((
            OwnershipDomainTransferInst(
                "handover",
                SIRValue("token", "Token"),
                "exclusive",
                "exclusive",
            ),
        ))
        original = tuple(block.instructions)

        with self.assertRaisesRegex(
            ValueError,
            r"ownership domain operation mismatch",
        ):
            place_ownership_domain_transfers(fn, plan)

        self.assertEqual(tuple(block.instructions), original)
        self.assertIs(block.instructions[0], marker)

    def test_module_domain_transfer_placement_applies_all_functions(self):
        module = SIRModule("test")
        isolate = SIRFunction("isolate", [], "void")
        isolate_block = isolate.add_block("0")
        isolate_block.add(
            OwnershipDomainPointInst(
                "quarantine", "token", None, "quarantine@5:5"
            )
        )
        isolate_block.add(ReturnInst(point_id="return@6:5"))
        plain = SIRFunction("plain", [], "void")
        plain.add_block("0").add(ReturnInst(point_id="return@10:5"))
        module.add_function(isolate)
        module.add_function(plain)

        empty_shared = SimpleNamespace(
            semantic=(), cleanup_segments=()
        )
        plan = OwnershipModuleSIRPlan((
            OwnershipFunctionSIRPlan(
                "isolate",
                OwnershipDomainSIRPlan((
                    OwnershipDomainTransferInst(
                        "quarantine",
                        SIRValue("token", "Token"),
                        "exclusive",
                        "island",
                    ),
                )),
                empty_shared,
            ),
            OwnershipFunctionSIRPlan(
                "plain",
                OwnershipDomainSIRPlan(()),
                empty_shared,
            ),
        ))

        placement = apply_ownership_module_domain_transfers(
            module, plan
        )

        self.assertEqual(placement.inserted_domain_instructions, 1)
        self.assertIsInstance(
            isolate_block.instructions[0],
            OwnershipDomainTransferInst,
        )
        self.assertIsInstance(
            plain.blocks[0].instructions[0], ReturnInst
        )

    def test_module_domain_transfer_placement_is_transactional(self):
        module = SIRModule("test")
        first = SIRFunction("first", [], "void")
        first_block = first.add_block("0")
        first_marker = OwnershipDomainPointInst(
            "quarantine", "token", None, "quarantine@5:5"
        )
        first_block.add(first_marker)
        second = SIRFunction("second", [], "void")
        second_block = second.add_block("0")
        second_marker = OwnershipDomainPointInst(
            "quarantine", "other", None, "quarantine@9:5"
        )
        second_block.add(second_marker)
        module.add_function(first)
        module.add_function(second)

        empty_shared = SimpleNamespace(
            semantic=(), cleanup_segments=()
        )
        plan = OwnershipModuleSIRPlan((
            OwnershipFunctionSIRPlan(
                "first",
                OwnershipDomainSIRPlan((
                    OwnershipDomainTransferInst(
                        "quarantine",
                        SIRValue("token", "Token"),
                        "exclusive",
                        "island",
                    ),
                )),
                empty_shared,
            ),
            OwnershipFunctionSIRPlan(
                "second",
                OwnershipDomainSIRPlan((
                    OwnershipDomainTransferInst(
                        "handover",
                        SIRValue("other", "Token"),
                        "exclusive",
                        "exclusive",
                    ),
                )),
                empty_shared,
            ),
        ))

        with self.assertRaisesRegex(
            ValueError,
            r"ownership domain operation mismatch",
        ):
            apply_ownership_module_domain_transfers(module, plan)

        self.assertIs(first_block.instructions[0], first_marker)
        self.assertIs(second_block.instructions[0], second_marker)

    def test_module_domain_transfer_placement_rejects_missing_function(self):
        module = SIRModule("test")
        module.add_function(SIRFunction("main", [], "void"))
        empty_shared = SimpleNamespace(
            semantic=(), cleanup_segments=()
        )
        plan = OwnershipModuleSIRPlan((
            OwnershipFunctionSIRPlan(
                "missing",
                OwnershipDomainSIRPlan(()),
                empty_shared,
            ),
        ))
        with self.assertRaisesRegex(
            ValueError,
            r"references missing function 'missing'",
        ):
            apply_ownership_module_domain_transfers(module, plan)

    def test_full_module_ownership_placement_combines_domain_and_arc(self):
        module = SIRModule("test")

        isolate = SIRFunction("isolate", [], "void")
        isolate_block = isolate.add_block("0")
        isolate_block.add(
            OwnershipDomainPointInst(
                "quarantine", "token", None, "quarantine@5:5"
            )
        )
        isolate_block.add(ReturnInst(point_id="return@6:5"))

        cleanup = SIRFunction("cleanup", [], "void")
        cleanup_block = cleanup.add_block("0")
        cleanup_block.add(ReturnInst(point_id="return@10:5"))

        module.add_function(isolate)
        module.add_function(cleanup)

        token = SIRValue("token", "Token")
        peer = SIRValue("peer", "Token")
        empty_shared = SharedOwnershipSIRPlan((), ())
        cleanup_shared = SharedOwnershipSIRPlan(
            (),
            (
                SimpleNamespace(
                    via="early_return",
                    point_id="return@10:5",
                    instructions=(ReleaseInst(peer), DestroyInst(peer)),
                ),
            ),
        )
        plan = OwnershipModuleSIRPlan((
            OwnershipFunctionSIRPlan(
                "isolate",
                OwnershipDomainSIRPlan((
                    OwnershipDomainTransferInst(
                        "quarantine", token, "exclusive", "island"
                    ),
                )),
                empty_shared,
            ),
            OwnershipFunctionSIRPlan(
                "cleanup",
                OwnershipDomainSIRPlan(()),
                cleanup_shared,
            ),
        ))

        placement = apply_ownership_module_plan(module, plan)

        self.assertEqual(placement.inserted_domain_instructions, 1)
        self.assertEqual(
            placement.inserted_return_cleanup_instructions, 2
        )
        self.assertEqual(placement.inserted_loop_control_instructions, 0)
        self.assertEqual(placement.inserted_backedge_instructions, 0)
        self.assertIsInstance(
            isolate_block.instructions[0],
            OwnershipDomainTransferInst,
        )
        self.assertEqual(
            tuple(type(item) for item in cleanup_block.instructions),
            (ReleaseInst, DestroyInst, ReturnInst),
        )

    def test_full_module_ownership_placement_preflights_arc_before_domain_mutation(self):
        module = SIRModule("test")

        isolate = SIRFunction("isolate", [], "void")
        isolate_block = isolate.add_block("0")
        marker = OwnershipDomainPointInst(
            "quarantine", "token", None, "quarantine@5:5"
        )
        isolate_block.add(marker)
        isolate_block.add(ReturnInst(point_id="return@6:5"))

        broken = SIRFunction("broken", [], "void")
        broken_block = broken.add_block("0")
        broken_return = ReturnInst(point_id="return@9:5")
        broken_block.add(broken_return)

        module.add_function(isolate)
        module.add_function(broken)

        token = SIRValue("token", "Token")
        empty_shared = SharedOwnershipSIRPlan((), ())
        broken_shared = SharedOwnershipSIRPlan(
            (),
            (
                SimpleNamespace(
                    via="early_return",
                    point_id="return@99:1",
                    instructions=(ReleaseInst(token),),
                ),
            ),
        )
        plan = OwnershipModuleSIRPlan((
            OwnershipFunctionSIRPlan(
                "isolate",
                OwnershipDomainSIRPlan((
                    OwnershipDomainTransferInst(
                        "quarantine", token, "exclusive", "island"
                    ),
                )),
                empty_shared,
            ),
            OwnershipFunctionSIRPlan(
                "broken",
                OwnershipDomainSIRPlan(()),
                broken_shared,
            ),
        ))

        with self.assertRaisesRegex(
            ValueError,
            r"shared ARC return cleanup point\(s\) missing from SIR CFG",
        ):
            apply_ownership_module_plan(module, plan)

        self.assertIs(isolate_block.instructions[0], marker)
        self.assertIs(broken_block.instructions[0], broken_return)

    def test_domain_trace_lowers_quarantine_and_handover(self):
        token_type = SimpleNamespace(name="Token")
        exclusive = SimpleNamespace(value="exclusive")
        island = SimpleNamespace(value="island")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="source", type=token_type),
                SimpleNamespace(name="destination", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="quarantine",
                    name="source",
                    type=token_type,
                    source_domain=exclusive,
                    target_domain=island,
                    destination=None,
                    destination_domain=None,
                ),
                SimpleNamespace(
                    kind="handover",
                    name="source",
                    type=token_type,
                    source_domain=island,
                    target_domain=exclusive,
                    destination="destination",
                    destination_domain=exclusive,
                ),
            ),
        )
        plan = lower_ownership_domain_trace(trace)
        self.assertEqual(len(plan.instructions), 2)
        quarantine, handover = plan.instructions
        self.assertIsInstance(quarantine, OwnershipDomainTransferInst)
        self.assertEqual(quarantine.operation, "quarantine")
        self.assertEqual(quarantine.source_domain, "exclusive")
        self.assertEqual(quarantine.target_domain, "island")
        self.assertIsNone(quarantine.destination)
        self.assertEqual(handover.operation, "handover")
        self.assertEqual(handover.source_domain, "island")
        self.assertEqual(handover.target_domain, "exclusive")
        self.assertEqual(handover.destination.name, "destination")

    def test_domain_trace_rejects_incomplete_quarantine_facts(self):
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="quarantine",
                    name="token",
                    type=token_type,
                    source_domain=None,
                    target_domain=SimpleNamespace(value="island"),
                ),
            ),
        )
        with self.assertRaisesRegex(
            ValueError,
            r"lacks complete domains for quarantine 'token'",
        ):
            lower_ownership_domain_trace(trace)

    def test_domain_trace_rejects_island_handover_without_destination(self):
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="handover",
                    name="token",
                    type=token_type,
                    source_domain=SimpleNamespace(value="island"),
                    target_domain=SimpleNamespace(value="exclusive"),
                    destination=None,
                    destination_domain=None,
                ),
            ),
        )
        with self.assertRaisesRegex(
            ValueError,
            r"island handover 'token' requires explicit destination",
        ):
            lower_ownership_domain_trace(trace)

    def test_module_ownership_analysis_lowers_all_function_plans(self):
        token_type = SimpleNamespace(name="Token")
        exclusive = SimpleNamespace(value="exclusive")
        island = SimpleNamespace(value="island")
        empty_cleanup = SimpleNamespace(steps=())
        empty_control = SimpleNamespace(actions=())

        quarantine_trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="quarantine",
                    name="token",
                    type=token_type,
                    source_domain=exclusive,
                    target_domain=island,
                    destination=None,
                    destination_domain=None,
                ),
            ),
            shared_cleanup=empty_cleanup,
            shared_path_cleanup=empty_cleanup,
            shared_loop_cleanup=empty_cleanup,
            shared_loop_control_exit=empty_control,
        )
        plain_trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=()),
            events=(),
            shared_cleanup=empty_cleanup,
            shared_path_cleanup=empty_cleanup,
            shared_loop_cleanup=empty_cleanup,
            shared_loop_control_exit=empty_control,
        )
        analysis = SimpleNamespace(
            traces=(("isolate", quarantine_trace), ("plain", plain_trace))
        )

        plan = lower_ownership_module_analysis(analysis)

        self.assertEqual(
            tuple(item.function for item in plan.functions),
            ("isolate", "plain"),
        )
        self.assertEqual(
            len(plan.functions[0].domain.instructions), 1
        )
        self.assertEqual(
            plan.functions[0].domain.instructions[0].operation,
            "quarantine",
        )
        self.assertEqual(
            plan.functions[0].shared.semantic, ()
        )
        self.assertEqual(
            plan.functions[1].domain.instructions, ()
        )
        self.assertEqual(
            plan.functions[1].shared.semantic, ()
        )

    def test_module_ownership_analysis_rejects_duplicate_function_traces(self):
        empty_cleanup = SimpleNamespace(steps=())
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=()),
            events=(),
            shared_cleanup=empty_cleanup,
            shared_path_cleanup=empty_cleanup,
            shared_loop_cleanup=empty_cleanup,
            shared_loop_control_exit=SimpleNamespace(actions=()),
        )
        analysis = SimpleNamespace(
            traces=(("main", trace), ("main", trace))
        )
        with self.assertRaisesRegex(
            ValueError,
            r"duplicate ownership trace for function 'main'",
        ):
            lower_ownership_module_analysis(analysis)

    def test_shared_ownership_trace_lowers_to_backend_neutral_sir_plan(self):
        token_type = SimpleNamespace(name="Token")
        shared_domain = object()
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
                SimpleNamespace(name="peer", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="domain_transition",
                    name="token",
                    via="share:peer",
                    domain=shared_domain,
                    type=token_type,
                ),
                SimpleNamespace(
                    kind="retain",
                    name="peer",
                    via="share:token",
                    domain=shared_domain,
                    type=token_type,
                ),
            ),
            shared_cleanup=SimpleNamespace(steps=(
                SimpleNamespace(
                    owner="peer",
                    account="token",
                    destroy_after=False,
                    via="scope_exit",
                    point_id=None,
                ),
                SimpleNamespace(
                    owner="token",
                    account="token",
                    destroy_after=True,
                    via="scope_exit",
                    point_id=None,
                ),
            )),
            shared_path_cleanup=SimpleNamespace(steps=()),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=()),
        )

        plan = lower_shared_ownership_trace(trace)

        self.assertEqual(
            tuple(type(inst) for inst in plan.semantic),
            (ShareInst, RetainInst),
        )
        self.assertEqual(len(plan.cleanup_segments), 1)
        segment = plan.cleanup_segments[0]
        self.assertEqual(segment.via, "scope_exit")
        self.assertEqual(segment.point_id, "function_exit")
        self.assertEqual(
            tuple(type(inst) for inst in segment.instructions),
            (ReleaseInst, ReleaseInst, DestroyInst),
        )

    def test_shared_ownership_sir_keeps_distinct_cfg_cleanup_points(self):
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
                SimpleNamespace(name="peer", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="domain_transition", name="token",
                    via="share:peer", type=token_type,
                ),
                SimpleNamespace(
                    kind="retain", name="peer",
                    via="share:token", type=token_type,
                ),
            ),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=(
                SimpleNamespace(
                    owner="peer", account="token",
                    destroy_after=False, via="early_return",
                    point_id="return@8:9",
                ),
                SimpleNamespace(
                    owner="token", account="token",
                    destroy_after=True, via="early_return",
                    point_id="return@8:9",
                ),
                SimpleNamespace(
                    owner="peer", account="token",
                    destroy_after=False, via="early_return",
                    point_id="return@10:5",
                ),
                SimpleNamespace(
                    owner="token", account="token",
                    destroy_after=True, via="early_return",
                    point_id="return@10:5",
                ),
            )),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=()),
        )
        plan = lower_shared_ownership_trace(trace)
        self.assertEqual(
            tuple(segment.point_id for segment in plan.cleanup_segments),
            ("return@8:9", "return@10:5"),
        )
        self.assertTrue(
            all(segment.via == "early_return" for segment in plan.cleanup_segments)
        )

    def test_shared_return_cleanup_is_inserted_before_matching_return(self):
        fn = SIRFunction("main", [], "void")
        first = fn.add_block("then")
        second = fn.add_block("fallthrough")
        first.add(ReturnInst(point_id="return@8:9"))
        second.add(ReturnInst(point_id="return@10:5"))

        peer = SIRValue("peer", "Token")
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                point_id="return@8:9",
                instructions=(ReleaseInst(peer), ReleaseInst(token), DestroyInst(token)),
            ),
            SimpleNamespace(
                point_id="return@10:5",
                instructions=(ReleaseInst(peer), ReleaseInst(token), DestroyInst(token)),
            ),
        ))

        inserted = place_shared_return_cleanup(fn, plan)
        self.assertEqual(inserted, 6)
        self.assertEqual(tuple(type(inst) for inst in first.instructions),
                         (ReleaseInst, ReleaseInst, DestroyInst, ReturnInst))
        self.assertEqual(tuple(type(inst) for inst in second.instructions),
                         (ReleaseInst, ReleaseInst, DestroyInst, ReturnInst))
        self.assertEqual(first.instructions[-1].point_id, "return@8:9")
        self.assertEqual(second.instructions[-1].point_id, "return@10:5")

    def test_shared_return_cleanup_leaves_non_return_segments_unplaced(self):
        fn = SIRFunction("main", [], "void")
        block = fn.add_block("entry")
        block.add(ReturnInst(point_id="return@5:5"))
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(point_id="while_backedge@4:5",
                            instructions=(ReleaseInst(token),)),
        ))
        inserted = place_shared_return_cleanup(fn, plan)
        self.assertEqual(inserted, 0)
        self.assertEqual(tuple(type(i) for i in block.instructions), (ReturnInst,))

    def test_shared_return_cleanup_fails_closed_when_cfg_point_is_missing(self):
        fn = SIRFunction("main", [], "void")
        fn.add_block("entry").add(ReturnInst(point_id="return@5:5"))
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(point_id="return@8:9",
                            instructions=(ReleaseInst(token),)),
        ))
        with self.assertRaisesRegex(ValueError, "missing from SIR CFG: return@8:9"):
            place_shared_return_cleanup(fn, plan)

    def test_shared_return_cleanup_rejects_duplicate_cfg_point(self):
        fn = SIRFunction("main", [], "void")
        fn.add_block("a").add(ReturnInst(point_id="return@5:5"))
        fn.add_block("b").add(ReturnInst(point_id="return@5:5"))
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(point_id="return@5:5",
                            instructions=(ReleaseInst(token),)),
        ))
        with self.assertRaisesRegex(ValueError, "matches multiple ReturnInst nodes"):
            place_shared_return_cleanup(fn, plan)

    def test_return_cleanup_missing_later_point_is_transactional(self):
        fn = SIRFunction("main", [], "void")
        first = fn.add_block("first")
        first.add(ReturnInst(point_id="return@5:5"))
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                point_id="return@5:5",
                instructions=(ReleaseInst(token),),
            ),
            SimpleNamespace(
                point_id="return@9:9",
                instructions=(ReleaseInst(token),),
            ),
        ))

        before = tuple(first.instructions)
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: return@9:9",
        ):
            place_shared_return_cleanup(fn, plan)
        self.assertEqual(tuple(first.instructions), before)
        self.assertEqual(tuple(type(i) for i in first.instructions), (ReturnInst,))

    def test_loop_control_missing_later_point_is_transactional(self):
        fn = SIRFunction("main", [], "void")
        first = fn.add_block("first")
        first.add(
            BranchInst(
                "cond",
                point_id="continue@5:5",
                control_kind="continue",
            )
        )
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_control:continue",
                point_id="continue@5:5",
                instructions=(ReleaseInst(token),),
            ),
            SimpleNamespace(
                via="loop_control:break",
                point_id="break@9:9",
                instructions=(ReleaseInst(token),),
            ),
        ))

        before = tuple(first.instructions)
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: break@9:9",
        ):
            place_shared_loop_control_cleanup(fn, plan)
        self.assertEqual(tuple(first.instructions), before)
        self.assertEqual(tuple(type(i) for i in first.instructions), (BranchInst,))

    def test_backedge_duplicate_cfg_point_is_transactional(self):
        fn = SIRFunction("main", [], "void")
        first = fn.add_block("first")
        second = fn.add_block("second")
        first.add(
            BranchInst(
                "cond",
                point_id="while_backedge@4:5",
                control_kind="backedge",
            )
        )
        second.add(
            BranchInst(
                "cond",
                point_id="while_backedge@4:5",
                control_kind="backedge",
            )
        )
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_backedge:while",
                point_id="while_backedge@4:5",
                instructions=(ReleaseInst(token),),
            ),
        ))

        before_first = tuple(first.instructions)
        before_second = tuple(second.instructions)
        with self.assertRaisesRegex(
            ValueError,
            "matches multiple BranchInst nodes",
        ):
            place_shared_loop_backedge_cleanup(fn, plan)
        self.assertEqual(tuple(first.instructions), before_first)
        self.assertEqual(tuple(second.instructions), before_second)

    def test_apply_shared_ownership_trace_preflights_all_cfg_points(self):
        fn = SIRFunction("main", [], "void")
        ret_block = fn.add_block("ret")
        ret_block.add(ReturnInst(point_id="return@5:5"))
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=(
                SimpleNamespace(
                    owner="token", account="token",
                    destroy_after=True, via="early_return",
                    point_id="return@5:5",
                ),
            )),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=(
                SimpleNamespace(
                    kind="release", owner="token",
                    via="continue:scope_exit",
                    point_id="continue@9:9",
                    defer_point_id=None,
                ),
            )),
        )

        before = tuple(ret_block.instructions)
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: continue@9:9",
        ):
            apply_shared_ownership_trace(fn, trace)
        self.assertEqual(tuple(ret_block.instructions), before)
        self.assertEqual(tuple(type(i) for i in ret_block.instructions), (ReturnInst,))

    def test_shared_ownership_trace_applies_to_generated_if_return_cfg(self):
        source = """
        module test::sir_arc_if_integration;

        pub fn maybe_stop(flag: bool) -> void {
            if flag {
                return;
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-arc-if-integration>").tokenize()
        ast = Parser(tokens, "<sir-arc-if-integration>").parse()
        fn = SIRGenerator().generate_from_ast(ast).functions[0]

        if_node = ast.decls[0].body[0]
        first_return = if_node.then_body[0]
        second_return = ast.decls[0].body[1]
        first_point = f"return@{first_return.span.line}:{first_return.span.col}"
        second_point = f"return@{second_return.span.line}:{second_return.span.col}"

        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
                SimpleNamespace(name="peer", type=token_type),
            )),
            events=(
                SimpleNamespace(
                    kind="domain_transition", name="token",
                    via="share:peer", type=token_type,
                ),
                SimpleNamespace(
                    kind="retain", name="peer",
                    via="share:token", type=token_type,
                ),
            ),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=(
                SimpleNamespace(
                    owner="peer", account="token",
                    destroy_after=False, via="early_return",
                    point_id=first_point,
                ),
                SimpleNamespace(
                    owner="token", account="token",
                    destroy_after=True, via="early_return",
                    point_id=first_point,
                ),
                SimpleNamespace(
                    owner="peer", account="token",
                    destroy_after=False, via="early_return",
                    point_id=second_point,
                ),
                SimpleNamespace(
                    owner="token", account="token",
                    destroy_after=True, via="early_return",
                    point_id=second_point,
                ),
            )),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=()),
        )

        placement = apply_shared_ownership_trace(fn, trace)

        self.assertEqual(placement.inserted_return_instructions, 6)
        self.assertEqual(
            tuple(type(inst) for inst in placement.plan.semantic),
            (ShareInst, RetainInst),
        )
        for block in fn.blocks[1:]:
            self.assertEqual(
                tuple(type(inst) for inst in block.instructions),
                (ReleaseInst, ReleaseInst, DestroyInst, ReturnInst),
            )

    def test_shared_ownership_trace_application_fails_on_cfg_mismatch(self):
        fn = SIRFunction("main", [], "void")
        fn.add_block("entry").add(ReturnInst(point_id="return@5:5"))
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=(
                SimpleNamespace(
                    owner="token", account="token",
                    destroy_after=True, via="early_return",
                    point_id="return@8:9",
                ),
            )),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=()),
        )
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: return@8:9",
        ):
            apply_shared_ownership_trace(fn, trace)

    def test_shared_loop_control_cleanup_places_before_continue_branch(self):
        fn = SIRFunction("main", [], "void")
        block = fn.add_block("loop_body")
        block.add(
            BranchInst(
                "loop_cond",
                point_id="continue@8:9",
                control_kind="continue",
            )
        )
        peer = SIRValue("peer", "Token")
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_control:continue",
                point_id="continue@8:9",
                instructions=(
                    ReleaseInst(peer),
                    ReleaseInst(token),
                    DestroyInst(token),
                ),
            ),
        ))

        inserted = place_shared_loop_control_cleanup(fn, plan)

        self.assertEqual(inserted, 3)
        self.assertEqual(
            tuple(type(inst) for inst in block.instructions),
            (ReleaseInst, ReleaseInst, DestroyInst, BranchInst),
        )
        self.assertEqual(block.instructions[-1].control_kind, "continue")

    def test_shared_loop_control_cleanup_places_before_break_branch(self):
        fn = SIRFunction("main", [], "void")
        block = fn.add_block("loop_body")
        block.add(
            BranchInst(
                "loop_exit",
                point_id="break@9:9",
                control_kind="break",
            )
        )
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_control:break",
                point_id="break@9:9",
                instructions=(
                    ReleaseInst(token),
                    DestroyInst(token),
                ),
            ),
        ))

        inserted = place_shared_loop_control_cleanup(fn, plan)

        self.assertEqual(inserted, 2)
        self.assertEqual(
            tuple(type(inst) for inst in block.instructions),
            (ReleaseInst, DestroyInst, BranchInst),
        )

    def test_shared_loop_control_cleanup_fails_on_missing_cfg_point(self):
        fn = SIRFunction("main", [], "void")
        fn.add_block("loop_body").add(
            BranchInst(
                "loop_exit",
                point_id="break@5:5",
                control_kind="break",
            )
        )
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_control:break",
                point_id="break@9:9",
                instructions=(ReleaseInst(token),),
            ),
        ))
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: break@9:9",
        ):
            place_shared_loop_control_cleanup(fn, plan)

    def test_shared_loop_control_expression_defer_lowers_before_arc(self):
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
                SimpleNamespace(name="peer", type=token_type),
            )),
            events=(),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=()),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=(
                SimpleNamespace(
                    kind="defer", owner="peer",
                    via="continue:expression",
                    point_id="continue@8:9",
                    defer_point_id="defer@7:9",
                ),
                SimpleNamespace(
                    kind="release", owner="peer",
                    via="continue:scope_exit",
                    point_id="continue@8:9",
                    defer_point_id=None,
                ),
                SimpleNamespace(
                    kind="release", owner="token",
                    via="continue:scope_exit",
                    point_id="continue@8:9",
                    defer_point_id=None,
                ),
                SimpleNamespace(
                    kind="destroy", owner="token",
                    via="continue:scope_exit",
                    point_id="continue@8:9",
                    defer_point_id=None,
                ),
            )),
        )

        plan = lower_shared_ownership_trace(trace)
        segment = next(
            item for item in plan.cleanup_segments
            if item.via == "loop_control:continue"
        )
        self.assertEqual(segment.point_id, "continue@8:9")
        self.assertEqual(
            tuple(type(inst) for inst in segment.instructions),
            (DeferUseInst, ReleaseInst, ReleaseInst, DestroyInst),
        )
        self.assertEqual(segment.instructions[0].defer_point_id, "defer@7:9")

        fn = SIRFunction("main", [], "void")
        block = fn.add_block("loop_body")
        block.add(
            BranchInst(
                "loop_cond",
                point_id="continue@8:9",
                control_kind="continue",
            )
        )
        inserted = place_shared_loop_control_cleanup(fn, plan)
        self.assertEqual(inserted, 4)
        self.assertEqual(
            tuple(type(inst) for inst in block.instructions),
            (DeferUseInst, ReleaseInst, ReleaseInst, DestroyInst, BranchInst),
        )

    def test_shared_loop_control_nonexpression_defer_remains_fail_closed(self):
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=()),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=(
                SimpleNamespace(
                    kind="defer", owner="token",
                    via="continue:call",
                    point_id="continue@8:9",
                    defer_point_id="defer@7:9",
                ),
            )),
        )
        with self.assertRaisesRegex(
            ValueError,
            "defer call lacks typed direct arguments",
        ):
            lower_shared_ownership_trace(trace)

    def test_shared_loop_control_direct_call_runs_once_before_arc(self):
        token_type = SimpleNamespace(name="Token")
        call = ("inspect", ("token", "peer"))
        actions = tuple(
            SimpleNamespace(
                kind="defer", owner=owner, via="continue:call",
                point_id="continue@8:9", defer_point_id="defer@7:9",
                defer_call=call,
            ) for owner in ("token", "peer")
        ) + (SimpleNamespace(
            kind="release", owner="peer", via="continue:scope_exit",
            point_id="continue@8:9", defer_point_id=None,
        ),)
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=tuple(
                SimpleNamespace(name=name, type=token_type)
                for name in ("token", "peer")
            )),
            events=(), shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=()),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=actions),
        )
        plan = lower_shared_ownership_trace(trace)
        segment = plan.cleanup_segments[0]
        self.assertEqual(tuple(type(i) for i in segment.instructions),
                         (CallInst, ReleaseInst))
        self.assertEqual(segment.instructions[0].callee, "inspect")
        self.assertEqual(tuple(v.name for v in segment.instructions[0].arguments),
                         ("token", "peer"))
        self.assertEqual(segment.instructions[0].defer_point_id, "defer@7:9")
        fn = SIRFunction("main", [], "void")
        block = fn.add_block("body")
        block.add(BranchInst("cond", "continue@8:9", "continue"))
        self.assertEqual(place_shared_loop_control_cleanup(fn, plan), 2)
        self.assertEqual(tuple(type(i) for i in block.instructions),
                         (CallInst, ReleaseInst, BranchInst))

    def test_shared_loop_control_defer_requires_source_identity(self):
        token_type = SimpleNamespace(name="Token")
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=(
                SimpleNamespace(name="token", type=token_type),
            )),
            events=(),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=()),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=(
                SimpleNamespace(
                    kind="defer",
                    owner="token",
                    via="continue:expression",
                    point_id="continue@8:9",
                    defer_point_id=None,
                ),
            )),
        )
        with self.assertRaisesRegex(
            ValueError,
            "loop-control defer lacks source identity",
        ):
            lower_shared_ownership_trace(trace)

    def test_shared_ownership_sir_lowering_fails_without_binding_type(self):
        trace = SimpleNamespace(
            final_env=SimpleNamespace(bindings=()),
            events=(
                SimpleNamespace(
                    kind="domain_transition",
                    name="ghost",
                    via="share:peer",
                    domain=object(),
                    type=None,
                ),
            ),
            shared_cleanup=SimpleNamespace(steps=()),
            shared_path_cleanup=SimpleNamespace(steps=()),
            shared_loop_cleanup=SimpleNamespace(steps=()),
            shared_loop_control_exit=SimpleNamespace(actions=()),
        )
        with self.assertRaisesRegex(ValueError, "lacks type for binding 'ghost'"):
            lower_shared_ownership_trace(trace)

    def test_sir_generator_from_ast(self):
        source = """
        module test::sir_probe;

        @system
        pub fn compute_sum(a: i32, b: i32) -> i32 {
            return a + b;
        }
        """
        tokens = Lexer(source, "<sir-probe>").tokenize()
        ast = Parser(tokens, "<sir-probe>").parse()

        generator = SIRGenerator()
        sir_mod = generator.generate_from_ast(ast)

        self.assertEqual(len(sir_mod.functions), 1)
        fn = sir_mod.functions[0]
        self.assertEqual(fn.name, "compute_sum")
        self.assertTrue(fn.is_system)
        self.assertEqual(len(fn.parameters), 2)
        return_node = ast.decls[0].body[-1]
        expected_point = (
            f"return@{return_node.span.line}:{return_node.span.col}"
        )
        self.assertIsInstance(fn.blocks[0].instructions[-1], ReturnInst)
        self.assertEqual(
            fn.blocks[0].instructions[-1].point_id,
            expected_point,
        )
        dump = sir_mod.dump()
        self.assertIn("sir_fn @system @compute_sum", dump)
        self.assertIn("alloc_stack", dump)

    def test_sir_generator_normalizes_primitive_type_nodes(self):
        source = """
        module test::sir_type_normalization;

        pub fn probe(flag: bool) -> void {
            return;
        }

        pub fn number() -> i32 {
            return 1;
        }
        """
        tokens = Lexer(source, "<sir-type-normalization>").tokenize()
        ast = Parser(tokens, "<sir-type-normalization>").parse()

        sir_mod = SIRGenerator().generate_from_ast(ast)
        probe, number = sir_mod.functions

        self.assertEqual(probe.return_type, "void")
        self.assertEqual(probe.parameters[0].type_name, "bool")
        self.assertEqual(number.return_type, "i32")

    def test_sir_generator_builds_cfg_for_if_then_return_and_fallthrough_return(self):
        source = """
        module test::sir_nested_return_probe;

        pub fn maybe_stop(flag: bool) -> void {
            if flag {
                return;
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-nested-return-probe>").tokenize()
        ast = Parser(tokens, "<sir-nested-return-probe>").parse()

        sir_mod = SIRGenerator().generate_from_ast(ast)
        fn = sir_mod.functions[0]

        self.assertEqual(len(fn.blocks), 3)
        self.assertIsInstance(fn.blocks[0].instructions[-1], CondBranchInst)

        if_node = ast.decls[0].body[0]
        nested_return = if_node.then_body[0]
        fallthrough_return = ast.decls[0].body[1]
        expected = {
            f"return@{nested_return.span.line}:{nested_return.span.col}",
            f"return@{fallthrough_return.span.line}:{fallthrough_return.span.col}",
        }
        actual = {
            inst.point_id
            for block in fn.blocks[1:]
            for inst in block.instructions
            if isinstance(inst, ReturnInst)
        }
        self.assertEqual(actual, expected)

    def test_sir_generator_builds_cfg_for_if_else_direct_returns(self):
        source = """
        module test::sir_if_else_return_probe;

        pub fn choose(flag: bool) -> void {
            if flag {
                return;
            } else {
                return;
            }
        }
        """
        tokens = Lexer(source, "<sir-if-else-return-probe>").tokenize()
        ast = Parser(tokens, "<sir-if-else-return-probe>").parse()

        sir_mod = SIRGenerator().generate_from_ast(ast)
        fn = sir_mod.functions[0]
        self.assertEqual(len(fn.blocks), 3)
        self.assertIsInstance(fn.blocks[0].instructions[-1], CondBranchInst)
        returns = [
            inst
            for block in fn.blocks[1:]
            for inst in block.instructions
            if isinstance(inst, ReturnInst)
        ]
        self.assertEqual(len(returns), 2)
        self.assertTrue(all(inst.point_id.startswith("return@") for inst in returns))

    def test_sir_generator_builds_continue_loop_cfg_with_identity(self):
        source = """
        module test::sir_continue_loop;

        pub fn spin(flag: bool) -> void {
            while flag {
                continue;
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-continue-loop>").tokenize()
        ast = Parser(tokens, "<sir-continue-loop>").parse()

        fn = SIRGenerator().generate_from_ast(ast).functions[0]

        self.assertEqual(len(fn.blocks), 4)
        self.assertIsInstance(fn.blocks[0].instructions[-1], BranchInst)
        self.assertIsInstance(fn.blocks[1].instructions[-1], CondBranchInst)
        control = fn.blocks[2].instructions[-1]
        self.assertIsInstance(control, BranchInst)
        self.assertEqual(control.control_kind, "continue")
        stmt = ast.decls[0].body[0].body[0]
        self.assertEqual(
            control.point_id,
            f"continue@{stmt.span.line}:{stmt.span.col}",
        )
        self.assertEqual(control.target_block, fn.blocks[1].label)

    def test_sir_generator_builds_break_loop_cfg_with_identity(self):
        source = """
        module test::sir_break_loop;

        pub fn stop(flag: bool) -> void {
            while flag {
                break;
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-break-loop>").tokenize()
        ast = Parser(tokens, "<sir-break-loop>").parse()

        fn = SIRGenerator().generate_from_ast(ast).functions[0]

        self.assertEqual(len(fn.blocks), 4)
        control = fn.blocks[2].instructions[-1]
        self.assertIsInstance(control, BranchInst)
        self.assertEqual(control.control_kind, "break")
        stmt = ast.decls[0].body[0].body[0]
        self.assertEqual(
            control.point_id,
            f"break@{stmt.span.line}:{stmt.span.col}",
        )
        self.assertEqual(control.target_block, fn.blocks[3].label)
        terminal = fn.blocks[3].instructions[-1]
        ret = ast.decls[0].body[1]
        self.assertEqual(
            terminal.point_id,
            f"return@{ret.span.line}:{ret.span.col}",
        )

    def test_generated_continue_loop_accepts_arc_control_placement(self):
        source = """
        module test::sir_continue_arc;

        pub fn spin(flag: bool) -> void {
            while flag {
                continue;
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-continue-arc>").tokenize()
        ast = Parser(tokens, "<sir-continue-arc>").parse()
        fn = SIRGenerator().generate_from_ast(ast).functions[0]
        control = ast.decls[0].body[0].body[0]
        point = f"continue@{control.span.line}:{control.span.col}"
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_control:continue",
                point_id=point,
                instructions=(ReleaseInst(token), DestroyInst(token)),
            ),
        ))

        inserted = place_shared_loop_control_cleanup(fn, plan)

        self.assertEqual(inserted, 2)
        self.assertEqual(
            tuple(type(inst) for inst in fn.blocks[2].instructions),
            (ReleaseInst, DestroyInst, BranchInst),
        )

    def test_unrepresentable_loop_control_keeps_fallback_prototype(self):
        source = """
        module test::sir_complex_loop;

        pub fn spin(flag: bool) -> void {
            while flag && flag {
                continue;
            }
        }
        """
        tokens = Lexer(source, "<sir-complex-loop>").tokenize()
        ast = Parser(tokens, "<sir-complex-loop>").parse()

        fn = SIRGenerator().generate_from_ast(ast).functions[0]

        self.assertEqual(len(fn.blocks), 1)
        self.assertIsInstance(fn.blocks[0].instructions[-1], ReturnInst)
        self.assertIsNone(fn.blocks[0].instructions[-1].point_id)

    def test_sir_generator_builds_empty_loop_backedge_identity(self):
        source = """
        module test::sir_backedge_loop;

        pub fn spin(flag: bool) -> void {
            while flag {
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-backedge-loop>").tokenize()
        ast = Parser(tokens, "<sir-backedge-loop>").parse()

        fn = SIRGenerator().generate_from_ast(ast).functions[0]

        self.assertEqual(len(fn.blocks), 4)
        backedge = fn.blocks[2].instructions[-1]
        self.assertIsInstance(backedge, BranchInst)
        self.assertEqual(backedge.control_kind, "backedge")
        loop = ast.decls[0].body[0]
        self.assertEqual(
            backedge.point_id,
            f"while_backedge@{loop.span.line}:{loop.span.col}",
        )
        self.assertEqual(backedge.target_block, fn.blocks[1].label)

    def test_generated_loop_backedge_accepts_arc_placement(self):
        source = """
        module test::sir_backedge_arc;

        pub fn spin(flag: bool) -> void {
            while flag {
            }
            return;
        }
        """
        tokens = Lexer(source, "<sir-backedge-arc>").tokenize()
        ast = Parser(tokens, "<sir-backedge-arc>").parse()
        fn = SIRGenerator().generate_from_ast(ast).functions[0]
        loop = ast.decls[0].body[0]
        point = f"while_backedge@{loop.span.line}:{loop.span.col}"
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_backedge:while",
                point_id=point,
                instructions=(ReleaseInst(token), DestroyInst(token)),
            ),
        ))

        inserted = place_shared_loop_backedge_cleanup(fn, plan)

        self.assertEqual(inserted, 2)
        self.assertEqual(
            tuple(type(inst) for inst in fn.blocks[2].instructions),
            (ReleaseInst, DestroyInst, BranchInst),
        )
        self.assertEqual(fn.blocks[2].instructions[-1].control_kind, "backedge")

    def test_loop_backedge_cleanup_fails_on_cfg_mismatch(self):
        fn = SIRFunction("main", [], "void")
        fn.add_block("loop_body").add(
            BranchInst(
                "loop_cond",
                point_id="while_backedge@5:5",
                control_kind="backedge",
            )
        )
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_backedge:while",
                point_id="while_backedge@9:9",
                instructions=(ReleaseInst(token),),
            ),
        ))
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: while_backedge@9:9",
        ):
            place_shared_loop_backedge_cleanup(fn, plan)

    def test_loop_backedge_placement_does_not_touch_continue_branch(self):
        fn = SIRFunction("main", [], "void")
        block = fn.add_block("loop_body")
        block.add(
            BranchInst(
                "loop_cond",
                point_id="continue@8:9",
                control_kind="continue",
            )
        )
        token = SIRValue("token", "Token")
        plan = SimpleNamespace(cleanup_segments=(
            SimpleNamespace(
                via="loop_backedge:while",
                point_id="while_backedge@4:5",
                instructions=(ReleaseInst(token),),
            ),
        ))
        with self.assertRaisesRegex(
            ValueError,
            "missing from SIR CFG: while_backedge@4:5",
        ):
            place_shared_loop_backedge_cleanup(fn, plan)
        self.assertEqual(
            tuple(type(inst) for inst in block.instructions),
            (BranchInst,),
        )

    def test_sir_generator_does_not_emit_valueless_nonvoid_if_returns(self):
        source = """
        module test::sir_nonvoid_if_return_probe;

        pub fn choose(flag: bool) -> i32 {
            if flag {
                return 1;
            } else {
                return 2;
            }
        }
        """
        tokens = Lexer(source, "<sir-nonvoid-if-return-probe>").tokenize()
        ast = Parser(tokens, "<sir-nonvoid-if-return-probe>").parse()

        sir_mod = SIRGenerator().generate_from_ast(ast)
        fn = sir_mod.functions[0]

        self.assertEqual(len(fn.blocks), 1)
        terminal = fn.blocks[0].instructions[-1]
        self.assertIsInstance(terminal, ReturnInst)
        self.assertIsNotNone(terminal.value)
        self.assertIsNone(terminal.point_id)

    def test_sir_generator_keeps_unrepresentable_nested_return_unidentified(self):
        source = """
        module test::sir_unrepresentable_nested_return;

        pub fn maybe_stop(flag: bool) -> void {
            if flag && flag {
                return;
            }
        }
        """
        tokens = Lexer(source, "<sir-unrepresentable-nested-return>").tokenize()
        ast = Parser(tokens, "<sir-unrepresentable-nested-return>").parse()

        sir_mod = SIRGenerator().generate_from_ast(ast)
        fn = sir_mod.functions[0]
        terminal = fn.blocks[0].instructions[-1]
        self.assertIsInstance(terminal, ReturnInst)
        self.assertIsNone(terminal.point_id)

    def test_definite_initialization_pass_detects_uninitialized_read(self):
        fn = SIRFunction("bad_fn", [], "i32")
        b = fn.add_block("0")
        slot = SIRValue("slot_uninit", "i32")
        res = SIRValue("res", "i32")
        b.add(AllocStackInst("uninit", "i32", slot))
        b.add(LoadInst(slot, res))  # Leitura antes do store!
        b.add(ReturnInst(res))

        mod = SIRModule("test_di")
        mod.add_function(fn)

        di_pass = DefiniteInitializationPass()
        result = di_pass.run(mod)
        self.assertFalse(result.success)
        self.assertTrue(any("lida antes de ser inicializada" in e for e in result.errors))

    def test_system_capability_pass_rejects_unauthorized_call(self):
        fn = SIRFunction("user_fn", [], "void", is_system=False)
        b = fn.add_block("0")
        b.add(CallInst("privileged_kernel_op", [], is_system=True))
        b.add(ReturnInst())

        mod = SIRModule("test_safety")
        mod.add_function(fn)

        safety_pass = SystemCapabilitySafetyPass()
        result = safety_pass.run(mod)
        self.assertFalse(result.success)
        self.assertTrue(any("em função não-privilegiada" in e for e in result.errors))

    def test_dead_code_elimination_removes_unreachable_instructions(self):
        fn = SIRFunction("dead_fn", [], "void")
        b = fn.add_block("0")
        v = SIRValue("v", "i32")
        b.add(ReturnInst())
        b.add(AllocStackInst("dead_var", "i32", v))  # Inalcançável após return!

        mod = SIRModule("test_dce")
        mod.add_function(fn)

        dce = DeadCodeEliminationPass()
        dce.run(mod)
        self.assertEqual(len(b.instructions), 1)
        self.assertIsInstance(b.instructions[0], ReturnInst)


if __name__ == "__main__":
    unittest.main()
