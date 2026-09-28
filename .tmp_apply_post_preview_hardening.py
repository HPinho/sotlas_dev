from pathlib import Path

ROOT = Path(__file__).resolve().parent
EMITTER = ROOT / "bootstrap/sotlas/native_compiler/emitter_c.sotlas"
MAIN = ROOT / "bootstrap/sotlas/native_compiler/main.sotlas"
TEST = ROOT / "tests/test_sotlas_native_struct_literal_sema.py"
STATUS = ROOT / "docs/sotlas_implementation_status.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


emitter = EMITTER.read_text(encoding="utf-8")

methods = r'''    pub fn find_struct_decl_for_literal(
        self: &Self,
        literal_index: usize
    ) -> usize {
        if !self.valid_node(literal_index) {
            return 0;
        }
        let literal: AstNode = unsafe { *(self.nodes + literal_index) };
        if literal.kind != AstKind::ExprStructLiteral || literal.str_len == 0 {
            return 0;
        }
        let module_index: usize = self.find_enclosing_module(literal_index);
        if !self.valid_node(module_index) {
            return 0;
        }
        let module_node: AstNode = unsafe { *(self.nodes + module_index) };
        let mut child: usize = module_node.first_child;
        while child != 0 {
            if !self.valid_node(child) {
                return 0;
            }
            let candidate: AstNode = unsafe { *(self.nodes + child) };
            if candidate.kind == AstKind::StructDecl && candidate.str_len != 0
                && self.source_slices_equal(
                    candidate.str_offset,
                    candidate.str_len,
                    literal.str_offset,
                    literal.str_len
                ) {
                return child;
            }
            child = candidate.next_sibling;
        }
        return 0;
    }

    pub fn find_struct_field_decl(
        self: &Self,
        struct_index: usize,
        init_index: usize
    ) -> usize {
        if !self.valid_node(struct_index) || !self.valid_node(init_index) {
            return 0;
        }
        let decl: AstNode = unsafe { *(self.nodes + struct_index) };
        let init: AstNode = unsafe { *(self.nodes + init_index) };
        if decl.kind != AstKind::StructDecl || init.kind != AstKind::StructFieldInit
            || init.str_len == 0 {
            return 0;
        }

        let mut field_index: usize = decl.first_child;
        while field_index != 0 {
            if !self.valid_node(field_index) {
                return 0;
            }
            let field: AstNode = unsafe { *(self.nodes + field_index) };
            if field.kind == AstKind::FieldDecl && field.str_len != 0
                && self.source_slices_equal(
                    field.str_offset,
                    field.str_len,
                    init.str_offset,
                    init.str_len
                ) {
                return field_index;
            }
            field_index = field.next_sibling;
        }
        return 0;
    }

    pub fn struct_literal_shape_valid(
        self: &Self,
        literal_index: usize
    ) -> bool {
        let struct_index: usize = self.find_struct_decl_for_literal(literal_index);
        if struct_index == 0 || !self.valid_node(literal_index) {
            return false;
        }
        let decl: AstNode = unsafe { *(self.nodes + struct_index) };
        let literal: AstNode = unsafe { *(self.nodes + literal_index) };

        let mut declared_count: usize = 0;
        let mut field_index: usize = decl.first_child;
        while field_index != 0 {
            if !self.valid_node(field_index) {
                return false;
            }
            let field: AstNode = unsafe { *(self.nodes + field_index) };
            if field.kind != AstKind::FieldDecl || field.str_len == 0
                || !self.valid_node(field.first_child) {
                return false;
            }
            let typ: AstNode = unsafe { *(self.nodes + field.first_child) };
            if typ.kind != AstKind::TypeRef || typ.next_sibling != 0 {
                return false;
            }
            declared_count = declared_count + 1;
            field_index = field.next_sibling;
        }

        let mut init_count: usize = 0;
        let mut init_index: usize = literal.first_child;
        while init_index != 0 {
            if !self.valid_node(init_index) {
                return false;
            }
            let init: AstNode = unsafe { *(self.nodes + init_index) };
            if init.kind != AstKind::StructFieldInit || init.str_len == 0
                || !self.valid_node(init.first_child)
                || self.find_struct_field_decl(struct_index, init_index) == 0 {
                return false;
            }
            let value: AstNode = unsafe { *(self.nodes + init.first_child) };
            if value.next_sibling != 0 {
                return false;
            }

            let mut previous: usize = literal.first_child;
            while previous != init_index {
                if previous == 0 || !self.valid_node(previous) {
                    return false;
                }
                let previous_init: AstNode = unsafe { *(self.nodes + previous) };
                if previous_init.kind != AstKind::StructFieldInit {
                    return false;
                }
                if self.source_slices_equal(
                    previous_init.str_offset,
                    previous_init.str_len,
                    init.str_offset,
                    init.str_len
                ) {
                    return false;
                }
                previous = previous_init.next_sibling;
            }

            init_count = init_count + 1;
            init_index = init.next_sibling;
        }

        return declared_count != 0 && declared_count == init_count;
    }

    pub fn fixed_array_type_matches_zero_repeat(
        self: &Self,
        type_index: usize,
        repeat_index: usize
    ) -> bool {
        if !self.valid_node(type_index) || !self.valid_node(repeat_index)
            || self.source == null {
            return false;
        }
        let typ: AstNode = unsafe { *(self.nodes + type_index) };
        let repeat: AstNode = unsafe { *(self.nodes + repeat_index) };
        if typ.kind != AstKind::TypeRef || typ.str_len < 5
            || repeat.kind != AstKind::ExprArrayRepeat
            || !self.valid_node(repeat.first_child) {
            return false;
        }
        let value_index: usize = repeat.first_child;
        let value: AstNode = unsafe { *(self.nodes + value_index) };
        let count_index: usize = value.next_sibling;
        if value.kind != AstKind::ExprLiteral
            || !self.source_slice_equals(value.str_offset, value.str_len, "0", 1)
            || !self.valid_node(count_index) {
            return false;
        }
        let count: AstNode = unsafe { *(self.nodes + count_index) };
        if count.kind != AstKind::ExprLiteral || count.str_len == 0
            || count.next_sibling != 0 {
            return false;
        }

        let mut i: usize = 0;
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 { i = i + 1; }
            else { break; }
        }
        if i >= typ.str_len || unsafe { *(self.source + typ.str_offset + i) } != 91 {
            return false;
        }
        i = i + 1;
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 { i = i + 1; }
            else { break; }
        }
        let element_start: usize = i;
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            let alpha: bool = (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122);
            let digit: bool = ch >= 48 && ch <= 57;
            if alpha || digit || ch == 95 { i = i + 1; }
            else { break; }
        }
        if i == element_start {
            return false;
        }
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 { i = i + 1; }
            else { break; }
        }
        if i >= typ.str_len || unsafe { *(self.source + typ.str_offset + i) } != 59 {
            return false;
        }
        i = i + 1;
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 { i = i + 1; }
            else { break; }
        }
        let count_start: usize = i;
        let mut nonzero: bool = false;
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch >= 48 && ch <= 57 {
                if ch != 48 { nonzero = true; }
                i = i + 1;
            } else {
                break;
            }
        }
        let type_count_len: usize = i - count_start;
        if type_count_len == 0 || !nonzero {
            return false;
        }
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 { i = i + 1; }
            else { break; }
        }
        if i >= typ.str_len || unsafe { *(self.source + typ.str_offset + i) } != 93 {
            return false;
        }
        i = i + 1;
        while i < typ.str_len {
            let ch: u8 = unsafe { *(self.source + typ.str_offset + i) };
            if ch == 32 || ch == 9 || ch == 10 || ch == 13 { i = i + 1; }
            else { return false; }
        }

        return self.source_slices_equal(
            typ.str_offset + count_start,
            type_count_len,
            count.str_offset,
            count.str_len
        );
    }

    pub fn type_ref_matches_struct_literal(
        self: &Self,
        type_index: usize,
        literal_index: usize
    ) -> bool {
        if !self.valid_node(type_index) || !self.valid_node(literal_index) {
            return false;
        }
        let typ: AstNode = unsafe { *(self.nodes + type_index) };
        let literal: AstNode = unsafe { *(self.nodes + literal_index) };
        if typ.kind != AstKind::TypeRef || literal.kind != AstKind::ExprStructLiteral
            || typ.str_len == 0 || literal.str_len == 0 {
            return false;
        }
        return self.source_slices_equal(
            typ.str_offset,
            typ.str_len,
            literal.str_offset,
            literal.str_len
        );
    }

    pub fn emit_expression_for_type(
        mut self: &mut Self,
        index: usize,
        type_index: usize
    ) -> bool {
        if !self.valid_node(index) || !self.valid_node(type_index) {
            return false;
        }
        let node: AstNode = unsafe { *(self.nodes + index) };
        if node.kind == AstKind::ExprStructLiteral {
            if !self.type_ref_matches_struct_literal(type_index, index) {
                return false;
            }
            return self.emit_struct_literal(index);
        }
        if node.kind == AstKind::ExprArrayRepeat {
            if !self.fixed_array_type_matches_zero_repeat(type_index, index) {
                return false;
            }
            return self.write_str("{0}", 3);
        }
        return self.emit_expression(index);
    }

    pub fn emit_struct_literal(
        mut self: &mut Self,
        literal_index: usize
    ) -> bool {
        if !self.struct_literal_shape_valid(literal_index) {
            return false;
        }
        let literal: AstNode = unsafe { *(self.nodes + literal_index) };
        let struct_index: usize = self.find_struct_decl_for_literal(literal_index);
        if struct_index == 0 {
            return false;
        }

        if !self.write_byte(40)
            || !self.write_source_slice(literal.str_offset, literal.str_len)
            || !self.write_str("){ ", 3) {
            return false;
        }

        let mut init_index: usize = literal.first_child;
        let mut first: bool = true;
        while init_index != 0 {
            if !self.valid_node(init_index) {
                return false;
            }
            let init: AstNode = unsafe { *(self.nodes + init_index) };
            let field_index: usize = self.find_struct_field_decl(
                struct_index, init_index
            );
            if field_index == 0 || !self.valid_node(init.first_child) {
                return false;
            }
            let field: AstNode = unsafe { *(self.nodes + field_index) };
            let type_index: usize = field.first_child;
            let value_index: usize = init.first_child;

            if !first && !self.write_str(", ", 2) {
                return false;
            }
            if !self.write_byte(46)
                || !self.write_source_slice(init.str_offset, init.str_len)
                || !self.write_str(" = ", 3) {
                return false;
            }
            if !self.emit_expression_for_type(value_index, type_index) {
                return false;
            }

            first = false;
            init_index = init.next_sibling;
        }
        return self.write_str(" }", 2);
    }

'''

