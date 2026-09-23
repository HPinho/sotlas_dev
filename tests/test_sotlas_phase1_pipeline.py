"""Public opt-in Phase-1 pipeline integration tests."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_canonical_package():
    """Load the production package under a unique test name.

    Some legacy tests prepend ROOT/tools to sys.path, where a compatibility
    package with the same top-level name exists. Loading by explicit package
    path keeps this integration test pinned to compiler/sotlas_compile without
    mutating or depending on global test discovery order.
    """
    name = "sotlas_phase1_public_package"
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
typed_ast = importlib.import_module(f"{sotlas_compile.__name__}.typed_ast")
try:
    _shared_sir_package = importlib.import_module("sotlas.sir")
except ImportError:
    sir_name = "sotlas_phase1_sir_package"
    sir_spec = importlib.util.spec_from_file_location(
        sir_name,
        ROOT / "compiler" / "sotlas" / "sir" / "__init__.py",
        submodule_search_locations=[str(ROOT / "compiler" / "sotlas" / "sir")],
    )
    assert sir_spec is not None and sir_spec.loader is not None
    sir_module = importlib.util.module_from_spec(sir_spec)
    sys.modules[sir_name] = sir_module
    sir_spec.loader.exec_module(sir_module)
    _shared_sir_package = sir_module
RetainInst = _shared_sir_package.RetainInst
DirectAccessInst = _shared_sir_package.DirectAccessInst
generate_checked_ownership_sir = (
    _shared_sir_package.generate_checked_ownership_sir
)
CallInst, DestroyInst, ReleaseInst, ReturnInst, ShareInst = (
    _shared_sir_package.CallInst, _shared_sir_package.DestroyInst,
    _shared_sir_package.ReleaseInst, _shared_sir_package.ReturnInst,
    _shared_sir_package.ShareInst,
)


class SotlasPhase1PipelineTests(unittest.TestCase):
    def test_public_phase1_pipeline_is_explicit_and_preserves_bootstrap_check(self):
        source = """module test::phase1_public;
sole struct Token { value: u32; }

fn read(t: Token) -> u32 {
    return t.value;
}
"""
        check_before = sotlas_compile.bootstrap.check
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-public>"
        )
        self.assertIs(sotlas_compile.bootstrap.check, check_before)
        self.assertEqual(result.semantic.maturity, typed_ast.MATURITY)
        self.assertEqual(
            result.semantic.typed_module.maturity, typed_ast.MATURITY
        )
        self.assertEqual(result.semantic.typed_module.structs[0].name, "Token")
        self.assertEqual(result.semantic.bodies[0].name, "read")

    def test_public_phase1_pipeline_exposes_composed_ownership_sir(self):
        source = """module test::phase1_ownership_sir;
sole struct Token { value: u32; }

fn isolate(token: Token) -> void {
    quarantine token;
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-ownership-sir>"
        )

        self.assertEqual(
            tuple(item.function for item in result.ownership_sir.functions),
            ("isolate",),
        )
        function_plan = result.ownership_sir.functions[0]
        self.assertEqual(len(function_plan.domain.instructions), 1)
        transfer = function_plan.domain.instructions[0]
        self.assertEqual(transfer.operation, "quarantine")
        self.assertEqual(transfer.source_domain, "exclusive")
        self.assertEqual(transfer.target_domain, "island")
        self.assertEqual(function_plan.shared.semantic, ())
        graph_transfer = result.semantic.ownership_domains.transfers[0]
        self.assertEqual(graph_transfer.via, "quarantine")
        self.assertEqual(
            transfer.source.name, graph_transfer.binding
        )
        self.assertEqual(
            transfer.point_id, graph_transfer.point_id
        )
        self.assertTrue(transfer.point_id.startswith("quarantine@"))

    def test_public_phase1_pipeline_exposes_canonical_shared_graph_account(self):
        source = """module test::phase1_shared_graph;
sole struct Token { value: u32; }

fn main(token: Token) -> void {
    let peer = share token;
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-shared-graph>"
        )
        graph = result.semantic.ownership_domains
        self.assertEqual(len(graph.planned_transitions), 1)
        self.assertEqual(len(graph.shared_accounts), 1)
        account = graph.shared_accounts[0]
        self.assertEqual(account.function, "main")
        self.assertEqual(account.binding, "token")
        self.assertEqual(account.owners, ("token", "peer"))
        self.assertEqual(account.strong_refs, 2)
        self.assertTrue(account.point_id.startswith("share@"))

    def test_public_phase1_pipeline_rejects_duplicate_quarantine_point(self):
        from sotlas_phase1_public_package import typed_ast

        source = """module test::phase1_duplicate_quarantine;
sole struct Token { value: u32; }
fn main(token: Token) -> void {
    quarantine token;
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-duplicate-quarantine>"
        )
        trace = result.semantic.ownership.traces[0][1]
        duplicate = typed_ast.OwnershipEvent(
            "quarantine", "token", "quarantine",
            typed_ast.OwnershipDomain.ISLAND,
            point_id="quarantine@4:5",
            type=typed_ast.SemanticType("Token"),
            source_domain=typed_ast.OwnershipDomain.EXCLUSIVE,
            target_domain=typed_ast.OwnershipDomain.ISLAND,
        )
        malformed = typed_ast.OwnershipModuleAnalysis(
            result.semantic.ownership.summaries,
            (("main", typed_ast.OwnershipTrace(
                trace.final_env, trace.events + (duplicate,),
                trace.shared_cleanup,
            )),),
        )
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            "duplicate ownership transfer point 'quarantine@4:5'",
        ):
            typed_ast.build_ownership_domain_graph(malformed)

    def test_public_phase1_pipeline_tracks_multiple_shared_alias_owners(self):
        source = """module test::phase1_shared_aliases;
sole struct Token { value: u32; }
fn main(token: Token) -> void {
    let peer = share token;
    let peer2 = share peer;
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(source)
        graph = result.semantic.ownership_domains
        account = graph.shared_accounts[0]
        self.assertEqual(account.owners, ("token", "peer", "peer2"))
        self.assertEqual(account.strong_refs, 3)
        self.assertEqual(
            [(item.source, item.alias, item.operation)
             for item in graph.shared_alias_points],
            [("token", "peer", "share"), ("peer", "peer2", "share_alias")],
        )
        shared = result.ownership_sir.functions[0].shared
        self.assertEqual(
            sum(isinstance(item, RetainInst) for item in shared.semantic), 2
        )

    def test_checked_sir_places_every_shared_alias_retain_and_release(self):
        source = """module test::phase1_shared_alias_sir;
