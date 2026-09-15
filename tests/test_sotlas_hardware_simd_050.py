"""Testes unitários para as novas capacidades do Sotlas 0.5.0:
- Hardware MMIO Registers com campos determinísticos de bits (register Reg: u32)
- Validação de largura de bits e detecção de overflow e overlaps de campos em tempo de compilação
- Volatile code generation para desreferenciamento de registradores via ponteiros de topologia
- Tipos SIMD vetoriais nativos (f32x4, f32x8, u8x16, u8x32, i32x4, etc.) e aritmética vetorial
- Verificação de tipos em operações com vetores
- Subcomando CLI `sotlas lsp` com suporte a --stdio
- Sincronização de versão 0.5.0
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "compiler"))

import sotlas
from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.sema import Sema, SotlasSemaError
from sotlas.codegen_c import CodegenC


class TestSotlasHardwareSimd050(unittest.TestCase):
    def _compile_ast(self, source: str, filename: str = "<test>"):
        tokens = Lexer(source, filename).tokenize()
        ast = Parser(tokens, filename).parse()
        sema = Sema(ast, filename, source)
        sema.check()
        return ast

    def _emit_c(self, source: str, filename: str = "<test>"):
        ast = self._compile_ast(source, filename)
        return CodegenC(ast).emit()

    def test_version_sync_050(self):
        self.assertEqual(sotlas.SOTLAS_VERSION, "0.5.0")
        self.assertEqual(sotlas.SOTLAS_LANG_VERSION, "0.5.0")

        pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.5.0"', pyproject)

        sotlas_toml = (_ROOT / "sotlas.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.5.0"', sotlas_toml)

        lock_path = _ROOT / "toolchain" / "sotlas.lock.json"
        lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock_data["language_version"], "0.5.0")

    def test_register_declaration_and_field_offsets(self):
        source = """\
module test::i2c;

pub register I2cControl: u32 {
    enable:      0;
    speed_mode:  1..2;
    restart_en:  5;
    master_mode: 6;
    rx_fifo_full: 8;
}

pub fn configure(val: I2cControl) -> u32 {
    return val.speed_mode;
}
"""
        ast = self._compile_ast(source)
        reg = [d for d in ast.decls if getattr(d, "name", "") == "I2cControl"][0]
        self.assertEqual(len(reg.fields), 5)
        self.assertEqual(reg.fields[0].name, "enable")
        self.assertEqual(reg.fields[0].lo_bit, 0)
        self.assertEqual(reg.fields[0].hi_bit, 0)
        self.assertEqual(reg.fields[1].name, "speed_mode")
        self.assertEqual(reg.fields[1].lo_bit, 1)
        self.assertEqual(reg.fields[1].hi_bit, 2)

    def test_register_bit_overflow_rejected(self):
        source = """\
module test::overflow;

pub register BadReg: u8 {
    valid: 0..7;
    overflow: 8;
}
"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self._compile_ast(source)
        self.assertIn("exceeds 8-bit backing type", str(ctx.exception))

    def test_register_bit_overlap_rejected(self):
        source = """\
module test::overlap;

pub register OverlapReg: u32 {
    field_a: 0..3;
    field_b: 2..5;
}
"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self._compile_ast(source)
        self.assertIn("overlaps bit 2 with field 'field_a'", str(ctx.exception))

    def test_register_unknown_field_rejected(self):
        source = """\
module test::field_error;

pub register MyReg: u32 {
    flag: 0;
}

pub fn test(r: MyReg) -> u32 {
    return r.non_existent;
}
"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self._compile_ast(source)
        self.assertIn("register 'MyReg' has no field 'non_existent'", str(ctx.exception))

    def test_register_volatile_pointer_codegen(self):
        source = """\
module test::driver;

pub register DeviceCtrl: u32 {
    enable: 0;
    reset: 1;
    speed: 2..3;
}

pub fn init_device(ptr: *rawphys DeviceCtrl) {
    unsafe {
        ptr.enable = 1;
        ptr.speed = 3;
    }
}
"""
        c_code = self._emit_c(source)
        self.assertIn("typedef uint32_t DeviceCtrl;", c_code)
        self.assertIn("DeviceCtrl_get_enable", c_code)
        self.assertIn("DeviceCtrl_set_enable", c_code)
        self.assertIn("DeviceCtrl_set_speed", c_code)
        self.assertIn("*ptr = DeviceCtrl_set_enable(*ptr, 1);", c_code)
        self.assertIn("*ptr = DeviceCtrl_set_speed(*ptr, 3);", c_code)

    def test_simd_vector_types_and_arithmetic(self):
        source = """\
module test::simd;

pub fn vector_add(a: f32x4, b: f32x4) -> f32x4 {
    let c: f32x4 = a + b;
    return c;
}

pub fn byte_vectors(a: u8x16, b: u8x16) -> u8x16 {
    return a + b;
}
"""
        ast = self._compile_ast(source)
        self.assertIsNotNone(ast)
        c_code = self._emit_c(source)
        self.assertIn("typedef float    f32x4 __attribute__((vector_size(16)));", c_code)
        self.assertIn("typedef uint8_t  u8x16 __attribute__((vector_size(16)));", c_code)
        self.assertIn("f32x4 vector_add(f32x4 a, f32x4 b)", c_code)
        self.assertIn("(a + b)", c_code)

    def test_simd_vector_mismatch_rejected(self):
        source = """\
module test::mismatch;

pub fn invalid_add(a: f32x4, b: u8x16) -> f32x4 {
    return a + b;
}
"""
        with self.assertRaises(SotlasSemaError) as ctx:
            self._compile_ast(source)
        self.assertIn("type mismatch in vector operation", str(ctx.exception))

    def test_sotlas_lsp_cli_help(self):
        cli_path = _ROOT / "compiler" / "sotlas" / "cli.py"
        res = subprocess.run([sys.executable, str(cli_path), "lsp", "--help"],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("usage: sotlas lsp", res.stdout)
        self.assertIn("--stdio", res.stdout)


if __name__ == "__main__":
    unittest.main()
