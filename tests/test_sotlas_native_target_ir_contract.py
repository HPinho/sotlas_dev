"""Gate for the Sotlas-written backend-neutral Target IR contract."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas_compile.bootstrap import compile_module, parse


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
        compile_module(module, [])

        self.assertIn("pub enum TargetOpcode", source)
        self.assertIn("pub struct TargetInstruction", source)
        self.assertIn("pub struct TargetFunction", source)
        self.assertIn("pub struct TargetModule", source)
        self.assertIn("pub fn target_opcode_is_terminator", source)
        self.assertIn("pub fn target_opcode_is_semantic_only", source)
        self.assertIn("pub fn target_type_is_integer", source)

        # This contract is intentionally independent of the legacy C route.
        self.assertNotIn("emitter_c", source)
        self.assertNotIn("CEmitter", source)
        self.assertNotIn("@extern(C)", source)


if __name__ == "__main__":
    unittest.main()