sole struct Token { value: u32; }
fn main(token: Token) -> void {
    let peer = share token;
    let peer2 = share peer;
    return;
}
"""
        checked = sotlas_compile.analyze_source_phase1(source)
        result = generate_checked_ownership_sir(checked)
        instructions = tuple(
            instruction
            for function in result.module.functions
            for block in function.blocks
            for instruction in block.instructions
        )
        self.assertEqual(sum(isinstance(item, ShareInst) for item in instructions), 1)
        self.assertEqual(sum(isinstance(item, RetainInst) for item in instructions), 2)
        self.assertEqual(sum(isinstance(item, ReleaseInst) for item in instructions), 3)
        self.assertEqual(sum(isinstance(item, DestroyInst) for item in instructions), 1)

    def test_checked_sir_places_deferred_method_on_each_return_path(self):
        source = """module test::phase1_deferred_method;
sole struct Token {
    value: u32;
    fn inspect(&self) -> void { return; }
}
fn main(flag: bool, token: Token) -> void {
    let peer = share token;
    defer peer.inspect();
    if flag { return; }
    return;
}
"""
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-deferred-method>"
        )
        result = generate_checked_ownership_sir(checked)
        function = next(
            function for function in result.module.functions
            if function.name == "main"
        )
        call_blocks = []
        for block in function.blocks:
            calls = [
                instruction for instruction in block.instructions
                if isinstance(instruction, CallInst)
                and instruction.callee == "Token_inspect"
            ]
            if calls:
                self.assertEqual(len(calls), 1)
                call_index = block.instructions.index(calls[0])
                return_index = next(
                    index for index, instruction
                    in enumerate(block.instructions)
                    if isinstance(instruction, ReturnInst)
                )
                cleanup_indexes = [
                    index for index, instruction
                    in enumerate(block.instructions)
                    if isinstance(instruction, (ReleaseInst, DestroyInst))
                ]
                self.assertTrue(cleanup_indexes)
                self.assertTrue(
                    all(call_index < index < return_index
                        for index in cleanup_indexes)
                )
                call_blocks.append(calls[0])
        self.assertEqual(len(call_blocks), 2)
        self.assertEqual(
            len({call.defer_point_id for call in call_blocks}), 1
        )

    def test_checked_sir_preserves_shared_direct_borrow_in_deferred_early_return(self):
        source = """module test::phase1_deferred_direct_shared;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn run(flag: bool, token: Token) -> void {
    let peer = share token;
    defer inspect(&peer);
    if flag { return; }
    return;
}
"""
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-deferred-direct-shared>"
        )
        result = generate_checked_ownership_sir(checked)
        function = next(
            function for function in result.module.functions
            if function.name == "run"
        )
        direct_markers = [
            item for block in function.blocks for item in block.instructions
            if isinstance(item, DirectAccessInst)
        ]
        self.assertEqual(len(direct_markers), 1)
        graph_access = next(
            access for access in checked.semantic.ownership_domains.direct_accesses
            if access.function == "run"
        )
        self.assertEqual(direct_markers[0].point_id, graph_access.point_id)
        self.assertEqual(direct_markers[0].source_domain, "shared")
        return_blocks = [
            block for block in function.blocks
            if any(isinstance(item, ReturnInst) for item in block.instructions)
        ]
        self.assertEqual(len(return_blocks), 2)
        calls = []
        for block in return_blocks:
            call_index = next(
                index for index, item in enumerate(block.instructions)
                if isinstance(item, CallInst) and item.callee == "inspect"
            )
            call = block.instructions[call_index]
            calls.append(call)
            self.assertEqual(len(call.arguments), 1)
            self.assertEqual(call.arguments[0].name, "peer")
            self.assertEqual(call.arguments[0].type_name, "Token*")
            return_index = next(
                index for index, item in enumerate(block.instructions)
                if isinstance(item, ReturnInst)
            )
            releases = [
                index for index, item in enumerate(block.instructions)
                if isinstance(item, (ReleaseInst, DestroyInst))
            ]
            self.assertTrue(releases)
            self.assertTrue(call_index < min(releases) < return_index)
        self.assertEqual(len({call.defer_point_id for call in calls}), 1)

    def test_deferred_direct_call_rejects_shared_alias_without_explicit_borrow(self):
        source = """module test::phase1_deferred_direct_requires_borrow;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> void { return; }
fn run(token: Token) -> void {
    let peer = share token;
    defer inspect(peer);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.bootstrap.SotlasBootstrapError,
            r"argumento 1 incompat",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-deferred-direct-requires-borrow>"
            )

    def test_public_phase1_pipeline_preserves_non_owning_whisper_contract(self):
        source = """module test::phase1_whisper;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> void { return; }
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper>"
        )
        function = result.semantic.typed_module.functions[0]
        self.assertIs(
            function.params[0].ownership_domain,
            typed_ast.OwnershipDomain.WHISPER,
        )
        summary = result.semantic.ownership.summaries[0]
        self.assertFalse(summary.params[0].takes_ownership)
        self.assertIs(
            summary.params[0].domain,
            typed_ast.OwnershipDomain.WHISPER,
        )
        self.assertEqual(
            result.semantic.ownership_domains.nodes, ()
        )

    def test_whisper_call_borrows_live_sole_argument_without_consuming_it(self):
        source = """module test::phase1_whisper_call;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return 1; }
