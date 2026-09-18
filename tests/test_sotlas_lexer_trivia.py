import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer, Token
from sotlas.token_types import TK


class TestSotlasLexerTriviaAndLiterals(unittest.TestCase):
    def test_lossless_trivia_reconstruction(self):
        source = """// Cabeçalho de módulo do kernel
module bkn::network;

/* Driver de interface virtio-net */
pub fn init_nic(pci_id: u32) -> bool {
    let base = 0x1000; // Base MMIO
    return true;
}
"""
        lexer = Lexer(source, "test_trivia.sotlas")
        tokens = lexer.tokenize()

        # Verifica que os comentários estão preservados nas trivias
        has_comment = any("// Cabeçalho" in t.leading_trivia for t in tokens)
        self.assertTrue(has_comment, "Comentário de linha deve estar preservado no leading_trivia")

        has_block_comment = any("/* Driver de interface" in t.leading_trivia for t in tokens)
        self.assertTrue(has_block_comment, "Comentário de bloco deve estar preservado no leading_trivia")

        # Reconstrução sem perdas: junta todas as trivias e valores dos tokens
        reconstructed = "".join(t.leading_trivia + t.value for t in tokens)
        self.assertEqual(reconstructed, source)

    def test_byte_string_literal(self):
        code = 'let ETHERNET_BROADCAST: [u8; 6] = b"\\xFF\\xFF\\xFF\\xFF\\xFF\\xFF";'
        tokens = Lexer(code, "test_bytes.sotlas").tokenize()
        byte_tokens = [t for t in tokens if t.kind == TK.BYTE_STR_LIT]
        self.assertEqual(len(byte_tokens), 1)
        self.assertEqual(len(byte_tokens[0].value), 6)
        self.assertEqual(byte_tokens[0].value, "\xFF\xFF\xFF\xFF\xFF\xFF")

    def test_raw_string_multiline(self):
        code = 'let SHADER: &str = r#"void main() { gl_FragColor = vec4(1.0); }"#;'
        tokens = Lexer(code, "test_raw.sotlas").tokenize()
        raw_tokens = [t for t in tokens if t.kind == TK.RAW_STR_LIT]
        self.assertEqual(len(raw_tokens), 1)
        self.assertIn("void main()", raw_tokens[0].value)

    def test_interpolated_string_token(self):
        code = 'let msg = $"MMIO Base: {base}, IRQ: {irq}";'
        tokens = Lexer(code, "test_interp.sotlas").tokenize()
        interp_tokens = [t for t in tokens if t.kind == TK.INTERPOLATED_STR_LIT]
        self.assertEqual(len(interp_tokens), 1)
        self.assertEqual(interp_tokens[0].value, "MMIO Base: {base}, IRQ: {irq}")


if __name__ == "__main__":
    unittest.main()
