"""Testes para o gerador de LLVM IR a partir do SIR."""
import sys
import importlib.util
import unittest
from io import StringIO
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "compiler"))

from sotlas.sir.instructions import (
    SIRModule, SIRFunction, SIRValue, AllocStackInst, StoreInst,
    LoadInst, CallInst, ReturnInst, ShareInst, RetainInst, ReleaseInst,
    BinaryOpInst,
    DestroyInst, OwnershipDomainPointInst, OwnershipDomainTransferInst,
    WhisperBorrowInst,
    DirectAccessInst,
    SharedOwnershipPointInst, DeferUseInst,
)
from sotlas.sir.generator import SIRGenerator
from sotlas.lexer import Lexer
from sotlas.parser import Parser
from sotlas.codegen_llvm import CodegenLLVM, to_llvm_type
from sotlas.execution_target import (
    ExecutionTargetError,
    resolve_execution_target,
)
from sotlas.llvm_toolchain import LLVMToolchain
from sotlas import cli

_FRONTEND_PATH = ROOT / "compiler" / "sotlas_compile"
_FRONTEND_SPEC = importlib.util.spec_from_file_location(
    "sotlas_llvm_target_feature_frontend",
    _FRONTEND_PATH / "__init__.py",
    submodule_search_locations=[str(_FRONTEND_PATH)],
)
assert _FRONTEND_SPEC is not None and _FRONTEND_SPEC.loader is not None
_FRONTEND_PACKAGE = importlib.util.module_from_spec(_FRONTEND_SPEC)
sys.modules[_FRONTEND_SPEC.name] = _FRONTEND_PACKAGE
_FRONTEND_SPEC.loader.exec_module(_FRONTEND_PACKAGE)
source_bootstrap = _FRONTEND_PACKAGE.bootstrap