fn caller(token: Token) -> u32 {
    let result = inspect(&token);
    return result;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-call>"
        )
        _, trace = next(
            item for item in result.semantic.ownership.traces
            if item[0] == "caller"
        )
        self.assertIs(
            trace.final_env.state_of("token"), typed_ast.VarState.LIVE
        )
        self.assertFalse(
            any(event.kind == "move" and event.name == "token"
                for event in trace.events)
        )
        graph = result.semantic.ownership_domains
        self.assertEqual(len(graph.whisper_borrows), 1)
        borrow = graph.whisper_borrows[0]
        self.assertEqual(borrow.function, "caller")
        self.assertEqual(borrow.callee, "inspect")
        self.assertEqual(borrow.parameter, "token")
        self.assertEqual(borrow.source, "token")
        self.assertIs(borrow.source_domain, typed_ast.OwnershipDomain.EXCLUSIVE)
        self.assertRegex(borrow.point_id, r"^whisper@\d+:\d+$")
        sir_function = next(
            item for item in result.ownership_sir.functions
            if item.function == "caller"
        )
        sir_borrows = [
            item for item in sir_function.domain.instructions
            if type(item).__name__ == "WhisperBorrowInst"
        ]
        self.assertEqual(len(sir_borrows), 1)
        self.assertEqual(sir_borrows[0].source.name, "token")
        self.assertEqual(sir_borrows[0].callee, "inspect")

    def test_whisper_forwarding_preserves_borrow_domain_through_sir(self):
        source = """module test::phase1_whisper_forward;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return token.value; }
fn forward(token: whisper Token) -> u32 { return inspect(token); }
fn caller(token: Token) -> u32 { return forward(&token); }
"""
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-forward>"
        )
        graph_borrow = next(
            item for item in checked.semantic.ownership_domains.whisper_borrows
            if item.function == "forward"
        )
        self.assertEqual(graph_borrow.source, "token")
        self.assertIs(
            graph_borrow.source_domain, typed_ast.OwnershipDomain.WHISPER
        )
        forward_fn = next(
            item for item in checked.ownership_sir.functions
            if item.function == "forward"
        )
        borrow = next(
            item for item in forward_fn.domain.instructions
            if type(item).__name__ == "WhisperBorrowInst"
        )
        self.assertEqual(borrow.source_domain, "whisper")
        self.assertEqual(borrow.callee, "inspect")

    def test_whisper_forwarding_inside_defer_preserves_borrow_domain(self):
        source = """module test::phase1_whisper_defer_forward;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> void { return; }
fn deferred(token: whisper Token) -> void {
    defer inspect(token);
    return;
}
"""
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-defer-forward>"
        )
        graph_borrow = next(
            item for item in checked.semantic.ownership_domains.whisper_borrows
            if item.function == "deferred"
        )
        self.assertEqual(graph_borrow.callee, "inspect")
        self.assertEqual(graph_borrow.source, "token")
        self.assertIs(
            graph_borrow.source_domain, typed_ast.OwnershipDomain.WHISPER
        )

    def test_direct_access_is_preserved_from_graph_through_sir(self):
        source = """module test::phase1_direct_call;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 { return 1; }
fn caller(token: Token) -> u32 {
    let result = inspect(&token);
    return result;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-direct-call>"
        )
        _, trace = next(
            item for item in result.semantic.ownership.traces
            if item[0] == "caller"
        )
        self.assertIs(
            trace.final_env.state_of("token"), typed_ast.VarState.LIVE
        )
        graph = result.semantic.ownership_domains
        self.assertEqual(len(graph.direct_accesses), 1)
        access = graph.direct_accesses[0]
        self.assertEqual((access.callee, access.parameter, access.source),
                         ("inspect", "token", "token"))
        self.assertRegex(access.point_id, r"^direct@\d+:\d+$")
        sir_function = next(
            item for item in result.ownership_sir.functions
            if item.function == "caller"
        )
        sir_accesses = [
            item for item in sir_function.domain.instructions
            if type(item).__name__ == "DirectAccessInst"
        ]
        self.assertEqual(len(sir_accesses), 1)
        self.assertEqual(sir_accesses[0].point_id, access.point_id)

    def test_direct_forwarding_preserves_call_scope_through_sir(self):
        source = """module test::phase1_direct_forward;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 { return token.value; }
fn forward(token: direct Token) -> u32 { return inspect(token); }
fn caller(token: Token) -> u32 { return forward(&token); }
"""
        checked = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-direct-forward>"
        )
        access = next(
            item for item in checked.semantic.ownership_domains.direct_accesses
            if item.function == "forward"
        )
        self.assertEqual(access.source, "token")
        self.assertIs(access.source_domain, typed_ast.OwnershipDomain.DIRECT)
        forward_fn = next(
            item for item in checked.ownership_sir.functions
            if item.function == "forward"
        )
        sir_access = next(
            item for item in forward_fn.domain.instructions
            if type(item).__name__ == "DirectAccessInst"
        )
        self.assertEqual(sir_access.source_domain, "direct")

    def test_direct_access_allows_frame_local_alias_and_scalar_read(self):
        source = """module test::phase1_direct_local_alias;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 {
    let alias = token;
    return alias.value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-direct-local-alias>"
        )
        self.assertEqual(result.semantic.ownership_domains.nodes, ())

    def test_whisper_allows_copying_scalar_field_value(self):
        source = """module test::phase1_whisper_scalar_read;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return token.value; }
fn caller(token: Token) -> u32 { return inspect(&token); }
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-scalar-read>"
        )
        self.assertEqual(len(result.semantic.ownership_domains.whisper_borrows), 1)

    def test_whisper_method_receiver_records_call_scoped_borrow(self):
        source = """module test::phase1_whisper_method;
sole struct Token { value: u32; }
impl Token {
    fn inspect(self: whisper Token) -> void { return; }
}
fn caller(token: Token) -> void {
    token.inspect();
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-method>"
        )
        borrow = result.semantic.ownership_domains.whisper_borrows[0]
        self.assertEqual(borrow.callee, "Token_inspect")
        self.assertEqual(borrow.source, "token")
        self.assertIs(borrow.source_domain, typed_ast.OwnershipDomain.EXCLUSIVE)

    def test_quarantine_rejects_use_of_preexisting_reference_alias(self):
        source = """module test::phase1_quarantine_alias;
sole struct Token { value: u32; }
fn isolate(token: Token) -> void {
    let alias = &token;
    quarantine token;
    unsafe { alias.value; }
    return;
}
        """
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "reference alias 'alias' to quarantined owner 'token' is used after quarantine",
        ):
            sotlas_compile.compile_source(
                source, filename="<canonical-quarantine-alias>"
            )

    def test_canonical_checker_rejects_alias_creation_after_quarantine(self):
        source = """module test::canonical_quarantine_new_alias;
sole struct Token { value: u32; }
fn isolate(token: Token) -> void {
    quarantine token;
    let alias = &token;
    unsafe { alias.value; }
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "cannot create reference alias to quarantined owner 'token'",
        ):
              sotlas_compile.compile_source(
                source, filename="<canonical-quarantine-new-alias>"
            )

    def test_canonical_checker_rejects_alias_saved_in_struct_after_quarantine(self):
        source = """module test::canonical_quarantine_field_alias;
