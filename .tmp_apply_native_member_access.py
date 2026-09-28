from pathlib import Path

ROOT = Path(__file__).resolve().parent
AST = ROOT / "bootstrap/sotlas/native_compiler/ast.sotlas"
PARSER = ROOT / "bootstrap/sotlas/native_compiler/parser.sotlas"
SEMA = ROOT / "bootstrap/sotlas/native_compiler/sema.sotlas"
EMITTER = ROOT / "bootstrap/sotlas/native_compiler/emitter_c.sotlas"


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

ast = AST.read_text(encoding="utf-8")
ast = once(
    ast,
    "    ExprArrayRepeat = 36\n",
    "    ExprArrayRepeat = 36,\n    ExprMember = 37\n",
    "ast member kind",
)
AST.write_text(ast, encoding="utf-8")

parser = PARSER.read_text(encoding="utf-8")
old_postfix = '''    pub fn parse_postfix_expression(mut self: &mut Self) -> usize {\n        let mut expr: usize = self.parse_primary_expression();\n        if expr == 0 {\n            return 0;\n        }\n\n        while self.match_token(TokenKind::Qmark) {\n            let qmark: Token = self.advance();\n            let try_node: usize = self.alloc_node(AstKind::TryExpr, qmark.span);\n            if try_node == 0 {\n                return 0;\n            }\n            if !self.append_child(try_node, expr) {\n                return 0;\n            }\n            expr = try_node;\n        }\n        return expr;\n    }\n'''
new_postfix = '''    pub fn parse_postfix_expression(mut self: &mut Self) -> usize {\n        let mut expr: usize = self.parse_primary_expression();\n        if expr == 0 {\n            return 0;\n        }\n\n        while self.match_token(TokenKind::Dot)\n            || self.match_token(TokenKind::Qmark) {\n            if self.match_token(TokenKind::Dot) {\n                self.advance();\n                let field: Token = self.current();\n                if field.kind != TokenKind::Ident {\n                    self.reject_current();\n                    return 0;\n                }\n                self.advance();\n                let member_node: usize = self.alloc_text_node(AstKind::ExprMember, field);\n                if member_node == 0 || !self.append_child(member_node, expr) {\n                    return 0;\n                }\n                expr = member_node;\n            } else {\n                let qmark: Token = self.advance();\n                let try_node: usize = self.alloc_node(AstKind::TryExpr, qmark.span);\n                if try_node == 0 {\n                    return 0;\n                }\n                if !self.append_child(try_node, expr) {\n                    return 0;\n                }\n                expr = try_node;\n            }\n        }\n        return expr;\n    }\n'''
parser = once(parser, old_postfix, new_postfix, "parser postfix")
PARSER.write_text(parser, encoding="utf-8")

sema = SEMA.read_text(encoding="utf-8")
check_anchor = '''            if node.kind == AstKind::ExprIdent\n                && !self.check_local_reference(\n                    nodes, node_count, node_index, source, source_len\n                ) {\n                return false;\n            }\n'''
check_new = '''            if node.kind == AstKind::ExprMember\n                && !self.check_member_access(\n                    nodes, node_count, node_index, source, source_len\n                ) {\n                return false;\n            }\n''' + check_anchor
sema = once(sema, check_anchor, check_new, "sema member gate")