class TestCodegenLLVM(unittest.TestCase):
    def test_unsigned_scalar_arithmetic_return_reaches_sir_and_llvm(self):
        for operator, operation in (("+", "add"), ("-", "sub"), ("*", "mul")):
            with self.subTest(operator=operator):
                source = f"""
module test::sir_arithmetic;
fn calculate(a: u32, b: u32) -> u32 {{ return a {operator} b; }}
"""
                parsed = source_bootstrap.parse(source)
                source_bootstrap.check(parsed)
                sir = SIRGenerator().generate_from_ast(parsed)
                instructions = sir.functions[0].blocks[0].instructions
                arithmetic = next(
                    instruction for instruction in instructions
                    if isinstance(instruction, BinaryOpInst)
                )
                self.assertEqual(arithmetic.operation, operation)
                self.assertIs(instructions[-1].value, arithmetic.result)
                llvm = CodegenLLVM(sir).emit()
                self.assertIn(
                    f"%{arithmetic.result.name} = {operation} i32 "
                    f"%{arithmetic.left.name}, %{arithmetic.right.name}",
                    llvm,
                )

        source = "module test::sir_arithmetic_legacy; fn calculate(a: u32, b: u32) -> u32 { return a + b; }"
        legacy = Parser(Lexer(source, "arithmetic.sotlas").tokenize()).parse()
        legacy_sir = SIRGenerator().generate_from_ast(legacy)
        self.assertTrue(any(
            isinstance(instruction, BinaryOpInst)
            for instruction in legacy_sir.functions[0].blocks[0].instructions
        ))

    def test_signed_scalar_arithmetic_is_rejected_by_sir_subset(self):
        source = "module test::sir_signed_arithmetic; fn calculate(a: i32, b: i32) -> i32 { return a + b; }"
        parsed = source_bootstrap.parse(source)
        source_bootstrap.check(parsed)
        sir = SIRGenerator().generate_from_ast(parsed)
        self.assertFalse(any(
            isinstance(instruction, BinaryOpInst)
            for instruction in sir.functions[0].blocks[0].instructions
        ))

        division = source_bootstrap.parse(
            "module test::sir_division; fn calculate(a: u32, b: u32) -> u32 { return a / b; }"
        )
        source_bootstrap.check(division)
        division_sir = SIRGenerator().generate_from_ast(division)
        self.assertFalse(any(
            isinstance(instruction, BinaryOpInst)
            for instruction in division_sir.functions[0].blocks[0].instructions
        ))

    def test_llvm_arithmetic_instruction_rejects_signed_types_and_unknown_ops(self):
        for operation, type_name in (("add", "i32"), ("div", "u32")):
            module = SIRModule(name="invalid_arithmetic")
            function = SIRFunction(
                name="calculate",
                parameters=[SIRValue("a", type_name), SIRValue("b", type_name)],
                return_type=type_name,
            )
            result = SIRValue("result", type_name)
            block = function.add_block("entry")
            block.add(BinaryOpInst(operation, function.parameters[0], function.parameters[1], result))
            block.add(ReturnInst(result))
            module.add_function(function)
            with self.subTest(operation=operation, type_name=type_name):
                with self.assertRaisesRegex(ValueError, "does not lower"):
                    CodegenLLVM(module).emit()

    def test_execution_target_contract_and_fail_closed_validation(self):
        host = resolve_execution_target("host")
        self.assertEqual(host.triple, "x86_64-pc-none")
        self.assertEqual(host.cpu_features, ("sse2",))
        avx2 = resolve_execution_target(
            "x86_64-unknown-linux-gnu", cpu_features=("avx2",)
        )
        self.assertEqual(avx2.cpu_features, ("sse2", "avx", "avx2"))
        self.assertEqual(avx2.abi, "sysv")
        with self.assertRaisesRegex(ExecutionTargetError, "unsupported execution target"):
            resolve_execution_target("riscv64-unknown-linux-gnu")
        with self.assertRaisesRegex(ExecutionTargetError, "unsupported x86-64 CPU features"):
            resolve_execution_target(cpu_features=("madeup",))
        with self.assertRaisesRegex(ExecutionTargetError, "must be strings"):
            resolve_execution_target(cpu_features=([],))

    def test_llvm_ir_uses_selected_target_and_cpu_features(self):
        module = SIRModule(name="target_contract")
        function = SIRFunction(name="main", parameters=[], return_type="Void")
        block = function.add_block("entry")
        block.add(ReturnInst())
        module.add_function(function)
        ir = CodegenLLVM(
            module,
            target="x86_64-pc-windows-msvc",
            cpu_features=("avx2",),
        ).emit()
        self.assertIn('target triple = "x86_64-pc-windows-msvc"', ir)
        self.assertIn('"target-features"="+sse2,+avx,+avx2"', ir)
        self.assertIn('"target-cpu"="x86-64"', ir)

    def test_aarch64_target_abi_features_and_llvm_ir(self):
        arm = resolve_execution_target(
            "aarch64-unknown-linux-gnu", cpu_features=("sve2", "crc")
        )
        self.assertEqual(arm.architecture, "aarch64")
        self.assertEqual(arm.abi, "aapcs64")
        self.assertEqual(arm.pointer_width, 64)
        self.assertEqual(arm.endianness, "little")
        self.assertEqual(arm.cpu_features, ("crc", "sve", "sve2"))
        self.assertEqual(
            arm.data_layout,
            "e-m:e-p270:32:32-p271:32:32-p272:64:64-"
            "i8:8:32-i16:16:32-i64:64-i128:128-n32:64-S128-Fn32",
        )

        module = SIRModule(name="aarch64_target_contract")
        function = SIRFunction(name="main", parameters=[], return_type="Void")
        function.add_block("entry").add(ReturnInst())
        module.add_function(function)
        ir = CodegenLLVM(module, target=arm).emit()
        self.assertIn('target triple = "aarch64-unknown-linux-gnu"', ir)
        self.assertIn(f'target datalayout = "{arm.data_layout}"', ir)
        self.assertIn('"target-cpu"="generic"', ir)
        self.assertIn('"target-features"="+crc,+sve,+sve2"', ir)

    def test_function_target_features_are_preserved_gated_and_fail_closed(self):
        source = """
module test::target_feature;
@target_feature(avx2)
fn vector_path() -> void { return; }
"""
        parsed = source_bootstrap.parse(source)
        source_bootstrap.check(parsed)
        self.assertIn("@target_feature(avx2)", parsed.functions[0].attributes)
        sir = SIRGenerator().generate_from_ast(parsed)
        function = sir.functions[0]
        self.assertEqual(function.required_cpu_features, ("avx2",))
        parsed_ast = Parser(Lexer(source, "target-feature.sotlas").tokenize()).parse()
        legacy_sir = SIRGenerator().generate_from_ast(parsed_ast)
        self.assertEqual(legacy_sir.functions[0].required_cpu_features, ("avx2",))
        with self.assertRaisesRegex(ValueError, "lacks features required"):
            CodegenLLVM(sir).emit()
        ir = CodegenLLVM(
            sir,
            target="x86_64-unknown-linux-gnu",
            cpu_features=("avx2",),
        ).emit()
        self.assertIn("define void @vector_path() #1", ir)
        self.assertIn('"sotlas-required-cpu-features"="avx2"', ir)
        with self.assertRaisesRegex(
            source_bootstrap.SotlasBootstrapError,
            "C11 backend does not lower function-specific CPU feature requirements",
        ):
            source_bootstrap.emit_c(parsed)

    def test_function_target_feature_rejects_architecture_mismatch(self):
        source = """
module test::target_feature_arch;
@target_feature(sve2)
fn vector_path() -> void { return; }
"""
        parsed = source_bootstrap.parse(source)
        source_bootstrap.check(parsed)
        sir = SIRGenerator().generate_from_ast(parsed)
        with self.assertRaisesRegex(ValueError, "unsupported x86-64 CPU features"):
            CodegenLLVM(
                sir,
                target="x86_64-unknown-linux-gnu",
                cpu_features=("avx2",),
            ).emit()

    def test_aarch64_abi_presets_use_object_format_specific_data_layouts(self):
        cases = (
            (
                "aarch64-apple-darwin",
                "darwin-aarch64",
                "e-m:o-p270:32:32-p271:32:32-p272:64:64-"
                "i64:64-i128:128-n32:64-S128-Fn32",
            ),
            (
                "aarch64-pc-windows-msvc",
                "winarm64",
                "e-m:w-p270:32:32-p271:32:32-p272:64:64-"
                "p:64:64-i32:32-i64:64-i128:128-n32:64-S128-Fn32",
            ),
            (
                "aarch64-unknown-none-elf",
                "aapcs64",
                "e-m:e-p270:32:32-p271:32:32-p272:64:64-"
                "i8:8:32-i16:16:32-i64:64-i128:128-n32:64-S128-Fn32",
            ),
        )
        for triple, abi, data_layout in cases:
            with self.subTest(triple=triple):
                target = resolve_execution_target(triple)
                self.assertEqual(target.abi, abi)
                self.assertEqual(target.data_layout, data_layout)

    def test_x86_64_darwin_target_uses_macho_data_layout(self):
        target = resolve_execution_target("x86_64-apple-darwin")
        self.assertEqual(target.abi, "darwin")
        self.assertEqual(
            target.data_layout,
            "e-m:o-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-"
            "f80:128-n8:16:32:64-S128",
        )

    def test_aarch64_rejects_x86_features_and_accepts_freestanding_alias(self):
        with self.assertRaisesRegex(ExecutionTargetError, "unsupported aarch64 CPU features"):
            resolve_execution_target("aarch64-unknown-linux-gnu", cpu_features=("avx2",))
        baremetal = resolve_execution_target("aarch64-freestanding")
        self.assertEqual(baremetal.triple, "aarch64-unknown-none-elf")
        self.assertTrue(baremetal.is_freestanding)

    def test_aarch64_freestanding_c11_uses_architecture_specific_flags(self):
        toolchain = LLVMToolchain()
        with patch.object(toolchain, "find_tool", return_value=Path("clang")), \
             patch("sotlas.llvm_toolchain.subprocess.run", return_value=SimpleNamespace(
                 returncode=0, stderr=""
             )) as run:
            toolchain.compile_c_to_obj(
                "int main(void) { return 0; }",
                Path("target-test.o"),
                is_freestanding=True,
                target="aarch64-unknown-none-elf",
                cpu_features=("crc", "sve", "sve2"),
            )
        command = run.call_args.args[0]
        self.assertIn("-target", command)
        self.assertIn("-ffreestanding", command)
        self.assertIn("+sve2", command)
        self.assertNotIn("-mno-red-zone", command)
        self.assertNotIn("-mno-sse", command)
        self.assertNotIn("-msve2", command)

    def test_cli_fails_closed_for_aarch64_internal_linker(self):
        args = SimpleNamespace(
            source="target.sotlas",
            target="aarch64-unknown-none-elf",
            cpu_feature=[],
            linker="internal",
        )
        error_output = StringIO()
        with patch.object(
            cli, "_read_source", return_value=(Path("target.sotlas"), "")
        ), patch.object(cli.sys, "stderr", error_output):
            result = cli._run_compile(args)

        self.assertEqual(result, 2)
        self.assertIn("linker interno suporta apenas", error_output.getvalue())

    def test_llvm_type_mapping(self):
        self.assertEqual(to_llvm_type("UInt32"), "i32")
        self.assertEqual(to_llvm_type("Int64"), "i64")
        self.assertEqual(to_llvm_type("Bool"), "i1")
        self.assertEqual(to_llvm_type("bool"), "i1")
        self.assertEqual(to_llvm_type("Void"), "void")
        self.assertEqual(to_llvm_type("*rawphys UInt8"), "ptr")

    def test_emit_simple_function(self):
        mod = SIRModule(name="test_mod")
        fn = SIRFunction(name="add_one", parameters=[SIRValue("x", "UInt32")], return_type="UInt32")
        bb0 = fn.add_block("0")
        
        alloc = AllocStackInst(var_name="res", type_name="UInt32", result=SIRValue("res_ptr", "*UInt32"))
        bb0.add(alloc)
        
        store = StoreInst(destination=SIRValue("res_ptr", "*UInt32"), source=SIRValue("x", "UInt32"))
        bb0.add(store)
        
        load = LoadInst(source=SIRValue("res_ptr", "*UInt32"), result=SIRValue("loaded", "UInt32"))
        bb0.add(load)
        
        ret = ReturnInst(value=SIRValue("loaded", "UInt32"))
        bb0.add(ret)
        
        mod.add_function(fn)
        
        codegen = CodegenLLVM(mod)
        llvm_ir = codegen.emit()
        
        self.assertIn("define i32 @add_one(i32 %x)", llvm_ir)
        self.assertIn("%res_ptr = alloca i32", llvm_ir)
        self.assertIn("store i32 %x, ptr %res_ptr", llvm_ir)
        self.assertIn("%loaded = load i32, ptr %res_ptr", llvm_ir)
        self.assertIn("ret i32 %loaded", llvm_ir)

    def test_ownership_instructions_fail_closed_without_runtime_abi(self):
        value = SIRValue("owner", "*Token")
        instructions = (
            ShareInst(value),
            RetainInst(value),
            ReleaseInst(value),
            DestroyInst(value),
            OwnershipDomainPointInst(
                "quarantine", "owner", None, "quarantine@1:1"
            ),
            OwnershipDomainTransferInst(
                "quarantine", value, "exclusive", "island"
            ),
            SharedOwnershipPointInst("owner", "peer", "share@1:1"),
            DeferUseInst(value, "defer@1:1"),
        )
        for instruction in instructions:
            with self.subTest(instruction=type(instruction).__name__):
                module = SIRModule(name="ownership_backend_gate")
                function = SIRFunction(
                    name="main", parameters=[], return_type="Void"
                )
                block = function.add_block("0")
                block.add(instruction)
                block.add(ReturnInst())
                module.add_function(function)
                with self.assertRaisesRegex(
                    ValueError,
                    "LLVM backend does not lower .*runtime ABI",
                ):
                    CodegenLLVM(module).emit()

    def test_resource_domain_transfers_fail_closed_with_domain_specific_abi_gate(self):
        for domain in ("region", "device", "external"):
            with self.subTest(domain=domain):
                module = SIRModule(name="resource_domain_backend_gate")
                function = SIRFunction(
                    name="main", parameters=[], return_type="Void"
                )
                block = function.add_block("0")
                block.add(OwnershipDomainTransferInst(
                    "handover", SIRValue("owner", "Token"), domain, domain,
                    destination=SIRValue("destination", "Token"),
                    point_id="handover@1:1",
                ))
                block.add(ReturnInst())
                module.add_function(function)
                with self.assertRaisesRegex(
                    ValueError,
                    rf"LLVM backend does not lower handover ownership transfer "
                    rf"{domain}->{domain} until the ownership-domain runtime ABI",
                ):
                    CodegenLLVM(module).emit()

    def test_direct_access_instruction_lowers_as_verified_noop(self):
        module = SIRModule(name="direct_access_backend")
        function = SIRFunction(name="main", parameters=[], return_type="Void")
        block = function.add_block("0")
        block.add(DirectAccessInst(
            SIRValue("owner", "*Token"),
            "inspect",
            "token",
            "exclusive",
            "direct@2:3",
        ))
        block.add(DirectAccessInst(
            SIRValue("borrowed", "*Token"),
            "inspect",
            "token",
            "direct",
            "direct@3:4",
        ))
        block.add(DirectAccessInst(
            SIRValue("region_owner", "*Token"),
            "inspect",
            "token",
            "region",
            "direct@4:5",
        ))
        block.add(DirectAccessInst(
            SIRValue("island_owner", "*Token"),
            "inspect",
            "token",
            "island",
            "direct@5:6",
        ))
        block.add(ReturnInst())
        module.add_function(function)

        llvm_ir = CodegenLLVM(module).emit()

        self.assertIn(
            "; direct access %owner -> @inspect.token [direct@2:3]",
            llvm_ir,
        )
        self.assertIn(
            "; direct access %borrowed -> @inspect.token [direct@3:4]",
            llvm_ir,
        )
        self.assertIn(
            "; direct access %region_owner -> @inspect.token [direct@4:5]",
            llvm_ir,
        )
        self.assertIn(
            "; direct access %island_owner -> @inspect.token [direct@5:6]",
            llvm_ir,
        )

    def test_direct_access_instruction_rejects_unverified_fact(self):
        module = SIRModule(name="direct_access_backend_gate")
        function = SIRFunction(name="main", parameters=[], return_type="Void")
        block = function.add_block("0")
        block.add(DirectAccessInst(
            SIRValue("owner", "*Token"),
            "inspect",
            "token",
            "device",
            "direct@2:3",
        ))
        block.add(ReturnInst())
        module.add_function(function)

        with self.assertRaisesRegex(ValueError, "invalid direct access fact"):
            CodegenLLVM(module).emit()

    def test_whisper_borrow_instruction_lowers_as_verified_noop(self):
        module = SIRModule(name="whisper_borrow_backend")
        function = SIRFunction(name="main", parameters=[], return_type="Void")
        block = function.add_block("0")
        block.add(WhisperBorrowInst(
            SIRValue("owner", "Token"),
            "inspect",
            "token",
            "exclusive",
            "whisper@2:3",
        ))
        block.add(WhisperBorrowInst(
            SIRValue("region_owner", "Token"),
            "inspect",
            "token",
            "region",
            "whisper@3:4",
        ))
        block.add(ReturnInst())
        module.add_function(function)

        llvm_ir = CodegenLLVM(module).emit()

        self.assertIn(
            "; whisper borrow %owner -> @inspect.token [whisper@2:3]",
            llvm_ir,
        )
        self.assertIn(
            "; whisper borrow %region_owner -> @inspect.token [whisper@3:4]",
            llvm_ir,
        )

    def test_whisper_borrow_from_island_is_validated_by_llvm(self):
        module = SIRModule(name="whisper_island_borrow_backend")
        function = SIRFunction(name="main", parameters=[], return_type="Void")
        block = function.add_block("0")
        block.add(WhisperBorrowInst(
            SIRValue("owner", "Token"),
            "inspect",
            "token",
            "island",
            "whisper@4:8",
        ))
        block.add(ReturnInst())
        module.add_function(function)

        llvm_ir = CodegenLLVM(module).emit()

        self.assertIn(
            "; whisper borrow %owner -> @inspect.token [whisper@4:8]",
            llvm_ir,
        )


if __name__ == "__main__":
    unittest.main()
