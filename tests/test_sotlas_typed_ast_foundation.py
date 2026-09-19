"""Isolated Phase-1 tests for the declaration Typed AST foundation."""
from pathlib import Path
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = _load(
    "sotlas_phase1_bootstrap",
    ROOT / "compiler" / "sotlas_compile" / "bootstrap.py",
)
typed_ast = _load(
    "sotlas_phase1_typed_ast",
    ROOT / "compiler" / "sotlas_compile" / "typed_ast.py",
)


SOURCE = """module test::phase1;

sole struct Handle {
    fd: u32;
}

pub const LIMIT: u32 = 8;

pub fn consume(h: Handle, count: usize) -> bool {
    if count > 0 {
        return true;
    }
    return false;
}
"""


class SotlasTypedAstFoundationTests(unittest.TestCase):
    def checked_ast(self):
        module = bootstrap.parse(SOURCE, filename="<phase1>")
        bootstrap.check(module)
        return module

    def test_builder_is_explicit_and_does_not_patch_production_checker(self):
        check_before = bootstrap.check
        module = self.checked_ast()
        typed = typed_ast.build_declaration_typed_ast(module)
        self.assertIs(bootstrap.check, check_before)
        self.assertFalse(hasattr(module, "typed_ast"))
        self.assertEqual(typed.maturity, "DECLARATIONS_ONLY")

    def test_declared_struct_and_sole_fact_are_preserved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        handle = typed.structs[0]
        self.assertEqual(handle.name, "Handle")
        self.assertTrue(handle.is_sole)
        self.assertEqual(handle.fields[0].name, "fd")
        self.assertEqual(handle.fields[0].type.name, "u32")

    def test_class_declaration_is_preserved(self):
        source = """module test::typed_class;
@layout(C)
pub class Counter {
    value: u32;

    pub fn increment(self: *mut Counter, amount: u32) -> u32 {
        return amount;
    }
}
fn main() -> void { return; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-class>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)

        self.assertEqual(len(typed.classes), 1)
        counter = typed.classes[0]
        self.assertEqual(counter.name, "Counter")
        self.assertTrue(counter.public)
        self.assertEqual(counter.attributes, ("@layout(C)",))
        self.assertEqual(
            [(field.name, field.type.name) for field in counter.fields],
            [("value", "u32")],
        )
        self.assertEqual(len(counter.methods), 1)
        method = counter.methods[0]
        self.assertEqual(method.name, "Counter_increment")
        self.assertEqual(
            [(param.name, param.type.name, param.type.pointer)
             for param in method.params],
            [("self", "Counter", True), ("amount", "u32", False)],
        )
        self.assertEqual(method.result.name, "u32")
        self.assertTrue(method.public)

    def test_function_signature_types_are_frozen(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        consume = typed.functions[0]
        self.assertEqual(consume.name, "consume")
        self.assertEqual(
            [(param.name, param.type.name) for param in consume.params],
            [("h", "Handle"), ("count", "usize")],
        )
        self.assertEqual(consume.result.name, "bool")

    def typed_from(self, source: str):
        module = bootstrap.parse(source, filename="<phase1-recursion>")
        bootstrap.check(module)
        return typed_ast.build_declaration_typed_ast(module)

    def test_sole_declaration_drives_initial_ownership_state(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        handle_type = typed_ast.SemanticType("Handle")
        self.assertIn("Handle", typed_ast.sole_type_names(typed))
        self.assertTrue(typed_ast.is_sole_type(handle_type, typed))
        self.assertIs(
            typed_ast.initial_ownership_state(handle_type, typed),
            typed_ast.VarState.LIVE,
        )

    def test_non_sole_type_has_no_move_state(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        plain = typed_ast.SemanticType("u32")
        self.assertFalse(typed_ast.is_sole_type(plain, typed))
        self.assertIsNone(typed_ast.initial_ownership_state(plain, typed))
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"handover target 'count' is not a sole value",
        ):
            typed_ast.require_sole_transfer("count", plain, typed)

    def test_pointer_to_sole_is_not_an_owning_value(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        pointer = typed_ast.SemanticType("Handle", pointer=True, mutable=True)
        self.assertFalse(typed_ast.is_sole_type(pointer, typed))
        self.assertIsNone(typed_ast.initial_ownership_state(pointer, typed))

    def test_explicit_sole_transfer_starts_live_then_moves(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        state = typed_ast.require_sole_transfer(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        self.assertIs(state, typed_ast.VarState.MOVED)

    def test_function_ownership_seeds_sole_parameter_and_local(self):
        source = """module test::ownership_seed;
sole struct Handle { fd: u32; }

