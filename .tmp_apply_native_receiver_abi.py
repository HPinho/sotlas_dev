from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEMA = ROOT / "bootstrap/sotlas/native_compiler/sema.sotlas"
EMITTER = ROOT / "bootstrap/sotlas/native_compiler/emitter_c.sotlas"
MAIN = ROOT / "bootstrap/sotlas/native_compiler/main.sotlas"


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

sema = SEMA.read_text(encoding="utf-8")
member_anchor = "    pub fn find_struct_for_type_ref(\n"
receiver_helpers = r'''    pub fn source_node_compact_equals(
        self: &Self,
        source: *const u8,
        source_len: usize,
        node: AstNode,
        expected: *const u8,
        expected_len: usize
    ) -> bool {
        if source == null || expected == null || node.str_len == 0
            || node.str_offset > source_len
            || node.str_len > source_len - node.str_offset {
            return false;
        }
        let mut source_i: usize = 0;
        let mut expected_i: usize = 0;
        while source_i < node.str_len {
            let ch: u8 = unsafe { *(source + node.str_offset + source_i) };
            source_i = source_i + 1;
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 {
                continue;
            }
            if expected_i >= expected_len {
                return false;
            }
            let want: u8 = unsafe { *(expected + expected_i) };
            if ch != want {
                return false;
            }
            expected_i = expected_i + 1;
        }
        return expected_i == expected_len;
    }

    pub fn find_enclosing_impl(
        self: &Self,
        nodes: *const AstNode,
        node_count: usize,
        index: usize
    ) -> usize {
        if nodes == null || index == 0 || index >= node_count {
            return 0;
        }
        let mut current: usize = index;
        let mut traversed: usize = 0;
        while current != 0 && traversed < node_count {
            if current >= node_count {
                return 0;
            }
            let node: AstNode = unsafe { *(nodes + current) };
            if node.kind == AstKind::ImplDecl {
                return current;
            }
            current = node.parent;
            traversed = traversed + 1;
        }
        return 0;
    }

    pub fn receiver_struct_for_member(
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
        let base: AstNode = unsafe { *(nodes + member.first_child) };
        if base.kind != AstKind::ExprIdent
            || !self.source_node_compact_equals(
                source, source_len, base, "self", 4
            ) {
            return 0;
        }
        let binding_index: usize = self.find_visible_binding(
            nodes, node_count, member.first_child, source, source_len
        );
        if binding_index == 0 || binding_index >= node_count {
            return 0;
        }
        let binding: AstNode = unsafe { *(nodes + binding_index) };
        if binding.kind != AstKind::ParamDecl
            || !self.source_node_compact_equals(
                source, source_len, binding, "self", 4
            ) {
            return 0;
        }
        let type_index: usize = self.binding_type_ref(
            nodes, node_count, binding_index
        );
        if type_index == 0 || type_index >= node_count {
            return 0;
        }
        let typ: AstNode = unsafe { *(nodes + type_index) };
        if !self.source_node_compact_equals(
                source, source_len, typ, "&Self", 5
            ) && !self.source_node_compact_equals(
                source, source_len, typ, "&mutSelf", 8
            ) {
            return 0;
        }
        let impl_index: usize = self.find_enclosing_impl(
            nodes, node_count, member_index
        );
        if impl_index == 0 || impl_index >= node_count {
            return 0;
        }
        let impl_node: AstNode = unsafe { *(nodes + impl_index) };
        let module_index: usize = self.find_enclosing_module(
            nodes, node_count, member_index
        );
        if module_index == 0 || module_index >= node_count {
            return 0;
        }
        let module_node: AstNode = unsafe { *(nodes + module_index) };
        let mut declaration_index: usize = module_node.first_child;
        while declaration_index != 0 {
            if declaration_index >= node_count {
                return 0;
            }
            let declaration: AstNode = unsafe { *(nodes + declaration_index) };
            if declaration.kind == AstKind::StructDecl
                && self.same_declaration_name(
                    source, source_len, declaration, impl_node
                ) {
                return declaration_index;
            }
            declaration_index = declaration.next_sibling;
        }
        return 0;
    }

    pub fn member_base_is_mutable_self(
        mut self: &mut Self,
        nodes: *const AstNode,
        node_count: usize,
        member_index: usize,
        source: *const u8,
        source_len: usize
    ) -> bool {
        if self.receiver_struct_for_member(
            nodes, node_count, member_index, source, source_len
        ) == 0 {
            return false;
        }
        let member: AstNode = unsafe { *(nodes + member_index) };
        let binding_index: usize = self.find_visible_binding(
            nodes, node_count, member.first_child, source, source_len
        );
        if binding_index == 0 || binding_index >= node_count {
            return false;
        }
        let binding: AstNode = unsafe { *(nodes + binding_index) };
        let type_index: usize = self.binding_type_ref(
            nodes, node_count, binding_index
        );
        if type_index == 0 || type_index >= node_count {
            return false;
        }
        let typ: AstNode = unsafe { *(nodes + type_index) };
        return binding.int_value == 1 && self.source_node_compact_equals(
            source, source_len, typ, "&mutSelf", 8
        );
    }

'''
sema = once(sema, member_anchor, receiver_helpers + member_anchor, "receiver helpers")

