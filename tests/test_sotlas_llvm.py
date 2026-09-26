"""Testes para o gerador de LLVM IR a partir do SIR."""
import sys
import unittest
from pathlib import Path

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
            resolve_execution_target("aarch64-unknown-linux-gnu")
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