fn consume(h: Handle) -> void {
    let local = Handle { fd: 1 };
    let count: u32 = 2;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-seed>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        env = typed_ast.seed_function_ownership(parsed, typed, "consume")
        self.assertIs(env.state_of("h"), typed_ast.VarState.LIVE)
        self.assertIs(env.state_of("local"), typed_ast.VarState.LIVE)
        self.assertIsNone(env.state_of("count"))

    def test_function_ownership_accepts_explicit_sole_local_type(self):
        source = """module test::ownership_explicit;
sole struct Token { value: u32; }

fn main() -> void {
    let first: Token = Token { value: 7 };
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-explicit>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        env = typed_ast.seed_function_ownership(parsed, typed, "main")
        self.assertIs(env.state_of("first"), typed_ast.VarState.LIVE)

    def test_function_ownership_does_not_guess_arbitrary_expression_types(self):
        source = """module test::ownership_conservative;
sole struct Token { value: u32; }

fn identity(t: Token) -> Token { return t; }
fn main(t: Token) -> void {
    let copy = t;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-conservative>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        env = typed_ast.seed_function_ownership(parsed, typed, "main")
        self.assertIs(env.state_of("t"), typed_ast.VarState.LIVE)
        self.assertIsNone(env.state_of("copy"))

    def test_linear_body_moves_sole_value_into_by_value_call(self):
        source = """module test::linear_call;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-linear-call>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_linear_function_ownership(
            parsed, typed, "main"
        )
        self.assertIs(
            trace.final_env.state_of("token"),
            typed_ast.VarState.MOVED,
        )
        self.assertIn(
            typed_ast.OwnershipEvent("move", "token", "call:consume"),
            trace.events,
        )

    def test_linear_body_move_assignment_transfers_owner(self):
        source = """module test::linear_let;
sole struct Token { value: u32; }

fn main() -> void {
    let first = Token { value: 1 };
    let second = first;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-linear-let>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_linear_function_ownership(
            parsed, typed, "main"
        )
        self.assertIs(
            trace.final_env.state_of("first"),
            typed_ast.VarState.MOVED,
        )
        self.assertIs(
            trace.final_env.state_of("second"),
            typed_ast.VarState.LIVE,
        )

    def test_linear_body_detects_double_move(self):
        source = """module test::linear_double;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(token);
    consume(token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-linear-double>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_linear_function_ownership(
                parsed, typed, "main"
            )

    def test_linear_body_does_not_move_copyable_argument(self):
        source = """module test::linear_copy;
fn consume(value: u32) -> void { return; }
fn main() -> void {
    let value: u32 = 1;
    consume(value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-linear-copy>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_linear_function_ownership(
            parsed, typed, "main"
        )
        self.assertIsNone(trace.final_env.state_of("value"))
        self.assertFalse(any(event.kind == "move" for event in trace.events))

    def test_field_read_after_move_is_rejected(self):
        source = """module test::field_after_move;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main() -> u32 {
    let token = Token { value: 1 };
    consume(token);
    return token.value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-field-after-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_field_read_after_conditional_move_is_rejected(self):
        source = """module test::field_after_maybe_move;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main(flag: bool) -> u32 {
    let token = Token { value: 1 };
    if flag {
        consume(token);
    }
    return token.value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-field-after-maybe>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after conditional move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_field_read_from_live_sole_owner_is_valid(self):
        source = """module test::field_live;
sole struct Token { value: u32; }

fn main() -> u32 {
    let token = Token { value: 7 };
    return token.value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-field-live>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(
            trace.final_env.state_of("token"),
            typed_ast.VarState.LIVE,
        )

    def test_ownership_if_returning_move_branch_does_not_poison_fallthrough(self):
        source = """module test::if_return_move;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn inspect(value: u32) -> void { return; }
fn main(flag: bool, token: Token) -> void {
    if flag {
        consume(move token);
        return;
    }
    inspect(token.value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-return-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)

    def test_ownership_if_else_returning_move_branch_preserves_then_fallthrough(self):
        source = """module test::if_else_return_move;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn inspect(value: u32) -> void { return; }
fn main(flag: bool, token: Token) -> void {
    if flag {
        inspect(token.value);
    } else {
        consume(move token);
        return;
    }
    inspect(token.value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-else-return-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)

    def test_ownership_if_both_terminating_branches_stop_fallthrough(self):
        source = """module test::if_both_return;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(flag: bool, token: Token) -> void {
    if flag {
        return;
    } else {
        return;
    }
    consume(move token);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-both-return>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)
        self.assertNotIn(
            typed_ast.OwnershipEvent("move", "token", "call:consume"),
            trace.events,
        )

    def test_canonical_if_one_sided_move_becomes_maybe_moved(self):
        source = """module test::if_one_sided;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main(flag: bool) -> void {
    let token = Token { value: 1 };
    if flag {
        consume(token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-one-sided>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(
            trace.final_env.state_of("token"),
            typed_ast.VarState.MAYBE_MOVED,
        )

    def test_canonical_if_both_branches_move_becomes_moved(self):
        source = """module test::if_both;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main(flag: bool) -> void {
    let token = Token { value: 1 };
    if flag {
        consume(token);
    } else {
        consume(token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-both>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(
            trace.final_env.state_of("token"),
            typed_ast.VarState.MOVED,
        )

    def test_canonical_if_rejects_use_after_conditional_move(self):
        source = """module test::if_use_after;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main(flag: bool) -> void {
    let token = Token { value: 1 };
    if flag {
        consume(token);
    }
    consume(token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-use-after>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after conditional move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_branch_local_sole_binding_does_not_escape_merge(self):
        source = """module test::if_local;
sole struct Token { value: u32; }

fn main(flag: bool) -> void {
    if flag {
        let local = Token { value: 1 };
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-if-local>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIsNone(trace.final_env.state_of("local"))

    def test_ownership_return_stops_unreachable_move_analysis(self):
        source = """module test::ownership_return_terminator;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    return;
    consume(move token);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-return>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)
        self.assertNotIn(
            typed_ast.OwnershipEvent("move", "token", "call:consume"),
            trace.events,
        )

    def test_ownership_break_stops_unreachable_move_analysis(self):
        source = """module test::ownership_break_terminator;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    loop {
        break;
        consume(move token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-break>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)
        self.assertIn(
            typed_ast.OwnershipEvent("control", "main", "break"),
            trace.events,
        )

    def test_ownership_continue_stops_unreachable_move_analysis(self):
        source = """module test::ownership_continue_terminator;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(flag: bool, token: Token) -> void {
    while flag {
        continue;
        consume(move token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-continue>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)
        self.assertIn(
            typed_ast.OwnershipEvent("control", "main", "continue"),
            trace.events,
        )

    def test_canonical_while_move_is_rejected(self):
        source = """module test::while_move;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main(flag: bool) -> void {
    let token = Token { value: 1 };
    while flag {
        consume(token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-while-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"sole value 'token' moved inside loop without reinitialization",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_conditional_break_move_is_not_discarded_from_loop_ownership(self):
        source = """module test::loop_conditional_break_move;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main(flag: bool, token: Token) -> void {
    loop {
        if flag {
            consume(move token);
            break;
        } else {
            break;
        }
    }
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-loop-conditional-break-move>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"sole value 'token' moved inside loop without reinitialization",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_canonical_loop_move_is_rejected(self):
        source = """module test::loop_move;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    loop {
        consume(token);
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-loop-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"sole value 'token' moved inside loop without reinitialization",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_canonical_while_without_move_preserves_owner(self):
        source = """module test::while_read;
sole struct Token { value: u32; }

fn inspect(value: u32) -> void { return; }
fn main(flag: bool) -> void {
    let token = Token { value: 1 };
    while flag {
        inspect(token.value);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-while-read>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(
            trace.final_env.state_of("token"),
            typed_ast.VarState.LIVE,
        )

    def test_loop_local_sole_binding_does_not_escape(self):
        source = """module test::loop_local;
sole struct Token { value: u32; }

fn main(flag: bool) -> void {
    while flag {
        let local = Token { value: 1 };
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-loop-local>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIsNone(trace.final_env.state_of("local"))

    def test_module_ownership_summary_exposes_call_contracts(self):
        source = """module test::summary;
sole struct Token { value: u32; }

fn forward(t: Token) -> Token { return t; }
fn consume(t: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-summary>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        summaries = {
            item.name: item
            for item in typed_ast.summarize_module_ownership(parsed, typed)
        }

        self.assertTrue(summaries["forward"].params[0].takes_ownership)
        self.assertTrue(summaries["forward"].returns_sole)
        self.assertTrue(summaries["consume"].params[0].takes_ownership)
        self.assertFalse(summaries["consume"].returns_sole)
        self.assertEqual(summaries["main"].calls, ("consume",))

    def test_module_ownership_summary_collects_nested_call_edges(self):
        source = """module test::nested_calls;
fn ping() -> void { return; }
fn main(flag: bool) -> void {
    if flag {
        ping();
    }
    while flag {
        ping();
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-nested-calls>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        summaries = {
            item.name: item
            for item in typed_ast.summarize_module_ownership(parsed, typed)
        }
        self.assertEqual(summaries["main"].calls, ("ping", "ping"))

    def test_module_ownership_analysis_keeps_per_function_traces(self):
        source = """module test::module_analysis;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-module-analysis>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        analysis = typed_ast.analyze_module_ownership(parsed, typed)
        traces = dict(analysis.traces)
        self.assertIn("consume", traces)
        self.assertIn("main", traces)
        self.assertIs(
            traces["main"].final_env.state_of("token"),
            typed_ast.VarState.MOVED,
        )

    def test_linear_typed_body_infers_local_and_return_types(self):
        source = """module test::typed_body;
fn main() -> i64 {
    let value = 41;
    let result: i64 = value + 1;
    return result;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-body>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.maturity, "STRUCTURED_BODY_TYPES")
        self.assertEqual(
            [(item.kind, item.name, item.type.name) for item in body.statements],
            [
                ("Let", "value", "i64"),
                ("Let", "result", "i64"),
                ("Return", None, "i64"),
            ],
        )

    def test_linear_typed_body_resolves_struct_member_type(self):
        source = """module test::typed_member;
struct Point { x: u32; }
fn main() -> u32 {
    let point = Point { x: 7 };
    return point.x;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-member>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[-1].expr.type.name, "u32")

    def test_linear_typed_body_resolves_known_call_result(self):
        source = """module test::typed_call;
fn answer() -> i64 { return 42; }
fn main() -> i64 {
    let value = answer();
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-call>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].type.name, "i64")
        self.assertEqual(body.statements[0].expr.type.name, "i64")

    def test_linear_typed_body_rejects_local_type_mismatch(self):
        source = """module test::typed_mismatch;
fn main() -> void {
    let value: bool = 1;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-mismatch>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"let 'value' type mismatch",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_linear_typed_body_checks_name_assignment(self):
        source = """module test::typed_assign;
fn main() -> i64 {
    let value: i64 = 1;
    value = 2;
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-assign>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        assign = body.statements[1]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.name, "value")
        self.assertEqual(assign.type.name, "i64")

    def test_linear_typed_body_rejects_assignment_type_mismatch(self):
        source = """module test::typed_assign_mismatch;
fn main() -> void {
    let value: i64 = 1;
    value = true;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-assign-mismatch>")
        # This negative test intentionally bypasses bootstrap.check because the
        # production checker already rejects the mismatch first. The isolated
        # Phase-1 body checker must independently reject the same invalid AST.
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"assignment type mismatch for 'value': expected i64, got bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_immutable_reference_member_assignment_is_rejected(self):
        source = """module test::immutable_reference_member_write;
struct Point { x: u32; }
fn write(point: &Point) -> void {
    point.x = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-immutable-reference-member-write>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"atribuição por referência imutável não é permitida",
        ):
            bootstrap.check(parsed)

    def test_typed_body_independently_rejects_immutable_reference_member_write(self):
        source = """module test::typed_immutable_reference_member_write;
struct Point { x: u32; }
fn write(point: &Point) -> void {
    point.x = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-immutable-reference-member-write>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"assignment through immutable reference is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "write")

    def test_mut_reference_member_assignment_is_valid(self):
        source = """module test::mut_reference_member_write;
struct Point { x: u32; }
fn write(point: &mut Point) -> void {
    point.x = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-mut-reference-member-write>"
        )
        bootstrap.check(parsed)
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed_module, "write")
        assign = body.statements[0]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.name, "x")
        self.assertEqual(assign.type.name, "u32")

    def test_linear_typed_body_checks_member_assignment(self):
        source = """module test::typed_member_assign;
struct Point { x: u32; }
fn main() -> u32 {
    let point = Point { x: 1 };
    point.x = 2u32;
    return point.x;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-member-assign>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        assign = body.statements[1]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.name, "x")
        self.assertEqual(assign.type.name, "u32")

    def test_typed_body_materializes_if_branches(self):
        source = """module test::typed_if;
fn main(flag: bool) -> i64 {
    if flag {
        return 1;
    } else {
        return 2;
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-if>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        branch = body.statements[0]
        self.assertEqual(branch.kind, "If")
        self.assertEqual(branch.expr.type.name, "bool")
        self.assertEqual(branch.body[0].kind, "Return")
        self.assertEqual(branch.else_body[0].kind, "Return")

    def test_typed_body_rejects_non_bool_if_condition_independently(self):
        source = """module test::typed_if_bad;
fn main() -> void {
    if 1 {
        return;
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-if-bad>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"if condition must be bool, got i64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_branch_local_does_not_escape_type_env(self):
        source = """module test::typed_if_scope;
fn main(flag: bool) -> void {
    if flag {
        let branch_value: i64 = 1;
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-if-scope>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].body[0].name, "branch_value")
        self.assertEqual(body.statements[-1].kind, "Return")

    def test_typed_body_materializes_while_loop_and_for(self):
        source = """module test::typed_loops;
fn main(flag: bool) -> void {
    while flag {
        let a: i64 = 1;
    }
    loop {
        let b: i64 = 2;
        break;
    }
    for i in 0usize..3usize {
        let copy: usize = i;
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-loops>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(
            [item.kind for item in body.statements],
            ["While", "Loop", "For", "Return"],
        )
        self.assertEqual(body.statements[0].expr.type.name, "bool")
        self.assertEqual(body.statements[1].body[0].name, "b")
        self.assertEqual(body.statements[2].name, "i")
        self.assertEqual(body.statements[2].type.name, "usize")
        self.assertEqual(body.statements[2].extra_expr.type.name, "usize")
        self.assertEqual(body.statements[2].body[0].type.name, "usize")

    def test_typed_body_for_variable_inherits_range_type(self):
        source = """module test::typed_for_range_type;
fn main() -> i32 {
    let result: i32 = 0;
    for i in 0i32..3i32 {
        let copy: i32 = i;
    }
    return result;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-for-range-type>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        loop = body.statements[1]
        self.assertEqual(loop.type.name, "i32")
        self.assertEqual(loop.expr.type.name, "i32")
        self.assertEqual(loop.extra_expr.type.name, "i32")
        self.assertEqual(loop.body[0].type.name, "i32")
        self.assertEqual(loop.body[0].expr.type.name, "i32")

    def test_typed_body_rejects_non_bool_while_condition_independently(self):
        source = """module test::typed_while_bad;
fn main() -> void {
    while 1 {
        return;
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-while-bad>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"while condition must be bool, got i64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_pointer_for_range_bounds(self):
        source = """module test::typed_for_pointer_bounds;
fn main(start: *mut u32, end: *mut u32) -> void {
    for i in start..end {
        return;
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-for-pointer-bounds>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"for range bounds must be scalar integers, got u32 and u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_array_for_range_bounds(self):
        source = """module test::typed_for_array_bounds;
fn main(start: [u32; 2], end: [u32; 2]) -> void {
    for i in start..end {
        return;
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-for-array-bounds>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"for range bounds must be scalar integers, got u32 and u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_mixed_for_bound_types_independently(self):
        source = """module test::typed_for_bad;
fn main() -> void {
    for i in 0usize..3u32 {
        return;
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-for-bad>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"for range bound type mismatch: usize vs u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_reference_function_field_call_does_not_require_unsafe(self):
        source = """module test::reference_fn_field_safe;
struct Dispatch {
    call: fn(u32) -> u32;
}
fn invoke(dispatch: &Dispatch) -> u32 {
    return dispatch.call(7u32);
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-fn-field-safe>"
        )
        bootstrap.check(parsed)
        invoke = next(item for item in parsed.functions if item.name == "invoke")
        call = invoke.body[0].value
        self.assertTrue(call.is_vtable_call)
        self.assertTrue(call.is_arrow)
        self.assertTrue(call.target_type.is_reference)
        self.assertEqual(call.target_type.name, "Dispatch")

    def test_mut_reference_function_field_call_does_not_require_unsafe(self):
        source = """module test::mut_reference_fn_field_safe;
struct Dispatch {
    call: fn(u32) -> u32;
}
fn invoke(dispatch: &mut Dispatch) -> u32 {
    return dispatch.call(7u32);
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-mut-reference-fn-field-safe>"
        )
        bootstrap.check(parsed)
        invoke = next(item for item in parsed.functions if item.name == "invoke")
        call = invoke.body[0].value
        self.assertTrue(call.is_vtable_call)
        self.assertTrue(call.is_arrow)
        self.assertTrue(call.target_type.is_reference)
        self.assertTrue(call.target_type.mutable)

    def test_pointer_function_field_call_requires_unsafe(self):
        source = """module test::pointer_fn_field_requires_unsafe;
struct Dispatch {
    call: fn(u32) -> u32;
}
fn invoke(ptr: *mut Dispatch) -> u32 {
    return ptr.call(7u32);
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-pointer-fn-field-requires-unsafe>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"chamada de campo de função via ponteiro exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_pointer_function_field_call_inside_unsafe_is_valid(self):
        source = """module test::pointer_fn_field_unsafe;
struct Dispatch {
    call: fn(u32) -> u32;
}
fn invoke(ptr: *mut Dispatch) -> u32 {
    unsafe {
        return ptr.call(7u32);
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-pointer-fn-field-unsafe>"
        )
        bootstrap.check(parsed)
        invoke = next(item for item in parsed.functions if item.name == "invoke")
        call = invoke.body[0].body[0].value
        self.assertTrue(call.is_vtable_call)
        self.assertTrue(call.is_arrow)
        self.assertEqual(call.target_type.name, "Dispatch")
        self.assertTrue(call.target_type.pointer)

    def test_bootstrap_rejects_unknown_member_field(self):
        source = """module test::bootstrap_unknown_member_field;
struct Point { x: u32; }
fn read(point: Point) -> u32 {
    return point.y;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-bootstrap-unknown-member-field>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"campo não declarado: Point\.y",
        ):
            bootstrap.check(parsed)

    def test_typed_body_rejects_unknown_member_field_independently(self):
        source = """module test::typed_unknown_member_field;
struct Point { x: u32; }
fn read(point: Point) -> u32 {
    return point.y;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-unknown-member-field>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"struct 'Point' has no field 'y'",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "read")

    def test_bootstrap_rejects_member_access_on_non_struct(self):
        source = """module test::bootstrap_scalar_member_target;
fn read(value: u32) -> u32 {
    return value.x;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-bootstrap-scalar-member-target>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"acesso a campo exige struct conhecido: u32",
        ):
            bootstrap.check(parsed)

    def test_reference_member_access_does_not_require_unsafe(self):
        source = """module test::reference_member_safe;
struct Point { x: u32; }
fn read(point: &Point) -> u32 {
    return point.x;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-member-safe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        member = body.statements[0].expr
        self.assertEqual(member.kind, "Member")
        self.assertEqual(member.type.name, "u32")
        self.assertFalse(member.type.pointer)
        self.assertFalse(member.type.is_reference)

    def test_mut_reference_member_access_does_not_require_unsafe(self):
        source = """module test::mut_reference_member_safe;
struct Point { x: u32; }
fn read(point: &mut Point) -> u32 {
    return point.x;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-mut-reference-member-safe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        member = body.statements[0].expr
        self.assertEqual(member.kind, "Member")
        self.assertEqual(member.type.name, "u32")
        self.assertFalse(member.type.pointer)

    def test_pointer_member_access_requires_unsafe(self):
        source = """module test::pointer_member_requires_unsafe;
struct Point { x: u32; }
fn read(ptr: *mut Point) -> u32 {
    return ptr.x;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-pointer-member-requires-unsafe>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"acesso a campo via ponteiro exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_pointer_member_access_inside_unsafe_is_valid(self):
        source = """module test::pointer_member_unsafe;
struct Point { x: u32; }
fn read(ptr: *mut Point) -> u32 {
    unsafe {
        return ptr.x;
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-pointer-member-unsafe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        unsafe_node = body.statements[0]
        member = unsafe_node.body[0].expr
        self.assertEqual(member.kind, "Member")
        self.assertEqual(member.type.name, "u32")
        self.assertFalse(member.type.pointer)
        self.assertFalse(member.type.is_array)

    def test_immutable_reference_array_index_assignment_is_rejected(self):
        source = """module test::immutable_reference_array_write;
fn write(values: &[u32; 2]) -> void {
    values[0] = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-immutable-reference-array-write>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"atribuição por referência imutável não é permitida",
        ):
            bootstrap.check(parsed)

    def test_typed_body_independently_rejects_immutable_reference_array_write(self):
        source = """module test::typed_immutable_reference_array_write;
fn write(values: &[u32; 2]) -> void {
    values[0] = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-immutable-reference-array-write>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"assignment through immutable reference is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "write")

    def test_mut_reference_array_index_assignment_is_valid(self):
        source = """module test::mut_reference_array_write;
fn write(values: &mut [u32; 2]) -> void {
    values[0] = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-mut-reference-array-write>"
        )
        bootstrap.check(parsed)
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed_module, "write")
        assign = body.statements[0]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.type.name, "u32")

    def test_raw_pointer_to_array_index_requires_unsafe(self):
        source = """module test::raw_pointer_array_index_requires_unsafe;
fn read(values: *mut [u32; 2]) -> u32 {
    return values[0];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-raw-pointer-array-index-requires-unsafe>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"indexação de ponteiro exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_reference_to_array_index_does_not_require_unsafe(self):
        source = """module test::reference_array_index_safe;
fn read(values: &[u32; 2]) -> u32 {
    return values[0];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-array-index-safe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        indexed = body.statements[0].expr
        self.assertEqual(indexed.kind, "Index")
        self.assertEqual(indexed.type.name, "u32")
        self.assertFalse(indexed.type.pointer)
        self.assertFalse(indexed.type.is_reference)

    def test_pointer_index_requires_unsafe(self):
        source = """module test::pointer_index_requires_unsafe;
fn read(ptr: *mut u32) -> u32 {
    return ptr[0];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-pointer-index-requires-unsafe>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"indexação de ponteiro exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_pointer_index_inside_unsafe_is_valid(self):
        source = """module test::pointer_index_unsafe;
fn read(ptr: *mut u32) -> u32 {
    unsafe {
        return ptr[0];
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-pointer-index-unsafe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        unsafe_node = body.statements[0]
        self.assertEqual(unsafe_node.kind, "Unsafe")
        self.assertEqual(unsafe_node.body[0].expr.kind, "Index")
        self.assertEqual(unsafe_node.body[0].expr.type.name, "u32")
        self.assertFalse(unsafe_node.body[0].expr.type.pointer)
        self.assertFalse(unsafe_node.body[0].expr.type.mutable)
        self.assertFalse(unsafe_node.body[0].expr.type.is_reference)

    def test_immutable_reference_deref_assignment_is_rejected(self):
        source = """module test::immutable_reference_deref_write;
fn write(value: &u32) -> void {
    *value = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-immutable-reference-deref-write>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"atribuição por referência imutável não é permitida",
        ):
            bootstrap.check(parsed)

    def test_mut_reference_deref_assignment_is_valid(self):
        source = """module test::mut_reference_deref_write;
fn write(value: &mut u32) -> void {
    *value = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-mut-reference-deref-write>"
        )
        bootstrap.check(parsed)
        write = next(item for item in parsed.functions if item.name == "write")
        assign = write.body[0]
        self.assertIsInstance(assign, bootstrap.Assign)
        self.assertIsInstance(assign.target, bootstrap.Unary)
        self.assertEqual(assign.target.op, "*")

    def test_typed_body_rejects_raw_pointer_index_write_outside_unsafe(self):
        source = """module test::typed_raw_pointer_index_write_requires_unsafe;
fn write(ptr: *mut u32) -> void {
    ptr[0] = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-index-write-requires-unsafe>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"raw pointer index assignment requires unsafe",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "write")

    def test_typed_body_accepts_raw_pointer_index_write_inside_unsafe(self):
        source = """module test::typed_raw_pointer_index_write_unsafe;
fn write(ptr: *mut u32) -> void {
    unsafe {
        ptr[0] = 7u32;
    }
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-index-write-unsafe>"
        )
        bootstrap.check(parsed)
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed_module, "write")
        assign = body.statements[0].body[0]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.type.name, "u32")

    def test_typed_body_rejects_raw_pointer_member_write_outside_unsafe(self):
        source = """module test::typed_raw_pointer_member_write_requires_unsafe;
struct Point { x: u32; }
fn write(ptr: *mut Point) -> void {
    ptr.x = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-member-write-requires-unsafe>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"raw pointer member assignment requires unsafe",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "write")

    def test_typed_body_accepts_raw_pointer_member_write_inside_unsafe(self):
        source = """module test::typed_raw_pointer_member_write_unsafe;
struct Point { x: u32; }
fn write(ptr: *mut Point) -> void {
    unsafe {
        ptr.x = 7u32;
    }
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-member-write-unsafe>"
        )
        bootstrap.check(parsed)
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed_module, "write")
        assign = body.statements[0].body[0]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.name, "x")
        self.assertEqual(assign.type.name, "u32")

    def test_typed_body_rejects_raw_pointer_deref_write_outside_unsafe(self):
        source = """module test::typed_raw_pointer_deref_write_requires_unsafe;
fn write(ptr: *mut u32) -> void {
    *ptr = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-deref-write-requires-unsafe>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"raw pointer dereference assignment requires unsafe",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "write")

    def test_typed_body_accepts_raw_pointer_deref_write_inside_unsafe(self):
        source = """module test::typed_raw_pointer_deref_write_unsafe;
fn write(ptr: *mut u32) -> void {
    unsafe {
        *ptr = 7u32;
    }
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-deref-write-unsafe>"
        )
        bootstrap.check(parsed)
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed_module, "write")
        unsafe_node = body.statements[0]
        self.assertEqual(unsafe_node.kind, "Unsafe")
        assign = unsafe_node.body[0]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.name, "*")
        self.assertEqual(assign.type.name, "u32")
        self.assertFalse(assign.type.pointer)
        self.assertFalse(assign.type.is_reference)

    def test_typed_body_independently_rejects_immutable_reference_deref_write(self):
        source = """module test::typed_immutable_reference_deref_write;
fn write(value: &u32) -> void {
    *value = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-immutable-reference-deref-write>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"assignment through immutable reference is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "write")

    def test_typed_body_accepts_mut_reference_deref_write(self):
        source = """module test::typed_mut_reference_deref_write;
fn write(value: &mut u32) -> void {
    *value = 7u32;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-mut-reference-deref-write>"
        )
        bootstrap.check(parsed)
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed_module, "write")
        assign = body.statements[0]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.name, "*")
        self.assertEqual(assign.type.name, "u32")
        self.assertFalse(assign.type.pointer)
        self.assertFalse(assign.type.is_reference)

    def test_bootstrap_rejects_implicit_reference_to_raw_pointer_return(self):
        source = """module test::implicit_reference_to_raw_pointer;
fn expose(value: &u32) -> *const u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-implicit-reference-to-raw-pointer>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            bootstrap.check(parsed)

    def test_bootstrap_rejects_implicit_raw_pointer_to_reference_return(self):
        source = """module test::implicit_raw_pointer_to_reference;
fn expose(value: *const u32) -> &u32 {
    unsafe {
        return value;
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-implicit-raw-pointer-to-reference>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            bootstrap.check(parsed)

    def test_bootstrap_rejects_immutable_to_mutable_reference_return(self):
        source = """module test::implicit_reference_mutability_strengthening;
fn strengthen(value: &u32) -> &mut u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-mutability-strengthening>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            bootstrap.check(parsed)

    def test_bootstrap_allows_mutable_to_immutable_reference_return(self):
        source = """module test::reference_mutability_weakening;
fn view(value: &mut u32) -> &u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-mutability-weakening>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "view")
        result = body.statements[0]
        self.assertEqual(result.kind, "Return")
        self.assertTrue(result.expr.type.is_reference)
        self.assertFalse(result.expr.type.mutable)

    def test_typed_body_independently_rejects_reference_mutability_strengthening(self):
        source = """module test::typed_reference_mutability_strengthening;
fn strengthen(value: &u32) -> &mut u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-reference-mutability-strengthening>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"return type mismatch",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "strengthen")

    def test_bootstrap_rejects_null_reference_return(self):
        source = """module test::null_reference;
fn bad() -> &u32 {
    return null;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-null-reference>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            bootstrap.check(parsed)

    def test_typed_body_accepts_null_raw_pointer_return(self):
        source = """module test::typed_null_raw_pointer;
fn empty() -> *const u32 {
    return null;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-null-raw-pointer>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "empty")
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_typed_body_accepts_raw_pointer_mutability_weakening(self):
        source = """module test::typed_raw_pointer_mutability_weakening;
fn view(value: *mut u32) -> *const u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-mutability-weakening>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "view")
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_typed_body_independently_rejects_raw_pointer_mutability_strengthening(self):
        source = """module test::typed_raw_pointer_mutability_strengthening;
fn strengthen(value: *const u32) -> *mut u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-mutability-strengthening>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"return type mismatch",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "strengthen")

    def test_typed_body_accepts_raw_pointer_to_void_pointer(self):
        source = """module test::typed_raw_pointer_to_void;
fn erase(value: *mut u32) -> *const void {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-raw-pointer-to-void>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "erase")
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "void")

    def test_typed_body_accepts_void_pointer_to_raw_pointer(self):
        source = """module test::typed_void_to_raw_pointer;
fn restore(value: *const void) -> *const u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-void-to-raw-pointer>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "restore")
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_typed_body_independently_rejects_void_pointer_mutability_strengthening(self):
        source = """module test::typed_void_pointer_strengthening;
fn strengthen(value: *const void) -> *mut u32 {
    return value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-void-pointer-strengthening>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"return type mismatch",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "strengthen")

    def test_typed_body_independently_rejects_null_reference_return(self):
        source = """module test::typed_null_reference;
fn bad() -> &u32 {
    return null;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-null-reference>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"return type mismatch",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "bad")

    def test_reference_deref_does_not_require_unsafe(self):
        source = """module test::reference_deref_safe;
fn read(value: &u32) -> u32 {
    return *value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-deref-safe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        expr = body.statements[0].expr
        self.assertEqual(expr.kind, "Unary")
        self.assertEqual(expr.type.name, "u32")
        self.assertFalse(expr.type.pointer)
        self.assertFalse(expr.type.is_reference)

    def test_mut_reference_deref_does_not_require_unsafe(self):
        source = """module test::mut_reference_deref_safe;
fn read(value: &mut u32) -> u32 {
    return *value;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-mut-reference-deref-safe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        expr = body.statements[0].expr
        self.assertEqual(expr.kind, "Unary")
        self.assertEqual(expr.type.name, "u32")
        self.assertFalse(expr.type.pointer)
        self.assertFalse(expr.type.mutable)

    def test_system_function_does_not_replace_unsafe_for_pointer_deref(self):
        source = """module test::system_requires_unsafe;
@system
fn read(ptr: *mut u32) -> u32 {
    return *ptr;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-system-requires-unsafe>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"desreferenciamento de ponteiro exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_system_function_accepts_pointer_deref_inside_unsafe(self):
        source = """module test::system_with_unsafe;
@system
fn read(ptr: *mut u32) -> u32 {
    unsafe {
        return *ptr;
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-system-with-unsafe>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "read")
        self.assertEqual(body.statements[0].kind, "Unsafe")
        self.assertEqual(body.statements[0].body[0].kind, "Return")
        self.assertEqual(body.statements[0].body[0].expr.type.name, "u32")

    def test_typed_body_materializes_unsafe_block(self):
        source = """module test::typed_unsafe;
fn main() -> i64 {
    unsafe {
        let value: i64 = 7;
        return value;
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-unsafe>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        unsafe_node = body.statements[0]
        self.assertEqual(unsafe_node.kind, "Unsafe")
        self.assertEqual(unsafe_node.body[0].kind, "Let")
        self.assertEqual(unsafe_node.body[0].type.name, "i64")
        self.assertEqual(unsafe_node.body[1].kind, "Return")

    def test_typed_unsafe_block_keeps_type_rules_active(self):
        source = """module test::typed_unsafe_mismatch;
fn main() -> void {
    unsafe {
        let value: bool = 1;
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-unsafe-mismatch>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"let 'value' type mismatch",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_phase1_snapshot_composes_typed_bodies_and_ownership(self):
        source = """module test::phase1_snapshot;
sole struct Token { value: u32; }

fn inspect(value: u32) -> void { return; }
fn main(flag: bool) -> u32 {
    let token = Token { value: 7 };
    if flag {
        inspect(token.value);
    }
    return token.value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-snapshot>")
        bootstrap.check(parsed)
        snapshot = typed_ast.build_phase1_semantic_snapshot(parsed)
        self.assertEqual(snapshot.maturity, "ISOLATED_PHASE1")
        self.assertEqual(snapshot.typed_module.structs[0].name, "Token")
        bodies = {body.name: body for body in snapshot.bodies}
        self.assertEqual(bodies["main"].statements[1].kind, "If")
        traces = dict(snapshot.ownership.traces)
        self.assertIs(
            traces["main"].final_env.state_of("token"),
            typed_ast.VarState.LIVE,
        )

    def test_phase1_snapshot_rejects_recursive_value_type(self):
        source = """module test::phase1_snapshot_recursive;
struct Node { next: Node; }
fn main() -> void { return; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-snapshot-recursive>")
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: Node -> Node",
        ):
            typed_ast.build_phase1_semantic_snapshot(parsed)

    def test_phase1_snapshot_rejects_double_move(self):
        source = """module test::phase1_snapshot_move;
sole struct Token { value: u32; }

fn consume(t: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(token);
    consume(token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-snapshot-move>")
        bootstrap.check(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.build_phase1_semantic_snapshot(parsed)

    def test_typed_body_types_char_and_unary_expressions(self):
        source = """module test::typed_unary;
fn negate(value: i64) -> i64 {
    let result = -value;
    return result;
}
fn flip(flag: bool) -> bool {
    return !flag;
}
fn char_code() -> u8 {
    return 'A';
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-unary>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        negate = typed_ast.build_linear_typed_body(parsed, typed, "negate")
        flip = typed_ast.build_linear_typed_body(parsed, typed, "flip")
        char_code = typed_ast.build_linear_typed_body(parsed, typed, "char_code")
        self.assertEqual(negate.statements[0].expr.type.name, "i64")
        self.assertEqual(flip.statements[0].expr.type.name, "bool")
        self.assertEqual(char_code.statements[0].expr.type.name, "u8")

    def test_typed_body_types_address_and_deref_inside_unsafe(self):
        source = """module test::typed_ptr_unary;
fn roundtrip(value: u32) -> u32 {
    unsafe {
        let ptr = &value;
        return *ptr;
    }
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-ptr-unary>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "roundtrip")
        unsafe_node = body.statements[0]
        self.assertTrue(unsafe_node.body[0].type.pointer)
        self.assertEqual(unsafe_node.body[1].expr.type.name, "u32")
        self.assertFalse(unsafe_node.body[1].expr.type.pointer)

    def test_typed_body_rejects_deref_of_non_pointer_independently(self):
        source = """module test::typed_bad_deref;
fn main(value: u32) -> u32 {
    return *value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-bad-deref>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"cannot dereference non-pointer type u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_integer_literal_fits_declared_type(self):
        source = """module test::typed_integer_context;
struct Pixel { channel: u8; }
fn take(value: u16) -> u16 { return value; }
fn main() -> u16 {
    let pixel = Pixel { channel: 255 };
    let local: u8 = 7;
    local = 8;
    take(9);
    return 10;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-int-context>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[1].type.name, "u8")
        self.assertEqual(body.statements[1].expr.type.name, "u8")
        self.assertEqual(body.statements[2].expr.type.name, "u8")
        self.assertEqual(body.statements[-1].expr.type.name, "u16")

    def test_contextual_constant_integer_expression_uses_expected_type(self):
        source = """module test::typed_integer_expr_context;
fn main() -> u8 {
    return 254 + 1;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-int-expr-context>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "u8")

    def test_contextual_constant_integer_expression_rejects_overflow(self):
        source = """module test::typed_integer_expr_overflow;
fn main() -> u8 {
    return 255 + 1;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-int-expr-overflow>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_constant_integer_expression_respects_explicit_suffix(self):
        source = """module test::typed_integer_expr_suffix;
fn main() -> u8 {
    return 254i64 + 1;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-int-expr-suffix>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"return type mismatch in 'main': expected u8, got i64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_integer_literal_rejects_out_of_range(self):
        source = """module test::typed_integer_range;
fn main() -> void {
    let value: u8 = 256;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-int-range>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_integer_literal_respects_explicit_suffix(self):
        source = """module test::typed_integer_suffix;
fn main() -> void {
    let value: u32 = 1i64;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-int-suffix>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"let 'value' type mismatch: declared u32, got i64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_struct_literal_checks_contextual_integer_field_range(self):
        source = """module test::typed_struct_field_range;
struct Pixel { channel: u8; }
fn main() -> Pixel {
    return Pixel { channel: 256 };
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-struct-field-range>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_types_array_literal_and_index(self):
        source = """module test::typed_array;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1];
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-array>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        values = body.statements[0]
        indexed = body.statements[1]
        self.assertTrue(values.type.is_array)
        self.assertEqual(values.type.array_size, 3)
        self.assertIsNotNone(values.type.elem_type)
        self.assertEqual(values.type.elem_type.name, "i64")
        self.assertEqual(indexed.expr.kind, "Index")
        self.assertEqual(indexed.expr.type.name, "i64")

    def test_typed_body_types_defer_expression(self):
        source = """module test::typed_defer_expr;
fn cleanup() -> void { return; }
fn main() -> void {
    defer cleanup();
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-defer-expr>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].kind, "Defer")
        self.assertIsNotNone(body.statements[0].expr)
        self.assertEqual(body.statements[0].expr.kind, "Call")
        self.assertEqual(body.statements[0].expr.type.name, "void")

    def test_typed_body_types_defer_assignment(self):
        source = """module test::typed_defer_assign;
fn main() -> u8 {
    let value: u8 = 1;
    defer value = 2;
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-defer-assign>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        deferred = body.statements[1]
        self.assertEqual(deferred.kind, "DeferAssign")
        self.assertEqual(deferred.type.name, "u8")
        self.assertEqual(deferred.expr.type.name, "u8")

    def test_typed_body_types_defer_block(self):
        source = """module test::typed_defer_block;
fn cleanup() -> void { return; }
fn main() -> void {
    defer {
        cleanup();
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-defer-block>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        deferred = body.statements[0]
        self.assertEqual(deferred.kind, "Defer")
        self.assertEqual(len(deferred.body), 1)
        self.assertEqual(deferred.body[0].kind, "Expression")

    def test_typed_body_rejects_defer_assignment_range(self):
        source = """module test::typed_defer_range;
fn main() -> void {
    let value: u8 = 1;
    defer value = 256;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-defer-range>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_types_array_index_assignment(self):
        source = """module test::typed_array_assign;
fn main() -> u8 {
    let values: [u8; 3] = [1, 2, 3];
    values[1] = 7;
    return values[1];
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-array-assign>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        assign = body.statements[1]
        self.assertEqual(assign.kind, "Assign")
        self.assertEqual(assign.type.name, "u8")
        self.assertEqual(assign.expr.type.name, "u8")

    def test_typed_body_contextualizes_array_index_assignment_literal(self):
        source = """module test::typed_array_assign_context;
fn main() -> u16 {
    let values: [u16; 2] = [1, 2];
    values[0] = 65535;
    return values[0];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-assign-context>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[1].expr.type.name, "u16")

    def test_typed_body_rejects_array_index_assignment_range(self):
        source = """module test::typed_array_assign_range;
fn main() -> void {
    let values: [u8; 2] = [1, 2];
    values[0] = 256;
    return;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-assign-range>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_array_assignment_oob_target(self):
        source = """module test::typed_array_assign_oob;
fn main() -> void {
    let values = [1, 2];
    values[2] = 3;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-array-assign-oob>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index 2 out of bounds for length 2",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_types_repeat_array_literal(self):
        source = """module test::typed_repeat_array;
fn main() -> u32 {
    let values = [7u32; 4];
    return values[0];
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-repeat-array>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].type.array_size, 4)
        self.assertEqual(body.statements[1].expr.type.name, "u32")

    def test_typed_body_rejects_mixed_array_elements_independently(self):
        source = """module test::typed_array_mixed;
fn main() -> void {
    let values = [1, true];
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-array-mixed>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array literal element type mismatch: i64 vs bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_bootstrap_rejects_scalar_index_target(self):
        source = """module test::bootstrap_scalar_index_target;
fn read(value: u32) -> u32 {
    return value[0];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-bootstrap-scalar-index-target>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"indexação exige array ou ponteiro",
        ):
            bootstrap.check(parsed)

    def test_typed_body_rejects_scalar_index_target_independently(self):
        source = """module test::typed_scalar_index_target;
fn read(value: u32) -> u32 {
    return value[0];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-scalar-index-target>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"indexing requires array or pointer, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "read")

    def test_bootstrap_rejects_array_as_index(self):
        source = """module test::bootstrap_array_index_shape;
fn read(values: [u32; 2], index: [u32; 2]) -> u32 {
    return values[index];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-bootstrap-array-index-shape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"índice deve ser inteiro escalar",
        ):
            bootstrap.check(parsed)

    def test_bootstrap_rejects_reference_as_index(self):
        source = """module test::bootstrap_reference_index_shape;
fn read(values: [u32; 2], index: &u32) -> u32 {
    return values[index];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-bootstrap-reference-index-shape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"índice deve ser inteiro escalar",
        ):
            bootstrap.check(parsed)

    def test_typed_body_rejects_array_as_index_independently(self):
        source = """module test::typed_array_index_shape;
fn read(values: [u32; 2], index: [u32; 2]) -> u32 {
    return values[index];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-array-index-shape>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index must be scalar integer, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "read")

    def test_typed_body_rejects_reference_as_index_independently(self):
        source = """module test::typed_reference_index_shape;
fn read(values: [u32; 2], index: &u32) -> u32 {
    return values[index];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-reference-index-shape>"
        )
        typed_module = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index must be scalar integer, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed_module, "read")

    def test_typed_body_rejects_non_integer_array_index_independently(self):
        source = """module test::typed_array_bad_index;
fn main() -> i64 {
    let values = [1, 2];
    return values[true];
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-array-bad-index>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index must be scalar integer, got bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_constant_expression_array_index_oob(self):
        source = """module test::typed_array_constant_expr_bounds;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1 + 2];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-constant-expr-bounds>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index 3 out of bounds for length 3",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_constant_expression_array_index_in_range(self):
        source = """module test::typed_array_constant_expr_in_range;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1 + 1];
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-constant-expr-in-range>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[-1].expr.type.name, "i64")

    def test_typed_body_rejects_literal_array_index_out_of_bounds(self):
        source = """module test::typed_array_bounds;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[3];
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-array-bounds>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index 3 out of bounds for length 3",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_enforces_unary_operator_types(self):
        source = """module test::typed_unary_rules;
fn invert(bits: u32) -> u32 { return ~bits; }
fn negate(value: f64) -> f64 { return -value; }
fn flip(flag: bool) -> bool { return !flag; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-unary-rules>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "invert"
            ).statements[0].expr.type.name,
            "u32",
        )
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "negate"
            ).statements[0].expr.type.name,
            "f64",
        )
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "flip"
            ).statements[0].expr.type.name,
            "bool",
        )

    def test_typed_body_rejects_logical_not_on_integer_independently(self):
        source = """module test::typed_bad_logical_not;
fn main(value: u32) -> bool { return !value; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-logical-not>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"logical not requires bool, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_bitwise_not_on_bool_independently(self):
        source = """module test::typed_bad_bitwise_not;
fn main(flag: bool) -> bool { return ~flag; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-bitwise-not>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"bitwise not requires integer, got bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_unary_minus_on_signed_integer(self):
        source = """module test::typed_signed_unary_minus;
fn main(value: i32) -> i32 {
    return -value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-signed-unary-minus>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "i32")

    def test_typed_body_rejects_unary_minus_on_unsigned_integer(self):
        source = """module test::typed_unsigned_unary_minus;
fn main(value: u32) -> u32 {
    return -value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-unsigned-unary-minus>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"unary minus requires signed integer or float, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_explicit_negative_unsigned_literal(self):
        source = """module test::typed_negative_unsigned_suffix;
fn main() -> u8 {
    return -1u8;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-negative-unsigned-suffix>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"unary minus requires signed integer or float, got u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_unary_minus_on_bool_independently(self):
        source = """module test::typed_bad_unary_minus;
fn main(flag: bool) -> bool { return -flag; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-unary-minus>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"unary minus requires signed integer or float, got bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_enforces_binary_operator_types(self):
        source = """module test::typed_binary_rules;
fn arithmetic(value: u32) -> u32 { return value + 1; }
fn compare(value: usize) -> bool { return value > 0; }
fn logic(a: bool, b: bool) -> bool { return a && b; }
fn bits(value: u16) -> u16 { return value | 1; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-binary-rules>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "arithmetic"
            ).statements[0].expr.type.name,
            "u32",
        )
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "compare"
            ).statements[0].expr.type.name,
            "bool",
        )
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "logic"
            ).statements[0].expr.type.name,
            "bool",
        )
        self.assertEqual(
            typed_ast.build_linear_typed_body(
                parsed, typed, "bits"
            ).statements[0].expr.type.name,
            "u16",
        )

    def test_typed_body_rejects_negative_signed_right_shift(self):
        source = """module test::typed_negative_right_shift;
fn main() -> i8 {
    return -2i8 >> 1i8;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-negative-right-shift>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"right shift of negative signed integer is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_nonnegative_signed_right_shift(self):
        source = """module test::typed_nonnegative_right_shift;
fn main() -> i8 {
    return 4i8 >> 1i8;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-nonnegative-right-shift>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "i8")

    def test_typed_body_rejects_constant_left_shift_overflow(self):
        source = """module test::typed_left_shift_overflow;
fn main() -> u8 {
    return 128u8 << 1u8;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-left-shift-overflow>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_negative_signed_left_shift(self):
        source = """module test::typed_negative_left_shift;
fn main() -> i8 {
    return -1i8 << 1i8;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-negative-left-shift>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"left shift of negative signed integer is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_constant_left_shift_in_range(self):
        source = """module test::typed_left_shift_in_range;
fn main() -> u8 {
    return 1u8 << 7u8;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-left-shift-in-range>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "u8")

    def test_typed_body_rejects_shift_equal_to_integer_width(self):
        source = """module test::typed_shift_width;
fn main(value: u32) -> u32 {
    return value << 32;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-shift-width>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"shift count 32 out of range for u32 width 32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_negative_shift_count(self):
        source = """module test::typed_negative_shift;
fn main(value: i32) -> i32 {
    return value >> -1;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-negative-shift>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"shift count -1 out of range for i32 width 32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_shift_below_integer_width(self):
        source = """module test::typed_shift_in_range;
fn main(value: u32) -> u32 {
    return value << 31;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-shift-in-range>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "u32")

    def test_typed_body_rejects_logical_operator_on_integer_independently(self):
        source = """module test::typed_bad_logic;
fn main(value: u32) -> bool { return value && value; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-logic>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"logical operator '&&' requires bool operands",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_constant_unsigned_add_overflow(self):
        source = """module test::typed_u8_add_overflow;
fn main() -> u8 {
    return 255u8 + 1u8;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-u8-add-overflow>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_constant_signed_multiply_overflow(self):
        source = """module test::typed_i8_mul_overflow;
fn main() -> i8 {
    return 64i8 * 2i8;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-i8-mul-overflow>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 128 out of range for i8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_constant_integer_arithmetic_in_range(self):
        source = """module test::typed_u8_add_in_range;
fn main() -> u8 {
    return 254u8 + 1u8;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-u8-add-in-range>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "u8")

    def test_typed_body_rejects_signed_minimum_division_by_minus_one(self):
        source = """module test::typed_i8_div_overflow;
fn main() -> i8 {
    return -128i8 / -1i8;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-i8-div-overflow>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer division overflow for i8 minimum divided by -1",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_signed_minimum_modulo_by_minus_one(self):
        source = """module test::typed_i8_mod_overflow;
fn main() -> i8 {
    return -128i8 % -1i8;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-i8-mod-overflow>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer modulo overflow for i8 minimum divided by -1",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_accepts_signed_minimum_division_by_one(self):
        source = """module test::typed_i8_div_in_range;
fn main() -> i8 {
    return -128i8 / 1i8;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-i8-div-in-range>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "i8")

    def test_typed_body_rejects_integer_division_by_literal_zero(self):
        source = """module test::typed_integer_div_zero;
fn main(value: u32) -> u32 {
    return value / 0;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-integer-div-zero>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer division by zero is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_integer_modulo_by_literal_zero(self):
        source = """module test::typed_integer_mod_zero;
fn main(value: i32) -> i32 {
    return value % 0;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-integer-mod-zero>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer modulo by zero is not allowed",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_arithmetic_on_integer_arrays(self):
        source = """module test::typed_array_arithmetic;
fn main(left: [u32; 2], right: [u32; 2]) -> [u32; 2] {
    return left + right;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-arithmetic>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"arithmetic operator '\+' requires numeric operands",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_relational_integer_arrays(self):
        source = """module test::typed_array_relational;
fn main(left: [u32; 2], right: [u32; 2]) -> bool {
    return left < right;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-relational>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"relational operator '<' requires numeric operands",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_bitwise_integer_arrays(self):
        source = """module test::typed_array_bitwise;
fn main(left: [u32; 2], right: [u32; 2]) -> [u32; 2] {
    return left & right;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-bitwise>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"bitwise operator '&' requires integer operands",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_shift_on_integer_arrays(self):
        source = """module test::typed_array_shift;
fn main(left: [u32; 2], right: [u32; 2]) -> [u32; 2] {
    return left << right;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-array-shift>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"shift operator '<<' requires integer operands",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_arithmetic_on_bool_independently(self):
        source = """module test::typed_bad_arithmetic;
fn main(flag: bool) -> bool { return flag + flag; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-arithmetic>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"arithmetic operator '\+' requires numeric operands",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_relational_mixed_explicit_integer_types(self):
        source = """module test::typed_bad_compare;
fn main(left: u32, right: u64) -> bool { return left < right; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-compare>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"relational operator '<' type mismatch: u32 vs u64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_allows_pointer_equality_with_null(self):
        source = """module test::typed_pointer_null;
fn is_null(ptr: *const u8) -> bool { return ptr == null; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-pointer-null>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "is_null")
        self.assertEqual(body.statements[0].expr.type.name, "bool")

    def test_typed_body_validates_explicit_numeric_casts(self):
        source = """module test::typed_cast_numeric;
fn widen(value: u16) -> u64 {
    return value as u64;
}
fn to_float(value: i32) -> f64 {
    return value as f64;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-cast-numeric>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        widen = typed_ast.build_linear_typed_body(parsed, typed, "widen")
        to_float = typed_ast.build_linear_typed_body(parsed, typed, "to_float")
        self.assertEqual(widen.statements[0].expr.kind, "Cast")
        self.assertEqual(widen.statements[0].expr.type.name, "u64")
        self.assertEqual(to_float.statements[0].expr.type.name, "f64")

    def test_reference_to_raw_pointer_cast_requires_unsafe(self):
        source = """module test::reference_pointer_cast_requires_unsafe;
fn expose(value: &mut u32) -> *mut u32 {
    return value as *mut u32;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-pointer-cast-requires-unsafe>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"conversão de referência para ponteiro cru exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_reference_to_raw_pointer_cast_inside_unsafe_is_valid(self):
        source = """module test::reference_pointer_cast_unsafe;
fn expose(value: &mut u32) -> *mut u32 {
    unsafe {
        return value as *mut u32;
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-reference-pointer-cast-unsafe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "expose")
        cast = body.statements[0].body[0].expr
        self.assertEqual(cast.kind, "Cast")
        self.assertEqual(cast.type.name, "u32")
        self.assertTrue(cast.type.pointer)
        self.assertTrue(cast.type.mutable)
        self.assertFalse(cast.type.is_reference)

    def test_integer_to_pointer_cast_requires_unsafe(self):
        source = """module test::integer_pointer_cast_requires_unsafe;
fn from_addr(addr: usize) -> *mut u32 {
    return addr as *mut u32;
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-integer-pointer-cast-requires-unsafe>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"conversão de inteiro para ponteiro exige bloco unsafe",
        ):
            bootstrap.check(parsed)

    def test_integer_to_pointer_cast_inside_unsafe_is_valid(self):
        source = """module test::integer_pointer_cast_unsafe;
fn from_addr(addr: usize) -> *mut u32 {
    unsafe {
        return addr as *mut u32;
    }
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-integer-pointer-cast-unsafe>"
        )
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "from_addr")
        cast = body.statements[0].body[0].expr
        self.assertEqual(cast.kind, "Cast")
        self.assertEqual(cast.type.name, "u32")
        self.assertTrue(cast.type.pointer)
        self.assertTrue(cast.type.mutable)

    def test_typed_body_validates_pointer_requalification_cast(self):
        source = """module test::typed_cast_pointer;
fn readonly(ptr: *mut u32) -> *const u32 {
    return ptr as *const u32;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-cast-pointer>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "readonly")
        self.assertTrue(body.statements[0].expr.type.pointer)
        self.assertFalse(body.statements[0].expr.type.mutable)
        self.assertEqual(body.statements[0].expr.type.name, "u32")

    def test_typed_body_rejects_bool_to_integer_cast_independently(self):
        source = """module test::typed_cast_bool;
fn main(flag: bool) -> u32 {
    return flag as u32;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-cast-bool>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"invalid cast from bool to u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_struct_to_integer_cast_independently(self):
        source = """module test::typed_cast_struct;
struct Point { x: u32; }
fn main(point: Point) -> u64 {
    return point as u64;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-cast-struct>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"invalid cast from Point to u64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_resolves_declared_method_call(self):
        source = """module test::typed_method;
struct Counter {
    value: u32;
    fn increment(self: *mut Counter, amount: u32) -> u32 {
        unsafe { return self.value + amount; }
    }
}
fn main() -> u32 {
    let counter = Counter { value: 1 };
    return counter.increment(2);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        call = body.statements[-1].expr
        self.assertEqual(call.kind, "MethodCall")
        self.assertEqual(call.type.name, "u32")
        self.assertEqual(call.label, "Counter.increment")

    def test_typed_body_contextualizes_method_integer_argument(self):
        source = """module test::typed_method_arg;
struct Counter {
    value: u32;
    fn increment(self: *mut Counter, amount: u16) -> u16 {
        return amount;
    }
}
fn main() -> u16 {
    let counter = Counter { value: 1 };
    return counter.increment(7);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method-arg>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[-1].expr.type.name, "u16")

    def test_typed_body_rejects_unknown_method_independently(self):
        source = """module test::typed_method_unknown;
struct Counter { value: u32; }
fn main(counter: Counter) -> u32 {
    return counter.missing();
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method-unknown>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"cannot type unknown method Counter\.missing",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_method_argument_mismatch_independently(self):
        source = """module test::typed_method_bad_arg;
struct Counter {
    value: u32;
    fn increment(self: *mut Counter, amount: u32) -> u32 {
        return amount;
    }
}
fn main(counter: Counter, flag: bool) -> u32 {
    return counter.increment(flag);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method-bad-arg>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"method Counter\.increment argument type mismatch: expected u32, got bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_array_literal_fits_declared_element_type(self):
        source = """module test::typed_array_context;
fn main() -> [u8; 3] {
    let values: [u8; 3] = [1, 2, 3];
    return values;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-array-context>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        array_type = body.statements[0].type
        self.assertTrue(array_type.is_array)
        self.assertEqual(array_type.array_size, 3)
        self.assertIsNotNone(array_type.elem_type)
        self.assertEqual(array_type.elem_type.name, "u8")
        self.assertEqual(body.statements[0].expr.type, array_type)

    def test_contextual_array_literal_rejects_length_mismatch(self):
        source = """module test::typed_array_length;
fn main() -> void {
    let values: [u8; 3] = [1, 2];
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-array-length>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array length mismatch: expected 3, got 2",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_array_literal_rejects_element_range(self):
        source = """module test::typed_array_element_range;
fn main() -> void {
    let values: [u8; 2] = [1, 256];
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-array-element-range>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_array_literal_applies_to_call_argument(self):
        source = """module test::typed_array_call;
fn consume(values: [u16; 2]) -> u16 {
    return values[0];
}
fn main() -> u16 {
    return consume([1, 2]);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-array-call>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "u16")

    def test_contextual_negative_integer_literal_fits_signed_type(self):
        source = """module test::typed_negative_context;
fn main() -> i8 {
    let value: i8 = -128;
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-negative-context>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].type.name, "i8")
        self.assertEqual(body.statements[0].expr.type.name, "i8")

    def test_contextual_negative_integer_literal_rejects_unsigned(self):
        source = """module test::typed_negative_unsigned;
fn main() -> void {
    let value: u8 = -1;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-negative-unsigned>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value -1 out of range for u8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_contextual_negative_integer_literal_rejects_signed_underflow(self):
        source = """module test::typed_negative_underflow;
fn main() -> void {
    let value: i8 = -129;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-negative-underflow>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value -129 out of range for i8",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_negative_literal_array_index(self):
        source = """module test::typed_negative_index;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[-1];
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-negative-index>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index -1 out of bounds for length 3",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_ownership_summary_records_method_call_edge(self):
        source = """module test::ownership_method_edge;
struct Counter { value: u32; }
impl Counter {
    fn increment(self: *mut Counter, amount: u32) -> u32 {
        return amount;
    }
}
fn main(counter: Counter) -> u32 {
    return counter.increment(1);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method-edge>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        summaries = {
            item.name: item
            for item in typed_ast.summarize_module_ownership(parsed, typed)
        }
        self.assertIn("Counter_increment", summaries["main"].calls)

    def test_ownership_method_call_moves_sole_argument(self):
        source = """module test::ownership_method_move;
sole struct Token { value: u32; }
struct Consumer { value: u32; }
impl Consumer {
    fn take(self: *mut Consumer, token: Token) -> void {
        return;
    }
}
fn main(consumer: Consumer) -> void {
    let token = Token { value: 1 };
    consumer.take(move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertTrue(
            any(
                event.kind == "move"
                and event.name == "token"
                and event.via == "method:Consumer_take"
                for event in trace.events
            )
        )

    def test_ownership_method_call_rejects_reusing_moved_argument(self):
        source = """module test::ownership_method_reuse;
sole struct Token { value: u32; }
struct Consumer { value: u32; }
impl Consumer {
    fn take(self: *mut Consumer, token: Token) -> void {
        return;
    }
}
fn main(consumer: Consumer) -> void {
    let token = Token { value: 1 };
    consumer.take(move token);
    consumer.take(move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-method-reuse>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_asm_requires_live_sole_operands(self):
        source = """module test::ownership_asm_live;
sole struct Token { value: u32; }
fn main(token: Token) -> void {
    asm("nop" : token.value : token.value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-asm-live>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)
        self.assertIn(
            typed_ast.OwnershipEvent("asm", "main", "operands"),
            trace.events,
        )

    def test_ownership_asm_rejects_input_from_moved_owner(self):
        source = """module test::ownership_asm_input_moved;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    consume(move token);
    asm("nop" : : token.value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-asm-input-moved>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_asm_rejects_output_through_moved_owner(self):
        source = """module test::ownership_asm_output_moved;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    consume(move token);
    asm("nop" : token.value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-asm-output-moved>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_asm_rejects_explicit_sole_move(self):
        source = """module test::ownership_asm_move;
sole struct Token { value: u32; }
fn main(token: Token) -> void {
    asm("nop" : : move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-asm-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"inline asm cannot transfer sole ownership",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_defer_reserves_moved_sole_value(self):
        source = """module test::ownership_defer_move;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    defer consume(move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-defer-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertIn(
            typed_ast.OwnershipEvent("defer", "main", "call"),
            trace.events,
        )
        self.assertIn(
            typed_ast.OwnershipEvent("move", "token", "call:consume"),
            trace.events,
        )

    def test_ownership_defer_rejects_use_after_reserved_move(self):
        source = """module test::ownership_defer_reuse;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    defer consume(move token);
    consume(move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-defer-reuse>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_defer_rejects_read_only_sole_capture(self):
        source = """module test::ownership_defer_read;
sole struct Token { value: u32; }
fn inspect(value: u32) -> void { return; }
fn main(token: Token) -> void {
    defer inspect(token.value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-defer-read>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"defer captures sole value 'token' without ownership transfer",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_unsafe_block_propagates_move(self):
        source = """module test::ownership_unsafe_move;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    unsafe {
        consume(move token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-unsafe-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertIn(
            typed_ast.OwnershipEvent("unsafe", "main", "block"),
            trace.events,
        )
        self.assertIn(
            typed_ast.OwnershipEvent("move", "token", "call:consume"),
            trace.events,
        )

    def test_ownership_unsafe_block_rejects_use_after_move(self):
        source = """module test::ownership_unsafe_reuse;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    unsafe {
        consume(move token);
        consume(move token);
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-unsafe-reuse>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_unsafe_block_drops_local_bindings(self):
        source = """module test::ownership_unsafe_scope;
sole struct Token { value: u32; }
fn main(token: Token) -> void {
    unsafe {
        let local = Token { value: 1 };
    }
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-unsafe-scope>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.LIVE)
        self.assertIsNone(trace.final_env.state_of("local"))

    def test_ownership_returned_call_moves_sole_argument(self):
        source = """module test::ownership_return_call;
sole struct Token { value: u32; }
fn relay(token: Token) -> Token { return token; }
fn main(token: Token) -> Token {
    return relay(move token);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-return-call>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        typed_ast.build_linear_typed_body(parsed, typed, "main")
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertIn(
            typed_ast.OwnershipEvent("move", "token", "call:relay"),
            trace.events,
        )

    def test_ownership_returned_method_moves_sole_argument(self):
        source = """module test::ownership_return_method;
sole struct Token { value: u32; }
struct Consumer { value: u32; }
impl Consumer {
    fn relay(self: *mut Consumer, token: Token) -> Token {
        return token;
    }
}
fn main(consumer: Consumer, token: Token) -> Token {
    return consumer.relay(move token);
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-return-method>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        typed_ast.build_linear_typed_body(parsed, typed, "main")
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertIn(
            typed_ast.OwnershipEvent(
                "move", "token", "method:Consumer_relay"
            ),
            trace.events,
        )

    def test_ownership_assignment_moves_direct_sole_source(self):
        source = """module test::ownership_assign_move;
sole struct Token { value: u32; }
fn main(first: Token, second: Token) -> void {
    first = move second;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-assign-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("first"), typed_ast.VarState.LIVE)
        self.assertIs(trace.final_env.state_of("second"), typed_ast.VarState.MOVED)
        self.assertIn(
            typed_ast.OwnershipEvent("move", "second", "assign:first"),
            trace.events,
        )

    def test_ownership_assignment_rejects_reinitializing_moved_target(self):
        source = """module test::ownership_assign_reinit;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(first: Token, second: Token) -> void {
    consume(move first);
    first = move second;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-assign-reinit>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'first' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_assignment_rejects_read_from_moved_owner(self):
        source = """module test::ownership_assign_read;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    let value: u32 = 0;
    consume(move token);
    value = token.value;
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-assign-read>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_ownership_try_wrapped_call_moves_sole_argument(self):
        source = """module test::ownership_try_call_move;
sole struct Token { value: u32; }
fn consume(token: Token, result: ResultU32) -> ResultU32 { return result; }
fn main(result: ResultU32) -> ResultU32 {
    let token = Token { value: 1 };
    let payload: u32 = consume(move token, result)?;
    return result;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-try-call-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        typed_ast.build_linear_typed_body(parsed, typed, "main")
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertTrue(
            any(
                event.kind == "move"
                and event.name == "token"
                and event.via == "call:consume"
                for event in trace.events
            )
        )

    def test_ownership_try_wrapped_method_moves_sole_argument(self):
        source = """module test::ownership_try_method_move;
sole struct Token { value: u32; }
struct Consumer { value: u32; }
impl Consumer {
    fn take(
        self: *mut Consumer,
        token: Token,
        result: ResultU32
    ) -> ResultU32 {
        return result;
    }
}
fn main(consumer: Consumer, result: ResultU32) -> ResultU32 {
    let token = Token { value: 1 };
    let payload: u32 = consumer.take(move token, result)?;
    return result;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-try-method-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        typed_ast.build_linear_typed_body(parsed, typed, "main")
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)
        self.assertTrue(
            any(
                event.kind == "move"
                and event.name == "token"
                and event.via == "method:Consumer_take"
                for event in trace.events
            )
        )

    def test_ownership_try_wrapped_call_rejects_reuse(self):
        source = """module test::ownership_try_call_reuse;
sole struct Token { value: u32; }
fn consume(token: Token, result: ResultU32) -> ResultU32 { return result; }
fn main(result: ResultU32) -> ResultU32 {
    let token = Token { value: 1 };
    let first: u32 = consume(move token, result)?;
    let second: u32 = consume(move token, result)?;
    return result;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-try-call-reuse>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        typed_ast.build_linear_typed_body(parsed, typed, "main")
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_explicit_move_expression_types_sole_value(self):
        source = """module test::typed_move;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-explicit-move>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        call = body.statements[1].expr
        self.assertEqual(call.kind, "Call")
        trace = typed_ast.analyze_function_ownership(parsed, typed, "main")
        self.assertIs(trace.final_env.state_of("token"), typed_ast.VarState.MOVED)

    def test_explicit_move_rejects_non_sole_value_independently(self):
        source = """module test::typed_move_nonsole;
fn consume(value: u32) -> void { return; }
fn main() -> void {
    let value: u32 = 1;
    consume(move value);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-move-nonsole>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"move requires sole value, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_explicit_move_detects_use_after_move(self):
        source = """module test::typed_move_after;
sole struct Token { value: u32; }
fn consume(token: Token) -> void { return; }
fn main() -> void {
    let token = Token { value: 1 };
    consume(move token);
    consume(move token);
    return;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-move-after>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            typed_ast.analyze_function_ownership(parsed, typed, "main")

    def test_typed_declarations_preserve_enum_variants(self):
        source = """module test::typed_enum_decl;
pub enum Mode {
    Off = 0,
    On = 1,
}
fn main() -> Mode { return Mode::On; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-enum-decl>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        self.assertEqual(len(typed.enums), 1)
        self.assertEqual(typed.enums[0].name, "Mode")
        self.assertEqual(
            [(item.name, item.value) for item in typed.enums[0].variants],
            [("Off", 0), ("On", 1)],
        )

    def test_typed_body_types_enum_access(self):
        source = """module test::typed_enum_access;
enum Mode {
    Off,
    On,
}
fn main() -> Mode { return Mode::On; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-enum-access>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.kind, "EnumAccess")
        self.assertEqual(body.statements[0].expr.type.name, "Mode")
        self.assertEqual(body.statements[0].expr.label, "Mode::On")

    def test_typed_body_rejects_unknown_enum_independently(self):
        source = """module test::typed_enum_unknown;
fn main() -> Missing { return Missing::Value; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-enum-unknown>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"unknown enum type 'Missing'",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_unknown_enum_variant_independently(self):
        source = """module test::typed_enum_variant;
enum Mode {
    Off,
    On,
}
fn main() -> Mode { return Mode::Missing; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-enum-variant>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"enum 'Mode' has no variant 'Missing'",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_types_try_result_u32(self):
        source = """module test::typed_try_u32;
fn passthrough(value: ResultU32) -> ResultU32 { return value; }
fn main(value: ResultU32) -> ResultU32 {
    let payload: u32 = passthrough(value)?;
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-try-u32>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.kind, "TryExpr")
        self.assertEqual(body.statements[0].expr.type.name, "u32")

    def test_typed_body_types_try_result_i32(self):
        source = """module test::typed_try_i32;
fn passthrough(value: ResultI32) -> ResultI32 { return value; }
fn main(value: ResultI32) -> ResultI32 {
    let payload: i32 = passthrough(value)?;
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-try-i32>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.kind, "TryExpr")
        self.assertEqual(body.statements[0].expr.type.name, "i32")

    def test_typed_body_rejects_try_on_non_result_independently(self):
        source = """module test::typed_try_non_result;
fn passthrough(value: u32) -> u32 { return value; }
fn main(value: u32) -> u32 {
    return passthrough(value)?;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-try-non-result>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"try operator requires Result value, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_try_when_caller_cannot_propagate_result(self):
        source = """module test::typed_try_bad_caller;
fn passthrough(value: ResultU32) -> ResultU32 { return value; }
fn main(value: ResultU32) -> u32 {
    let payload: u32 = passthrough(value)?;
    return payload;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-try-bad-caller>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"try operator in 'main' requires enclosing function to return "
            r"ResultU32, got u32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_typed_body_rejects_try_with_different_result_wrapper(self):
        source = """module test::typed_try_wrong_wrapper;
fn passthrough(value: ResultU32) -> ResultU32 { return value; }
fn main(value: ResultU32, other: ResultI32) -> ResultI32 {
    let payload: u32 = passthrough(value)?;
    return other;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-try-wrong-wrapper>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"try operator in 'main' requires enclosing function to return "
            r"ResultU32, got ResultI32",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_ownership_summary_records_call_wrapped_by_try(self):
        source = """module test::ownership_try_edge;
fn passthrough(value: ResultU32) -> ResultU32 { return value; }
fn main(value: ResultU32) -> ResultU32 {
    let payload: u32 = passthrough(value)?;
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-ownership-try-edge>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        summaries = {
            item.name: item
            for item in typed_ast.summarize_module_ownership(parsed, typed)
        }
        self.assertIn("passthrough", summaries["main"].calls)

    def test_typed_body_types_if_expression(self):
        source = """module test::typed_if_expr;
fn choose(flag: bool) -> i64 {
    let value = if flag { 1 } else { 2 };
    return value;
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-if-expr>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "choose")
        self.assertEqual(body.statements[0].expr.kind, "IfExpr")
        self.assertEqual(body.statements[0].expr.type.name, "i64")

    def test_typed_body_rejects_non_bool_if_expression_condition_independently(self):
        source = """module test::typed_if_expr_bad_condition;
fn choose() -> i64 {
    return if 1 { 1 } else { 2 };
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-if-expr-bad-condition>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"if expression condition must be bool, got i64",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "choose")

    def test_typed_body_rejects_if_expression_branch_mismatch_independently(self):
        source = """module test::typed_if_expr_bad_branches;
fn choose(flag: bool) -> i64 {
    return if flag { 1 } else { true };
}
"""
        parsed = bootstrap.parse(
            source, filename="<phase1-typed-if-expr-bad-branches>"
        )
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"if expression branch type mismatch: i64 vs bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "choose")

    def test_struct_literal_validates_field_shape(self):
        source = """module test::typed_struct_shape;
struct Pair { left: u32; right: u32; }
fn main() -> Pair {
    return Pair { left: 1, right: 2 };
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-struct-shape>")
        bootstrap.check(parsed)
        typed = typed_ast.build_declaration_typed_ast(parsed)
        body = typed_ast.build_linear_typed_body(parsed, typed, "main")
        self.assertEqual(body.statements[0].expr.type.name, "Pair")

    def test_struct_literal_rejects_unknown_field_independently(self):
        source = """module test::typed_struct_unknown;
struct Pair { left: u32; right: u32; }
fn main() -> Pair {
    return Pair { left: 1, wrong: 2 };
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-struct-unknown>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"unknown field 'wrong' in struct literal 'Pair'",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_struct_literal_rejects_missing_field_independently(self):
        source = """module test::typed_struct_missing;
struct Pair { left: u32; right: u32; }
fn main() -> Pair {
    return Pair { left: 1 };
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-struct-missing>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"missing field\(s\) in struct literal 'Pair': right",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_struct_literal_rejects_duplicate_field_independently(self):
        source = """module test::typed_struct_duplicate;
struct Pair { left: u32; right: u32; }
fn main() -> Pair {
    return Pair { left: 1, left: 2, right: 3 };
}
"""
        parsed = bootstrap.parse(source, filename="<phase1-typed-struct-duplicate>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"duplicate field 'left' in struct literal 'Pair'",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

    def test_conditional_move_in_one_branch_becomes_maybe_moved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        base = typed_ast.OwnershipEnv().declare(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        merged = typed_ast.merge_conditional_ownership(
            base, ("handle",), ()
        )
        self.assertIs(
            merged.state_of("handle"),
            typed_ast.VarState.MAYBE_MOVED,
        )

    def test_conditional_move_in_both_branches_becomes_moved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        base = typed_ast.OwnershipEnv().declare(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        merged = typed_ast.merge_conditional_ownership(
            base, ("handle",), ("handle",)
        )
        self.assertIs(merged.state_of("handle"), typed_ast.VarState.MOVED)

    def test_loop_move_is_rejected_without_reinitialization(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        base = typed_ast.OwnershipEnv().declare(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"sole value 'handle' moved inside loop without reinitialization",
        ):
            typed_ast.validate_loop_ownership(base, ("handle",))
        self.assertIs(base.state_of("handle"), typed_ast.VarState.LIVE)

    def test_empty_loop_body_preserves_ownership(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        base = typed_ast.OwnershipEnv().declare(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        result = typed_ast.validate_loop_ownership(base, ())
        self.assertEqual(result, base)

    def test_ownership_env_tracks_only_sole_bindings(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        env = typed_ast.OwnershipEnv()
        env = env.declare("handle", typed_ast.SemanticType("Handle"), typed)
        env2 = env.declare("count", typed_ast.SemanticType("u32"), typed)
        self.assertIs(env2.state_of("handle"), typed_ast.VarState.LIVE)
        self.assertIsNone(env2.state_of("count"))

    def test_ownership_env_move_invalidates_only_source_binding(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        env = typed_ast.OwnershipEnv().declare(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        moved = env.move("handle")
        self.assertIs(env.state_of("handle"), typed_ast.VarState.LIVE)
        self.assertIs(moved.state_of("handle"), typed_ast.VarState.MOVED)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'handle' after move",
        ):
            moved.require_live("handle")

    def test_ownership_env_branch_merge_produces_maybe_moved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        base = typed_ast.OwnershipEnv().declare(
            "handle", typed_ast.SemanticType("Handle"), typed
        )
        merged = base.move("handle").merge(base)
        self.assertIs(
            merged.state_of("handle"),
            typed_ast.VarState.MAYBE_MOVED,
        )

    def test_ownership_env_rejects_untracked_move(self):
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"ownership binding 'x' is not tracked",
        ):
            typed_ast.OwnershipEnv().move("x")

    def test_sole_move_state_transitions_live_to_moved(self):
        state = typed_ast.move_state("handle", typed_ast.VarState.LIVE)
        self.assertIs(state, typed_ast.VarState.MOVED)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'handle' after move",
        ):
            typed_ast.move_state("handle", state)

    def test_branch_merge_marks_one_sided_move_as_maybe_moved(self):
        state = typed_ast.merge_branch_states(
            typed_ast.VarState.MOVED,
            typed_ast.VarState.LIVE,
        )
        self.assertIs(state, typed_ast.VarState.MAYBE_MOVED)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"after conditional move",
        ):
            typed_ast.require_live("token", state)

    def test_branch_merge_keeps_two_sided_move_as_moved(self):
        state = typed_ast.merge_branch_states(
            typed_ast.VarState.MOVED,
            typed_ast.VarState.MOVED,
        )
        self.assertIs(state, typed_ast.VarState.MOVED)

    def test_live_state_remains_usable(self):
        typed_ast.require_live("value", typed_ast.VarState.LIVE)

    def test_unsigned_integer_bounds_are_exact(self):
        u8 = typed_ast.SemanticType("u8")
        self.assertEqual(typed_ast.integer_bounds(u8), (0, 255))
        typed_ast.validate_integer_value(0, u8)
        typed_ast.validate_integer_value(255, u8)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value 256 out of range for u8",
        ):
            typed_ast.validate_integer_value(256, u8)

    def test_signed_integer_bounds_are_exact(self):
        i8 = typed_ast.SemanticType("i8")
        self.assertEqual(typed_ast.integer_bounds(i8), (-128, 127))
        typed_ast.validate_integer_value(-128, i8)
        typed_ast.validate_integer_value(127, i8)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer value -129 out of range for i8",
        ):
            typed_ast.validate_integer_value(-129, i8)

    def test_integer_validator_rejects_non_integer_type(self):
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"integer type expected, got bool",
        ):
            typed_ast.integer_bounds(typed_ast.SemanticType("bool"))

    def test_direct_recursive_value_type_is_rejected(self):
        typed = self.typed_from("""module test::recursive;
struct Node {
    next: Node;
}
fn main() -> void { return; }
""")
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: Node -> Node",
        ):
            typed_ast.validate_no_recursive_value_types(typed)

    def test_indirect_recursive_value_type_is_rejected(self):
        typed = self.typed_from("""module test::recursive_indirect;
struct Left {
    right: Right;
}
struct Right {
    left: Left;
}
fn main() -> void { return; }
""")
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: (Left -> Right -> Left|Right -> Left -> Right)",
        ):
            typed_ast.validate_no_recursive_value_types(typed)

    def test_pointer_indirection_breaks_recursive_value_cycle(self):
        typed = self.typed_from("""module test::recursive_pointer;
struct Node {
    next: *mut Node;
}
fn main() -> void { return; }
""")
        typed_ast.validate_no_recursive_value_types(typed)
        self.assertTrue(typed.structs[0].fields[0].type.pointer)

    def test_global_type_and_storage_facts_are_preserved(self):
        typed = typed_ast.build_declaration_typed_ast(self.checked_ast())
        limit = typed.globals[0]
        self.assertEqual(limit.name, "LIMIT")
        self.assertEqual(limit.type.name, "u32")
        self.assertTrue(limit.is_const)
        self.assertFalse(limit.is_mut)


if __name__ == "__main__":
    unittest.main()