sole struct Token { value: u32; }
struct Holder { ptr: *mut Token; }
fn isolate(token: Token) -> void {
    let mut holder: Holder = 0;
    unsafe { holder.ptr = (&token) as *mut Token; }
    quarantine token;
    unsafe { holder.ptr.value; }
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "reference alias 'holder' to quarantined owner 'token' is used after quarantine",
        ):
              sotlas_compile.compile_source(
                source, filename="<canonical-quarantine-field-alias>"
            )

    def test_canonical_checker_rejects_quarantine_after_alias_passed_to_call(self):
        source = """module test::canonical_quarantine_escaped_alias;
sole struct Token { value: u32; }
fn observe(value: &Token) -> void { return; }
fn isolate(token: Token) -> void {
    let alias = &token;
    observe(alias);
    quarantine token;
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "cannot quarantine owner 'token' after a reference alias escaped to a call",
        ):
            sotlas_compile.compile_source(
                source, filename="<canonical-quarantine-call-escape>"
            )

    def test_canonical_checker_rejects_quarantine_with_alias_in_loop(self):
        source = """module test::canonical_quarantine_loop_alias;
sole struct Token { value: u32; }
fn isolate(token: Token, again: bool) -> void {
    let alias = &token;
    while again {
        alias.value;
        quarantine token;
    }
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "quarantine of 'token' inside a loop with reference aliases requires path-sensitive lifetime analysis",
        ):
            sotlas_compile.compile_source(
                source, filename="<canonical-quarantine-loop-alias>"
            )

    def test_quarantine_allows_alias_that_is_dead_before_transition(self):
        source = """module test::phase1_quarantine_dead_alias;
sole struct Token { value: u32; }
fn isolate(token: Token) -> void {
    let alias = &token;
    alias.value;
    quarantine token;
    return;
}
"""
        sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-quarantine-dead-alias>"
        )

    def test_quarantine_in_one_branch_does_not_invalidate_sibling_branch_alias(self):
        source = """module test::quarantine_disjoint_branches;
sole struct Token { value: u32; }
fn isolate(token: Token, should_isolate: bool) -> void {
    let alias = &token;
    if should_isolate {
        quarantine token;
        return;
    } else {
        unsafe { alias.value; }
        return;
    }
}
"""
        sotlas_compile.compile_source(
            source, filename="<quarantine-disjoint-branches>"
        )

    def test_quarantine_in_conditional_branch_still_invalidates_alias_after_join(self):
        source = """module test::quarantine_branch_join;
sole struct Token { value: u32; }
fn isolate(token: Token, should_isolate: bool) -> void {
    let alias = &token;
    if should_isolate {
        quarantine token;
    }
    unsafe { alias.value; }
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "reference alias 'alias' to quarantined owner 'token' is used after quarantine",
        ):
            sotlas_compile.compile_source(
                source, filename="<quarantine-branch-join>"
            )

    def test_quarantined_alias_cannot_escape_through_opaque_call(self):
        source = """module test::quarantine_opaque_alias;
sole struct Token { value: u32; }
fn observe(value: &Token) -> void { return; }
fn isolate(token: Token) -> void {
    let alias = &token;
    quarantine token;
    observe(alias);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "reference alias 'alias' to quarantined owner 'token' is used after quarantine",
        ):
            sotlas_compile.compile_source(
                source, filename="<quarantine-opaque-alias>"
            )

    def test_whisper_rejects_returning_pointer_field_from_borrowed_owner(self):
        source = """module test::phase1_whisper_field_escape;
sole struct Token { value: u32; }
sole struct Holder { token_ptr: *Token; }
fn leak(holder: whisper Holder) -> *Token {
    return holder.token_ptr;
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            "whisper-derived pointer cannot escape through return",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-whisper-field-escape>"
            )

    def test_direct_access_rejects_derived_pointer_escape(self):
        source = """module test::phase1_direct_escape;
sole struct Token { value: u32; }
sole struct Holder { token_ptr: *Token; }
fn leak(holder: direct Holder) -> *Token {
    return holder.token_ptr;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "direct-derived pointer cannot escape through return",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-direct-escape>"
            )

    def test_direct_escape_is_rejected_by_production_checker(self):
        source = """module test::production_direct_escape;
sole struct Token { value: u32; }
sole struct Holder { token_ptr: *Token; }
fn leak(holder: direct Holder) -> *Token { return holder.token_ptr; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-direct-escape>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "direct-derived pointer cannot escape through return",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_direct_access_cannot_cross_opaque_extern_boundary(self):
        source = """module test::direct_extern;
sole struct Token { value: u32; }
extern "C" { fn sink(token: direct Token); }
@system fn caller(token: Token) -> void {
    unsafe { sink(&token); }
    return;
}
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<direct-extern>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "direct access cannot be passed to external function 'sink'",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_whisper_borrow_cannot_cross_opaque_extern_boundary(self):
        source = """module test::whisper_extern_boundary;
sole struct Token { value: u32; }
extern "C" { fn sink(token: whisper Token); }
@system fn caller(token: Token) -> void {
    unsafe { sink(&token); }
    return;
}
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<whisper-extern-boundary>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "whisper access cannot be passed to external function 'sink'",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_direct_access_from_island_requires_alias_contract(self):
        source = """module test::direct_island_alias;
