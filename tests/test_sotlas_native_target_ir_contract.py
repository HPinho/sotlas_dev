"""Gate for the Sotlas-written backend-neutral Target IR contract."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile.bootstrap import _public_import_maps, check, parse


class SotlasNativeTargetIRContractTests(unittest.TestCase):
    def test_target_ir_contract_is_valid_sotlas_without_c_backend_dependencies(self):
        path = (
            ROOT
            / "bootstrap"
            / "sotlas"
            / "native_compiler"
            / "backend"
            / "target_ir.sotlas"
        )
        source = path.read_text(encoding="utf-8")
        module = parse(source, filename=str(path))
        check(module)

        self.assertIn("pub enum TargetOpcode", source)
        self.assertIn("pub struct TargetInstruction", source)
        self.assertIn("pub struct TargetFunction", source)
        self.assertIn("pub struct TargetParameter", source)
        self.assertIn("pub struct TargetModule", source)
        self.assertIn("pub parameter_count: u32", source)
        self.assertIn("pub fn target_opcode_is_terminator", source)
        self.assertIn("pub fn target_opcode_is_semantic_only", source)
        self.assertIn("pub fn target_type_is_integer", source)

        # This contract is intentionally independent of the legacy C route.
        self.assertNotIn("emitter_c", source)
        self.assertNotIn("CEmitter", source)
        self.assertNotIn("@extern(C)", source)

    def test_scalar_ast_lowering_contract_is_typed_and_native(self):
        native_root = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        paths = [
            native_root / "token.sotlas",
            native_root / "ast.sotlas",
            native_root / "sema.sotlas",
            native_root / "backend" / "target_ir.sotlas",
        ]
        imported = [
            parse(path.read_text(encoding="utf-8"), filename=str(path))
            for path in paths
        ]
        path = native_root / "backend" / "lower_scalar.sotlas"
        source = path.read_text(encoding="utf-8")
        module = parse(source, filename=str(path))
        check(module, *_public_import_maps(imported))

        self.assertIn("pub fn lower_scalar_module", source)
        self.assertIn("TargetOpcode::ConstInt", source)
        self.assertIn("TargetOpcode::Add", source)
        self.assertIn("TargetOpcode::Sub", source)
        self.assertIn("TargetOpcode::Mul", source)
        self.assertIn("TargetOpcode::Return", source)
        self.assertIn("return lowering.reject", source)
        self.assertNotIn("emitter_c", source)
        self.assertNotIn("CEmitter", source)
        self.assertNotIn("@extern(C)", source)


if __name__ == "__main__":
    unittest.main()
