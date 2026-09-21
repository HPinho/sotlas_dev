"""Testes unitários para o Sotlas Intermediate Representation (SIR)."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.sir import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, CallInst, ReturnInst, CondBranchInst,
    ShareInst, RetainInst, ReleaseInst, DestroyInst,
    lower_shared_ownership_trace, place_shared_return_cleanup,
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
