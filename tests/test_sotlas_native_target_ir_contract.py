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
        self.assertIn("pub fn target_module_validate_cfg", source)
        self.assertIn("pub fn target_module_validate_ssa_dominance", source)
        self.assertIn("target_cfg_block_has_edge", source)
        self.assertIn("predecessor_count", source)
        self.assertIn("target_value_matches", source)
        self.assertIn("prior.block_id == incoming.block_id", source)

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

    def test_native_main_has_a_target_ir_entry_point_separate_from_c_emission(self):
        native_root = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        dependency_names = (
            "token", "ast", "lexer", "parser", "sema", "emitter_c",
            "target_ir", "lower_scalar", "x86_64_scalar",
        )
        # Keep this gate at the checker boundary: it type-checks the Sotlas
        # modules but does not ask Stage-0 to generate C for the Target IR.
        imported = []
        for name in dependency_names:
            dependency_path = next(native_root.rglob(f"{name}.sotlas"))
            imported.append(
                parse(
                    dependency_path.read_text(encoding="utf-8"),
                    filename=str(dependency_path),
                )
            )
        path = native_root / "main.sotlas"
        source = path.read_text(encoding="utf-8")
        check(parse(source, filename=str(path)), *_public_import_maps(imported))

        entry = source.split(
            "pub fn sotlas_native_lower_scalar_diagnostic(", 1
        )[1]
        self.assertIn("lower_scalar_module(&mut lowering", entry)
        self.assertNotIn("CEmitter::new", entry)
        self.assertNotIn("emit_module", entry)

    def test_x86_scalar_emitter_is_fail_closed_and_target_ir_native(self):
        native_root = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        target_path = native_root / "backend" / "target_ir.sotlas"
        target_module = parse(
            target_path.read_text(encoding="utf-8"), filename=str(target_path)
        )
        path = native_root / "backend" / "x86_64_scalar.sotlas"
        source = path.read_text(encoding="utf-8")
        check(
            parse(source, filename=str(path)),
            *_public_import_maps([target_module]),
        )

        self.assertIn("pub fn emit_x86_64_scalar_constant", source)
        self.assertIn("pub fn emit_elf64_scalar_function_object", source)
        self.assertIn("pub fn link_elf64_scalar_executable", source)
        self.assertIn("put_section_header", source)
        self.assertIn("TargetOpcode::ConstInt", source)
        self.assertIn("TargetOpcode::Return", source)
        self.assertIn("append_u32_decimal", source)
        self.assertIn("capacity - *length", source)
        self.assertNotIn("emitter_c", source)
        self.assertNotIn("CEmitter", source)
        self.assertNotIn("@extern(C)", source)


if __name__ == "__main__":
    unittest.main()
