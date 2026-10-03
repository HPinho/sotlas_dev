"""Testes unitários para o novo compilador nativo auto-hospedado (Sotlas in Sotlas)."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas import compile_source
from sotlas.llvm_toolchain import default_toolchain
from sotlas_compile.bootstrap import PREAMBLE, compile_module, emit_c, parse
from sotlas_compile import compile_source as canonical_compile_source


class TestSotlasNativeCompilerSelfhost(unittest.TestCase):
    def test_native_compiler_parses_rejects_and_emits_executable_c(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        order = ("token", "ast", "lexer", "parser", "sema", "emitter_c", "main")
        modules = {
            path.stem: parse(path.read_text(encoding="utf-8"), filename=str(path))
            for path in module_dir.glob("*.sotlas")
        }
        self.assertEqual(set(modules), set(order))

        fragments = [PREAMBLE]
        for name in order:
            compile_module(
                modules[name],
                [modules[dependency] for dependency in order if dependency != name],
            )
            fragments.append(emit_c(
                modules[name], mangle=False, include_preamble=False
            ))

        with tempfile.TemporaryDirectory(prefix="sotlas-native-compiler-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            compiler_obj = root / "native_compiler.obj"
            driver_c = root / "driver.c"
            driver_obj = root / "driver.obj"
            compiler_exe = root / ("native_compiler.exe" if os.name == "nt" else "native_compiler")
            generated_c = root / "generated.c"
            app_obj = root / "generated.obj"
            app_exe = root / ("generated.exe" if os.name == "nt" else "generated")
            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(
                "#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\n"
                "#include <string.h>\n"
                "extern size_t sotlas_native_compile_diagnostic(const uint8_t *, size_t, "
                "uint8_t *, size_t, uint32_t *, uint32_t *);\n"
                "int main(int argc, char **argv) {\n"
                "  if (argc == 4 && strcmp(argv[1], \"--compile\") == 0) {\n"
                "    static uint8_t input[65536], output[1048576];\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 30;\n"
                "    size_t len = fread(input, 1, sizeof(input), src);\n"
                "    int read_error = ferror(src); fclose(src); if (read_error) return 31;\n"
                "    uint32_t err_line = 0, err_col = 0;\n"
                "    size_t out_len = sotlas_native_compile_diagnostic(input, len, output, sizeof(output), &err_line, &err_col);\n"
                "    printf(\"%zu|%u|%u\\n\", out_len, err_line, err_col);\n"
                "    if (out_len == 0) return 0;\n"
                "    FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 32;\n"
                "    size_t written = fwrite(output, 1, out_len, dest); fclose(dest);\n"
                "    return written == out_len ? 0 : 33;\n"
                "  }\n"
                "  static const uint8_t bad[] = \"module test::bad;\\nfn (\";\n"
                "  static const uint8_t duplicate[] = \"module test::duplicate;\\n"
                "fn run() -> i32 { return 0; }\\n"
                "fn run() -> i32 { return 1; }\\n\";\n"
                "  static const uint8_t duplicate_parameter[] = "
                "\"module test::duplicate_parameter;\\n"
                "fn run(value: i32, value: i32) -> i32 { return value; }\\n\";\n"
                "  static const uint8_t duplicate_local[] = "
                "\"module test::duplicate_local;\\nfn run() -> i32 {\\n"
                " let item: i32 = 0;\\n let item: i32 = 1;\\n return item;\\n}\\n\";\n"
                "  static const uint8_t unsupported_struct[] = "
                "\"module test::unsupported_struct;\\nstruct Item {\\n value: i32,\\n}\\n\";\n"
                "  static const uint8_t unsupported_enum[] = "
                "\"module test::unsupported_enum;\\nenum Choice {\\n Ready,\\n}\\n\";\n"
                "  static const uint8_t break_outside_loop[] = "
                "\"module test::break_outside_loop;\\nbreak;\\n\";\n"
                "  static const uint8_t continue_outside_loop[] = "
                "\"module test::continue_outside_loop;\\ncontinue;\\n\";\n"
                "  static const uint8_t return_outside_function[] = "
                "\"module test::return_outside_function;\\nreturn 0;\\n\";\n"
                "  static const uint8_t unknown_local[] = "
                "\"module test::unknown_local;\\nfn run() -> i32 { return missing; }\\n\";\n"
                "  static const uint8_t unknown_call[] = "
                "\"module test::unknown_call;\\nfn run() -> i32 { return missing(); }\\n\";\n"
                "  static const uint8_t wrong_arity[] = "
                "\"module test::wrong_arity;\\n"
                "fn identity(seed: i32) -> i32 { return seed; }\\n"
                "fn run() -> i32 { return identity(); }\\n\";\n"
                "  static const uint8_t wrong_argument_type[] = "
                "\"module test::wrong_argument_type;\\n"
                "fn consume(seed: u32) -> u32 { return seed; }\\n"
                "fn run(value: f32) -> u32 { return consume(value); }\\n\";\n"
                "  static const uint8_t wrong_expression_type[] = "
                "\"module test::wrong_expression_type;\\n"
                "fn consume(seed: u32) -> u32 { return seed; }\\n"
                "fn run(left: f32, right: u32) -> u32 { return consume(left + right); }\\n\";\n"
                "  static const uint8_t wrong_return_type[] = "
                "\"module test::wrong_return_type;\\n"
                "fn convert(value: f32) -> u32 { return value; }\\n\";\n"
                "  static const uint8_t missing_return_value[] = "
                "\"module test::missing_return_value;\\n"
                "fn run() -> i32 { return; }\\n\";\n"
                "  static const uint8_t missing_return_path[] = "
                "\"module test::missing_return_path;\\n"
                "fn run(flag: bool) -> i32 { if flag { return 1; } }\\n\";\n"
                "  static const uint8_t both_return_paths[] = "
                "\"module test::both_return_paths;\\n"
                "fn run(flag: bool) -> i32 { if flag { return 1; } else { return 2; } }\\n\";\n"
                "  static const uint8_t immutable_assignment[] = "
                "\"module test::immutable_assignment;\\nfn run() -> i32 {\\n"
                " let answer: i32 = 0;\\n answer = 1;\\n return answer;\\n}\\n\";\n"
                "  static const uint8_t good[] = \"module test::good;\\n"
                "fn identity(seed: i32) -> i32 { var answer: i32 = seed; answer = answer; return answer; }\\n"
                "fn forward(value: i32) -> i32 { return identity(value); }\\n"
                "fn arithmetic(value: i32) -> i32 { return identity(value + 0); }\\n"
                "fn unsafe_forward(value: i32) -> i32 { unsafe { return value; } }\\n"
                "pub fn main() -> i32 { return unsafe_forward(arithmetic(0)); }\\n\";\n"
                "  uint8_t output[65536]; uint32_t line = 0, col = 0;\n"
                "  size_t size = sotlas_native_compile_diagnostic(bad, sizeof(bad)-1, "
                "output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 4) return 1;\n"
                "  size = sotlas_native_compile_diagnostic(duplicate, sizeof(duplicate)-1, "
                "output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 1) return 5;\n"
                "  size = sotlas_native_compile_diagnostic(duplicate_parameter, "
                "sizeof(duplicate_parameter)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 20) { "
                "fprintf(stderr, \"duplicate parameter: %zu %u %u\\n\", size, line, col); "
                "return 6; }\n"
                "  size = sotlas_native_compile_diagnostic(duplicate_local, "
                "sizeof(duplicate_local)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 4 || col != 2) return 7;\n"
                "  size = sotlas_native_compile_diagnostic(unsupported_struct, "
                "sizeof(unsupported_struct)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 2) { "
                "fprintf(stderr, \"unsupported struct: %zu %u %u\\n\", size, line, col); "
                "return 8; }\n"
                "  size = sotlas_native_compile_diagnostic(unsupported_enum, "
                "sizeof(unsupported_enum)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 2) { "
                "fprintf(stderr, \"unsupported enum: %zu %u %u\\n\", size, line, col); "
                "return 9; }\n"
                "  size = sotlas_native_compile_diagnostic(break_outside_loop, "
                "sizeof(break_outside_loop)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) return 10;\n"
                "  size = sotlas_native_compile_diagnostic(continue_outside_loop, "
                "sizeof(continue_outside_loop)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) return 11;\n"
                "  size = sotlas_native_compile_diagnostic(return_outside_function, "
                "sizeof(return_outside_function)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) return 12;\n"
                "  size = sotlas_native_compile_diagnostic(unknown_local, "
                "sizeof(unknown_local)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 26) { "
                "fprintf(stderr, \"unknown local: %zu %u %u\\n\", size, line, col); "
                "return 13; }\n"
                "  size = sotlas_native_compile_diagnostic(unknown_call, "
                "sizeof(unknown_call)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 26) { "
                "fprintf(stderr, \"unknown call: %zu %u %u\\n\", size, line, col); "
                "return 15; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_arity, "
                "sizeof(wrong_arity)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 26) { "
                "fprintf(stderr, \"wrong arity: %zu %u %u\\n\", size, line, col); "
                "return 16; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_argument_type, "
                "sizeof(wrong_argument_type)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 44) { "
                "fprintf(stderr, \"argument type: %zu %u %u\\n\", size, line, col); "
                "return 17; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_expression_type, "
                "sizeof(wrong_expression_type)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 60) { "
                "fprintf(stderr, \"expression type: %zu %u %u\\n\", size, line, col); "
                "return 18; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_return_type, "
                "sizeof(wrong_return_type)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 40) { "
                "fprintf(stderr, \"return type: %zu %u %u\\n\", size, line, col); "
                "return 19; }\n"
                "  size = sotlas_native_compile_diagnostic(missing_return_value, "
                "sizeof(missing_return_value)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 19) { "
                "fprintf(stderr, \"missing return value: %zu %u %u\\n\", size, line, col); "
                "return 20; }\n"
                "  size = sotlas_native_compile_diagnostic(missing_return_path, "
                "sizeof(missing_return_path)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) { "
                "fprintf(stderr, \"missing return path: %zu %u %u\\n\", size, line, col); "
                "return 21; }\n"
                "  size = sotlas_native_compile_diagnostic(both_return_paths, "
                "sizeof(both_return_paths)-1, output, sizeof(output), &line, &col);\n"
                "  if (size == 0 || line != 0 || col != 0) return 22;\n"
                "  size = sotlas_native_compile_diagnostic(immutable_assignment, "
                "sizeof(immutable_assignment)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 4 || col != 2) { "
                "fprintf(stderr, \"immutable assignment: %zu %u %u\\n\", size, line, col); "
                "return 14; }\n"
                "  size = sotlas_native_compile_diagnostic(good, sizeof(good)-1, "
                "output, sizeof(output), &line, &col);\n"
                "  if (size == 0 || line != 0 || col != 0 || argc != 2) return 2;\n"
                "  FILE *file = fopen(argv[1], \"wb\"); if (!file) return 3;\n"
                "  size_t written = fwrite(output, 1, size, file); fclose(file);\n"
                "  return written == size ? 0 : 4;\n}\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], compiler_exe)
            run_compiler = subprocess.run(
                [str(compiler_exe), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_compiler.returncode, 0, run_compiler.stderr)
            self.assertTrue(generated_c.is_file())

            default_toolchain.compile_c_to_obj(generated_c, app_obj, opt_level=0)
            default_toolchain.link_native_binary([app_obj], app_exe)
            run_app = subprocess.run(
                [str(app_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(run_app.returncode, 0, run_app.stderr)

            cases = (
                (
                    "parser_tree",
                    "module parity::tree;\n"
                    "pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
                    "pub fn apply(value: i32) -> i32 { return add(value, 2); }\n",
                    True,
                    False,
                ),
                (
                    "parser_diagnostic",
                    "module parity::syntax;\n"
                    "pub fn broken() -> i32 { return 1 + ; }\n",
                    False,
                    True,
                ),
                (
                    "semantic_duplicate",
                    "module parity::duplicate;\n"
                    "fn run() -> i32 { return 1; }\n"
                    "fn run() -> i32 { return 2; }\n",
                    False,
                    False,
                ),
                (
                    "semantic_unknown_name",
                    "module parity::unknown;\n"
                    "fn run() -> i32 { return missing; }\n",
                    False,
                    False,
                ),
                (
                    "semantic_return_type",
                    "module parity::wrong_type;\n"
                    "fn run() -> i32 { return true; }\n",
                    False,
                    False,
                ),
                (
                    "lex_unterminated_block_comment",
                    "module parity::bad_comment;\n/* never closed",
                    False,
                    True,
                ),
                (
                    "lex_unterminated_string",
                    'module parity::bad_string;\nfn run() -> i32 { return "open; }\n',
                    False,
                    True,
                ),
                (
                    "lex_invalid_character",
                    "module parity::bad_character;\n§\n",
                    False,
                    True,
                ),
            )
            for name, source, expected_acceptance, compare_location in cases:
                with self.subTest(case=name):
                    source_path = root / f"{name}.sotlas"
                    native_c = root / f"{name}.c"
                    source_path.write_text(source, encoding="utf-8")
                    try:
                        canonical_c = canonical_compile_source(
                            source, filename=f"{name}.sotlas"
                        )
                        canonical_error = None
                    except Exception as error:
                        canonical_c = None
                        canonical_error = error
                    canonical_accepted = canonical_error is None
                    self.assertEqual(canonical_accepted, expected_acceptance)

                    native_result = subprocess.run(
                        [str(compiler_exe), "--compile", str(source_path), str(native_c)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(native_result.returncode, 0, native_result.stderr)
                    fields = native_result.stdout.strip().split("|")
                    self.assertEqual(len(fields), 3, native_result.stdout)
                    native_size, native_line, native_col = map(int, fields)
                    native_accepted = native_size > 0
                    self.assertEqual(native_accepted, canonical_accepted)

                    if compare_location:
                        self.assertIsNotNone(canonical_error)
                        self.assertEqual(
                            (native_line, native_col),
                            (canonical_error.line, canonical_error.column),
                        )

                    if name == "parser_tree":
                        self.assertTrue(native_c.is_file())
                        reference_module = parse(source, filename=name)
                        names = [function.name for function in reference_module.functions]
                        self.assertEqual(names, ["add", "apply"])
                        self.assertEqual(
                            [len(function.params) for function in reference_module.functions],
                            [2, 1],
                        )

                        # Both pipelines accept the same parsed module, and
                        # their emitted C must expose the same function ABI.
                        for function_name, arity in (
                            ("add", 2),
                            ("apply", 1),
                        ):
                            for code in (native_c.read_text(encoding="utf-8"), canonical_c):
                                signature = next(
                                    (
                                        line.strip()
                                        for line in code.splitlines()
                                        if function_name + "(" in line
                                        and "{" in line
                                    ),
                                    None,
                                )
                                self.assertIsNotNone(
                                    signature, f"missing {function_name} definition"
                                )
                                self.assertEqual(
                                    signature.count(",") + (0 if "()" in signature else 1),
                                    arity,
                                )

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

    def test_native_parser_records_unexpected_token_location_and_rejects_module(self):
        parser_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        text = parser_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(parser_file))
        self.assertIn("pub error_count: usize;", text)
        self.assertIn("pub error_line: u32;", text)
        self.assertIn("pub error_col: u32;", text)
        self.assertIn("self.error_line = tok.span.line;", text)
        self.assertIn("self.error_col = tok.span.col;", text)
        self.assertIn("self.error_count = self.error_count + 1;", text)
        error_check = text.index("if self.error_count != 0")
        self.assertIn("return 0;", text[error_check:])
        self.assertIn("error_line", c_code)
        self.assertIn("error_col", c_code)

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

    def test_native_result_u64_i32_preserves_err_zero(self):
        abi_file = ROOT / "include" / "sotlas" / "sotlas_abi.h"
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        abi_text = abi_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_RESULT_U64_I32_DEFINED", abi_text)
        self.assertIn("bool is_ok;", abi_text)
        self.assertIn("uint64_t ok;", abi_text)
        self.assertIn("int32_t err;", abi_text)
        self.assertIn("SotlasResultU64I32", emitter_text)
        self.assertIn(".payload.ok", emitter_text)
        self.assertIn(".payload.err", emitter_text)
        self.assertIn(".is_ok", emitter_text)

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
        self.assertIn('return self.write_str("SotlasResultU64I32", 18);', emitter_text)
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

    def test_native_emitter_lowers_result_ok_err_constructors(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn source_slice_equals_compact", text)
        self.assertIn("pub fn result_constructor_kind", text)
        self.assertIn('"Result::ok"', text)
        self.assertIn('"Result::err"', text)
        self.assertIn('"Result::Ok"', text)
        self.assertIn('"Result::Err"', text)
        self.assertIn("pub fn emit_result_u64_constructor", text)
        self.assertIn('"(SotlasResultU64I32){ .is_ok = true, .payload.ok = "', text)
        self.assertIn('"(SotlasResultU64I32){ .is_ok = false, .payload.err = "', text)
        self.assertIn("self.emit_result_u64_constructor(ret.first_child)", text)
        self.assertIn("node.kind == AstKind::ExprPath", text)

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
        self.assertIn("self.emit_expression_for_type(ret.first_child, type_index)", text)
        self.assertIn("self.emit_return_scope_defers(return_index)", text)
        self.assertIn('"return __sotlas_return_value;', text)
        capture_at = text.index("self.emit_expression_for_type(ret.first_child, type_index)")
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

    def test_native_emitter_lowers_result_try_statement(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_try_statement", text)
        self.assertIn("try_node.kind != AstKind::TryExpr", text)
        self.assertIn("self.try_call_returns_result_u64_i32(try_index)", text)
        self.assertIn("SotlasResultU64I32 __sotlas_try_value = ", text)
        self.assertIn("self.emit_function_exit_defers(try_index)", text)
        self.assertIn('"return __sotlas_try_value;', text)
        self.assertIn("node.kind == AstKind::TryExpr", text)
        self.assertIn("return self.emit_try_statement(index);", text)

    def test_native_emitter_lowers_direct_result_try_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_module_function_by_name", text)
        self.assertIn("pub fn try_call_returns_result_u64_i32", text)
        self.assertIn("pub fn try_context_returns_result_u64_i32", text)
        self.assertIn("pub fn emit_try_let_statement", text)
        self.assertIn('"SotlasResultU64I32 __sotlas_try_"', text)
        self.assertIn('".is_ok) {\\n"', text)
        self.assertIn("self.emit_function_exit_defers(let_index)", text)
        self.assertIn('"return __sotlas_try_"', text)
        self.assertIn('".payload.ok;\\n"', text)
        self.assertIn(
            "return self.emit_try_let_statement(index, type_index, init_index);",
            text,
        )

    def test_native_emitter_inferrs_u64_from_result_try_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_try_let_u64_statement", text)
        self.assertIn("type_node.kind == AstKind::TryExpr", text)
        self.assertIn(
            "return self.emit_try_let_u64_statement(index, type_index);",
            text,
        )
        self.assertIn("uint64_t ", text)
        self.assertIn('";\\nif (!__sotlas_try_"', text)
        self.assertIn(
            "return self.emit_try_let_u64_statement(let_index, try_index);",
            text,
        )

    def test_native_emitter_lowers_result_constructor_local_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn(
            "self.type_ref_is_result_u64_i32(type_index)",
            text,
        )
        self.assertIn(
            "self.result_constructor_kind(init_index) != 0",
            text,
        )
        self.assertIn(
            "self.emit_result_u64_constructor(init_index)",
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
        self.assertIn("self.emit_expression_for_type(init_index, type_index)", text)
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
        self.assertIn("sotlas_native_compile_diagnostic", c_code)
        self.assertIn("g_token_buffer", c_code)
        self.assertIn("g_ast_node_buffer", c_code)
        self.assertIn("AST_NODE_BUFFER_CAPACITY", c_code)
        self.assertIn("if !lex.is_at_end()", text)
        self.assertIn("CEmitter", c_code)

    def test_native_compiler_exposes_parser_error_line_and_column(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        text = main_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(main_file))
        self.assertIn("pub fn sotlas_native_compile_diagnostic(", text)
        self.assertIn("error_line: *mut u32", text)
        self.assertIn("error_col: *mut u32", text)
        self.assertIn("*error_line = p.error_line", text)
        self.assertIn("*error_col = p.error_col", text)
        self.assertIn("sotlas_native_compile_diagnostic(", c_code)
        self.assertIn("sotlas_native_compile(", text)


if __name__ == "__main__":
    unittest.main()