old_resolve = '''        let errors_before: usize = self.error_count;\n        let base_type: usize = self.infer_expression_type_ref(\n            nodes, node_count, member.first_child, source, source_len\n        );\n        if self.error_count != errors_before || base_type == 0 {\n            return 0;\n        }\n        let struct_index: usize = self.find_struct_for_type_ref(\n            nodes, node_count, base_type, member_index, source, source_len\n        );\n        if struct_index == 0 {\n            return 0;\n        }\n        return self.find_struct_field_for_member(\n            nodes, node_count, struct_index, member_index, source, source_len\n        );\n'''
new_resolve = '''        let receiver_struct: usize = self.receiver_struct_for_member(\n            nodes, node_count, member_index, source, source_len\n        );\n        if receiver_struct != 0 {\n            return self.find_struct_field_for_member(\n                nodes, node_count, receiver_struct, member_index, source, source_len\n            );\n        }\n\n        let errors_before: usize = self.error_count;\n        let base_type: usize = self.infer_expression_type_ref(\n            nodes, node_count, member.first_child, source, source_len\n        );\n        if self.error_count != errors_before || base_type == 0 {\n            return 0;\n        }\n        let struct_index: usize = self.find_struct_for_type_ref(\n            nodes, node_count, base_type, member_index, source, source_len\n        );\n        if struct_index == 0 {\n            return 0;\n        }\n        return self.find_struct_field_for_member(\n            nodes, node_count, struct_index, member_index, source, source_len\n        );\n'''
sema = once(sema, old_resolve, new_resolve, "receiver member resolution")

assign_start = '''            if node.kind == AstKind::AssignStmt {\n                let target_index: usize = node.first_child;\n'''
start = sema.find(assign_start)
if start < 0:
    raise SystemExit("assignment block start not found")
end_marker = '''            }\n            node_index = node_index + 1;\n'''
end = sema.find(end_marker, start)
if end < 0:
    raise SystemExit("assignment block end not found")
end += len("            }\n")
new_assign = r'''            if node.kind == AstKind::AssignStmt {
                let target_index: usize = node.first_child;
                if target_index == 0 || target_index >= node_count {
                    self.error_count = self.error_count + 1;
                    self.error_line = node.span.line;
                    self.error_col = node.span.col;
                    return false;
                }
                let target: AstNode = unsafe { *(nodes + target_index) };
                if target.kind == AstKind::ExprMember {
                    if !self.member_base_is_mutable_self(
                        nodes, node_count, target_index, source, source_len
                    ) {
                        self.error_count = self.error_count + 1;
                        self.error_line = target.span.line;
                        self.error_col = target.span.col;
                        return false;
                    }
                } else if target.kind == AstKind::ExprIdent {
                    let binding_index: usize = self.find_visible_binding(
                        nodes, node_count, target_index, source, source_len
                    );
                    if binding_index == 0 || binding_index >= node_count {
                        self.error_count = self.error_count + 1;
                        self.error_line = target.span.line;
                        self.error_col = target.span.col;
                        return false;
                    }
                    let binding: AstNode = unsafe { *(nodes + binding_index) };
                    if binding.int_value != 1 {
                        self.error_count = self.error_count + 1;
                        self.error_line = target.span.line;
                        self.error_col = target.span.col;
                        return false;
                    }
                } else {
                    self.error_count = self.error_count + 1;
                    self.error_line = target.span.line;
                    self.error_col = target.span.col;
                    return false;
                }
            }
'''
sema = sema[:start] + new_assign + sema[end:]
SEMA.write_text(sema, encoding="utf-8")

