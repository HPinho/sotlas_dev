"""Testes para o gerador de LLVM IR a partir do SIR."""
import sys
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
    DestroyInst, OwnershipDomainPointInst, OwnershipDomainTransferInst,
    WhisperBorrowInst,
    DirectAccessInst,
    SharedOwnershipPointInst, DeferUseInst,
)
from sotlas.codegen_llvm import CodegenLLVM, to_llvm_type
from sotlas.execution_target import (
    ExecutionTargetError,
    resolve_execution_target,
)
from sotlas.llvm_toolchain import LLVMToolchain
from sotlas import cli


class TestCodegenLLVM(unittest.TestCase):
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
