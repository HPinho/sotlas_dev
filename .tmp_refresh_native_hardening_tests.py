from pathlib import Path

ROOT = Path(__file__).resolve().parent
SELFHOST = ROOT / "tests/test_sotlas_native_compiler_selfhost.py"
TOKEN = ROOT / "tests/test_sotlas_native_token_constructor_parser.py"

text = SELFHOST.read_text(encoding="utf-8")
old = '        self.assertIn("self.emit_expression(ret.first_child)", text)\n'
new = '        self.assertIn("self.emit_expression_for_type(ret.first_child, type_index)", text)\n'
if text.count(old) != 1:
    raise SystemExit(f"return assertion anchor count={text.count(old)}")
text = text.replace(old, new, 1)
text = text.replace(
    '        capture_at = text.index("self.emit_expression(ret.first_child)")\n',
    '        capture_at = text.index("self.emit_expression_for_type(ret.first_child, type_index)")\n',
    1,
)
old_local = '        self.assertIn("self.emit_expression(init_index)", text)\n'
new_local = '        self.assertIn("self.emit_expression_for_type(init_index, type_index)", text)\n'
if text.count(old_local) != 1:
    raise SystemExit(f"local assertion anchor count={text.count(old_local)}")
text = text.replace(old_local, new_local, 1)
SELFHOST.write_text(text, encoding="utf-8")

token = TOKEN.read_text(encoding="utf-8")
old_token = '            self.assertIn("return (Token){ ", lowered_text)\n'
new_token = (
    '            self.assertIn("Token __sotlas_return_value = (Token){ ", lowered_text)\n'
    '            self.assertIn("return __sotlas_return_value;", lowered_text)\n'
)
if token.count(old_token) != 1:
    raise SystemExit(f"token assertion anchor count={token.count(old_token)}")
token = token.replace(old_token, new_token, 1)
TOKEN.write_text(token, encoding="utf-8")
print("native hardening test contracts refreshed")