sole struct Token { value: u32; }
fn inspect(token: direct Token) -> u32 { return token.value; }
fn caller(token: island Token) -> u32 { return inspect(&token); }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<direct-island-alias>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "direct access to island owner 'token' requires an explicit island alias contract",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_rejects_indirect_direct_parameters(self):
        source = """module test::direct_fn_pointer;
sole struct Token { value: u32; }
fn invoke(callback: fn(direct Token) -> u32) -> void { return; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-direct-fn-pointer>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "direct access is not supported through nested or indirect function parameter types",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_whisper_rejects_unsafe_cast_escape(self):
        source = """module test::phase1_whisper_cast_escape;
sole struct Token { value: u32; }
fn leak(token: whisper Token) -> *Token {
    unsafe { return token as *Token; }
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            "whisper-derived pointer cannot escape through return",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-whisper-cast-escape>"
            )

    def test_production_checker_rejects_whisper_pointer_escape(self):
        source = """module test::production_whisper_escape;
sole struct Token { value: u32; }
fn leak(token: whisper Token) -> *Token {
    unsafe { return token as *Token; }
}
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-escape>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "whisper-derived pointer cannot escape through return",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_allows_copying_scalar_from_whisper(self):
        source = """module test::production_whisper_scalar;
sole struct Token { value: u32; }
fn read(token: whisper Token) -> u32 { return token.value; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-scalar>"
        )
        sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_allows_forwarding_to_verified_noescape_function(self):
        source = """module test::production_whisper_forward;
sole struct Token { value: u32; }
fn relay(token: whisper Token) -> u32 { return forward(token); }
fn forward(token: &Token) -> u32 { return observe(token); }
fn observe(token: &Token) -> u32 { return token.value; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-forward>"
        )
        sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_rejects_forwarding_to_escaping_function(self):
        source = """module test::production_whisper_unsafe_forward;
sole struct Token { value: u32; }
fn leak(token: &Token) -> *Token {
    unsafe { return token as *Token; }
}
fn relay(token: whisper Token) -> *Token {
    unsafe { return leak(token); }
}
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-unsafe-forward>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "whisper-derived reference cannot be forwarded through a call without a verified no-escape parameter summary",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_allows_forwarding_to_verified_noescape_method(self):
        source = """module test::production_whisper_method;
sole struct Token { value: u32; }
impl Token {
    fn inspect(self: &Token) -> u32 { return self.value; }
}
fn relay(token: whisper Token) -> u32 { return token.inspect(); }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-method>"
        )
        sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_rejects_forwarding_to_external_parameter(self):
        source = """module test::production_whisper_extern;
sole struct Token { value: u32; }
extern "C" fn inspect(value: &Token) -> u32;
@system fn relay(token: whisper Token) -> u32 {
    return inspect(token);
}
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-extern>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "whisper-derived reference cannot be forwarded through a call without a verified no-escape parameter summary",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_production_checker_does_not_apply_direct_summary_to_shadowed_callee(self):
        source = """module test::production_whisper_shadowed_callee;
sole struct Token { value: u32; }
fn observe(value: &Token) -> usize { return value.value as usize; }
fn escape(value: &Token) -> usize {
    unsafe { return value as *Token as usize; }
}
fn relay(token: whisper Token) -> usize {
    let observe: fn(&Token) -> usize = escape;
    return observe(token);
}
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<production-whisper-shadowed-callee>"
        )
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            "whisper-derived reference cannot be forwarded through a call without a verified no-escape parameter summary",
        ):
            sotlas_compile.bootstrap.check(parsed)

    def test_whisper_rejects_pointer_cast_erased_to_integer_return(self):
        source = """module test::phase1_whisper_integer_escape;
sole struct Token { value: u32; }
fn leak(token: whisper Token) -> usize {
    unsafe { return token as usize; }
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            "whisper-derived value cannot escape through return",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-whisper-integer-escape>"
            )

    def test_whisper_rejects_pointer_alias_local_return_escape(self):
        source = """module test::phase1_whisper_local_escape;
sole struct Token { value: u32; }
fn leak(token: whisper Token) -> *Token {
    unsafe {
        let saved: *Token = token as *Token;
        return saved;
    }
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            "whisper-derived pointer cannot escape through return",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-whisper-local-escape>"
            )

    def test_whisper_borrow_of_shared_owner_records_shared_source_domain(self):
        source = """module test::phase1_whisper_shared;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> void { return; }
fn caller(token: Token) -> void {
    let alias = share token;
    inspect(&alias);
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-shared>"
        )
        borrows = result.semantic.ownership_domains.whisper_borrows
        self.assertEqual(len(borrows), 1)
        self.assertEqual(borrows[0].source, "alias")
        self.assertIs(borrows[0].source_domain, typed_ast.OwnershipDomain.SHARED)

    def test_whisper_borrow_from_island_owner_reaches_graph_and_sir(self):
        source = """module test::phase1_whisper_island;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> void { return; }
fn caller(token: island Token) -> void {
    inspect(&token);
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-whisper-island>"
        )
        borrow = result.semantic.ownership_domains.whisper_borrows[0]
        self.assertEqual(borrow.source, "token")
        self.assertIs(borrow.source_domain, typed_ast.OwnershipDomain.ISLAND)
        sir_function = next(
            item for item in result.ownership_sir.functions
            if item.function == "caller"
        )
        sir_borrow = next(
            item for item in sir_function.domain.instructions
            if type(item).__name__ == "WhisperBorrowInst"
        )
        self.assertEqual(sir_borrow.source_domain, "island")

    def test_whisper_call_rejects_moved_sole_argument(self):
        source = """module test::phase1_whisper_moved;
sole struct Token { value: u32; }
fn inspect(token: whisper Token) -> u32 { return 1; }
fn consume(token: Token) -> void { return; }
fn caller(token: Token) -> u32 {
    consume(move token);
    return inspect(&token);
}
        """
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError, "after move"
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-whisper-moved>"
            )

    def test_public_phase1_pipeline_rejects_nested_whisper_type_shapes(self):
        for inner_type in ("*Token", "*mut Token", "&Token", "&mut Token"):
            with self.subTest(inner_type=inner_type):
                source = (
                    "module test::phase1_whisper_shape; "
                    "sole struct Token { value: u32; } "
                    f"fn inspect(token: whisper {inner_type}) -> void "
                    "{ return; }"
                )
                with self.assertRaisesRegex(
                    sotlas_compile.SotlasBootstrapError,
                    "whisper currently requires an unqualified, direct",
                ):
                    sotlas_compile.analyze_source_phase1(source)

    def test_public_phase1_pipeline_exposes_empty_ownership_sir_for_plain_code(self):
        source = """module test::phase1_plain_sir;