member_helpers = r'''    pub fn find_struct_for_type_ref(
        self: &Self,
        nodes: *const AstNode,
        node_count: usize,
        type_index: usize,
        context_index: usize,
        source: *const u8,
        source_len: usize
    ) -> usize {
        if nodes == null || type_index == 0 || context_index == 0
            || type_index >= node_count || context_index >= node_count {
            return 0;
        }
        let typ: AstNode = unsafe { *(nodes + type_index) };
        if typ.kind != AstKind::TypeRef || typ.str_len == 0 {
            return 0;
        }
        let module_index: usize = self.find_enclosing_module(
            nodes, node_count, context_index
        );
        if module_index == 0 {
            return 0;
        }
        let module_node: AstNode = unsafe { *(nodes + module_index) };
        let mut declaration_index: usize = module_node.first_child;
        let mut traversed: usize = 0;
        while declaration_index != 0 {
            if declaration_index >= node_count || traversed >= MAX_SYMBOLS {
                return 0;
            }
            let declaration: AstNode = unsafe { *(nodes + declaration_index) };
            if declaration.kind == AstKind::StructDecl
                && declaration.str_len != 0
                && self.same_source_text(source, source_len, declaration, typ) {
                return declaration_index;
            }
            declaration_index = declaration.next_sibling;
            traversed = traversed + 1;
        }
        return 0;
    }

    pub fn find_struct_field_for_member(
        self: &Self,
        nodes: *const AstNode,
        node_count: usize,
        struct_index: usize,
        member_index: usize,
        source: *const u8,
        source_len: usize
    ) -> usize {
        if nodes == null || struct_index == 0 || member_index == 0
            || struct_index >= node_count || member_index >= node_count {
            return 0;
        }
        let declaration: AstNode = unsafe { *(nodes + struct_index) };
        let member: AstNode = unsafe { *(nodes + member_index) };
        if declaration.kind != AstKind::StructDecl
            || member.kind != AstKind::ExprMember || member.str_len == 0 {
            return 0;
        }
        let mut field_index: usize = declaration.first_child;
        let mut traversed: usize = 0;
        while field_index != 0 {
            if field_index >= node_count || traversed >= MAX_SYMBOLS {
                return 0;
            }
            let field: AstNode = unsafe { *(nodes + field_index) };
            if field.kind == AstKind::FieldDecl && field.str_len != 0
                && self.same_declaration_name(
                    source, source_len, field, member
                ) {
                return field_index;
            }
            field_index = field.next_sibling;
            traversed = traversed + 1;
        }
        return 0;
    }

    pub fn resolve_member_field(
        mut self: &mut Self,
        nodes: *const AstNode,
        node_count: usize,
        member_index: usize,
        source: *const u8,
        source_len: usize
    ) -> usize {
        if nodes == null || member_index == 0 || member_index >= node_count {
            return 0;
        }
        let member: AstNode = unsafe { *(nodes + member_index) };
        if member.kind != AstKind::ExprMember || member.first_child == 0
            || member.first_child >= node_count {
            return 0;
        }
        let errors_before: usize = self.error_count;
        let base_type: usize = self.infer_expression_type_ref(
            nodes, node_count, member.first_child, source, source_len
        );
        if self.error_count != errors_before || base_type == 0 {
            return 0;
        }
        let struct_index: usize = self.find_struct_for_type_ref(
            nodes, node_count, base_type, member_index, source, source_len
        );
        if struct_index == 0 {
            return 0;
        }
        return self.find_struct_field_for_member(
            nodes, node_count, struct_index, member_index, source, source_len
        );
    }

    pub fn check_member_access(
        mut self: &mut Self,
        nodes: *const AstNode,
        node_count: usize,
        member_index: usize,
        source: *const u8,
        source_len: usize
    ) -> bool {
        if nodes == null || member_index == 0 || member_index >= node_count {
            self.error_count = self.error_count + 1;
            return false;
        }
        let member: AstNode = unsafe { *(nodes + member_index) };
        let errors_before: usize = self.error_count;
        let field_index: usize = self.resolve_member_field(
            nodes, node_count, member_index, source, source_len
        );
        if self.error_count != errors_before {
            return false;
        }
        if field_index == 0 {
            return self.reject_node(member);
        }
        return true;
    }

'''
helper_anchor = "    pub fn infer_expression_type_ref(\n"
sema = once(sema, helper_anchor, member_helpers + helper_anchor, "member semantic helpers")

infer_anchor = '''        if expression.kind == AstKind::ExprStructLiteral {\n            if !self.check_struct_literal(\n                nodes, node_count, expression_index, source, source_len\n            ) {\n                return 0;\n            }\n            return expression_index;\n        }\n'''
infer_new = infer_anchor + '''        if expression.kind == AstKind::ExprMember {\n            let field_index: usize = self.resolve_member_field(\n                nodes, node_count, expression_index, source, source_len\n            );\n            if field_index == 0 || field_index >= node_count {\n                return 0;\n            }\n            return self.binding_type_ref(nodes, node_count, field_index);\n        }\n'''
sema = once(sema, infer_anchor, infer_new, "member type inference")
SEMA.write_text(sema, encoding="utf-8")

emitter = EMITTER.read_text(encoding="utf-8")
emit_anchor = '''        if node.kind == AstKind::ExprStructLiteral {\n            return self.emit_struct_literal(index);\n        }\n        if node.kind == AstKind::ExprArrayRepeat {\n'''
emit_new = '''        if node.kind == AstKind::ExprStructLiteral {\n            return self.emit_struct_literal(index);\n        }\n        if node.kind == AstKind::ExprMember {\n            if !self.valid_node(node.first_child) || node.str_len == 0 {\n                return false;\n            }\n            if !self.emit_expression(node.first_child)\n                || !self.write_byte(46) {\n                return false;\n            }\n            return self.write_source_slice(node.str_offset, node.str_len);\n        }\n        if node.kind == AstKind::ExprArrayRepeat {\n'''
emitter = once(emitter, emit_anchor, emit_new, "member C lowering")
EMITTER.write_text(emitter, encoding="utf-8")
print("typed native member access applied")
