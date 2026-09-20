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

    def test_native_parser_persists_function_return_type_slice(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("TypeRef = 27", ast_text)
        self.assertIn("pub fn set_node_text_range", parser_text)
        self.assertIn("let type_node: usize = self.alloc_node(AstKind::TypeRef", parser_text)
        self.assertIn(
            "self.set_node_text_range(type_node, type_start, type_end)",
            parser_text,
        )
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

    def test_native_main_fails_closed_on_parser_failure(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        text = main_file.read_text(encoding="utf-8")
        self.assertIn("let module_node: usize = p.parse_module();", text)
        self.assertIn("if module_node == 0", text)

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

    def test_native_emitter_collects_only_active_return_defers(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_defer_prefix_lifo", text)
        self.assertIn("if index == stop_before", text)
        self.assertIn("pub fn emit_scope_defers_before", text)
        self.assertIn("stop.parent != block_index", text)
        self.assertIn("pub fn emit_return_scope_defers", text)
        self.assertIn("let mut child_on_path: usize = return_index;", text)
        self.assertIn("let mut parent_index: usize = return_node.parent;", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("parent_node.kind == AstKind::FnDecl", text)

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
        self.assertIn("self.emit_block_normal_exit(body_index)", text)
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