emitter = EMITTER.read_text(encoding="utf-8")
old_member = '''        if node.kind == AstKind::ExprMember {\n            if !self.valid_node(node.first_child) || node.str_len == 0 {\n                return false;\n            }\n            if !self.emit_expression(node.first_child)\n                || !self.write_byte(46) {\n                return false;\n            }\n            return self.write_source_slice(node.str_offset, node.str_len);\n        }\n'''
new_member = '''        if node.kind == AstKind::ExprMember {\n            if !self.valid_node(node.first_child) || node.str_len == 0 {\n                return false;\n            }\n            let base: AstNode = unsafe { *(self.nodes + node.first_child) };\n            if !self.emit_expression(node.first_child) {\n                return false;\n            }\n            if base.kind == AstKind::ExprIdent\n                && self.source_slice_equals(base.str_offset, base.str_len, "self", 4) {\n                if !self.write_str("->", 2) {\n                    return false;\n                }\n            } else if !self.write_byte(46) {\n                return false;\n            }\n            return self.write_source_slice(node.str_offset, node.str_len);\n        }\n'''
emitter = once(emitter, old_member, new_member, "receiver member lowering")
EMITTER.write_text(emitter, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
old_param = '''        if node.kind == AstKind::ParamDecl {\n            if emitter.source_slice_equals(node.str_offset, node.str_len, "self", 4) {\n                return false;\n            }\n            if !first_param && !emitter.write_str(", ", 2) {\n                return false;\n            }\n            if !emitter.emit_parameter(child) {\n                return false;\n            }\n            first_param = false;\n        } else if node.kind != AstKind::TypeRef && node.kind != AstKind::Block {\n'''
new_param = '''        if node.kind == AstKind::ParamDecl {\n            if !first_param && !emitter.write_str(", ", 2) {\n                return false;\n            }\n            if emitter.source_slice_equals(node.str_offset, node.str_len, "self", 4) {\n                if !first_param || !emitter.valid_node(node.first_child) {\n                    return false;\n                }\n                let receiver_type: AstNode = unsafe { *(emitter.nodes + node.first_child) };\n                if receiver_type.kind != AstKind::TypeRef {\n                    return false;\n                }\n                if node.int_value == 1\n                    && emitter.source_slice_equals_compact(\n                        receiver_type.str_offset, receiver_type.str_len, "&mutSelf", 8\n                    ) {\n                    if !emitter.write_source_slice(impl_node.str_offset, impl_node.str_len)\n                        || !emitter.write_str(" *self", 6) {\n                        return false;\n                    }\n                } else if node.int_value == 0\n                    && emitter.source_slice_equals_compact(\n                        receiver_type.str_offset, receiver_type.str_len, "&Self", 5\n                    ) {\n                    if !emitter.write_str("const ", 6)\n                        || !emitter.write_source_slice(impl_node.str_offset, impl_node.str_len)\n                        || !emitter.write_str(" *self", 6) {\n                        return false;\n                    }\n                } else {\n                    return false;\n                }\n            } else if !emitter.emit_parameter(child) {\n                return false;\n            }\n            first_param = false;\n        } else if node.kind != AstKind::TypeRef && node.kind != AstKind::Block {\n'''
main = once(main, old_param, new_param, "receiver ABI emission")
MAIN.write_text(main, encoding="utf-8")
print("bounded native receiver ABI applied")
