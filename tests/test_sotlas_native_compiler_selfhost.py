"""Testes unitários para o novo compilador nativo auto-hospedado (Sotlas in Sotlas)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas import compile_source


class TestSotlasNativeCompilerSelfhost(unittest.TestCase):
    def test_native_token_module_compiles(self):
        token_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "token.sotlas"
        self.assertTrue(token_file.is_file())
        text = token_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(token_file))
        self.assertIn("TokenKind", c_code)
        self.assertIn("Span", c_code)
        self.assertIn("Token", c_code)

    def test_native_lexer_preserves_operator_and_delimiter_spans(self):
        lexer_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "lexer.sotlas"
        text = lexer_file.read_text(encoding="utf-8")
        self.assertIn("pub fn token_from_span", text)
        self.assertIn("tok.span.offset = start_offset;", text)
        self.assertIn("tok.span.length = self.cursor - start_offset;", text)
        self.assertIn(
            "self.token_from_span(TokenKind::Gt, start_line, start_col, start_offset)",
            text,
        )
        self.assertIn(
            "self.token_from_span(TokenKind::Qmark, start_line, start_col, start_offset)",
            text,
        )

    def test_native_lexer_module_compiles(self):
        lexer_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "lexer.sotlas"
        self.assertTrue(lexer_file.is_file())
        text = lexer_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(lexer_file))
        self.assertIn("Lexer", c_code)
        self.assertIn("next_token", c_code)
        self.assertIn("classify_keyword", c_code)

    def test_native_ast_module_compiles(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        self.assertTrue(ast_file.is_file())
        text = ast_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(ast_file))
        self.assertIn("AstKind", c_code)
        self.assertIn("AstNode", c_code)

    def test_native_parser_module_compiles(self):
        parser_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        self.assertTrue(parser_file.is_file())
        text = parser_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(parser_file))
        self.assertIn("Parser", c_code)
        self.assertIn("parse_module", c_code)
        self.assertIn("parse_statement", c_code)
        self.assertIn("node_capacity", c_code)
        self.assertIn("AstNode", c_code)

    def test_native_parser_persists_allocated_ast_nodes(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub nodes: *mut AstNode;", text)
        self.assertIn("pub node_capacity: usize;", text)
        self.assertIn("*(self.nodes + idx) = AstNode::new(kind, span);", text)
        self.assertIn("self.node_count >= self.node_capacity", text)

    def test_native_ast_links_parent_ownership(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub parent: usize;", ast_text)
        self.assertIn("parent: 0", ast_text)
        self.assertIn("if child_node.parent != 0", parser_text)
        self.assertIn("child_node.parent = parent;", parser_text)
        self.assertIn("*(self.nodes + child) = child_node;", parser_text)

    def test_native_parser_links_module_declarations(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub fn append_child", text)
        self.assertIn("parent_node.first_child = child;", text)
        self.assertIn("current_node.next_sibling = child;", text)
        self.assertIn("let decl_node: usize = self.parse_declaration();", text)
        self.assertIn("self.append_child(mod_node, decl_node)", text)
        self.assertIn("if self.cursor <= before", text)

    def test_native_parser_persists_function_parameters(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("let mut param_mutable: bool = false;", text)
        self.assertIn("let param_node: usize = self.alloc_node(AstKind::ParamDecl", text)
        self.assertIn("self.set_node_text(param_node, param_name)", text)
        self.assertIn("stored_param.int_value = 1;", text)
        self.assertIn("let param_type: usize = self.parse_type_ref(2);", text)
        self.assertIn("self.append_child(param_node, param_type)", text)
        self.assertIn("self.append_child(fn_node, param_node)", text)

    def test_native_parser_persists_function_return_type_slice(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("TypeRef = 27", ast_text)
        self.assertIn("pub fn set_node_text_range", parser_text)
        self.assertIn("let type_node: usize = self.parse_type_ref(3);", parser_text)
        self.assertIn("self.append_child(fn_node, type_node)", parser_text)

    def test_native_parser_persists_function_body_blocks(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub fn parse_block", text)
        self.assertIn("AstKind::Block", text)
        self.assertIn("let stmt_node: usize = self.parse_statement();", text)
        self.assertIn("self.append_child(block_node, stmt_node)", text)
        self.assertIn("let body_node: usize = self.parse_block();", text)
        self.assertIn("self.append_child(fn_node, body_node)", text)

    def test_native_main_emits_parsed_module_tree(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        emitter_text = emitter_file.read_text(encoding="utf-8")
        main_text = main_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_module", emitter_text)
        self.assertIn("module_node.kind != AstKind::Module", emitter_text)
        self.assertIn("node.kind == AstKind::Import", emitter_text)
        self.assertIn("node.kind == AstKind::FnDecl", emitter_text)
        self.assertIn("self.emit_function(child)", emitter_text)
        self.assertIn("if !emitter.emit_module(module_node)", main_text)

    def test_native_main_fails_closed_on_parser_failure(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        text = main_file.read_text(encoding="utf-8")
        self.assertIn("let module_node: usize = p.parse_module();", text)
        self.assertIn("if module_node == 0", text)

    def test_native_parser_persists_local_mutability_and_type(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("let mut is_mutable: bool = tok.kind == TokenKind::KwVar;", text)
        self.assertIn("self.match_token(TokenKind::KwMut)", text)
        self.assertIn("stored_node.int_value = 1;", text)
        self.assertIn("pub fn parse_type_ref", text)
        self.assertIn("let type_node: usize = self.parse_type_ref(1);", text)
        self.assertIn("self.append_child(let_node, type_node)", text)

    def test_native_parser_persists_loop_jump_statements(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("BreakStmt = 28", ast_text)
        self.assertIn("ContinueStmt = 29", ast_text)
        self.assertIn("tok.kind == TokenKind::KwBreak", parser_text)
        self.assertIn("AstKind::BreakStmt", parser_text)
        self.assertIn("tok.kind == TokenKind::KwContinue", parser_text)
        self.assertIn("AstKind::ContinueStmt", parser_text)

    def test_native_parser_persists_defer_payload_ast(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("DeferStmt = 26", ast_text)
        self.assertIn("tok.kind == TokenKind::KwDefer", parser_text)
        self.assertIn("AstKind::DeferStmt", parser_text)
        self.assertIn("payload_node = self.parse_expression_statement();", parser_text)
        self.assertIn("AstKind::AssignStmt", parser_text)
        self.assertIn("AstKind::ExprCall", parser_text)
        self.assertIn("AstKind::ExprBinary", parser_text)
        self.assertIn("self.append_child(defer_node, payload_node)", parser_text)

    def test_native_ast_retains_source_slices_for_emission(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        parser_text = parser_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        main_text = main_file.read_text(encoding="utf-8")
        self.assertIn("node.str_offset = tok.span.offset;", parser_text)
        self.assertIn("node.str_len = tok.span.length;", parser_text)
        self.assertIn("alloc_text_node(AstKind::ExprIdent, tok)", parser_text)
        self.assertIn("alloc_text_node(AstKind::ExprLiteral, tok)", parser_text)
        self.assertIn("pub source: *const u8;", emitter_text)
        self.assertIn("pub fn write_source_slice", emitter_text)
        self.assertIn("len > self.source_len - offset", emitter_text)
        self.assertIn("source_len: usize", emitter_text)
        self.assertIn("p.node_count", main_text)

    def test_native_emitter_can_serialize_defer_payload_ast(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub nodes: *const AstNode;", text)
        self.assertIn("pub fn emit_expression", text)
        self.assertIn("AstKind::ExprBinary", text)
        self.assertIn("AstKind::ExprCall", text)
        self.assertIn("pub fn emit_statement_payload", text)
        self.assertIn("AstKind::AssignStmt", text)
        self.assertIn("pub fn emit_defer_payload", text)
        self.assertIn("node.kind != AstKind::DeferStmt", text)

    def test_native_emitter_can_lower_deferred_block_payload(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("let payload_index: usize = node.first_child;", text)
        self.assertIn("let payload: AstNode = unsafe", text)
        self.assertIn("payload.kind == AstKind::Block", text)
        self.assertIn("return self.emit_braced_block(payload_index);", text)
        self.assertIn("return self.emit_statement_payload(payload_index);", text)

    def test_native_emitter_collects_block_defers_in_lifo_order(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_defer_chain_lifo", text)
        self.assertIn(
            "self.emit_defer_chain_lifo(node.next_sibling)",
            text,
        )
        self.assertIn("return self.emit_defer_payload(index);", text)
        self.assertIn("pub fn emit_block_exit_defers", text)
        self.assertIn("block.kind != AstKind::Block", text)
        self.assertIn(
            "return self.emit_defer_chain_lifo(block.first_child);",
            text,
        )
        recurse_at = text.index("self.emit_defer_chain_lifo(node.next_sibling)")
        emit_at = text.index("return self.emit_defer_payload(index);", recurse_at)
        self.assertLess(recurse_at, emit_at)

    def test_native_emitter_shares_function_exit_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_function_exit_defers", text)
        self.assertIn("let mut child_on_path: usize = exit_index;", text)
        self.assertIn("let mut parent_index: usize = exit_node.parent;", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("return self.emit_function_exit_defers(return_index);", text)

    def test_native_emitter_collects_only_active_return_defers(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_defer_prefix_lifo", text)
        self.assertIn("if index == stop_before", text)
        self.assertIn("pub fn emit_scope_defers_before", text)
        self.assertIn("stop.parent != block_index", text)
        self.assertIn("pub fn emit_function_exit_defers", text)
        self.assertIn("let mut child_on_path: usize = exit_index;", text)
        self.assertIn("let mut parent_index: usize = exit_node.parent;", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("parent_node.kind == AstKind::FnDecl", text)
        self.assertIn("pub fn emit_return_scope_defers", text)
        self.assertIn("return_node.kind != AstKind::ReturnStmt", text)
        self.assertIn(
            "return self.emit_function_exit_defers(return_index);",
            text,
        )

    def test_native_emitter_collects_loop_jump_defers_until_while(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_loop_jump_scope_defers", text)
        self.assertIn("jump.kind != AstKind::BreakStmt", text)
        self.assertIn("jump.kind != AstKind::ContinueStmt", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("parent_node.kind == AstKind::WhileStmt", text)
        self.assertIn("A loop jump outside a loop is structurally invalid", text)

    def test_native_emitter_fails_closed_before_result_abi_exists(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("node.kind == AstKind::TryExpr", text)
        self.assertIn("self.try_context_returns_result(index)", text)
        self.assertIn("Until Result<T,E> has a native C11 ABI", text)
        self.assertIn("if self.type_ref_is_result(type_index)", text)
        self.assertIn("Never leak the Sotlas", text)

    def test_native_emitter_uses_stable_result_u64_abi(self):
        abi_file = ROOT / "include" / "sotlas" / "sotlas_abi.h"
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        abi_text = abi_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_RESULT_U64_DEFINED", abi_text)
        self.assertIn("SotlasResultU64", abi_text)
        self.assertIn("pub fn type_ref_is_result_u64_i32", emitter_text)
        self.assertIn('"Result<u64,i32>"', emitter_text)
        self.assertIn('return self.write_str("SotlasResultU64", 15);', emitter_text)
        self.assertIn("SOTLAS_RESULT_U64_DEFINED", emitter_text)

    def test_native_emitter_recognizes_result_try_context(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn type_ref_is_result", text)
        self.assertIn('self.source_slice_equals(typ.str_offset, 6, "Result", 6)', text)
        self.assertIn("return close == 62;", text)
        self.assertIn("pub fn try_context_returns_result", text)
        self.assertIn("node.kind != AstKind::TryExpr", text)
        self.assertIn("self.find_enclosing_function(try_index)", text)
        self.assertIn("self.find_function_return_type(fn_index)", text)
        self.assertIn("return self.type_ref_is_result(type_index);", text)

    def test_native_emitter_captures_return_before_defer_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_enclosing_function", text)
        self.assertIn("pub fn find_function_return_type", text)
        self.assertIn("pub fn emit_c_type", text)
        self.assertIn("pub fn emit_return_statement", text)
        self.assertIn('" __sotlas_return_value = "', text)
        self.assertIn("self.emit_expression(ret.first_child)", text)
        self.assertIn("self.emit_return_scope_defers(return_index)", text)
        self.assertIn('"return __sotlas_return_value;', text)
        capture_at = text.index("self.emit_expression(ret.first_child)")
        cleanup_at = text.index(
            "self.emit_return_scope_defers(return_index)",
            capture_at,
        )
        final_return_at = text.index(
            "return __sotlas_return_value;",
            cleanup_at,
        )
        self.assertLess(capture_at, cleanup_at)
        self.assertLess(cleanup_at, final_return_at)

    def test_native_emitter_supports_function_prototypes(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("let body_index: usize = self.find_function_body(fn_index);", text)
        self.assertIn('return self.write_str(");\\n", 3);', text)
        prototype_at = text.index('return self.write_str(");\\n", 3);')
        body_at = text.index("return self.emit_braced_block(body_index);", prototype_at)
        self.assertLess(prototype_at, body_at)

    def test_native_emitter_lowers_function_signature_and_body(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_function_body", text)
        self.assertIn("pub fn emit_parameter", text)
        self.assertIn("param.kind != AstKind::ParamDecl", text)
        self.assertIn("self.emit_c_type(type_index)", text)
        self.assertIn("pub fn emit_function", text)
        self.assertIn("self.find_function_return_type(fn_index)", text)
        self.assertIn("node.kind == AstKind::ParamDecl", text)
        self.assertIn("self.emit_parameter(child)", text)
        self.assertIn("self.find_function_body(fn_index)", text)
        self.assertIn("return self.emit_braced_block(body_index);", text)

    def test_native_emitter_literal_write_lengths_match(self):
        import ast
        import re

        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        pattern = re.compile(r'write_str\(("(?:\\.|[^"\\])*"),\s*(\d+)\)')
        mismatches = []
        for match in pattern.finditer(text):
            literal = ast.literal_eval(match.group(1))
            declared = int(match.group(2))
            if len(literal) != declared:
                mismatches.append((literal, declared, len(literal)))
        self.assertEqual(mismatches, [])

    def test_native_emitter_lowers_direct_result_try_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_module_function_by_name", text)
        self.assertIn("pub fn try_call_returns_result_u64_i32", text)
        self.assertIn("pub fn try_context_returns_result_u64_i32", text)
        self.assertIn("pub fn emit_try_let_statement", text)
        self.assertIn('"SotlasResultU64 __sotlas_try_"', text)
        self.assertIn('".status != 0) {\\n"', text)
        self.assertIn("self.emit_function_exit_defers(let_index)", text)
        self.assertIn('"return __sotlas_try_"', text)
        self.assertIn('".value;\\n"', text)
        self.assertIn(
            "return self.emit_try_let_statement(index, type_index, init_index);",
            text,
        )

    def test_native_emitter_lowers_typed_local_declarations(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_let_statement", text)
        self.assertIn("node.kind != AstKind::LetStmt", text)
        self.assertIn("type_node.kind != AstKind::TypeRef", text)
        self.assertIn("self.emit_c_type(type_index)", text)
        self.assertIn("self.write_source_slice(node.str_offset, node.str_len)", text)
        self.assertIn("let init_index: usize = type_node.next_sibling;", text)
        self.assertIn("self.emit_expression(init_index)", text)
        self.assertIn("return self.emit_let_statement(index);", text)

    def test_native_emitter_lowers_while_body_as_lexical_scope(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_while_statement", text)
        self.assertIn("node.kind != AstKind::WhileStmt", text)
        self.assertIn("self.emit_expression(cond_index)", text)
        self.assertIn("return self.emit_braced_block(body_index);", text)
        self.assertIn("node.kind == AstKind::WhileStmt", text)
        self.assertIn("return self.emit_while_statement(index);", text)

    def test_native_emitter_lowers_if_else_blocks(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_braced_block", text)
        self.assertIn("pub fn emit_if_statement", text)
        self.assertIn("node.kind != AstKind::IfStmt", text)
        self.assertIn("self.emit_expression(cond_index)", text)
        self.assertIn("self.emit_braced_block(then_index)", text)
        self.assertIn("else_node.kind == AstKind::Block", text)
        self.assertIn("else_node.kind == AstKind::IfStmt", text)
        self.assertIn("return self.emit_if_statement(else_index);", text)
        self.assertIn("return self.emit_if_statement(index);", text)

    def test_native_emitter_lowers_unsafe_as_nested_lexical_block(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_unsafe_block", text)
        self.assertIn("node.kind != AstKind::UnsafeBlock", text)
        self.assertIn("body.kind != AstKind::Block", text)
        self.assertIn("return self.emit_braced_block(body_index);", text)
        self.assertIn("pub fn emit_braced_block", text)
        self.assertIn("self.emit_block_normal_exit(block_index)", text)
        self.assertIn("node.kind == AstKind::UnsafeBlock", text)
        self.assertIn("return self.emit_unsafe_block(index);", text)

    def test_native_emitter_runs_block_defers_after_normal_statements(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_normal_statement", text)
        self.assertIn("node.kind == AstKind::DeferStmt", text)
        self.assertIn("pub fn emit_block_normal_exit", text)
        self.assertIn("while stmt != 0", text)
        self.assertIn("self.emit_normal_statement(stmt)", text)
        self.assertIn("return self.emit_block_exit_defers(block_index);", text)
        walk_at = text.index("while stmt != 0")
        cleanup_at = text.index(
            "return self.emit_block_exit_defers(block_index);",
            walk_at,
        )
        self.assertLess(walk_at, cleanup_at)

    def test_native_block_loop_jump_stops_path_after_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_loop_jump_statement", text)
        self.assertIn("self.emit_loop_jump_scope_defers(jump_index)", text)
        self.assertIn('return self.write_str("break;\\n", 7);', text)
        self.assertIn('return self.write_str("continue;\\n", 10);', text)
        self.assertIn("stmt_node.kind == AstKind::BreakStmt", text)
        self.assertIn("stmt_node.kind == AstKind::ContinueStmt", text)
        self.assertIn("return self.emit_loop_jump_statement(stmt);", text)
        jump_branch = text.index("stmt_node.kind == AstKind::BreakStmt")
        ordinary_emit = text.index("self.emit_normal_statement(stmt)", jump_branch)
        self.assertLess(jump_branch, ordinary_emit)

    def test_native_block_return_stops_fallthrough_and_duplicate_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("stmt_node.kind == AstKind::ReturnStmt", text)
        self.assertIn("return self.emit_return_statement(stmt);", text)
        self.assertIn("Only a fallthrough path reaches the normal lexical cleanup", text)
        return_branch = text.index("stmt_node.kind == AstKind::ReturnStmt")
        statement_emit = text.index("self.emit_normal_statement(stmt)", return_branch)
        fallthrough_cleanup = text.index(
            "return self.emit_block_exit_defers(block_index);",
            statement_emit,
        )
        self.assertLess(return_branch, statement_emit)
        self.assertLess(statement_emit, fallthrough_cleanup)

    def test_native_parser_keeps_nested_generic_type_ranges(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub fn parse_type_ref", text)
        self.assertIn("let mut angle_depth: i64 = 0;", text)
        self.assertIn("kind == TokenKind::Lt", text)
        self.assertIn("kind == TokenKind::Gt", text)
        self.assertIn("kind == TokenKind::Shr", text)
        self.assertIn("angle_depth != 0", text)
        self.assertIn("self.parse_type_ref(1)", text)
        self.assertIn("self.parse_type_ref(2)", text)
        self.assertIn("self.parse_type_ref(3)", text)

    def test_native_parser_persists_qualified_expression_paths(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("ExprPath = 31", ast_text)
        self.assertIn("self.match_token(TokenKind::DColon)", parser_text)
        self.assertIn("let path_node: usize = self.alloc_node(AstKind::ExprPath", parser_text)
        self.assertIn("self.set_node_text_range(path_node, tok, path_end)", parser_text)
        self.assertIn("callee_node = path_node;", parser_text)
        self.assertIn("self.append_child(call_node, callee_node)", parser_text)

    def test_native_parser_persists_try_propagation_expression(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("TryExpr = 30", ast_text)
        self.assertIn("pub fn parse_postfix_expression", parser_text)
        self.assertIn("self.match_token(TokenKind::Qmark)", parser_text)
        self.assertIn("AstKind::TryExpr", parser_text)
        self.assertIn("self.append_child(try_node, expr)", parser_text)
        self.assertIn("return self.parse_postfix_expression();", parser_text)

    def test_native_parser_and_emitter_support_unary_expressions(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        parser_text = parser_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn parse_unary_expression", parser_text)
        self.assertIn("AstKind::ExprUnary", parser_text)
        self.assertIn("self.parse_unary_expression()", parser_text)
        self.assertIn("pub fn emit_unary_operator", emitter_text)
        self.assertIn("node.kind == AstKind::ExprUnary", emitter_text)
        self.assertIn("self.emit_unary_operator(node.int_value)", emitter_text)

    def test_native_parser_persists_nested_statement_tree(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("self.append_child(let_node, val_node)", text)
        self.assertIn("self.append_child(ret_node, expr_node)", text)
        self.assertIn("self.append_child(unsafe_node, body_node)", text)
        self.assertIn("self.append_child(clinch_node, body_node)", text)
        self.assertIn("self.append_child(clinch_node, revert_node)", text)
        self.assertIn("self.append_child(if_node, cond_node)", text)
        self.assertIn("self.append_child(if_node, then_node)", text)
        self.assertIn("self.append_child(if_node, else_node)", text)
        self.assertIn("self.append_child(while_node, cond_node)", text)
        self.assertIn("self.append_child(while_node, body_node)", text)

    def test_native_sema_module_compiles(self):
        sema_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "sema.sotlas"
        self.assertTrue(sema_file.is_file())
        text = sema_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(sema_file))
        self.assertIn("SymbolKind", c_code)
        self.assertIn("Sema", c_code)
        self.assertIn("check_system_privilege", c_code)

    def test_native_emitter_c_module_compiles(self):
        emitter_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        self.assertTrue(emitter_file.is_file())
        text = emitter_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(emitter_file))
        self.assertIn("CEmitter", c_code)
        self.assertIn("write_byte", c_code)
        self.assertIn("emit_header", c_code)

    def test_native_main_module_compiles(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        self.assertTrue(main_file.is_file())
        text = main_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(main_file))
        self.assertIn("sotlas_native_compile", c_code)
        self.assertIn("g_token_buffer", c_code)
        self.assertIn("g_ast_node_buffer", c_code)
        self.assertIn("AST_NODE_BUFFER_CAPACITY", c_code)
        self.assertIn("CEmitter", c_code)


if __name__ == "__main__":
    unittest.main()