fn main(value: u32) -> u32 {
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-plain-sir>"
        )
        self.assertEqual(len(result.ownership_sir.functions), 1)
        function_plan = result.ownership_sir.functions[0]
        self.assertEqual(function_plan.domain.instructions, ())
        self.assertEqual(function_plan.shared.semantic, ())
        self.assertEqual(function_plan.shared.cleanup_segments, ())

    def test_public_phase1_pipeline_rejects_non_bool_control_flow_in_bootstrap(self):
        source = """module test::phase1_bool_control_flow;
fn main() -> void {
    if 1 {
        return;
    }
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"condição de if deve ser bool",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-bool-control-flow>"
            )

    def test_public_phase1_pipeline_accepts_raw_pointer_arithmetic_inside_unsafe(self):
        source = """module test::phase1_pointer_arithmetic;
fn advance(ptr: *const u8, offset: usize) -> *const u8 {
    unsafe {
        return ptr + offset;
    }
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-pointer-arithmetic>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "advance"
        )
        result_type = body.statements[0].body[0].expr.type
        self.assertTrue(result_type.pointer)
        self.assertFalse(result_type.is_reference)
        self.assertEqual(result_type.name, "u8")

    def test_public_phase1_pipeline_rejects_mixed_for_bounds_in_bootstrap(self):
        source = """module test::phase1_for_mixed_bounds;
fn main() -> void {
    for i in 0usize..3u32 {
        return;
    }
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"tipos dos limites de for incompatíveis: usize vs u32",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-for-mixed-bounds>"
            )

    def test_public_phase1_pipeline_rejects_explicit_numeric_type_mismatch_in_bootstrap(self):
        source = """module test::phase1_numeric_type_mismatch;
fn main(left: u32, right: u64) -> bool {
    return left < right;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"tipos incompatíveis em operador relacional <: u32 vs u64",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-numeric-type-mismatch>"
            )

    def test_public_phase1_pipeline_rejects_struct_literal_field_type_overflow_in_bootstrap(self):
        source = """module test::phase1_struct_literal_field_type;
struct Pixel { channel: u8; }
fn main() -> Pixel {
    return Pixel { channel: 256 };
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"valor inteiro 256 fora do intervalo para u8 \[0, 255\]",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-struct-literal-field-type>"
            )

    def test_public_phase1_pipeline_rejects_invalid_struct_literal_shape_in_bootstrap(self):
        source = """module test::phase1_struct_literal_shape;
struct Pair { left: u32; right: u32; }
fn main() -> Pair {
    return Pair { left: 1 };
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"campo\(s\) ausente\(s\) em struct literal Pair: right",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-struct-literal-shape>"
            )

    def test_public_phase1_pipeline_rejects_invalid_unary_operator_domain_in_bootstrap(self):
        source = """module test::phase1_unary_operator_domain;
fn main(value: u32) -> u32 {
    return -value;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"operador - unário exige inteiro signed ou float",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-unary-operator-domain>"
            )

    def test_public_phase1_pipeline_rejects_invalid_numeric_operator_domain_in_bootstrap(self):
        source = """module test::phase1_numeric_operator_domain;
fn main(flag: bool) -> bool {
    return flag + flag;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"operador aritmético \+ exige operandos numéricos escalares",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-numeric-operator-domain>"
            )

    def test_public_phase1_pipeline_types_valid_function_field_call(self):
        source = """module test::phase1_fn_field_valid;
struct Dispatch {
    call: fn(u16) -> u32;
}
fn invoke(dispatch: &Dispatch) -> u32 {
    return dispatch.call(7);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-fn-field-valid>"
        )
        body = next(
            item for item in result.semantic.bodies
            if item.name == "invoke"
        )
        self.assertEqual(body.statements[0].expr.type.name, "u32")

    def test_public_phase1_pipeline_rejects_function_field_contract_in_bootstrap(self):
        source = """module test::phase1_fn_field_bad_type;
struct Dispatch {
    call: fn(u32) -> u32;
}
fn invoke(dispatch: &Dispatch, flag: bool) -> u32 {
    return dispatch.call(flag);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em campo de função "
            r"Dispatch\.call: esperado u32, recebido bool",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-fn-field-bad-type>"
            )

    def test_public_phase1_pipeline_rejects_explicit_method_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_method_explicit_numeric_mismatch;
