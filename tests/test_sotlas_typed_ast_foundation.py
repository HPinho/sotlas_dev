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
            r"array index must be integer, got bool",
        ):
            typed_ast.build_linear_typed_body(parsed, typed, "main")

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

    def test_typed_body_rejects_unary_minus_on_bool_independently(self):
        source = """module test::typed_bad_unary_minus;
fn main(flag: bool) -> bool { return -flag; }
"""
        parsed = bootstrap.parse(source, filename="<phase1-bad-unary-minus>")
        typed = typed_ast.build_declaration_typed_ast(parsed)
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"unary minus requires numeric operand, got bool",
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