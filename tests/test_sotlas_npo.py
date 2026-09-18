import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.codegen_c import CodegenC


class TestSotlasNPO(unittest.TestCase):
    def test_npo_option_rawphys_generates_pointer(self):
        code = """module test_npo;
        pub fn check_npo() {
            let mut opt_ptr: Option<*rawphys u32> = Option::None;
            let val: u32 = 100;
            opt_ptr = Option::Some(&val);
            if let Option::Some(addr) = opt_ptr {
                let x = *addr;
            }
        }
        """
        tokens = Lexer(code, "test_npo.sotlas").tokenize()
        ast = Parser(tokens, "test_npo.sotlas").parse()
        codegen = CodegenC(ast)
        c_code = codegen.emit()

        # Verifica que Option<*rawphys u32> gerou como ponteiro volátil em vez de struct Option
        self.assertIn("volatile uint32_t*", c_code)
        # Verifica que Option::None é emitido como ponteiro nulo (0 / NULL)
        self.assertIn("((void*)0)", c_code)
        # Verifica pattern match com NPO choose_expr
        self.assertIn("__builtin_classify_type", c_code)


if __name__ == "__main__":
    unittest.main()
