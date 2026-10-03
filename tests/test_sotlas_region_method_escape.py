"""REGION reference escape checks across resolved method boundaries."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "compiler" / "sotlas_compile"


def _load_package():
    name = "sotlas_region_method_escape_package"
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
bootstrap = package.bootstrap


class SotlasRegionMethodEscapeTests(unittest.TestCase):
    def test_region_argument_can_forward_to_region_return_transfer(self):
        source = """module app::region_return_forwarding;
sole struct Token { value: u32; }
fn pass(token: region Token) -> region Token { return move token; }
fn run(token: region Token) -> void {
    let returned: region Token = pass(move token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-return-forwarding>")
        bootstrap.check(module)

    def test_region_noescape_contract_accepts_closed_mutual_recursion(self):
        source = """module app::region_recursive_forwarding;
sole struct Token { value: u32; }
fn first(token: region Token, depth: u32) -> void {
    if depth == 0 { return; }
    second(move token, depth - 1);
    return;
}
fn second(token: region Token, depth: u32) -> void {
    if depth == 0 { return; }
    first(move token, depth - 1);
    return;
}
fn run(token: region Token) -> void {
    first(move token, 2);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-recursive-forwarding>"
        )
        bootstrap.check(module)

    def test_region_noescape_recursive_cycle_still_rejects_escape_path(self):
        source = """module app::region_recursive_escape;
sole struct Token { value: u32; }
fn leak(token: Token) -> void { return; }
fn first(token: region Token, depth: u32) -> void {
    if depth == 0 { return; }
    second(move token, depth - 1);
    return;
}
fn second(token: region Token, depth: u32) -> void {
    if depth == 0 { leak(move token); return; }
    first(move token, depth - 1);
    return;
}
fn run(token: region Token) -> void {
    first(move token, 2);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-recursive-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"(cannot escape through an opaque call|no proven no-escape contract)",
        ):
            bootstrap.check(module)

    def test_region_argument_rejects_callee_returning_borrow(self):
        source = """module app::region_callee_return_escape;
sole struct Token { value: u32; }
fn borrow(token: region Token) -> &Token { return &token; }
fn run(token: region Token) -> void {
    let borrowed = borrow(move token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-callee-return-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference to region owner 'token' cannot escape through return",
        ):
            bootstrap.check(module)

    def test_region_argument_rejects_imported_callee_without_noescape_proof(self):
        callee_source = """module app::region_imported_borrow;
sole struct Token { value: u32; }
fn borrow(token: region Token) -> &Token { return &token; }
"""
        callee_module = bootstrap.parse(
            callee_source, filename="<region-imported-borrow>"
        )
        caller_source = """module app::region_importer;
sole struct Token { value: u32; }
fn run(token: region Token) -> void {
    let borrowed = borrow(move token);
    return;
}
"""
        caller_module = bootstrap.parse(
            caller_source, filename="<region-importer>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot cross call to 'borrow'.*no-escape contract",
        ):
            bootstrap.check(
                caller_module,
                imported_fns={"borrow": callee_module.functions[0]},
                imported_types={"Token": callee_module.structs[0]},
            )

    def test_region_return_origin_cannot_be_lost_before_owning_call(self):
        source = """module app::region_returned_owner_escape;
sole struct Token { value: u32; }
fn pass(token: region Token) -> region Token { return move token; }
fn consume(token: Token) -> void { return; }
fn run(token: region Token) -> void {
    let returned = pass(move token);
    consume(move returned);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-returned-owner-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference to region owner 'returned' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_nested_region_field_cannot_escape_to_owning_call(self):
        source = """module app::region_nested_field_escape;
sole struct Token { value: u32; }
sole struct Holder { token: Token; tag: u32; }
fn consume(token: Token) -> void { return; }
fn inspect(tag: u32) -> void { return; }
fn run(holder: region Holder) -> void {
    consume(move holder.token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-nested-field-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'holder' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_scalar_field_read_from_region_aggregate_remains_allowed(self):
        source = """module app::region_scalar_field_read;
sole struct Token { value: u32; }
sole struct Holder { token: Token; tag: u32; }
fn inspect(tag: u32) -> void { return; }
fn run(holder: region Holder) -> void {
    inspect(holder.tag);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-scalar-field-read>"
        )
        bootstrap.check(module)

    def test_region_array_element_cannot_escape_to_owning_call(self):
        source = """module app::region_array_element_escape;
sole struct Token { value: u32; }
sole struct Bundle { tokens: [Token; 2]; }
fn consume(token: Token) -> void { return; }
fn run(bundle: region Bundle) -> void {
    consume(move bundle.tokens[0]);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-array-element-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'bundle' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_region_field_cannot_escape_through_owning_method_parameter(self):
        source = """module app::region_method_value_escape;
sole struct Token { value: u32; }
sole struct Holder { token: Token; }
struct Sink {
    value: u32;
    fn consume(&self, token: Token) -> void { return; }
}
fn run(sink: Sink, holder: region Holder) -> void {
    sink.consume(move holder.token);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-method-value-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'holder' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_region_method_body_cannot_return_borrow_of_region_parameter(self):
        source = """module app::region_method_body_return_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    fn borrow(&self, token: region Token) -> &Token {
        return &token;
    }
}
fn run(inspector: Inspector, token: region Token) -> void {
    inspector.borrow(move token);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-method-body-return-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference to region owner 'token' cannot escape through return",
        ):
            bootstrap.check(module)

    def test_handover_invalidates_aliases_to_transferred_region_owner(self):
        source = """module app::region_handover_alias;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(source: region Token, destination: region Token) -> u32 {
    let alias = &source;
    consume(move destination);
    handover source to destination;
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"alias.*(moved|handover|transferred)|handover.*alias",
        ):
            bootstrap.check(module)

    def test_move_invalidates_aliases_to_consumed_region_owner(self):
        source = """module app::region_move_alias;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(source: region Token, destination: region Token) -> u32 {
    let alias = &destination;
    consume(move destination);
    handover source to destination;
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-move-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference alias 'alias' to moved owner 'destination' is used after move",
        ):
            bootstrap.check(module)

    def test_move_keeps_aliases_to_unrelated_region_owner_live(self):
        source = """module app::region_move_other_alias;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(destination: region Token, other: region Token) -> u32 {
    let alias = &other;
    consume(move destination);
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-move-other-alias>")
        bootstrap.check(module)

    def test_move_in_one_branch_invalidates_alias_after_join(self):
        source = """module app::region_move_branch_alias;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(destination: region Token, flag: bool) -> u32 {
    let alias = &destination;
    if flag { consume(move destination); }
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-move-branch-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference alias 'alias' to moved owner 'destination' is used after move",
        ):
            bootstrap.check(module)

    def test_move_in_loop_invalidates_alias_after_loop_exit(self):
        source = """module app::region_move_loop_alias;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(destination: region Token, flag: bool) -> u32 {
    let alias = &destination;
    while flag { consume(move destination); break; }
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-move-loop-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference alias 'alias' to moved owner 'destination' is used after move",
        ):
            bootstrap.check(module)

    def test_alias_rebound_after_move_can_target_live_region_owner(self):
        source = """module app::region_move_alias_rebind;
sole struct Token { value: u32; }
fn consume(token: region Token) -> void { return; }
fn run(destination: region Token, other: region Token) -> u32 {
    let mut alias = &destination;
    consume(move destination);
    alias = &other;
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-move-alias-rebind>")
        bootstrap.check(module)

    def test_handover_rejects_deferred_use_of_region_alias(self):
        source = """module app::region_handover_defer_alias;
sole struct Token { value: u32; }
fn run(source: region Token, destination: region Token) -> void {
    let alias = &source;
    defer { let snapshot: u32 = alias.value; }
    handover source to destination;
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-defer-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"defer uses reference alias 'alias' after handover of owner 'source'",
        ):
            bootstrap.check(module)

    def test_defer_can_use_alias_rebound_away_from_transferred_owner(self):
        source = """module app::region_handover_defer_rebind;
sole struct Token { value: u32; }
fn run(source: region Token, destination: region Token, other: region Token) -> void {
    let mut alias = &source;
    defer { let snapshot: u32 = alias.value; }
    alias = &other;
    handover source to destination;
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-defer-rebind>")
        bootstrap.check(module)

    def test_handover_in_one_branch_invalidates_alias_after_join(self):
        source = """module app::region_handover_branch_alias;
sole struct Token { value: u32; }
fn run(source: region Token, destination: region Token, flag: bool) -> u32 {
    let alias = &source;
    if flag { handover source to destination; }
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-branch-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference alias 'alias' to transferred owner 'source' is used after handover",
        ):
            bootstrap.check(module)

    def test_handover_in_loop_invalidates_alias_after_break(self):
        source = """module app::region_handover_loop_alias;
sole struct Token { value: u32; }
fn run(source: region Token, destination: region Token, flag: bool) -> u32 {
    let alias = &source;
    while flag {
        handover source to destination;
        break;
    }
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-loop-alias>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference alias 'alias' to transferred owner 'source' is used after handover",
        ):
            bootstrap.check(module)

    def test_handover_in_branch_without_later_alias_use_is_allowed(self):
        source = """module app::region_handover_branch_unused_alias;
sole struct Token { value: u32; }
fn run(source: region Token, destination: region Token, flag: bool) -> u32 {
    let alias = &source;
    if flag { handover source to destination; }
    return 0u32;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-branch-unused-alias>")
        bootstrap.check(module)

    def test_handover_alias_can_be_rebound_to_a_live_region_owner(self):
        source = """module app::region_handover_alias_rebind;
sole struct Token { value: u32; }
fn run(source: region Token, destination: region Token, other: region Token) -> u32 {
    let mut alias = &source;
    handover source to destination;
    alias = &other;
    return alias.value;
}
"""
        module = bootstrap.parse(source, filename="<region-handover-alias-rebind>")
        bootstrap.check(module)

    def test_region_owner_cannot_escape_through_enum_payload(self):
        source = """module app::region_enum_payload_escape;
sole struct Token { value: u32; }
enum Envelope { Owned(Token), Empty }
fn consume(value: Envelope) -> void { return; }
fn run(token: region Token) -> void {
    let envelope = Envelope::Owned(move token);
    consume(move envelope);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-enum-payload-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_region_owner_can_remain_in_nested_local_aggregates(self):
        source = """module app::region_nested_aggregate_local;
sole struct Token { value: u32; }
sole struct Inner { token: Token; }
sole struct Outer { inner: Inner; }
fn inspect(token: region Token) -> void {
    let inner: Inner = Inner { token: move token };
    let outer: Outer = Outer { inner: move inner };
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-nested-aggregate-local>"
        )
        bootstrap.check(module)

    def test_region_owner_cannot_escape_through_nested_owned_aggregates(self):
        source = """module app::region_nested_aggregate_escape;
sole struct Token { value: u32; }
sole struct Inner { token: Token; }
sole struct Outer { inner: Inner; }
fn capture(token: region Token) -> Outer {
    let inner: Inner = Inner { token: move token };
    return Outer { inner: move inner };
}
"""
        module = bootstrap.parse(
            source, filename="<region-nested-aggregate-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token' cannot escape through return or aggregate storage",
        ):
            bootstrap.check(module)

    def test_region_reference_cannot_escape_through_nested_borrow_aggregates(self):
        source = """module app::region_nested_borrow_return;
sole struct Token { value: u32; }
struct Borrow { value: &u32; }
struct Inner { borrow: Borrow; }
struct Outer { inner: Inner; }
fn capture(token: region Token) -> Outer {
    return Outer { inner: Inner { borrow: Borrow { value: &token.value } } };
}
"""
        module = bootstrap.parse(
            source, filename="<region-nested-borrow-return>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"reference to region owner 'token' cannot escape through return",
        ):
            bootstrap.check(module)

    def test_region_owner_cannot_escape_after_nested_aggregate_reassignment(self):
        source = """module app::region_nested_aggregate_reassignment_escape;
sole struct Token { value: u32; }
sole struct Inner { token: Token; }
sole struct Outer { inner: Inner; }
fn capture(token: region Token, other: Token) -> Outer {
    let mut value: Outer = Outer { inner: Inner { token: move other } };
    value = Outer { inner: Inner { token: move token } };
    return move value;
}
"""
        module = bootstrap.parse(
            source, filename="<region-nested-aggregate-reassignment-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token' cannot escape through return or aggregate storage",
        ):
            bootstrap.check(module)

    def test_region_aggregate_cannot_be_forwarded_to_opaque_exclusive_parameter(self):
        source = """module app::region_nested_aggregate_call_escape;
sole struct Token { value: u32; }
sole struct Inner { token: Token; }
sole struct Outer { inner: Inner; }
fn sink(value: Outer) -> void { return; }
fn capture(token: region Token) -> void {
    let inner: Inner = Inner { token: move token };
    let outer: Outer = Outer { inner: move inner };
    sink(move outer);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-nested-aggregate-call-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_region_aggregate_origin_joined_from_conditional_assignment(self):
        source = """module app::region_nested_aggregate_branch_escape;
sole struct Token { value: u32; }
sole struct Inner { token: Token; }
sole struct Outer { inner: Inner; }
fn sink(value: Outer) -> void { return; }
fn capture(token: region Token, other: Token, flag: bool) -> void {
    let mut value: Outer = Outer { inner: Inner { token: move other } };
    if flag { value = Outer { inner: Inner { token: move token } }; }
    sink(move value);
    return;
}
"""
        module = bootstrap.parse(
            source, filename="<region-nested-aggregate-branch-escape>"
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"region owner 'token' cannot escape through an opaque call",
        ):
            bootstrap.check(module)

    def test_region_reference_can_cross_method_direct_and_whisper_params(self):
        source = """module app::region_method_safe;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn inspect_direct(&self, token: direct Token) -> void { return; }
    fn inspect_whisper(&self, token: whisper Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token) -> void {
    inspector.inspect_direct(&token);
    inspector.inspect_whisper(&token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-method-safe>")
        bootstrap.check(module)

    def test_region_reference_cannot_escape_through_plain_reference_method_param(self):
        source = """module app::region_method_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token) -> void {
    inspector.capture(&token);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-method-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)

    def test_region_alias_cannot_hide_escape_through_method_param(self):
        source = """module app::region_method_alias_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token) -> void {
    let alias = &token;
    inspector.capture(alias);
    return;
}
"""
        module = bootstrap.parse(source, filename="<region-method-alias-escape>")
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)

    def test_region_alias_assigned_in_branch_cannot_hide_method_escape(self):
        source = """module app::region_method_branch_alias_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token, other: Token, flag: bool) -> void {
    let mut alias: &Token = &other;
    if flag { alias = &token; }
    inspector.capture(alias);
    return;
}
"""
        module = bootstrap.parse(
            source,
            filename="<region-method-branch-alias-escape>",
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)

    def test_region_alias_in_either_if_arm_cannot_hide_method_escape(self):
        source = """module app::region_method_either_arm_alias_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token, other: Token, flag: bool) -> void {
    let mut alias: &Token = &other;
    if flag { alias = &token; } else { alias = &token; }
    inspector.capture(alias);
    return;
}
"""
        module = bootstrap.parse(
            source,
            filename="<region-method-either-arm-alias-escape>",
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)

    def test_branch_local_shadow_does_not_replace_outer_alias(self):
        source = """module app::region_method_shadowed_branch_alias;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token, other: Token, flag: bool) -> void {
    let alias: &Token = &other;
    if flag { let alias: &Token = &token; }
    inspector.capture(alias);
    return;
}
"""
        module = bootstrap.parse(
            source,
            filename="<region-method-shadowed-branch-alias>",
        )
        bootstrap.check(module)

    def test_region_alias_assigned_in_loop_cannot_hide_method_escape(self):
        source = """module app::region_method_loop_alias_escape;
sole struct Token { value: u32; }
sole struct Inspector {
    value: u32;
    fn capture(&self, token: &Token) -> void { return; }
}
fn run(inspector: Inspector, token: region Token, other: Token, flag: bool) -> void {
    let mut alias: &Token = &other;
    while flag { alias = &token; break; }
    inspector.capture(alias);
    return;
}
"""
        module = bootstrap.parse(
            source,
            filename="<region-method-loop-alias-escape>",
        )
        with self.assertRaisesRegex(
            bootstrap.SotlasBootstrapError,
            r"cannot escape through method .*capture.*direct or whisper",
        ):
            bootstrap.check(module)


if __name__ == "__main__":
    unittest.main()