struct Counter {
    value: u32;
    fn increment(self: *mut Counter, amount: u32) -> u32 {
        return amount;
    }
}
fn main(counter: Counter) -> u32 {
    return counter.increment(1u64);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em método Counter\.increment: "
            r"esperado u32, recebido u64",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-method-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_rejects_method_contract_mismatch_in_bootstrap(self):
        source = """module test::phase1_method_contract;
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
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em método Counter\.increment",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-method-contract>"
            )

    def test_public_phase1_pipeline_rejects_explicit_call_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_call_explicit_numeric_mismatch;
fn take(value: u32) -> u32 {
    return value;
}
fn main() -> u32 {
    return take(1u64);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em chamada take: "
            r"esperado u32, recebido u64",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-call-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_rejects_call_contract_mismatch_in_bootstrap(self):
        source = """module test::phase1_call_contract;
fn consume(value: u32) -> void {
    return;
}
fn main(flag: bool) -> void {
    consume(flag);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em chamada consume",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-call-contract>"
            )

    def test_public_phase1_pipeline_rejects_explicit_return_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_return_explicit_numeric_mismatch;
fn main() -> u32 {
    return 1u64;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"retorno incompatível",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-return-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_rejects_explicit_assignment_numeric_mismatch_in_bootstrap(self):
        source = """module test::phase1_assignment_explicit_numeric_mismatch;
fn main() -> void {
    let value: u32 = 1u32;
    value = 2u64;
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"atribuição incompatível",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-assignment-explicit-numeric-mismatch>",
            )

    def test_public_phase1_pipeline_reuses_canonical_parse_and_check(self):
        source = """module test::phase1_public_invalid;
fn main() -> void {
    let value: i64 = 1;
    value = true;
    return;
}
"""
        with self.assertRaises(sotlas_compile.SotlasBootstrapError):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-public-invalid>"
            )

    def test_public_phase1_pipeline_rejects_constant_left_shift_overflow_in_bootstrap(self):
        source = """module test::phase1_left_shift_overflow;
fn main() -> u8 {
    return 128u8 << 1u8;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"valor inteiro 256 fora do intervalo para u8 \[0, 255\]",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-left-shift-overflow>"
            )

    def test_public_phase1_pipeline_rejects_out_of_range_shift_in_bootstrap(self):
        source = """module test::phase1_shift_width;
fn main(value: u32) -> u32 {
    return value << 32;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"contador de deslocamento 32 fora do intervalo para u32 de largura 32",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-shift-width>"
            )

    def test_public_phase1_pipeline_rejects_signed_minimum_division_overflow_in_bootstrap(self):
        source = """module test::phase1_i8_div_overflow;
fn main() -> i8 {
    return -128i8 / -1i8;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"overflow de divisão inteira para mínimo de i8 dividido por -1",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-i8-div-overflow>"
            )

    def test_public_phase1_pipeline_rejects_constant_integer_division_by_zero_in_bootstrap(self):
        source = """module test::phase1_integer_div_zero;
fn main(value: u32) -> u32 {
    return value / (2 - 2);
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"divisão inteira por zero não é permitida",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-integer-div-zero>"
            )

    def test_public_phase1_pipeline_rejects_constant_integer_overflow_in_bootstrap(self):
        source = """module test::phase1_integer_overflow;
fn main() -> u8 {
    return 255u8 + 1u8;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"valor inteiro 256 fora do intervalo para u8 \[0, 255\]",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-integer-overflow>"
            )

    def test_public_phase1_pipeline_accepts_in_range_constant_integer_arithmetic(self):
        source = """module test::phase1_integer_in_range;
fn main() -> u8 {
    return 254u8 + 1u8;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-integer-in-range>"
        )
        body = result.semantic.bodies[0]
        self.assertEqual(body.statements[0].expr.type.name, "u8")

    def test_public_phase1_pipeline_rejects_sole_use_after_move(self):
        source = """module test::phase1_sole_use_after_move;
sole struct Token { value: u32; }

fn consume(token: Token) -> void { return; }
fn main(token: Token) -> u32 {
    consume(move token);
    return token.value;
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"use of sole value 'token' after move",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-sole-use-after-move>"
            )

    def test_public_phase1_pipeline_accepts_consumed_sole_without_reuse(self):
        source = """module test::phase1_sole_move_valid;
sole struct Token { value: u32; }

fn consume(token: Token) -> void { return; }
fn main(token: Token) -> void {
    consume(move token);
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-sole-move-valid>"
        )
        traces = dict(result.semantic.ownership.traces)
        self.assertIs(
            traces["main"].final_env.state_of("token"),
            typed_ast.VarState.MOVED,
        )

    def test_public_phase1_pipeline_rejects_constant_array_index_oob(self):
        source = """module test::phase1_bounds_oob;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1 + 2];
}
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"array index 3 out of bounds for length 3",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-bounds-oob>"
            )

    def test_public_phase1_pipeline_accepts_constant_array_index_in_range(self):
        source = """module test::phase1_bounds_in_range;
fn main() -> i64 {
    let values = [1, 2, 3];
    return values[1 + 1];
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-bounds-in-range>"
        )
        body = result.semantic.bodies[0]
        self.assertEqual(body.statements[-1].expr.type.name, "i64")

    def test_public_phase1_pipeline_system_does_not_replace_unsafe(self):
        source = """module test::phase1_system_requires_unsafe;
@system
fn read(ptr: *mut u32) -> u32 {
    return *ptr;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"desreferenciamento de ponteiro exige bloco unsafe",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-system-requires-unsafe>"
            )

    def test_public_phase1_pipeline_accepts_system_pointer_deref_inside_unsafe(self):
        source = """module test::phase1_system_with_unsafe;
@system
fn read(ptr: *mut u32) -> u32 {
    unsafe {
        return *ptr;
    }
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-system-with-unsafe>"
        )
        body = result.semantic.bodies[0]
        self.assertEqual(body.statements[0].kind, "Unsafe")
        self.assertEqual(body.statements[0].body[0].kind, "Return")
        self.assertEqual(body.statements[0].body[0].expr.type.name, "u32")

    def test_public_phase1_pipeline_preserves_mutable_local_metadata(self):
        source = """module test::phase1_binding_mutability_metadata;
fn main() -> u32 {
    let mut value: u32 = 7u32;
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-binding-mutability-metadata>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "main"
        )
        binding = body.statements[0]
        self.assertEqual(binding.kind, "Let")
        self.assertTrue(binding.is_mut)
        self.assertEqual(binding.name, "value")

    def test_public_phase1_pipeline_forms_safe_references_with_address_of(self):
        source = """module test::phase1_address_of_reference;
fn read(value: &u32) -> u32 {
    return *value;
}
fn main() -> u32 {
    let value: u32 = 7u32;
    return read(&value);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-address-of-reference>"
        )
        main = next(
            item for item in result.semantic.bodies if item.name == "main"
        )
        self.assertEqual(main.statements[-1].expr.type.name, "u32")

    def test_public_phase1_pipeline_rejects_mut_borrow_of_immutable_binding(self):
        source = """module test::phase1_mut_borrow_immutable_binding;
