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

    def test_native_call_capability_metadata_is_validated_before_emission(self):
        """Typed per-argument capability roles are bounded and fail closed."""
        base = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "backend"
        ir = (base / "target_ir.sotlas").read_text(encoding="utf-8")
        lowering = (base / "lower_scalar.sotlas").read_text(encoding="utf-8")
        self.assertIn("pub const TARGET_CALL_CAPABILITIES_TYPED: u32 = 16;", ir)
        self.assertIn("instruction.flags != TARGET_CALL_CAPABILITIES_TYPED", ir)
        self.assertIn("instruction.operand_count > 24", ir)
        self.assertIn("(instruction.immediate_bits >>", ir)
        self.assertIn("pub fn call_capability_profile", lowering)
        self.assertIn("self.function_parameter_domain_from_ast(", lowering)
        self.assertIn("call.flags = TARGET_CALL_CAPABILITIES_TYPED;", lowering)
        self.assertIn("call.immediate_bits = call_capabilities;", lowering)
        self.assertIn("(*(self.instructions + self.instruction_count - 1)).immediate_bits = call_capabilities;", lowering)

    def test_sv848b_windows_slashes_unsigned_parity_contract(self):
        """Equivalent parity without native modulo in nested argv parsing."""
        path = ROOT / "bootstrap" / "sotlas" / "native_driver" / "windows.sotlas"
        source = path.read_text(encoding="utf-8")
        self.assertIn("if (slashes & 1) == 1 {", source)
        self.assertIn("count = slashes >> 1;", source)
        self.assertNotIn("count = slashes / 2;", source)
        self.assertNotIn("slashes % 2", source)
        for count in range(513):
            self.assertEqual((count & 1) == 1, count % 2 == 1)
            self.assertEqual(count >> 1, count // 2)

    def test_sv848b_stage1_large_native_ir_has_real_backing_capacity(self):
        """Reinforce the native Windows cross-build without weakening its gate."""
        source = (ROOT / "bootstrap" / "sotlas" / "native_compiler" /
                  "main.sotlas").read_text(encoding="utf-8")
        bounds = {
            "TARGET_VALUE_CAPACITY": ("TargetValue", "g_target_values", 131072),
            "TARGET_INSTR_CAPACITY": ("TargetInstruction", "g_target_instructions", 262144),
            "TARGET_OPERAND_CAPACITY": ("TargetOperand", "g_target_operands", 524288),
            "TARGET_BLOCK_CAPACITY": ("TargetBlock", "g_target_blocks", 65536),
        }
        for limit, (element, variable, expected) in bounds.items():
            with self.subTest(capacity=limit):
                self.assertIn(
                    f"pub const {limit}: usize = {expected};", source
                )
                self.assertIn(
                    f"static mut {variable}: [{element}; {expected}] = 0;", source
                )
        # Keep the stage-one frontend parser's existing accepted source bound
        # rather than bypassing diagnostics or changing the test workload.
        self.assertIn("AST_NODE_BUFFER_CAPACITY: usize = 262144", source)
        self.assertIn("lower_scalar_module(&mut lowering", source)
        self.assertIn("TARGET_VALUE_CAPACITY,", source)
        self.assertIn("TARGET_INSTR_CAPACITY,", source)
        self.assertIn("TARGET_OPERAND_CAPACITY,", source)
        self.assertIn("TARGET_BLOCK_CAPACITY,", source)

    def test_windows_native_stage2_argument_parser_split_preserves_bounds(self):
        """The native PE selfhost compiler keeps bounded argv decode isolated."""
        path = ROOT / "bootstrap" / "sotlas" / "native_driver" / "windows.sotlas"
        source = path.read_text(encoding="utf-8")
        subparser = source.split("fn windows_parse_one_argument(", 1)[1]
        subparser = subparser.split("fn windows_parse_arguments()", 1)[0]
        outer = source.split("fn windows_parse_arguments()", 1)[1]
        outer = outer.split("@system pub fn main_entry()", 1)[0]
        self.assertIn("windows_push_argument_byte(argument,index,", subparser)
        self.assertIn("if index == 4096 { return 0; }", subparser)
        self.assertIn("if quoted { return 0; }", subparser)
        self.assertIn("windows_argument_pointers[argument]", subparser)
        self.assertIn("windows_parse_one_argument(command,limit,position,argument)", outer)
        self.assertIn("if next == 0 || next <= position { return 0; }", outer)
        self.assertIn("if argument >= 67 { return 0; }", outer)
        self.assertIn("if limit == 32768 { return 0; }", outer)
        self.assertIn("if (slashes & 1) == 1 {", subparser)
        self.assertIn("count = slashes >> 1;", subparser)
        self.assertNotIn("windows_append_argument(argument,index,", subparser)
        self.assertNotIn("windows_append_argument(argument,index,", outer)
        # The actual Windows Stage2 -> Stage3 PE fixed-point execution remains
        # mandatory in test_sotlas_native_windows_driver.
    def test_sv848b_windows_driver_ir_arenas_match_compiler_profile(self):
        """Native Stage2/Stage3 must not silently retain Stage1's old arenas."""
        root = ROOT / "bootstrap" / "sotlas"
        compiler = (root / "native_compiler" / "main.sotlas").read_text(
            encoding="utf-8"
        )
        windows = (root / "native_driver" / "windows.sotlas").read_text(
            encoding="utf-8"
        )
        arenas = (
            ("VALUE", "TargetValue", "driver_values", 131072),
            ("INSTR", "TargetInstruction", "driver_instructions", 262144),
            ("OPERAND", "TargetOperand", "driver_operands", 524288),
            ("BLOCK", "TargetBlock", "driver_blocks", 65536),
            ("FUNCTION", "TargetFunction", "driver_functions", 8192),
        )
        for kind, element, name, capacity in arenas:
            with self.subTest(arena=kind):
                self.assertIn(
                    f"pub const TARGET_{kind}_CAPACITY: usize = {capacity};",
                    compiler,
                )
                self.assertIn(
                    f"static mut {name}: [{element}; {capacity}] = 0;",
                    windows,
                )
                self.assertIn(
                    f"unsafe {{ {name} as *mut {element} }}, {capacity}",
                    windows,
                )
        # The other independently bounded arenas remain wired through.
        for element, name, capacity in (
            ("TargetParameter", "driver_parameters", 16384),
            ("TargetPhiInput", "driver_phi_inputs", 16384),
            ("u32", "driver_targets", 65536),
        ):
            with self.subTest(arena=name):
                self.assertIn(
                    f"static mut {name}: [{element}; {capacity}] = 0;",
                    windows,
                )
                self.assertIn(
                    f"unsafe {{ {name} as *mut {element} }}, {capacity}",
                    windows,
                )
        self.assertIn(
            "if !lower_scalar_module(&mut lowering, module_index, &mut ir) {",
            windows,
        )
        # The real PE rebuild + exact Stage2/Stage3 binary equality gate is
        # not replaced or skipped by this structural regression test.

    def test_sv848b_installed_native_driver_ir_arenas_match_compiler_profile(self):
        """The packaged Linux seed must not retain older lowering arena limits."""
        root = ROOT / "bootstrap" / "sotlas"
        compiler = (root / "native_compiler" / "main.sotlas").read_text(
            encoding="utf-8"
        )
        packaging = (ROOT / "packaging" / "native_linux.py").read_text(
            encoding="utf-8"
        )
        arenas = (
            ("VALUE", "TargetValue", "driver_values", 131072),
            ("INSTR", "TargetInstruction", "driver_instructions", 262144),
            ("OPERAND", "TargetOperand", "driver_operands", 524288),
            ("BLOCK", "TargetBlock", "driver_blocks", 65536),
            ("FUNCTION", "TargetFunction", "driver_functions", 8192),
        )
        remaining = (
            ("TargetParameter", "driver_parameters", 16384),
            ("TargetPhiInput", "driver_phi_inputs", 16384),
            ("u32", "driver_targets", 65536),
        )
        for platform in ("linux", "windows", "darwin"):
            with self.subTest(platform=platform):
                driver = (
                    root / "native_driver" / f"{platform}.sotlas"
                ).read_text(encoding="utf-8")
                self.assertIn("ScalarLowering::new(", driver)
                self.assertIn(
                    "if !lower_scalar_module(&mut lowering, module_index, &mut ir) {",
                    driver,
                )
                for kind, element, name, limit in arenas:
                    with self.subTest(platform=platform, arena=kind):
                        self.assertIn(
                            f"pub const TARGET_{kind}_CAPACITY: usize = {limit};",
                            compiler,
                        )
                        self.assertIn(
                            f"static mut {name}: [{element}; {limit}] = 0;",
                            driver,
                        )
                        self.assertIn(
                            f"unsafe {{ {name} as *mut {element} }}, {limit}",
                            driver,
                        )
                for element, name, limit in remaining:
                    with self.subTest(platform=platform, arena=name):
                        self.assertIn(
                            f"static mut {name}: [{element}; {limit}] = 0;",
                            driver,
                        )
                        self.assertIn(
                            f"unsafe {{ {name} as *mut {element} }}, {limit}",
                            driver,
                        )
                self.assertIn(
                    f'files["src/sotlas/compiler/{platform}_driver.sotlas"]',
                    packaging,
                )
        # Packaging must build the freestanding native Linux seed from
        # precisely the source whose arena bounds were verified above.
        self.assertIn(
            'ROOT / "bootstrap/sotlas/native_driver/linux.sotlas"',
            packaging,
        )
        self.assertIn('build_stage1_native_compiler(producer', packaging)
        self.assertIn('"--compile-obj"', packaging)
        # Keep the end-to-end packaging workflow and native Windows fixed
        # point checks enabled; this static guard supplements them.

    def test_sv848c_void_call_capabilities_and_callee_domains_are_checked(self):
        """Typed void calls cannot lose roles; foreign roles fail closed."""
        root = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "backend"
        lowering = (root / "lower_scalar.sotlas").read_text(encoding="utf-8")
        target = (root / "target_ir.sotlas").read_text(encoding="utf-8")
        body = lowering.split("pub fn lower_direct_void_call_statement(", 1)[1]
        body = body.split("pub fn lower_return_statement(", 1)[0]
        self.assertIn("self.call_capability_profile(callee_decl, argument_count)", body)
        self.assertIn("call.flags = TARGET_CALL_CAPABILITIES_TYPED;", body)
        self.assertIn("call.immediate_bits = capabilities;", body)
        self.assertIn("capabilities == 18446744073709551615", body)
        calls = target.split("pub fn target_module_validate_calls(", 1)[1]
        calls = calls.split("pub fn target_module_validate_ssa_dominance(", 1)[0]
        self.assertIn("instruction.flags == TARGET_CALL_CAPABILITIES_TYPED", calls)
        self.assertIn("TARGET_VALUE_DOMAIN_MASK", calls)
        self.assertIn("TARGET_VALUE_DOMAIN_SHIFT", calls)
        self.assertIn("if actual_role != expected_role { return false; }", calls)
        self.assertIn("if actual_role != 0 { return false; }", calls)
        self.assertIn("if argument_type != parameter.type_tag { return false; }", calls)

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