anchor = "    pub fn emit_expression(mut self: &mut Self, index: usize) -> bool {\n"
emitter = replace_once(emitter, anchor, methods + anchor, "insert canonical literal methods")

old_ident = '''        if node.kind == AstKind::ExprIdent || node.kind == AstKind::ExprLiteral {\n            return self.write_source_slice(node.str_offset, node.str_len);\n        }\n\n        if node.kind == AstKind::ExprPath {\n'''
new_ident = '''        if node.kind == AstKind::ExprIdent || node.kind == AstKind::ExprLiteral {\n            return self.write_source_slice(node.str_offset, node.str_len);\n        }\n\n        if node.kind == AstKind::ExprStructLiteral {\n            return self.emit_struct_literal(index);\n        }\n        if node.kind == AstKind::ExprArrayRepeat {\n            // Array repeat requires a declared target type so count and element\n            // semantics cannot be invented by the backend.\n            return false;\n        }\n\n        if node.kind == AstKind::ExprPath {\n'''
emitter = replace_once(emitter, old_ident, new_ident, "wire struct literal expression")

old_return = '''        } else if !self.emit_expression(ret.first_child) {\n            return false;\n        }\n'''
new_return = '''        } else if !self.emit_expression_for_type(ret.first_child, type_index) {\n            return false;\n        }\n'''
emitter = replace_once(emitter, old_return, new_return, "typed return lowering")