fn write(value: &mut u32) -> void {
    *value = 9u32;
    return;
}
fn main() -> void {
    let value: u32 = 7u32;
    write(&mut value);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"referência mutável exige binding mutável",
        ):
            sotlas_compile.analyze_source_phase1(
                source,
                filename="<phase1-mut-borrow-immutable-binding>",
            )

    def test_public_phase1_pipeline_forms_mut_references_with_address_of_mut(self):
        source = """module test::phase1_address_of_mut_reference;
fn write(value: &mut u32) -> void {
    *value = 9u32;
    return;
}
fn main() -> u32 {
    let mut value: u32 = 7u32;
    write(&mut value);
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-address-of-mut-reference>"
        )
        main = next(
            item for item in result.semantic.bodies if item.name == "main"
        )
        self.assertEqual(main.statements[-1].expr.type.name, "u32")

    def test_public_phase1_pipeline_accepts_reference_mutability_weakening(self):
        source = """module test::phase1_reference_mutability_weakening;
fn view(value: &mut u32) -> &u32 {
    return value;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-reference-mutability-weakening>"
        )
        body = result.semantic.bodies[0]
        returned = body.statements[0].expr.type
        self.assertTrue(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_public_phase1_pipeline_accepts_string_literal_const_u8_pointer(self):
        source = """module test::phase1_string_literal;
fn consume(value: *const u8) -> *const u8 {
    return value;
}
fn text() -> *const u8 {
    return consume("sotlas");
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-string-literal>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "text"
        )
        returned = body.statements[0].expr.type
        self.assertEqual(returned.name, "u8")
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.mutable)
        self.assertFalse(returned.is_reference)

    def test_public_phase1_pipeline_rejects_pointer_comparison_type_mismatch_in_bootstrap(self):
        source = """module test::phase1_pointer_compare_mismatch;
fn same(left: *mut u32, right: *const u32) -> bool {
    return left == right;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"tipos incompatíveis em comparação ==: u32 vs u32",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-pointer-compare-mismatch>"
            )

    def test_public_phase1_pipeline_rejects_reference_null_comparison(self):
        source = """module test::phase1_reference_null_comparison;
fn is_null(value: &u32) -> bool {
    return value == null;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"referência segura não pode ser comparada a null",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-reference-null-comparison>"
            )

    def test_public_phase1_pipeline_accepts_null_raw_pointer_return(self):
        source = """module test::phase1_null_raw_pointer;
fn empty() -> *mut u32 {
    return null;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-null-raw-pointer>"
        )
        returned = result.semantic.bodies[0].statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertTrue(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_public_phase1_pipeline_accepts_raw_pointer_mutability_weakening(self):
        source = """module test::phase1_raw_pointer_mutability_weakening;
fn view(value: *const u32) -> *const u32 {
    return value;
}
fn expose(value: *mut u32) -> *const u32 {
    return view(value);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-raw-pointer-mutability-weakening>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "expose"
        )
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "u32")

    def test_public_phase1_pipeline_accepts_raw_void_pointer_compatibility(self):
        source = """module test::phase1_raw_void_pointer_compatibility;
fn erase(value: *const void) -> *const void {
    return value;
}
fn expose(value: *mut u32) -> *const void {
    return erase(value);
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-raw-void-pointer-compatibility>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "expose"
        )
        returned = body.statements[0].expr.type
        self.assertTrue(returned.pointer)
        self.assertFalse(returned.is_reference)
        self.assertFalse(returned.mutable)
        self.assertEqual(returned.name, "void")

    def test_public_phase1_pipeline_rejects_recursive_value_type(self):
        source = """module test::phase1_recursive_value;
struct Node {
    next: Node;
}
fn main() -> void { return; }
"""
        with self.assertRaisesRegex(
            typed_ast.Phase1SemanticError,
            r"recursive value type: Node -> Node",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-recursive-value>"
            )

    def test_public_phase1_pipeline_allows_recursive_pointer_indirection(self):
        source = """module test::phase1_recursive_pointer;
struct Node {
    next: *mut Node;
}
fn main() -> void { return; }
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-recursive-pointer>"
        )
        field_type = result.semantic.typed_module.structs[0].fields[0].type
        self.assertTrue(field_type.pointer)
        self.assertEqual(field_type.name, "Node")

    def test_normal_package_import_does_not_auto_attach_phase1_state(self):
        source = """module test::phase1_no_side_effect;
fn main() -> void { return; }
"""
        parsed = sotlas_compile.bootstrap.parse(
            source, filename="<phase1-no-side-effect>"
        )
        sotlas_compile.bootstrap.check(parsed)
        self.assertFalse(hasattr(parsed, "typed_ast"))
        self.assertFalse(hasattr(parsed, "phase1"))



    def test_public_phase1_pipeline_accepts_function_values_with_exact_signature(self):
        source = """module test::phase1_function_value;
fn bump(value: u32) -> u32 {
    return value + 1;
}
fn install(callback: fn(u32) -> u32) -> void {
    return;
}
fn main() -> void {
    let local: fn(u32) -> u32 = bump;
    install(local);
    return;
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-function-value>"
        )
        emitted = sotlas_compile.bootstrap.emit_c(result.parsed_module)
        self.assertIn("uint32_t (*callback)(uint32_t)", emitted)
        self.assertIn("uint32_t (*local)(uint32_t) = bump;", emitted)

    def test_public_phase1_pipeline_rejects_function_value_signature_mismatch(self):
        source = """module test::phase1_function_value_mismatch;
fn wrong(value: u64) -> u32 {
    return 1;
}
fn install(callback: fn(u32) -> u32) -> void {
    return;
}
fn main() -> void {
    install(wrong);
    return;
}
"""
        with self.assertRaisesRegex(
            sotlas_compile.SotlasBootstrapError,
            r"argumento 1 incompatível em chamada install",
        ):
            sotlas_compile.analyze_source_phase1(
                source, filename="<phase1-function-value-mismatch>"
            )



    def test_public_phase1_pipeline_deref_value_does_not_inherit_pointer_mutability(self):
        source = """module test::phase1_deref_value_type;
struct Boxed {
    value: u32;
}
fn consume(value: Boxed) -> u32 {
    return value.value;
}
fn read(ptr: *mut Boxed) -> u32 {
    unsafe {
        return consume(*ptr);
    }
}
"""
        result = sotlas_compile.analyze_source_phase1(
            source, filename="<phase1-deref-value-type>"
        )
        body = next(
            item for item in result.semantic.bodies if item.name == "read"
        )
        self.assertEqual(body.statements[0].body[0].expr.type.name, "u32")


if __name__ == "__main__":
    unittest.main()