old_let = '''            } else if !self.emit_expression(init_index) {\n                return false;\n            }\n'''
new_let = '''            } else if !self.emit_expression_for_type(init_index, type_index) {\n                return false;\n            }\n'''
emitter = replace_once(emitter, old_let, new_let, "typed local lowering")
EMITTER.write_text(emitter, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
start_marker = "pub fn native_find_struct_decl_for_literal(\n"
end_marker = "pub fn emit_native_static_impl_function(\n"
start = main.find(start_marker)
end = main.find(end_marker, start + 1)
if start < 0 or end < 0 or end <= start:
    raise SystemExit("main: canonical literal adapter region anchors not found")
main = main[:start] + main[end:]

fn_marker = "pub fn emit_native_static_impl_function(\n"
fn_start = main.find(fn_marker)
body_start_marker = "    let body: AstNode = unsafe { *(emitter.nodes + body_index) };\n"
body_start = main.find(body_start_marker, fn_start)
return_marker = "    return emitter.emit_braced_block(body_index);\n"
body_end = main.find(return_marker, body_start)
if fn_start < 0 or body_start < 0 or body_end < 0:
    raise SystemExit("main: static impl special literal lowering block not found")
body_end += len(return_marker)
main = main[:body_start] + return_marker + main[body_end:]

if "emit_native_struct_literal" in main or "native_struct_literal_shape_valid" in main:
    raise SystemExit("main: duplicate literal adapter survived canonicalization")
MAIN.write_text(main, encoding="utf-8")

test = TEST.read_text(encoding="utf-8")
test = replace_once(
    test,
    '"""Require native struct semantics without widening the certified lowering surface."""',
    '"""Require strict native struct semantics through the canonical C emitter."""',
    "test docstring",
)
test = replace_once(
    test,
    '    if (expect_emitter_boundary("valid_top_level_shape", valid_top_level_shape) != 0) return 2;',
    '    if (expect_success("valid_top_level_shape", valid_top_level_shape) != 0) return 2;',
    "top-level struct literal now lowers",
)
insert_source_anchor = '''    static const char unknown_struct[] =\n'''
new_source = '''    static const char valid_nested_array[] =\n        "module test::valid_nested_array;\\n"\n        "struct Span { line: u32; }\\n"\n        "struct Packet { span: Span; bytes: [u8; 4]; }\\n"\n        "pub fn make() -> Packet { return Packet { span: Span { line: 1 }, bytes: [0; 4] }; }\\n";\n\n'''
test = replace_once(test, insert_source_anchor, new_source + insert_source_anchor, "nested array fixture")
test = replace_once(
    test,
    '    if (expect_semantic_failure_at("unknown_struct", unknown_struct, 2) != 0) return 3;',
    '    if (expect_success("valid_nested_array", valid_nested_array) != 0) return 3;\n    if (expect_semantic_failure_at("unknown_struct", unknown_struct, 2) != 0) return 4;',
    "nested array assertion",
)
for old, new in [
    ('return 4;', 'return 5;'),
    ('return 5;', 'return 6;'),
    ('return 6;', 'return 7;'),
    ('return 7;', 'return 8;'),
    ('return 8;', 'return 9;'),
    ('return 9;', 'return 10;'),
    ('return 10;', 'return 11;'),
]:
    # Only shift semantic-case return codes in the tail, not helper functions.
    pass
# Shift the remaining tail explicitly to keep deterministic unique exit codes.
test = test.replace('if (expect_semantic_failure_at("unknown_field", unknown_field, 3) != 0) return 4;', 'if (expect_semantic_failure_at("unknown_field", unknown_field, 3) != 0) return 5;')
test = test.replace('if (expect_semantic_failure_at("duplicate_field", duplicate_field, 3) != 0) return 5;', 'if (expect_semantic_failure_at("duplicate_field", duplicate_field, 3) != 0) return 6;')
test = test.replace('if (expect_semantic_failure_at("missing_field", missing_field, 3) != 0) return 6;', 'if (expect_semantic_failure_at("missing_field", missing_field, 3) != 0) return 7;')
test = test.replace('if (expect_semantic_failure_at("nested_type_mismatch", nested_type_mismatch, 5) != 0) return 7;', 'if (expect_semantic_failure_at("nested_type_mismatch", nested_type_mismatch, 5) != 0) return 8;')
test = test.replace('if (expect_semantic_failure_at("array_count_mismatch", array_count_mismatch, 3) != 0) return 8;', 'if (expect_semantic_failure_at("array_count_mismatch", array_count_mismatch, 3) != 0) return 9;')
test = test.replace('if (expect_semantic_failure_at("array_nonzero_repeat", array_nonzero_repeat, 3) != 0) return 9;', 'if (expect_semantic_failure_at("array_nonzero_repeat", array_nonzero_repeat, 3) != 0) return 10;')
test = test.replace('if (expect_semantic_failure_at("return_type_mismatch", return_type_mismatch, 4) != 0) return 10;', 'if (expect_semantic_failure_at("return_type_mismatch", return_type_mismatch, 4) != 0) return 11;')
TEST.write_text(test, encoding="utf-8")

status = STATUS.read_text(encoding="utf-8")
status = status.replace("**Atualizado em:** 2026-09-26", "**Atualizado em:** 2026-09-28", 1)
status = status.replace(
    "**Último baseline verde certificado antes do candidato 1.0:** `ea527ea`",
    "**Último baseline verde certificado antes do hardening atual:** `b63b6ba`",
    1,
)
status = status.replace(
    "**CI de referência:** Sotlas CI & Toolchain Build Farm #653 — workflow `success` nessa baseline. O commit de release precisa ter execução própria verde.",
    "**CI de referência:** Sotlas CI & Toolchain Build Farm #874 — workflow `success` nessa baseline. Todo hardening posterior precisa ter execução própria verde antes de substituir essa referência.",
    1,
)
status_anchor = "## Preview hardening update — 2026-09-26\n\n"
status_note = (
    "- Native self-host hardening moves typed `ExprStructLiteral` and contextual zero `ExprArrayRepeat` lowering into the canonical C emitter; top-level functions, locals and static impl methods therefore share the same backend path instead of a bootstrap-only constructor adapter. Shape/type/count mismatches remain fail-closed and semantically diagnosed before emission.\n"
)
status = replace_once(status, status_anchor, status_anchor + status_note, "status hardening note")
STATUS.write_text(status, encoding="utf-8")

print("post-preview hardening source transformations applied")
