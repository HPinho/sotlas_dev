"""Testes unitários para o novo compilador nativo auto-hospedado (Sotlas in Sotlas)."""
from pathlib import Path
import os
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "compiler"))
sys.path.insert(0, str(ROOT / "tools"))

from sotlas import compile_source
from sotlas.llvm_toolchain import default_toolchain
from sotlas_compile.bootstrap import PREAMBLE, compile_module, emit_c, parse
from sotlas_compile import compile_source as canonical_compile_source


class TestSotlasNativeCompilerSelfhost(unittest.TestCase):
    def test_native_compiler_parses_rejects_and_emits_executable_c(self):
        module_dir = ROOT / "bootstrap" / "sotlas" / "native_compiler"
        order = (
            "token", "ast", "lexer", "parser", "sema", "emitter_c",
            "target_ir", "lower_scalar", "x86_64_scalar", "main",
        )
        modules = {
            path.stem: parse(path.read_text(encoding="utf-8"), filename=str(path))
            for path in module_dir.rglob("*.sotlas")
        }
        self.assertEqual(set(modules), set(order))

        fragments = [PREAMBLE]
        for name in order:
            compile_module(
                modules[name],
                [modules[dependency] for dependency in order if dependency != name],
            )
            fragments.append(emit_c(
                modules[name], mangle=False, include_preamble=False
            ))

        with tempfile.TemporaryDirectory(prefix="sotlas-native-compiler-") as tmp:
            root = Path(tmp)
            compiler_c = root / "native_compiler.c"
            compiler_obj = root / "native_compiler.obj"
            driver_c = root / "driver.c"
            driver_obj = root / "driver.obj"
            compiler_exe = root / ("native_compiler.exe" if os.name == "nt" else "native_compiler")
            generated_c = root / "generated.c"
            app_obj = root / "generated.obj"
            app_exe = root / ("generated.exe" if os.name == "nt" else "generated")
            compiler_c.write_text("\n".join(fragments), encoding="utf-8")
            driver_c.write_text(
                "#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\n"
                "#include <stdbool.h>\n#include <string.h>\n"
                "extern size_t sotlas_native_compile_diagnostic(const uint8_t *, size_t, "
                "uint8_t *, size_t, uint32_t *, uint32_t *);\n"
                "struct TargetSourceSlice { size_t offset, length; };\n"
                "struct TargetInstruction { uint32_t opcode, result_value, type_tag, "
                "first_operand, operand_count, first_phi_input, phi_input_count, "
                "first_target, target_count; uint64_t immediate_bits; "
                "struct TargetSourceSlice symbol, source_point; uint32_t flags; };\n"
                "struct TargetModule { uint32_t version, function_count, parameter_count, "
                "block_count, instruction_count, value_count, operand_count, "
                "phi_input_count, target_count; };\n"
                "struct TargetFunction { struct TargetSourceSlice name; uint32_t return_type, "
                "first_parameter, parameter_count, first_block, block_count, flags; };\n"
                "struct TargetBlock { uint32_t id; struct TargetSourceSlice label; "
                "uint32_t first_instruction, instruction_count; };\n"
                "struct TargetOperand { uint32_t value_id; };\n"
                "struct TargetParameter { uint32_t value_id, type_tag; struct TargetSourceSlice name; };\n"
                "struct TargetValue { uint32_t id, type_tag; struct TargetSourceSlice source_name; uint32_t flags; };\n"
                "struct TargetPhiInput { uint32_t value_id, block_id; };\n"
                "extern bool sotlas_native_lower_scalar_diagnostic(const uint8_t *, size_t, "
                "void *, size_t, void *, size_t, struct TargetInstruction *, size_t, "
                "void *, size_t, void *, size_t, uint32_t *, size_t, void *, size_t, void *, size_t, "
                "struct TargetModule *, uint32_t *, uint32_t *);\n"
                "extern bool emit_x86_64_scalar_constant(const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, "
                "const struct TargetBlock *, const struct TargetInstruction *, "
                "const struct TargetOperand *, uint8_t *, size_t, size_t *);\n"
                "extern bool emit_x86_64_scalar_function(uint32_t, const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, "
                "const struct TargetParameter *, const struct TargetBlock *, "
                "const struct TargetInstruction *, const struct TargetOperand *, "
                "uint8_t *, size_t, size_t *);\n"
                "extern bool emit_x86_64_scalar_if_return(uint32_t, const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, "
                "const struct TargetParameter *, const struct TargetBlock *, "
                "const struct TargetInstruction *, const struct TargetOperand *, const uint32_t *, "
                "uint8_t *, size_t, size_t *);\n"
                "extern bool emit_x86_64_scalar_cfg(uint32_t, const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, "
                "const struct TargetParameter *, const struct TargetValue *, const struct TargetBlock *, "
                "const struct TargetInstruction *, const struct TargetOperand *, const struct TargetPhiInput *, const uint32_t *, "
                "uint8_t *, size_t, size_t *);\n"
                "extern bool emit_x86_64_scalar_module(uint32_t, const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, "
                "const struct TargetParameter *, const struct TargetValue *, const struct TargetBlock *, "
                "const struct TargetInstruction *, const struct TargetOperand *, "
                "uint8_t *, size_t, size_t *);\n"
                "extern bool emit_elf64_scalar_function_object(const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, "
                "const struct TargetParameter *, const struct TargetValue *, const struct TargetBlock *, const struct TargetInstruction *, "
                "const struct TargetOperand *, const struct TargetPhiInput *, const uint32_t *, uint8_t *, size_t, size_t *);\n"
                "extern bool emit_elf64_scalar_module_object(const uint8_t *, size_t, "
                "const struct TargetModule *, const struct TargetFunction *, const struct TargetParameter *, const struct TargetValue *, "
                "const struct TargetBlock *, const struct TargetInstruction *, const struct TargetOperand *, "
                "uint8_t *, size_t, size_t *);\n"
                "extern bool link_elf64_scalar_executable(const uint8_t *, size_t, "
                "const uint32_t *, uint32_t, uint8_t *, size_t, size_t *);\n"
                "extern bool target_module_validate_cfg(const struct TargetModule *, "
                "const struct TargetFunction *, const struct TargetParameter *, "
                "const struct TargetValue *, const struct TargetBlock *, "
                "const struct TargetInstruction *, const struct TargetOperand *, "
                "const struct TargetPhiInput *, const uint32_t *);\n"
                "extern bool target_module_validate_ssa_dominance(const struct TargetModule *, "
                "const struct TargetFunction *, const struct TargetParameter *, "
                "const struct TargetValue *, const struct TargetBlock *, "
                "const struct TargetInstruction *, const struct TargetOperand *, "
                "const struct TargetPhiInput *, const uint32_t *, uint8_t *, size_t);\n"
                "int main(int argc, char **argv) {\n"
                "  if (argc == 3 && strcmp(argv[1], \"--lower\") == 0) {\n"
                "    static uint8_t input[65536];\n"
                "    _Alignas(max_align_t) unsigned char values[16384], parameters[16384], "
                "operands[16384], blocks[8192], functions[8192]; uint32_t targets[128];\n"
                "    struct TargetInstruction instructions[128];\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 34;\n"
                "    size_t len = fread(input, 1, sizeof(input), src);\n"
                "    int read_error = ferror(src); fclose(src); if (read_error) return 35;\n"
                "    struct TargetModule module = {0}; uint32_t line = 0, col = 0;\n"
                "    bool ok = sotlas_native_lower_scalar_diagnostic(input, len, values, 128, "
                "parameters, 128, instructions, 128, operands, 128, NULL, 0, targets, 128, blocks, 128, "
                "functions, 128, &module, &line, &col);\n"
                "    if (ok && !target_module_validate_cfg(&module, "
                "(const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, "
                "(const struct TargetValue *)values, (const struct TargetBlock *)blocks, "
                "instructions, (const struct TargetOperand *)operands, NULL, NULL)) return 36;\n"
                "    if (ok) { struct TargetBlock bad = *(const struct TargetBlock *)blocks; "
                "bad.instruction_count = 0; if (target_module_validate_cfg(&module, "
                "(const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, "
                "(const struct TargetValue *)values, &bad, instructions, "
                "(const struct TargetOperand *)operands, NULL, NULL)) return 37; }\n"
                "    printf(\"%d|%u|%u|%u|%u|%u|%u|%u|%u|%u\\n\", ok, line, col, "
                "module.function_count, module.parameter_count, module.block_count, "
                "module.instruction_count, module.value_count, module.operand_count, "
                "module.version);\n"
                "    for (uint32_t i = 0; i < module.instruction_count; ++i) "
                "printf(\"%u:%llu%c\", instructions[i].opcode, "
                "(unsigned long long)instructions[i].immediate_bits, "
                "i + 1 == module.instruction_count ? '\\n' : '|');\n"
                "    return 0;\n"
                "  }\n"
                "  if (argc == 2 && strcmp(argv[1], \"--cfg\") == 0) {\n"
                "    struct TargetModule cfg = {1, 1, 1, 3, 3, 1, 1, 0, 2};\n"
                "    struct TargetFunction fn = {0}; fn.return_type = 16; fn.parameter_count = 1; fn.block_count = 3;\n"
                "    struct TargetParameter cfg_parameters[1] = {{1, 1, {0, 0}}};\n"
                "    struct TargetBlock cfg_blocks[3] = {{0}};\n"
                "    cfg_blocks[0].id = 1; cfg_blocks[0].instruction_count = 1;\n"
                "    cfg_blocks[1].id = 2; cfg_blocks[1].first_instruction = 1; cfg_blocks[1].instruction_count = 1;\n"
                "    cfg_blocks[2].id = 3; cfg_blocks[2].first_instruction = 2; cfg_blocks[2].instruction_count = 1;\n"
                "    struct TargetInstruction cfg_instructions[3] = {{0}};\n"
                "    cfg_instructions[0].opcode = 13; cfg_instructions[0].operand_count = 1; cfg_instructions[0].target_count = 2;\n"
                "    cfg_instructions[1].opcode = 14; cfg_instructions[1].type_tag = 16; cfg_instructions[2].opcode = 14; cfg_instructions[2].type_tag = 16;\n"
                "    struct TargetOperand cfg_operands[1] = {{1}};\n"
                "    struct TargetValue cfg_values[1] = {{0}}; cfg_values[0].id = 1; cfg_values[0].type_tag = 1;\n"
                "    uint32_t cfg_targets[2] = {2, 3};\n"
                "    if (!target_module_validate_cfg(&cfg, &fn, cfg_parameters, cfg_values, cfg_blocks, cfg_instructions, cfg_operands, NULL, cfg_targets)) return 50;\n"
                "    uint8_t cfg_scratch[64] = {0};\n"
                "    if (!target_module_validate_ssa_dominance(&cfg, &fn, cfg_parameters, cfg_values, cfg_blocks, cfg_instructions, cfg_operands, NULL, cfg_targets, cfg_scratch, sizeof(cfg_scratch))) return 58;\n"
                "    if (target_module_validate_ssa_dominance(&cfg, &fn, cfg_parameters, cfg_values, cfg_blocks, cfg_instructions, cfg_operands, NULL, cfg_targets, cfg_scratch, 1)) return 65;\n"
                "    struct TargetModule loop_cfg = {1, 1, 1, 3, 3, 1, 1, 0, 3};\n"
                "    struct TargetFunction loop_fn = {0}; loop_fn.return_type = 16; loop_fn.parameter_count = 1; loop_fn.block_count = 3;\n"
                "    struct TargetBlock loop_blocks[3] = {{0}}; for (uint32_t i = 0; i < 3; ++i) { loop_blocks[i].id = i + 1; loop_blocks[i].first_instruction = i; loop_blocks[i].instruction_count = 1; }\n"
                "    struct TargetInstruction loop_instructions[3] = {{0}}; loop_instructions[0].opcode = 12; loop_instructions[0].target_count = 1; loop_instructions[1].opcode = 13; loop_instructions[1].operand_count = 1; loop_instructions[1].first_target = 1; loop_instructions[1].target_count = 2; loop_instructions[2].opcode = 14; loop_instructions[2].type_tag = 16;\n"
                "    uint32_t loop_targets[3] = {2, 2, 3}; uint8_t loop_scratch[64] = {0};\n"
                "    if (!target_module_validate_ssa_dominance(&loop_cfg, &loop_fn, cfg_parameters, cfg_values, loop_blocks, loop_instructions, cfg_operands, NULL, loop_targets, loop_scratch, sizeof(loop_scratch))) return 59;\n"
                "    cfg_targets[1] = 99;\n"
                "    if (target_module_validate_cfg(&cfg, &fn, cfg_parameters, cfg_values, cfg_blocks, cfg_instructions, cfg_operands, NULL, cfg_targets)) return 51;\n"
                "    struct TargetModule phi_cfg = {1, 1, 1, 4, 7, 4, 2, 2, 4};\n"
                "    struct TargetFunction phi_fn = {0}; phi_fn.return_type = 4; phi_fn.parameter_count = 1; phi_fn.block_count = 4;\n"
                "    struct TargetParameter phi_parameters[1] = {{1, 1, {0, 0}}};\n"
                "    struct TargetBlock phi_blocks[4] = {{0}};\n"
                "    for (uint32_t i = 0; i < 4; ++i) phi_blocks[i].id = i + 1;\n"
                "    phi_blocks[0].first_instruction = 0; phi_blocks[0].instruction_count = 1;\n"
                "    phi_blocks[1].first_instruction = 1; phi_blocks[1].instruction_count = 2;\n"
                "    phi_blocks[2].first_instruction = 3; phi_blocks[2].instruction_count = 2;\n"
                "    phi_blocks[3].first_instruction = 5; phi_blocks[3].instruction_count = 2;\n"
                "    struct TargetInstruction phi_instructions[7] = {{0}};\n"
                "    phi_instructions[0].opcode = 13; phi_instructions[0].operand_count = 1; phi_instructions[0].target_count = 2;\n"
                "    phi_instructions[1].opcode = 4; phi_instructions[1].type_tag = 4; phi_instructions[1].result_value = 2; phi_instructions[1].immediate_bits = 2;\n"
                "    phi_instructions[2].opcode = 12; phi_instructions[2].target_count = 1; phi_instructions[2].first_target = 2;\n"
                "    phi_instructions[3].opcode = 4; phi_instructions[3].type_tag = 4; phi_instructions[3].result_value = 3; phi_instructions[3].immediate_bits = 3;\n"
                "    phi_instructions[4].opcode = 12; phi_instructions[4].target_count = 1; phi_instructions[4].first_target = 3;\n"
                "    phi_instructions[5].opcode = 9; phi_instructions[5].type_tag = 4; phi_instructions[5].result_value = 4; phi_instructions[5].phi_input_count = 2;\n"
                "    phi_instructions[6].opcode = 14; phi_instructions[6].type_tag = 4; phi_instructions[6].operand_count = 1; phi_instructions[6].first_operand = 1;\n"
                "    struct TargetOperand phi_operands[2] = {{1}, {4}};\n"
                "    struct TargetPhiInput incoming[2] = {{2, 2}, {3, 3}};\n"
                "    struct TargetValue phi_values[4] = {{0}}; for (uint32_t i = 0; i < 4; ++i) { phi_values[i].id = i + 1; phi_values[i].type_tag = i == 0 ? 1 : 4; }\n"
                "    uint32_t phi_targets[4] = {2, 3, 4, 4};\n"
                "    if (!target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 52;\n"
                "    uint8_t phi_scratch[64] = {0};\n"
                "    if (!target_module_validate_ssa_dominance(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets, phi_scratch, sizeof(phi_scratch))) return 62;\n"
                "    phi_operands[1].value_id = 2;\n"
                "    if (!target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 63;\n"
                "    if (target_module_validate_ssa_dominance(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets, phi_scratch, sizeof(phi_scratch))) return 64;\n"
                "    phi_operands[1].value_id = 4;\n"
                "    incoming[0].block_id = 1;\n"
                "    if (target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 53;\n"
                "    incoming[0].block_id = 2; incoming[1].block_id = 2;\n"
                "    if (target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 54;\n"
                "    incoming[1].block_id = 3; phi_instructions[3].phi_input_count = 1;\n"
                "    if (target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 55;\n"
                "    phi_instructions[3].phi_input_count = 2; incoming[0].value_id = 1;\n"
                "    if (target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 56;\n"
                "    incoming[0].value_id = 2; phi_operands[1].value_id = 1;\n"
                "    if (target_module_validate_cfg(&phi_cfg, &phi_fn, phi_parameters, phi_values, phi_blocks, phi_instructions, phi_operands, incoming, phi_targets)) return 57;\n"
                "    return 0;\n"
                "  }\n"
                "  if (argc == 4 && (strcmp(argv[1], \"--asm\") == 0 || strcmp(argv[1], \"--bad-call\") == 0 || strcmp(argv[1], \"--bad-call-type\") == 0)) {\n"
                "    static uint8_t input[65536], assembly[8192];\n"
                "    _Alignas(max_align_t) unsigned char values[16384], parameters[16384], "
                "blocks[8192], functions[8192]; uint32_t targets[128];\n"
                "    struct TargetInstruction instructions[128];\n"
                "    struct TargetOperand operands[128];\n"
                "    struct TargetModule module = {0}; uint32_t line = 0, col = 0; size_t asm_len = 0;\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 40;\n"
                "    size_t len = fread(input, 1, sizeof(input), src); int read_error = ferror(src); fclose(src);\n"
                "    if (read_error || !sotlas_native_lower_scalar_diagnostic(input, len, values, 128, "
                "parameters, 128, instructions, 128, operands, 128, NULL, 0, targets, 128, blocks, 128, functions, 128, "
                "&module, &line, &col)) return 41;\n"
                "    if (strcmp(argv[1], \"--bad-call\") == 0 || strcmp(argv[1], \"--bad-call-type\") == 0) { bool found_call = false; "
                "      for (uint32_t i = 0; i < module.instruction_count; ++i) if (instructions[i].opcode == 10) { "
                "        if (strcmp(argv[1], \"--bad-call\") == 0) { instructions[i].symbol.offset = 0; instructions[i].symbol.length = 6; } "
                "        else { uint32_t arg = ((struct TargetOperand *)operands)[instructions[i].first_operand].value_id; ((struct TargetValue *)values)[arg - 1].type_tag = 1; } "
                "        found_call = true; break; } "
                "      if (!found_call) return 76; }\n"
                "    uint32_t abi = 1;\n"
                "#if defined(_WIN32)\n    abi = 2;\n#endif\n"
                "    bool emitted = module.function_count == 1\n"
                "      ? emit_x86_64_scalar_function(abi, input, len, &module, "
                "(const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, "
                "(const struct TargetBlock *)blocks, instructions, operands, assembly, sizeof(assembly), &asm_len)\n"
                "      : emit_x86_64_scalar_module(abi, input, len, &module, "
                "(const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, "
                "(const struct TargetBlock *)blocks, instructions, operands, assembly, sizeof(assembly), &asm_len);\n"
                "    if (strcmp(argv[1], \"--bad-call\") == 0 || strcmp(argv[1], \"--bad-call-type\") == 0) return emitted ? 77 : 0;\n"
                "    if (!emitted) return 42;\n"
                "    FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 43;\n"
                "    size_t written = fwrite(assembly, 1, asm_len, dest); fclose(dest);\n"
                "    return written == asm_len ? 0 : 44;\n"
                "  }\n"
                "  if (argc == 3 && strcmp(argv[1], \"--bad-compare\") == 0) {\n"
                "    static uint8_t input[65536];\n"
                "    _Alignas(max_align_t) unsigned char values[16384], parameters[16384], blocks[8192], functions[8192];\n"
                "    struct TargetInstruction instructions[128]; struct TargetOperand operands[128]; uint32_t targets[128];\n"
                "    struct TargetModule module = {0}; uint32_t line = 0, col = 0;\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 72;\n"
                "    size_t len = fread(input, 1, sizeof(input), src); int read_error = ferror(src); fclose(src);\n"
                "    if (read_error || !sotlas_native_lower_scalar_diagnostic(input, len, values, 128, parameters, 128, instructions, 128, operands, 128, NULL, 0, targets, 128, blocks, 128, functions, 128, &module, &line, &col)) return 73;\n"
                "    bool found = false; for (uint32_t i = 0; i < module.instruction_count; ++i) if (instructions[i].opcode == 8) { instructions[i].immediate_bits = 999; found = true; }\n"
                "    if (!found) return 74;\n"
                "    return target_module_validate_cfg(&module, (const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, (const struct TargetBlock *)blocks, instructions, (const struct TargetOperand *)operands, NULL, targets) ? 75 : 0;\n"
                "  }\n"
                "  if (argc == 3 && strcmp(argv[1], \"--cfg-phi-loop\") == 0) {\n"
                "    static const uint8_t source[] = \"phi_loop\"; uint8_t assembly[4096]; size_t asm_len = 0;\n"
                "    struct TargetModule module = {1, 1, 0, 4, 10, 6, 6, 2, 4};\n"
                "    struct TargetFunction fn = {{0, 8}, 4, 0, 0, 0, 4, 0}; struct TargetParameter params[1] = {{0}};\n"
                "    struct TargetValue values[6] = {{1,4,{0,0},0},{2,4,{0,0},0},{3,4,{0,0},0},{4,1,{0,0},0},{5,4,{0,0},0},{6,4,{0,0},0}};\n"
                "    struct TargetBlock blocks[4] = {{0,{0,0},0,3},{0,{0,0},3,3},{0,{0,0},6,3},{0,{0,0},9,1}}; for (uint32_t i=0;i<4;++i) blocks[i].id=i+1;\n"
                "    struct TargetInstruction instructions[10] = {{0}};\n"
                "    instructions[0].opcode=4; instructions[0].type_tag=4; instructions[0].result_value=1; instructions[1].opcode=4; instructions[1].type_tag=4; instructions[1].result_value=2; instructions[1].immediate_bits=3;\n"
                "    instructions[2].opcode=12; instructions[2].target_count=1;\n"
                "    instructions[3].opcode=9; instructions[3].type_tag=4; instructions[3].result_value=3; instructions[3].phi_input_count=2;\n"
                "    instructions[4].opcode=8; instructions[4].type_tag=1; instructions[4].result_value=4; instructions[4].first_operand=0; instructions[4].operand_count=2; instructions[4].immediate_bits=88;\n"
                "    instructions[5].opcode=13; instructions[5].type_tag=1; instructions[5].first_operand=2; instructions[5].operand_count=1; instructions[5].first_target=1; instructions[5].target_count=2;\n"
                "    instructions[6].opcode=4; instructions[6].type_tag=4; instructions[6].result_value=5; instructions[6].immediate_bits=1;\n"
                "    instructions[7].opcode=5; instructions[7].type_tag=4; instructions[7].result_value=6; instructions[7].first_operand=3; instructions[7].operand_count=2;\n"
                "    instructions[8].opcode=12; instructions[8].first_target=3; instructions[8].target_count=1;\n"
                "    instructions[9].opcode=14; instructions[9].type_tag=4; instructions[9].first_operand=5; instructions[9].operand_count=1;\n"
                "    struct TargetOperand operands[6]={{3},{2},{4},{3},{5},{3}}; struct TargetPhiInput phi_inputs[2]={{1,1},{6,3}}; uint32_t targets[4]={2,3,4,2};\n"
                "    if (!target_module_validate_cfg(&module,&fn,params,values,blocks,instructions,operands,phi_inputs,targets)) return 90; uint8_t scratch[128]={0};\n"
                "    if (!target_module_validate_ssa_dominance(&module,&fn,params,values,blocks,instructions,operands,phi_inputs,targets,scratch,sizeof(scratch))) return 91;\n"
                "    uint32_t abi=1;\n#if defined(_WIN32)\n    abi=2;\n#endif\n"
                "    if (!emit_x86_64_scalar_cfg(abi,source,sizeof(source)-1,&module,&fn,params,values,blocks,instructions,operands,phi_inputs,targets,assembly,sizeof(assembly),&asm_len)) return 92;\n"
                "    FILE *dest=fopen(argv[2],\"wb\"); if(!dest) return 93; size_t written=fwrite(assembly,1,asm_len,dest); fclose(dest); return written==asm_len?0:94;\n"
                "  }\n"
                "  if (argc == 3 && (strcmp(argv[1], \"--cfg-phi\") == 0 || strcmp(argv[1], \"--cfg-phi-object\") == 0 || strcmp(argv[1], \"--bad-cfg-phi\") == 0)) {\n"
                "    static const uint8_t source[] = \"phi_diamond\"; uint8_t assembly[4096]; size_t asm_len = 0;\n"
                "    struct TargetModule module = {1, 1, 1, 4, 7, 4, 2, 2, 4};\n"
                "    struct TargetFunction fn = {{0, 11}, 4, 0, 1, 0, 4, 0};\n"
                "    struct TargetParameter params[1] = {{1, 1, {0, 0}}};\n"
                "    struct TargetValue values[4] = {{1, 1, {0, 0}, 0}, {2, 4, {0, 0}, 0}, {3, 4, {0, 0}, 0}, {4, 4, {0, 0}, 0}};\n"
                "    struct TargetBlock blocks[4] = {{0, {0,0}, 0, 1}, {0, {0,0}, 1, 2}, {0, {0,0}, 3, 2}, {0, {0,0}, 5, 2}};\n"
                "    for (uint32_t i = 0; i < 4; ++i) blocks[i].id = i + 1;\n"
                "    struct TargetInstruction instructions[7] = {{0}};\n"
                "    instructions[0].opcode = 13; instructions[0].type_tag = 1; instructions[0].operand_count = 1; instructions[0].target_count = 2;\n"
                "    instructions[1].opcode = 4; instructions[1].type_tag = 4; instructions[1].result_value = 2; instructions[1].immediate_bits = 17;\n"
                "    instructions[2].opcode = 12; instructions[2].target_count = 1; instructions[2].first_target = 2;\n"
                "    instructions[3].opcode = 4; instructions[3].type_tag = 4; instructions[3].result_value = 3; instructions[3].immediate_bits = 29;\n"
                "    instructions[4].opcode = 12; instructions[4].target_count = 1; instructions[4].first_target = 3;\n"
                "    instructions[5].opcode = 9; instructions[5].type_tag = 4; instructions[5].result_value = 4; instructions[5].phi_input_count = 2;\n"
                "    instructions[6].opcode = 14; instructions[6].type_tag = 4; instructions[6].operand_count = 1; instructions[6].first_operand = 1;\n"
                "    struct TargetOperand operands[2] = {{1}, {4}}; struct TargetPhiInput phi_inputs[2] = {{2, 2}, {3, 3}}; uint32_t targets[4] = {2, 3, 4, 4};\n"
                "    bool bad_phi = strcmp(argv[1], \"--bad-cfg-phi\") == 0; if (bad_phi) phi_inputs[0].block_id = 1;\n"
                "    if (bad_phi) { if (target_module_validate_cfg(&module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets)) return 84; } "
                "    else if (!target_module_validate_cfg(&module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets)) return 84;\n"
                "    if (bad_phi) { if (emit_x86_64_scalar_cfg(1, source, sizeof(source) - 1, &module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets, assembly, sizeof(assembly), &asm_len)) return 89; if (emit_elf64_scalar_function_object(source, sizeof(source)-1, &module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets, assembly, sizeof(assembly), &asm_len)) return 96; return 0; }\n"
                "    uint8_t scratch[128] = {0}; if (!target_module_validate_ssa_dominance(&module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets, scratch, sizeof(scratch))) return 85;\n"
                "    uint32_t abi = 1;\n#if defined(_WIN32)\n    abi = 2;\n#endif\n"
                "    if (!emit_x86_64_scalar_cfg(abi, source, sizeof(source) - 1, &module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets, assembly, sizeof(assembly), &asm_len)) return 86;\n"
                "    if (strcmp(argv[1], \"--cfg-phi-object\") == 0) { asm_len = 0; if (!emit_elf64_scalar_function_object(source, sizeof(source)-1, &module, &fn, params, values, blocks, instructions, operands, phi_inputs, targets, assembly, sizeof(assembly), &asm_len)) return 95; }\n"
                "    FILE *dest = fopen(argv[2], \"wb\"); if (!dest) return 87; size_t written = fwrite(assembly, 1, asm_len, dest); fclose(dest); return written == asm_len ? 0 : 88;\n"
                "  }\n"
                "  if (argc == 3 && (strcmp(argv[1], \"--cfg-loop\") == 0 || strcmp(argv[1], \"--bad-cfg-loop\") == 0)) {\n"
                "    static const uint8_t source[] = \"loop_choice\"; uint8_t assembly[4096]; size_t asm_len = 0;\n"
                "    struct TargetModule module = {1, 1, 1, 3, 4, 2, 2, 0, 3};\n"
                "    struct TargetFunction fn = {{0, 11}, 4, 0, 1, 0, 3, 0};\n"
                "    struct TargetParameter params[1] = {{1, 1, {0, 0}}};\n"
                "    struct TargetValue values[2] = {{1, 1, {0, 0}, 0}, {2, 4, {0, 0}, 0}};\n"
                "    struct TargetBlock blocks[3] = {{0, {0,0}, 0, 1}, {0, {0,0}, 1, 1}, {0, {0,0}, 2, 2}};\n"
                "    blocks[0].id = 1; blocks[1].id = 2; blocks[2].id = 3;\n"
                "    struct TargetInstruction instructions[4] = {{0}};\n"
                "    instructions[0].opcode = 13; instructions[0].type_tag = 1; instructions[0].operand_count = 1; instructions[0].target_count = 2;\n"
                "    instructions[1].opcode = 12; instructions[1].target_count = 1; instructions[1].first_target = 2;\n"
                "    instructions[2].opcode = 4; instructions[2].type_tag = 4; instructions[2].result_value = 2; instructions[2].immediate_bits = 7;\n"
                "    instructions[3].opcode = 14; instructions[3].type_tag = 4; instructions[3].operand_count = 1; instructions[3].first_operand = 1;\n"
                "    struct TargetOperand operands[2] = {{1}, {2}}; uint32_t targets[3] = {3, 2, 1};\n"
                "    bool bad_cfg = strcmp(argv[1], \"--bad-cfg-loop\") == 0; if (bad_cfg) targets[2] = 99;\n"
                "    uint8_t scratch[128] = {0};\n"
                "    if (bad_cfg) { if (target_module_validate_cfg(&module, &fn, params, values, blocks, instructions, operands, NULL, targets)) return 78; } "
                "    else if (!target_module_validate_cfg(&module, &fn, params, values, blocks, instructions, operands, NULL, targets)) return 78;\n"
                "    if (bad_cfg) { if (emit_x86_64_scalar_cfg(1, source, sizeof(source) - 1, &module, &fn, params, values, blocks, instructions, operands, NULL, targets, assembly, sizeof(assembly), &asm_len)) return 83; return 0; }\n"
                "    if (!target_module_validate_ssa_dominance(&module, &fn, params, values, blocks, instructions, operands, NULL, targets, scratch, sizeof(scratch))) return 79;\n"
                "    uint32_t abi = 1;\n#if defined(_WIN32)\n    abi = 2;\n#endif\n"
                "    if (!emit_x86_64_scalar_cfg(abi, source, sizeof(source) - 1, &module, &fn, params, values, blocks, instructions, operands, NULL, targets, assembly, sizeof(assembly), &asm_len)) return 80;\n"
                "    FILE *dest = fopen(argv[2], \"wb\"); if (!dest) return 81; size_t written = fwrite(assembly, 1, asm_len, dest); fclose(dest); return written == asm_len ? 0 : 82;\n"
                "  }\n"
                "  if (argc == 4 && (strcmp(argv[1], \"--cfg-asm\") == 0 || strcmp(argv[1], \"--ir-extern\") == 0 || strcmp(argv[1], \"--ir-extern-bad-flag\") == 0 || strcmp(argv[1], \"--ir-extern-bad-param\") == 0)) {\n"
                "    static uint8_t input[65536], assembly[8192];\n"
                "    _Alignas(max_align_t) unsigned char values[16384], parameters[16384], blocks[8192], functions[8192];\n"
                "    struct TargetInstruction instructions[128]; struct TargetOperand operands[128]; struct TargetPhiInput phi_inputs[128]; uint32_t targets[128];\n"
                "    struct TargetModule module = {0}; uint32_t line = 0, col = 0; size_t asm_len = 0;\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 65;\n"
                "    size_t len = fread(input, 1, sizeof(input), src); int read_error = ferror(src); fclose(src);\n"
                "    if (read_error || !sotlas_native_lower_scalar_diagnostic(input, len, values, 128, parameters, 128, instructions, 128, operands, 128, phi_inputs, 128, targets, 128, blocks, 128, functions, 128, &module, &line, &col)) return 66;\n"
                "    if (strncmp(argv[1], \"--ir-extern\", 11) == 0) { struct TargetFunction *fs = (struct TargetFunction *)functions; struct TargetParameter *ps = (struct TargetParameter *)parameters; bool bad = strcmp(argv[1], \"--ir-extern\") != 0; bool found_ext = false, found_call = false; uint32_t signature_params = 0; for (uint32_t i = 0; i < module.function_count; ++i) if (fs[i].flags == 4 && fs[i].block_count == 0 && fs[i].parameter_count == 2) found_ext = true; for (uint32_t i = 0; i < module.parameter_count; ++i) if (ps[i].value_id == 0 && ps[i].type_tag == 4) ++signature_params; for (uint32_t i = 0; i < module.instruction_count; ++i) if (instructions[i].opcode == 10 && instructions[i].symbol.length != 0 && instructions[i].operand_count == 2) found_call = true; if (!found_ext || !found_call || signature_params != 2) return 72; if (strcmp(argv[1], \"--ir-extern-bad-flag\") == 0) fs[1].flags = 0; if (strcmp(argv[1], \"--ir-extern-bad-param\") == 0) ps[1].value_id = 1; bool valid = target_module_validate_cfg(&module, fs, ps, (const struct TargetValue *)values, (const struct TargetBlock *)blocks, instructions, (const struct TargetOperand *)operands, phi_inputs, targets); if (bad && valid) return 75; if (!bad && !valid) return 76; FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 73; const char *report = bad ? \"external-invalid-rejected\" : \"external-signature-ok\"; size_t written = fwrite(report, 1, strlen(report), dest); fclose(dest); return written == strlen(report) ? 0 : 74; }\n"
                "    if (!target_module_validate_cfg(&module, (const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, (const struct TargetBlock *)blocks, instructions, (const struct TargetOperand *)operands, phi_inputs, targets)) return 67;\n"
                "    uint8_t scratch[4096] = {0};\n"
                "    if (!target_module_validate_ssa_dominance(&module, (const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, (const struct TargetBlock *)blocks, instructions, (const struct TargetOperand *)operands, phi_inputs, targets, scratch, sizeof(scratch))) return 68;\n"
                "    uint32_t abi = 1;\n#if defined(_WIN32)\n    abi = 2;\n#endif\n"
                "    if (!emit_x86_64_scalar_cfg(abi, input, len, &module, (const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, (const struct TargetBlock *)blocks, instructions, operands, phi_inputs, targets, assembly, sizeof(assembly), &asm_len)) return 69;\n"
                "    FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 70;\n"
                "    size_t written = fwrite(assembly, 1, asm_len, dest); fclose(dest); return written == asm_len ? 0 : 71;\n"
                "  }\n"
                "  if (argc == 4 && (strcmp(argv[1], \"--obj\") == 0 || strcmp(argv[1], \"--bad-object-type\") == 0 || strcmp(argv[1], \"--bad-object-target\") == 0 || strcmp(argv[1], \"--bad-object-call\") == 0 || strcmp(argv[1], \"--bad-object-call-type\") == 0)) {\n"
                "    static uint8_t input[65536], object[8192];\n"
                "    _Alignas(max_align_t) unsigned char values[16384], parameters[16384], "
                "blocks[8192], functions[8192]; uint32_t targets[128];\n"
                "    struct TargetInstruction instructions[128]; struct TargetOperand operands[128]; struct TargetPhiInput phi_inputs[128];\n"
                "    struct TargetModule module = {0}; uint32_t line = 0, col = 0; size_t obj_len = 0;\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 45;\n"
                "    size_t len = fread(input, 1, sizeof(input), src); int read_error = ferror(src); fclose(src);\n"
                "    if (read_error || !sotlas_native_lower_scalar_diagnostic(input, len, values, 128, "
                "parameters, 128, instructions, 128, operands, 128, phi_inputs, 128, targets, 128, blocks, 128, functions, 128, "
                "&module, &line, &col)) return 46;\n"
                "    if (strcmp(argv[1], \"--bad-object-type\") == 0) ((struct TargetValue *)values)[0].type_tag = 1;\n"
                "    if (strcmp(argv[1], \"--bad-object-target\") == 0) targets[0] = module.block_count + 1;\n"
                "    if (strcmp(argv[1], \"--bad-object-call\") == 0) for (uint32_t i = 0; i < module.instruction_count; ++i) if (instructions[i].opcode == 10) instructions[i].symbol.offset = len + 1;\n"
                "    if (strcmp(argv[1], \"--bad-object-call-type\") == 0) for (uint32_t i = 0; i < module.instruction_count; ++i) if (instructions[i].opcode == 10 && instructions[i].operand_count != 0) ((struct TargetValue *)values)[operands[instructions[i].first_operand].value_id - 1].type_tag = 1;\n"
                "    bool object_emitted = module.function_count > 1 ? "
                "emit_elf64_scalar_module_object(input, len, &module, "
                "(const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, "
                "(const struct TargetBlock *)blocks, instructions, (const struct TargetOperand *)operands, "
                "object, sizeof(object), &obj_len) : "
                "emit_elf64_scalar_function_object(input, len, &module, "
                "(const struct TargetFunction *)functions, (const struct TargetParameter *)parameters, (const struct TargetValue *)values, (const struct TargetBlock *)blocks, "
                "instructions, (const struct TargetOperand *)operands, phi_inputs, targets, object, sizeof(object), &obj_len);\n"
                "    if (strcmp(argv[1], \"--bad-object-type\") == 0) return object_emitted ? 77 : 0;\n"
                "    if (strcmp(argv[1], \"--bad-object-target\") == 0) return object_emitted ? 78 : 0;\n"
                "    if (strcmp(argv[1], \"--bad-object-call\") == 0) return object_emitted ? 79 : 0;\n"
                "    if (strcmp(argv[1], \"--bad-object-call-type\") == 0) return object_emitted ? 80 : 0;\n"
                "    if (!object_emitted) return 47;\n"
                "    FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 48;\n"
                "    size_t written = fwrite(object, 1, obj_len, dest); fclose(dest);\n"
                "    return written == obj_len ? 0 : 49;\n"
                "  }\n"
                "  if (argc == 4 && (strcmp(argv[1], \"--link\") == 0 || strcmp(argv[1], \"--link-six\") == 0 || strcmp(argv[1], \"--link-one\") == 0 || strcmp(argv[1], \"--link-one-invalid\") == 0)) {\n"
                "    static uint8_t object[8192], executable[16384]; size_t executable_len = 0;\n"
                "    uint32_t arguments[6] = {1,2,3,4,5,6}; uint32_t argument_count = strcmp(argv[1], \"--link-six\") == 0 ? 6 : ((strcmp(argv[1], \"--link-one\") == 0 || strcmp(argv[1], \"--link-one-invalid\") == 0) ? 1 : 0);\n"
                "    if (strcmp(argv[1], \"--link-one-invalid\") == 0) arguments[0] = 2;\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 58;\n"
                "    size_t object_len = fread(object, 1, sizeof(object), src);\n"
                "    int read_error = ferror(src); int extra = fgetc(src); fclose(src);\n"
                "    if (read_error || extra != EOF || !link_elf64_scalar_executable(object, object_len, argument_count ? arguments : NULL, argument_count, executable, sizeof(executable), &executable_len)) return 59;\n"
                "    FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 60;\n"
                "    size_t written = fwrite(executable, 1, executable_len, dest); fclose(dest);\n"
                "    return written == executable_len ? 0 : 61;\n"
                "  }\n"
                "  if (argc == 4 && strcmp(argv[1], \"--compile\") == 0) {\n"
                "    static uint8_t input[65536], output[1048576];\n"
                "    FILE *src = fopen(argv[2], \"rb\"); if (!src) return 30;\n"
                "    size_t len = fread(input, 1, sizeof(input), src);\n"
                "    int read_error = ferror(src); fclose(src); if (read_error) return 31;\n"
                "    uint32_t err_line = 0, err_col = 0;\n"
                "    size_t out_len = sotlas_native_compile_diagnostic(input, len, output, sizeof(output), &err_line, &err_col);\n"
                "    printf(\"%zu|%u|%u\\n\", out_len, err_line, err_col);\n"
                "    if (out_len == 0) return 0;\n"
                "    FILE *dest = fopen(argv[3], \"wb\"); if (!dest) return 32;\n"
                "    size_t written = fwrite(output, 1, out_len, dest); fclose(dest);\n"
                "    return written == out_len ? 0 : 33;\n"
                "  }\n"
                "  static const uint8_t bad[] = \"module test::bad;\\nfn (\";\n"
                "  static const uint8_t duplicate[] = \"module test::duplicate;\\n"
                "fn run() -> i32 { return 0; }\\n"
                "fn run() -> i32 { return 1; }\\n\";\n"
                "  static const uint8_t duplicate_parameter[] = "
                "\"module test::duplicate_parameter;\\n"
                "fn run(value: i32, value: i32) -> i32 { return value; }\\n\";\n"
                "  static const uint8_t duplicate_local[] = "
                "\"module test::duplicate_local;\\nfn run() -> i32 {\\n"
                " let item: i32 = 0;\\n let item: i32 = 1;\\n return item;\\n}\\n\";\n"
                "  static const uint8_t unsupported_struct[] = "
                "\"module test::unsupported_struct;\\nstruct Item {\\n value: i32,\\n}\\n\";\n"
                "  static const uint8_t unsupported_enum[] = "
                "\"module test::unsupported_enum;\\nenum Choice {\\n Ready,\\n}\\n\";\n"
                "  static const uint8_t break_outside_loop[] = "
                "\"module test::break_outside_loop;\\nbreak;\\n\";\n"
                "  static const uint8_t continue_outside_loop[] = "
                "\"module test::continue_outside_loop;\\ncontinue;\\n\";\n"
                "  static const uint8_t return_outside_function[] = "
                "\"module test::return_outside_function;\\nreturn 0;\\n\";\n"
                "  static const uint8_t unknown_local[] = "
                "\"module test::unknown_local;\\nfn run() -> i32 { return missing; }\\n\";\n"
                "  static const uint8_t unknown_call[] = "
                "\"module test::unknown_call;\\nfn run() -> i32 { return missing(); }\\n\";\n"
                "  static const uint8_t wrong_arity[] = "
                "\"module test::wrong_arity;\\n"
                "fn identity(seed: i32) -> i32 { return seed; }\\n"
                "fn run() -> i32 { return identity(); }\\n\";\n"
                "  static const uint8_t wrong_argument_type[] = "
                "\"module test::wrong_argument_type;\\n"
                "fn consume(seed: u32) -> u32 { return seed; }\\n"
                "fn run(value: f32) -> u32 { return consume(value); }\\n\";\n"
                "  static const uint8_t wrong_expression_type[] = "
                "\"module test::wrong_expression_type;\\n"
                "fn consume(seed: u32) -> u32 { return seed; }\\n"
                "fn run(left: f32, right: u32) -> u32 { return consume(left + right); }\\n\";\n"
                "  static const uint8_t wrong_return_type[] = "
                "\"module test::wrong_return_type;\\n"
                "fn convert(value: f32) -> u32 { return value; }\\n\";\n"
                "  static const uint8_t missing_return_value[] = "
                "\"module test::missing_return_value;\\n"
                "fn run() -> i32 { return; }\\n\";\n"
                "  static const uint8_t missing_return_path[] = "
                "\"module test::missing_return_path;\\n"
                "fn run(flag: bool) -> i32 { if flag { return 1; } }\\n\";\n"
                "  static const uint8_t both_return_paths[] = "
                "\"module test::both_return_paths;\\n"
                "fn run(flag: bool) -> i32 { if flag { return 1; } else { return 2; } }\\n\";\n"
                "  static const uint8_t immutable_assignment[] = "
                "\"module test::immutable_assignment;\\nfn run() -> i32 {\\n"
                " let answer: i32 = 0;\\n answer = 1;\\n return answer;\\n}\\n\";\n"
                "  static const uint8_t good[] = \"module test::good;\\n"
                "fn identity(seed: i32) -> i32 { var answer: i32 = seed; answer = answer; return answer; }\\n"
                "fn forward(value: i32) -> i32 { return identity(value); }\\n"
                "fn arithmetic(value: i32) -> i32 { return identity(value + 0); }\\n"
                "fn unsafe_forward(value: i32) -> i32 { unsafe { return value; } }\\n"
                "pub fn main() -> i32 { return unsafe_forward(arithmetic(0)); }\\n\";\n"
                "  uint8_t output[65536]; uint32_t line = 0, col = 0;\n"
                "  size_t size = sotlas_native_compile_diagnostic(bad, sizeof(bad)-1, "
                "output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 4) return 1;\n"
                "  size = sotlas_native_compile_diagnostic(duplicate, sizeof(duplicate)-1, "
                "output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 1) return 5;\n"
                "  size = sotlas_native_compile_diagnostic(duplicate_parameter, "
                "sizeof(duplicate_parameter)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 20) { "
                "fprintf(stderr, \"duplicate parameter: %zu %u %u\\n\", size, line, col); "
                "return 6; }\n"
                "  size = sotlas_native_compile_diagnostic(duplicate_local, "
                "sizeof(duplicate_local)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 4 || col != 2) return 7;\n"
                "  size = sotlas_native_compile_diagnostic(unsupported_struct, "
                "sizeof(unsupported_struct)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 2) { "
                "fprintf(stderr, \"unsupported struct: %zu %u %u\\n\", size, line, col); "
                "return 8; }\n"
                "  size = sotlas_native_compile_diagnostic(unsupported_enum, "
                "sizeof(unsupported_enum)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 2) { "
                "fprintf(stderr, \"unsupported enum: %zu %u %u\\n\", size, line, col); "
                "return 9; }\n"
                "  size = sotlas_native_compile_diagnostic(break_outside_loop, "
                "sizeof(break_outside_loop)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) return 10;\n"
                "  size = sotlas_native_compile_diagnostic(continue_outside_loop, "
                "sizeof(continue_outside_loop)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) return 11;\n"
                "  size = sotlas_native_compile_diagnostic(return_outside_function, "
                "sizeof(return_outside_function)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) return 12;\n"
                "  size = sotlas_native_compile_diagnostic(unknown_local, "
                "sizeof(unknown_local)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 26) { "
                "fprintf(stderr, \"unknown local: %zu %u %u\\n\", size, line, col); "
                "return 13; }\n"
                "  size = sotlas_native_compile_diagnostic(unknown_call, "
                "sizeof(unknown_call)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 26) { "
                "fprintf(stderr, \"unknown call: %zu %u %u\\n\", size, line, col); "
                "return 15; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_arity, "
                "sizeof(wrong_arity)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 26) { "
                "fprintf(stderr, \"wrong arity: %zu %u %u\\n\", size, line, col); "
                "return 16; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_argument_type, "
                "sizeof(wrong_argument_type)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 44) { "
                "fprintf(stderr, \"argument type: %zu %u %u\\n\", size, line, col); "
                "return 17; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_expression_type, "
                "sizeof(wrong_expression_type)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 3 || col != 60) { "
                "fprintf(stderr, \"expression type: %zu %u %u\\n\", size, line, col); "
                "return 18; }\n"
                "  size = sotlas_native_compile_diagnostic(wrong_return_type, "
                "sizeof(wrong_return_type)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 40) { "
                "fprintf(stderr, \"return type: %zu %u %u\\n\", size, line, col); "
                "return 19; }\n"
                "  size = sotlas_native_compile_diagnostic(missing_return_value, "
                "sizeof(missing_return_value)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 19) { "
                "fprintf(stderr, \"missing return value: %zu %u %u\\n\", size, line, col); "
                "return 20; }\n"
                "  size = sotlas_native_compile_diagnostic(missing_return_path, "
                "sizeof(missing_return_path)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 2 || col != 1) { "
                "fprintf(stderr, \"missing return path: %zu %u %u\\n\", size, line, col); "
                "return 21; }\n"
                "  size = sotlas_native_compile_diagnostic(both_return_paths, "
                "sizeof(both_return_paths)-1, output, sizeof(output), &line, &col);\n"
                "  if (size == 0 || line != 0 || col != 0) return 22;\n"
                "  size = sotlas_native_compile_diagnostic(immutable_assignment, "
                "sizeof(immutable_assignment)-1, output, sizeof(output), &line, &col);\n"
                "  if (size != 0 || line != 4 || col != 2) { "
                "fprintf(stderr, \"immutable assignment: %zu %u %u\\n\", size, line, col); "
                "return 14; }\n"
                "  size = sotlas_native_compile_diagnostic(good, sizeof(good)-1, "
                "output, sizeof(output), &line, &col);\n"
                "  if (size == 0 || line != 0 || col != 0 || argc != 2) return 2;\n"
                "  FILE *file = fopen(argv[1], \"wb\"); if (!file) return 3;\n"
                "  size_t written = fwrite(output, 1, size, file); fclose(file);\n"
                "  return written == size ? 0 : 4;\n}\n",
                encoding="utf-8",
            )
            default_toolchain.compile_c_to_obj(compiler_c, compiler_obj, opt_level=0)
            default_toolchain.compile_c_to_obj(driver_c, driver_obj, opt_level=0)
            default_toolchain.link_native_binary([compiler_obj, driver_obj], compiler_exe)
            cfg_validation = subprocess.run(
                [str(compiler_exe), "--cfg"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(cfg_validation.returncode, 0, cfg_validation.stderr)
            run_compiler = subprocess.run(
                [str(compiler_exe), str(generated_c)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run_compiler.returncode, 0, run_compiler.stderr)
            self.assertTrue(generated_c.is_file())

            scalar_source = root / "scalar_target.sotlas"
            scalar_source.write_text(
                "module test::scalar_target;\n"
                "fn blend(left: u32, right: u32) -> u32 { "
                "return left * 3 + right - 2; }\n",
                encoding="utf-8",
            )
            lower_result = subprocess.run(
                [str(compiler_exe), "--lower", str(scalar_source)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(lower_result.returncode, 0, lower_result.stderr)
            lower_lines = lower_result.stdout.strip().splitlines()
            self.assertEqual(lower_lines[0], "1|0|0|1|2|1|6|7|7|1")
            self.assertEqual(lower_lines[1], "4:3|7:0|5:0|4:2|6:0|14:0")
            identity_source = root / "identity_target.sotlas"
            identity_source.write_text(
                "module test::identity;\n"
                "fn identity(seed: u32) -> u32 { return seed; }\n",
                encoding="utf-8",
            )
            identity_native = subprocess.run(
                [str(compiler_exe), "--lower", str(identity_source)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(identity_native.returncode, 0, identity_native.stderr)
            scalar_native_instructions = [
                tuple(map(int, item.split(":")))
                for item in identity_native.stdout.strip().splitlines()[1].split("|")
            ]
            scalar_canonical_script = "\n".join((
                "from pathlib import Path",
                "import json, sys",
                "from sotlas_compile import analyze_source_phase1, build_canonical_checked_ownership_sir",
                "from sotlas_compile.target_ir import lower_sir_to_target_ir",
                "source_path = Path(sys.argv[1])",
                "checked = analyze_source_phase1(source_path.read_text(encoding='utf-8'), filename=str(source_path))",
                "checked_sir, _ = build_canonical_checked_ownership_sir(checked)",
                "target = lower_sir_to_target_ir(checked_sir.module)",
                "opcodes = {'return': 14}",
                "instructions = [i for b in target['functions'][0]['blocks'] for i in b['instructions'] if i['op'] in opcodes]",
                "print(json.dumps([(opcodes[i['op']], i.get('attributes', {}).get('value', 0)) for i in instructions]))",
            ))
            canonical_env = os.environ.copy()
            canonical_env["PYTHONPATH"] = str(ROOT / "compiler")
            scalar_canonical_result = subprocess.run(
                [sys.executable, "-c", scalar_canonical_script, str(identity_source)],
                capture_output=True,
                text=True,
                check=False,
                env=canonical_env,
            )
            self.assertEqual(
                scalar_canonical_result.returncode, 0, scalar_canonical_result.stderr
            )
            import json
            scalar_canonical_instructions = [
                tuple(item) for item in json.loads(scalar_canonical_result.stdout)
            ]
            self.assertEqual(
                scalar_native_instructions, scalar_canonical_instructions
            )

            constant_source = root / "constant_target.sotlas"
            constant_source.write_text(
                "module test::constant_target;\n"
                "fn constant() -> u32 { return 7; }\n",
                encoding="utf-8",
            )
            constant_native = subprocess.run(
                [str(compiler_exe), "--lower", str(constant_source)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(constant_native.returncode, 0, constant_native.stderr)
            native_instructions = [
                tuple(map(int, item.split(":")))
                for item in constant_native.stdout.strip().splitlines()[1].split("|")
            ]
            canonical_script = "\n".join((
                "from pathlib import Path",
                "import json, sys",
                "from sotlas_compile import analyze_source_phase1, build_canonical_checked_ownership_sir",
                "from sotlas_compile.target_ir import lower_sir_to_target_ir",
                "source_path = Path(sys.argv[1])",
                "checked = analyze_source_phase1(source_path.read_text(encoding='utf-8'), filename=str(source_path))",
                "checked_sir, _ = build_canonical_checked_ownership_sir(checked)",
                "target = lower_sir_to_target_ir(checked_sir.module)",
                "opcodes = {'const_int': 4, 'return': 14}",
                "instructions = [i for b in target['functions'][0]['blocks'] for i in b['instructions']]",
                "print(json.dumps([(opcodes[i['op']], i.get('attributes', {}).get('value', 0)) for i in instructions]))",
            ))
            canonical_result = subprocess.run(
                [sys.executable, "-c", canonical_script, str(constant_source)],
                capture_output=True,
                text=True,
                check=False,
                env=canonical_env,
            )
            self.assertEqual(canonical_result.returncode, 0, canonical_result.stderr)
            canonical_instructions = [tuple(item) for item in json.loads(canonical_result.stdout)]
            self.assertEqual(native_instructions, canonical_instructions)

            assembly_file = root / "constant_target.s"
            assembly_result = subprocess.run(
                [str(compiler_exe), "--asm", str(constant_source), str(assembly_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(assembly_result.returncode, 0, assembly_result.stderr)
            assembly_text = assembly_file.read_text(encoding="utf-8")
            self.assertIn(".globl constant", assembly_text)
            self.assertIn("movl $7, %eax", assembly_text)
            self.assertIn("ret", assembly_text)
            clang = default_toolchain.find_tool("clang")
            self.assertIsNotNone(clang, "native C tests already require Clang")

            native_object = root / "constant_target_native.o"
            object_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(constant_source), str(native_object)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(object_emit.returncode, 0, object_emit.stderr)
            bad_object_type = subprocess.run(
                [
                    str(compiler_exe), "--bad-object-type", str(constant_source),
                    str(root / "bad_object_type.o"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                bad_object_type.returncode,
                0,
                "Sotlas ELF writer accepted a non-u32 Target IR result",
            )
            object_bytes = native_object.read_bytes()
            self.assertEqual(object_bytes[:7], b"\x7fELF\x02\x01\x01")
            self.assertEqual(struct.unpack_from("<HHI", object_bytes, 16), (1, 62, 1))
            section_header_offset = struct.unpack_from("<Q", object_bytes, 40)[0]
            self.assertEqual(struct.unpack_from("<HHH", object_bytes, 58), (64, 6, 4))
            abi_note_header = section_header_offset + 320
            abi_note_offset = struct.unpack_from("<Q", object_bytes, abi_note_header + 24)[0]
            self.assertEqual(struct.unpack_from("<III", object_bytes, abi_note_offset), (7, 4, 1))
            self.assertEqual(object_bytes[abi_note_offset + 12:abi_note_offset + 19], b"SOTLAS\0")
            self.assertEqual(struct.unpack_from("<I", object_bytes, abi_note_offset + 20)[0], 0)
            text_section = struct.unpack_from(
                "<IIQQQQIIQQ", object_bytes, section_header_offset + 64
            )
            self.assertEqual(text_section[1], 1)  # SHT_PROGBITS
            self.assertEqual(text_section[2], 6)  # SHF_ALLOC | SHF_EXECINSTR
            text_offset, text_size = text_section[4], text_section[5]
            constant_machine_code = object_bytes[text_offset:text_offset + text_size]
            self.assertTrue(constant_machine_code.startswith(b"\x55\x48\x89\xe5"))
            self.assertIn(b"\xb8\x07\x00\x00\x00", constant_machine_code)
            self.assertTrue(constant_machine_code.endswith(b"\xc9\xc3"))
            string_offset, string_size = struct.unpack_from(
                "<QQ", object_bytes, section_header_offset + 192 + 24
            )
            symbol_name = object_bytes[string_offset:string_offset + string_size]
            self.assertIn(b"\x00constant\x00", symbol_name)

            linked_constant = root / "constant_native_linked"
            native_link = subprocess.run(
                [str(compiler_exe), "--link", str(native_object), str(linked_constant)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(native_link.returncode, 0, native_link.stderr)
            linked_bytes = linked_constant.read_bytes()
            self.assertEqual(linked_bytes[:7], b"\x7fELF\x02\x01\x01")
            self.assertEqual(struct.unpack_from("<HHI", linked_bytes, 16), (2, 62, 1))
            self.assertEqual(struct.unpack_from("<Q", linked_bytes, 24)[0], 0x400000 + 120)
            self.assertEqual(struct.unpack_from("<H", linked_bytes, 56)[0], 1)
            malformed_object = root / "malformed_object.o"
            malformed_object.write_bytes(b"BAD!" + object_bytes[4:])
            rejected_link = subprocess.run(
                [str(compiler_exe), "--link", str(malformed_object), str(root / "must_not_exist")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(rejected_link.returncode, 0)
            for malformed_name, offset, format_code, invalid_value in (
                ("bad_shstr_index", 62, "<H", 3),
                ("bad_text_flags", section_header_offset + 64 + 8, "<Q", 0),
                ("bad_section_name", section_header_offset + 128, "<I", 9),
                ("bad_text_alignment", section_header_offset + 64 + 48, "<Q", 1),
            ):
                malformed_bytes = bytearray(object_bytes)
                struct.pack_into(format_code, malformed_bytes, offset, invalid_value)
                malformed_path = root / f"{malformed_name}.o"
                malformed_path.write_bytes(malformed_bytes)
                malformed_output = root / f"{malformed_name}_output"
                malformed_result = subprocess.run(
                    [str(compiler_exe), "--link", str(malformed_path), str(malformed_output)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(malformed_result.returncode, 0, malformed_name)
                self.assertFalse(malformed_output.exists(), malformed_name)
            if sys.platform.startswith("linux"):
                linked_constant.chmod(0o755)
                linked_run = subprocess.run(
                    [str(linked_constant)], capture_output=True, text=True, check=False
                )
                self.assertEqual(linked_run.returncode, 7, linked_run.stderr)

            if sys.platform.startswith("linux"):
                elf_caller = root / "elf_object_caller.c"
                elf_caller.write_text(
                    "#include <stdint.h>\nextern uint32_t constant(void);\n"
                    "int main(void) { return constant() == 7u ? 0 : 1; }\n",
                    encoding="utf-8",
                )
                elf_executable = root / "elf_object_native"
                link_result = subprocess.run(
                    [str(clang), str(elf_caller), str(native_object), "-o", str(elf_executable)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(link_result.returncode, 0, link_result.stderr)
                run_result = subprocess.run(
                    [str(elf_executable)], capture_output=True, text=True, check=False
                )
                self.assertEqual(run_result.returncode, 0, run_result.stderr)

            object_arithmetic_source = root / "object_arithmetic.sotlas"
            object_arithmetic_source.write_text(
                "module test::object_arithmetic;\n"
                "fn arithmetic() -> u32 { return 4 * 3 + 5 - 2; }\n",
                encoding="utf-8",
            )
            arithmetic_native_object = root / "object_arithmetic.o"
            arithmetic_object_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(object_arithmetic_source), str(arithmetic_native_object)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(arithmetic_object_emit.returncode, 0, arithmetic_object_emit.stderr)
            arithmetic_object_bytes = arithmetic_native_object.read_bytes()
            arithmetic_shoff = struct.unpack_from("<Q", arithmetic_object_bytes, 40)[0]
            arithmetic_text_section = struct.unpack_from(
                "<IIQQQQIIQQ", arithmetic_object_bytes, arithmetic_shoff + 64
            )
            arithmetic_text_offset = arithmetic_text_section[4]
            arithmetic_text_size = arithmetic_text_section[5]
            arithmetic_machine_code = arithmetic_object_bytes[
                arithmetic_text_offset:arithmetic_text_offset + arithmetic_text_size
            ]
            self.assertIn(b"\x0f\xaf\x85", arithmetic_machine_code)
            self.assertIn(b"\x03\x85", arithmetic_machine_code)
            self.assertIn(b"\x2b\x85", arithmetic_machine_code)
            linked_arithmetic = root / "arithmetic_native_linked"
            arithmetic_native_link = subprocess.run(
                [str(compiler_exe), "--link", str(arithmetic_native_object), str(linked_arithmetic)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(arithmetic_native_link.returncode, 0, arithmetic_native_link.stderr)
            if sys.platform.startswith("linux"):
                linked_arithmetic.chmod(0o755)
                linked_arithmetic_run = subprocess.run(
                    [str(linked_arithmetic)], capture_output=True, text=True, check=False
                )
                self.assertEqual(linked_arithmetic_run.returncode, 15, linked_arithmetic_run.stderr)
            if sys.platform.startswith("linux"):
                arithmetic_caller = root / "elf_arithmetic_caller.c"
                arithmetic_caller.write_text(
                    "#include <stdint.h>\nextern uint32_t arithmetic(void);\n"
                    "int main(void) { return arithmetic() == 15u ? 0 : 1; }\n",
                    encoding="utf-8",
                )
                arithmetic_elf_executable = root / "elf_arithmetic_native"
                arithmetic_link = subprocess.run(
                    [str(clang), str(arithmetic_caller), str(arithmetic_native_object), "-o", str(arithmetic_elf_executable)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(arithmetic_link.returncode, 0, arithmetic_link.stderr)
                arithmetic_elf_run = subprocess.run(
                    [str(arithmetic_elf_executable)], capture_output=True, text=True, check=False
                )
                self.assertEqual(arithmetic_elf_run.returncode, 0, arithmetic_elf_run.stderr)

            parameter_object_source = root / "parameter_object.sotlas"
            parameter_object_source.write_text(
                "module test::parameter_object;\n"
                "fn combine(left: u32, right: u32) -> u32 { "
                "return left * 3 + right - 2; }\n",
                encoding="utf-8",
            )
            parameter_object = root / "parameter_object.o"
            parameter_object_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(parameter_object_source), str(parameter_object)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(parameter_object_emit.returncode, 0, parameter_object_emit.stderr)
            parameter_object_bytes = parameter_object.read_bytes()
            parameter_shoff = struct.unpack_from("<Q", parameter_object_bytes, 40)[0]
            parameter_text_section = struct.unpack_from(
                "<IIQQQQIIQQ", parameter_object_bytes, parameter_shoff + 64
            )
            parameter_code = parameter_object_bytes[
                parameter_text_section[4]:parameter_text_section[4] + parameter_text_section[5]
            ]
            self.assertTrue(b"\x89\xbd\xf8\xff\xff\xff" in parameter_code or b"\x89\x85\xf8\xff\xff\xff" in parameter_code)  # EDI -> slot 1
            self.assertIn(b"\x89\xb5\xf0\xff\xff\xff", parameter_code)  # ESI -> slot 2
            if sys.platform.startswith("linux"):
                parameter_caller = root / "parameter_object_caller.c"
                parameter_caller.write_text(
                    "#include <stdint.h>\nextern uint32_t combine(uint32_t, uint32_t);\n"
                    "int main(void) { return combine(4u, 5u) == 15u ? 0 : 1; }\n",
                    encoding="utf-8",
                )
                parameter_exe = root / "parameter_object_native"
                parameter_link = subprocess.run(
                    [str(clang), str(parameter_caller), str(parameter_object), "-o", str(parameter_exe)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(parameter_link.returncode, 0, parameter_link.stderr)
                parameter_run = subprocess.run(
                    [str(parameter_exe)], capture_output=True, text=True, check=False
                )
                self.assertEqual(parameter_run.returncode, 0, parameter_run.stderr)

            six_parameter_source = root / "six_parameter_object.sotlas"
            six_parameter_source.write_text(
                "module test::six_parameter_object;\n"
                "fn sum_six(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32) -> u32 { "
                "return a + b + c + d + e + f; }\n",
                encoding="utf-8",
            )
            six_parameter_object = root / "six_parameter_object.o"
            six_parameter_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(six_parameter_source), str(six_parameter_object)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(six_parameter_emit.returncode, 0, six_parameter_emit.stderr)
            six_parameter_bytes = six_parameter_object.read_bytes()
            six_parameter_shoff = struct.unpack_from("<Q", six_parameter_bytes, 40)[0]
            six_parameter_text = struct.unpack_from(
                "<IIQQQQIIQQ", six_parameter_bytes, six_parameter_shoff + 64
            )
            six_parameter_code = six_parameter_bytes[
                six_parameter_text[4]:six_parameter_text[4] + six_parameter_text[5]
            ]
            # SysV integer argument registers: edi, esi, edx, ecx, r8d and r9d.
            for encoding in (
                b"\x89\x85", b"\x89\xb5", b"\x89\x95", b"\x89\x8d",
                b"\x44\x89\x85", b"\x44\x89\x8d",
            ):
                self.assertIn(encoding, six_parameter_code)
            six_parameter_link = subprocess.run(
                [str(compiler_exe), "--link", str(six_parameter_object), str(root / "invalid_entry_abi")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(six_parameter_link.returncode, 0)
            self.assertFalse((root / "invalid_entry_abi").exists())
            six_parameter_linked = root / "six_parameter_sotlas_linked"
            six_parameter_sotlas_link = subprocess.run(
                [str(compiler_exe), "--link-six", str(six_parameter_object), str(six_parameter_linked)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(six_parameter_sotlas_link.returncode, 0, six_parameter_sotlas_link.stderr)
            if sys.platform.startswith("linux"):
                six_parameter_linked.chmod(0o755)
                six_parameter_linked_run = subprocess.run(
                    [str(six_parameter_linked)], capture_output=True, text=True, check=False
                )
                self.assertEqual(six_parameter_linked_run.returncode, 21, six_parameter_linked_run.stderr)
                six_parameter_caller = root / "six_parameter_object_caller.c"
                six_parameter_caller.write_text(
                    "#include <stdint.h>\n"
                    "extern uint32_t sum_six(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t,uint32_t);\n"
                    "int main(void) { return sum_six(1u,2u,3u,4u,5u,6u) == 21u ? 0 : 1; }\n",
                    encoding="utf-8",
                )
                six_parameter_exe = root / "six_parameter_object_native"
                six_parameter_native_link = subprocess.run(
                    [str(clang), str(six_parameter_caller), str(six_parameter_object), "-o", str(six_parameter_exe)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(six_parameter_native_link.returncode, 0, six_parameter_native_link.stderr)
                six_parameter_run = subprocess.run(
                    [str(six_parameter_exe)], capture_output=True, text=True, check=False
                )
                self.assertEqual(six_parameter_run.returncode, 0, six_parameter_run.stderr)

            bool_entry_source = root / "bool_entry.sotlas"
            bool_entry_source.write_text(
                "module test::bool_entry;\n"
                "fn main(flag: bool) -> u32 { if flag { return 1; } else { return 0; } }\n",
                encoding="utf-8",
            )
            bool_entry_object = root / "bool_entry.o"
            bool_entry_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(bool_entry_source), str(bool_entry_object)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(bool_entry_emit.returncode, 0, bool_entry_emit.stderr)
            bool_entry_executable = root / "bool_entry_native"
            bool_entry_link = subprocess.run(
                [str(compiler_exe), "--link-one", str(bool_entry_object), str(bool_entry_executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(bool_entry_link.returncode, 0, bool_entry_link.stderr)
            invalid_bool_entry = root / "bool_entry_invalid_native"
            invalid_bool_link = subprocess.run(
                [str(compiler_exe), "--link-one-invalid", str(bool_entry_object), str(invalid_bool_entry)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(invalid_bool_link.returncode, 0)
            self.assertFalse(invalid_bool_entry.exists())
            if sys.platform.startswith("linux"):
                bool_entry_executable.chmod(0o755)
                bool_entry_run = subprocess.run(
                    [str(bool_entry_executable)], capture_output=True, text=True, check=False,
                )
                self.assertEqual(bool_entry_run.returncode, 1, bool_entry_run.stderr)

            linked_call_module = root / "linked_call_module.sotlas"
            linked_call_module.write_text(
                "module test::linked_call_module;\n"
                "fn main(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32) -> u32 { return sum_six(a, b, c, d, e, f); }\n"
                "fn sum_six(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32) -> u32 { return a + b + c + d + e + f; }\n",
                encoding="utf-8",
            )
            linked_call_object = root / "linked_call_module.o"
            linked_call_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(linked_call_module), str(linked_call_object)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(linked_call_emit.returncode, 0, linked_call_emit.stderr)
            linked_call_executable = root / "linked_call_module_native"
            linked_call_link = subprocess.run(
                [str(compiler_exe), "--link-six", str(linked_call_object), str(linked_call_executable)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(linked_call_link.returncode, 0, linked_call_link.stderr)
            if sys.platform.startswith("linux"):
                linked_call_executable.chmod(0o755)
                linked_call_run = subprocess.run(
                    [str(linked_call_executable)], capture_output=True, text=True, check=False,
                )
                self.assertEqual(linked_call_run.returncode, 21, linked_call_run.stderr)

            external_ir_source = root / "external_ir.sotlas"
            external_ir_source.write_text(
                "module test::external_ir;\n"
                "fn caller(value: u32) -> u32 { return ext_add(value, 1); }\n"
                "fn ext_add(left: u32, right: u32) -> u32;\n",
                encoding="utf-8",
            )
            external_ir_report = root / "external_ir.report"
            external_ir_result = subprocess.run(
                [str(compiler_exe), "--ir-extern", str(external_ir_source), str(external_ir_report)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(external_ir_result.returncode, 0, external_ir_result.stderr)
            self.assertEqual(external_ir_report.read_text(encoding="utf-8"), "external-signature-ok")

            constant_module_source = root / "constant_module_object.sotlas"
            constant_module_source.write_text(
                "module test::constant_module_object;\n"
                "fn first_value() -> u32 { return 7; }\n"
                "fn helper(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32) -> u32 { "
                "return a + b + c + d + e + f; }\n"
                "fn second_value() -> u32 { return helper(1, 2, 3, 4, 5, 6); }\n",
                encoding="utf-8",
            )
            constant_module_object = root / "constant_module_object.o"
            constant_module_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(constant_module_source), str(constant_module_object)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(constant_module_emit.returncode, 0, constant_module_emit.stderr)
            constant_module_bytes = constant_module_object.read_bytes()
            constant_module_shoff = struct.unpack_from("<Q", constant_module_bytes, 40)[0]
            constant_module_symtab = struct.unpack_from(
                "<IIQQQQIIQQ", constant_module_bytes, constant_module_shoff + 128
            )
            self.assertEqual(constant_module_symtab[5], 96)
            second_symbol = constant_module_symtab[4] + 48
            self.assertEqual(struct.unpack_from("<Q", constant_module_bytes, second_symbol + 8)[0], 30)
            self.assertGreater(struct.unpack_from("<Q", constant_module_bytes, second_symbol + 16)[0], 30)
            linked_constant_module = root / "constant_module_linked"
            link_constant_module = subprocess.run(
                [str(compiler_exe), "--link", str(constant_module_object), str(linked_constant_module)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(link_constant_module.returncode, 0, link_constant_module.stderr)
            if sys.platform.startswith("linux"):
                linked_constant_module.chmod(0o755)
                linked_constant_module_run = subprocess.run(
                    [str(linked_constant_module)], capture_output=True, text=True, check=False
                )
                self.assertEqual(linked_constant_module_run.returncode, 7, linked_constant_module_run.stderr)
                constant_module_caller = root / "constant_module_caller.c"
                constant_module_caller.write_text(
                    "#include <stdint.h>\nextern uint32_t first_value(void); extern uint32_t helper(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t); extern uint32_t second_value(void);\n"
                    "int main(void) { return first_value() == 7u && helper(1u,2u,3u,4u,5u,6u) == 21u && second_value() == 21u ? 0 : 1; }\n",
                    encoding="utf-8",
                )
                constant_module_exe = root / "constant_module_native"
                constant_module_native_link = subprocess.run(
                    [str(clang), str(constant_module_caller), str(constant_module_object), "-o", str(constant_module_exe)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(constant_module_native_link.returncode, 0, constant_module_native_link.stderr)
                constant_module_native_run = subprocess.run(
                    [str(constant_module_exe)], capture_output=True, text=True, check=False
                )
                self.assertEqual(constant_module_native_run.returncode, 0, constant_module_native_run.stderr)

            unsupported_constant_module = root / "unsupported_constant_module.sotlas"
            unsupported_constant_module.write_text(
                "module test::unsupported_constant_module;\n"
                "fn first() -> u32 { return 7; }\n"
                "fn second(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32, g: u32) -> u32 { return a; }\n",
                encoding="utf-8",
            )
            unsupported_constant_module_output = root / "unsupported_constant_module.o"
            unsupported_constant_module_result = subprocess.run(
                [str(compiler_exe), "--obj", str(unsupported_constant_module), str(unsupported_constant_module_output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unsupported_constant_module_result.returncode, 0)
            self.assertFalse(unsupported_constant_module_output.exists())

            # The Sotlas-authored ELF writer and linker execute both sides of
            # a conditional CFG without invoking an assembler.
            for branch_name, condition, expected_exit in (
                ("true", "2 < 3", 19),
                ("false", "3 < 2", 23),
            ):
                branch_module = root / f"cfg_object_{branch_name}.sotlas"
                branch_module.write_text(
                    "module test::cfg_object;\n"
                    f"fn main() -> u32 {{ if {condition} {{ return 19; }} else {{ return 23; }} }}\n",
                    encoding="utf-8",
                )
                branch_object = root / f"cfg_object_{branch_name}.o"
                branch_emit = subprocess.run(
                    [str(compiler_exe), "--obj", str(branch_module), str(branch_object)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(branch_emit.returncode, 0, branch_emit.stderr)
                if branch_name == "true":
                    excess_argument_executable = root / "cfg_object_excess_arguments"
                    excess_arguments = subprocess.run(
                        [str(compiler_exe), "--link-six", str(branch_object), str(excess_argument_executable)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertNotEqual(excess_arguments.returncode, 0)
                    self.assertFalse(excess_argument_executable.exists())
                    bad_branch_object = root / "cfg_object_bad_target.o"
                    bad_branch = subprocess.run(
                        [str(compiler_exe), "--bad-object-target", str(branch_module), str(bad_branch_object)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(bad_branch.returncode, 0, bad_branch.stderr)
                    self.assertFalse(bad_branch_object.exists())
                if sys.platform.startswith("linux"):
                    branch_executable = root / f"cfg_object_{branch_name}"
                    branch_link = subprocess.run(
                        [str(compiler_exe), "--link", str(branch_object), str(branch_executable)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(branch_link.returncode, 0, branch_link.stderr)
                    branch_executable.chmod(0o755)
                    branch_run = subprocess.run(
                        [str(branch_executable)], capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(branch_run.returncode, expected_exit, branch_run.stderr)

            recursive_module = root / "recursive_cfg.sotlas"
            recursive_module.write_text(
                "module test::recursive_cfg;\n"
                "fn countdown(n: u32) -> u32 { if n == 0 { return 0; } else { return countdown(n - 1); } }\n",
                encoding="utf-8",
            )
            recursive_object = root / "recursive_cfg.o"
            recursive_emit = subprocess.run(
                [str(compiler_exe), "--obj", str(recursive_module), str(recursive_object)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(recursive_emit.returncode, 0, recursive_emit.stderr)
            invalid_recursive_object = root / "recursive_cfg_invalid_call.o"
            invalid_recursive = subprocess.run(
                [str(compiler_exe), "--bad-object-call", str(recursive_module), str(invalid_recursive_object)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(invalid_recursive.returncode, 0, invalid_recursive.stderr)
            self.assertFalse(invalid_recursive_object.exists())
            invalid_recursive_type_object = root / "recursive_cfg_invalid_call_type.o"
            invalid_recursive_type = subprocess.run(
                [str(compiler_exe), "--bad-object-call-type", str(recursive_module), str(invalid_recursive_type_object)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(invalid_recursive_type.returncode, 0, invalid_recursive_type.stderr)
            self.assertFalse(invalid_recursive_type_object.exists())
            if sys.platform.startswith("linux"):
                recursive_caller = root / "recursive_cfg_caller.c"
                recursive_caller.write_text(
                    "#include <stdint.h>\nextern uint32_t countdown(uint32_t);\n"
                    "int main(void) { return countdown(32u) == 0u ? 0 : 1; }\n",
                    encoding="utf-8",
                )
                recursive_executable = root / "recursive_cfg_native"
                recursive_link = subprocess.run(
                    [str(clang), str(recursive_caller), str(recursive_object), "-o", str(recursive_executable)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(recursive_link.returncode, 0, recursive_link.stderr)
                recursive_run = subprocess.run(
                    [str(recursive_executable)], capture_output=True, text=True, check=False,
                )
                self.assertEqual(recursive_run.returncode, 0, recursive_run.stderr)

            forward_call_module = root / "forward_call_module.sotlas"
            forward_call_module.write_text(
                "module test::forward_call_module;\n"
                "fn first() -> u32 { return second(18); }\n"
                "fn second(value: u32) -> u32 { return value + 1; }\n",
                encoding="utf-8",
            )
            forward_call_output = root / "forward_call_module.o"
            forward_call_result = subprocess.run(
                [str(compiler_exe), "--obj", str(forward_call_module), str(forward_call_output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(forward_call_result.returncode, 0, forward_call_result.stderr)
            forward_call_linked = root / "forward_call_module_linked"
            forward_call_link_result = subprocess.run(
                [str(compiler_exe), "--link", str(forward_call_output), str(forward_call_linked)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(forward_call_link_result.returncode, 0, forward_call_link_result.stderr)
            if sys.platform.startswith("linux"):
                forward_call_linked.chmod(0o755)
                forward_call_run = subprocess.run(
                    [str(forward_call_linked)], capture_output=True, text=True, check=False
                )
                self.assertEqual(forward_call_run.returncode, 19, forward_call_run.stderr)
            bad_arity_module = root / "bad_arity_module.sotlas"
            bad_arity_module.write_text(
                "module test::bad_arity_module;\n"
                "fn first() -> u32 { return second(18, 19); }\n"
                "fn second(value: u32) -> u32 { return value; }\n",
                encoding="utf-8",
            )
            bad_arity_output = root / "bad_arity_module.o"
            bad_arity_result = subprocess.run(
                [str(compiler_exe), "--obj", str(bad_arity_module), str(bad_arity_output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad_arity_result.returncode, 0)
            self.assertFalse(bad_arity_output.exists())


            assembly_obj = root / "constant_target.obj"
            assemble_result = subprocess.run(
                [str(clang), "-c", str(assembly_file), "-o", str(assembly_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(assemble_result.returncode, 0, assemble_result.stderr)
            caller_c = root / "constant_target_caller.c"
            caller_c.write_text(
                "#include <stdint.h>\nextern uint32_t constant(void);\n"
                "int main(void) { return constant() == 7u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            caller_obj = root / "constant_target_caller.obj"
            native_exe = root / (
                "constant_target_native.exe" if os.name == "nt" else "constant_target_native"
            )
            default_toolchain.compile_c_to_obj(caller_c, caller_obj, opt_level=0)
            default_toolchain.link_native_binary([assembly_obj, caller_obj], native_exe)
            native_run = subprocess.run(
                [str(native_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(native_run.returncode, 0, native_run.stderr)

            arithmetic_source = root / "arithmetic_target.sotlas"
            arithmetic_source.write_text(
                "module test::arithmetic_target;\n"
                "fn blend(left: u32, right: u32) -> u32 { "
                "return left * 3 + right - 2; }\n",
                encoding="utf-8",
            )
            arithmetic_assembly = root / "arithmetic_target.s"
            arithmetic_emit = subprocess.run(
                [str(compiler_exe), "--asm", str(arithmetic_source), str(arithmetic_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(arithmetic_emit.returncode, 0, arithmetic_emit.stderr)
            arithmetic_text = arithmetic_assembly.read_text(encoding="utf-8")
            self.assertIn(".globl blend", arithmetic_text)
            self.assertIn("imul", arithmetic_text)
            arithmetic_obj = root / "arithmetic_target.obj"
            assemble_result = subprocess.run(
                [str(clang), "-c", str(arithmetic_assembly), "-o", str(arithmetic_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(assemble_result.returncode, 0, assemble_result.stderr)
            arithmetic_caller = root / "arithmetic_target_caller.c"
            arithmetic_caller.write_text(
                "#include <stdint.h>\n"
                "extern uint32_t blend(uint32_t, uint32_t);\n"
                "int main(void) { return blend(4u, 5u) == 15u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            arithmetic_caller_obj = root / "arithmetic_target_caller.obj"
            arithmetic_exe = root / (
                "arithmetic_target_native.exe" if os.name == "nt" else "arithmetic_target_native"
            )
            default_toolchain.compile_c_to_obj(
                arithmetic_caller, arithmetic_caller_obj, opt_level=0
            )
            default_toolchain.link_native_binary(
                [arithmetic_obj, arithmetic_caller_obj], arithmetic_exe
            )
            arithmetic_run = subprocess.run(
                [str(arithmetic_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(arithmetic_run.returncode, 0, arithmetic_run.stderr)

            branch_source = root / "branch_target.sotlas"
            branch_source.write_text(
                "module test::branch_target;\n"
                "fn choose(yes: u32, no: u32) -> u32 { "
                "if yes < no { return yes * 3 + 2; } else { return no - 1; } }\n",
                encoding="utf-8",
            )
            branch_assembly = root / "branch_target.s"
            branch_emit = subprocess.run(
                [str(compiler_exe), "--cfg-asm", str(branch_source), str(branch_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(branch_emit.returncode, 0, branch_emit.stderr)
            branch_text = branch_assembly.read_text(encoding="utf-8")
            self.assertIn("setb %al", branch_text)
            self.assertIn("jne .Lchoose_bb2", branch_text)
            self.assertIn("jmp .Lchoose_bb3", branch_text)
            invalid_comparison = subprocess.run(
                [str(compiler_exe), "--bad-compare", str(branch_source)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(invalid_comparison.returncode, 0, invalid_comparison.stderr)
            branch_obj = root / "branch_target.obj"
            assemble_result = subprocess.run(
                [str(clang), "-c", str(branch_assembly), "-o", str(branch_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(assemble_result.returncode, 0, assemble_result.stderr)
            branch_caller = root / "branch_target_caller.c"
            branch_caller.write_text(
                "#include <stdint.h>\n"
                "extern uint32_t choose(uint32_t, uint32_t);\n"
                "int main(void) { return choose(17u, 29u) == 53u "
                "&& choose(34u, 29u) == 28u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            branch_caller_obj = root / "branch_target_caller.obj"
            branch_exe = root / ("branch_target_native.exe" if os.name == "nt" else "branch_target_native")
            default_toolchain.compile_c_to_obj(branch_caller, branch_caller_obj, opt_level=0)
            default_toolchain.link_native_binary([branch_obj, branch_caller_obj], branch_exe)
            branch_run = subprocess.run(
                [str(branch_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(branch_run.returncode, 0, branch_run.stderr)
            loop_assembly = root / "loop_choice.s"
            loop_emit = subprocess.run(
                [str(compiler_exe), "--cfg-loop", str(loop_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(loop_emit.returncode, 0, loop_emit.stderr)
            bad_loop_emit = subprocess.run(
                [str(compiler_exe), "--bad-cfg-loop", str(root / "bad_loop.s")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad_loop_emit.returncode, 0, "scalar CFG emitter accepted an invalid branch target")
            loop_text = loop_assembly.read_text(encoding="utf-8")
            self.assertIn("jmp .Lloop_choice_bb1", loop_text)
            loop_obj = root / "loop_choice.obj"
            loop_assemble = subprocess.run(
                [str(clang), "-c", str(loop_assembly), "-o", str(loop_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(loop_assemble.returncode, 0, loop_assemble.stderr)
            loop_caller = root / "loop_choice_caller.c"
            loop_caller.write_text(
                "#include <stdint.h>\nextern uint32_t loop_choice(uint32_t);\n"
                "int main(void) { return loop_choice(1u) == 7u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            loop_caller_obj = root / "loop_choice_caller.obj"
            default_toolchain.compile_c_to_obj(loop_caller, loop_caller_obj, opt_level=0)
            loop_exe = root / ("loop_choice.exe" if os.name == "nt" else "loop_choice")
            default_toolchain.link_native_binary([loop_obj, loop_caller_obj], loop_exe)
            loop_run = subprocess.run([str(loop_exe)], capture_output=True, text=True, check=False)
            self.assertEqual(loop_run.returncode, 0, loop_run.stderr)
            phi_assembly = root / "phi_diamond.s"
            phi_emit = subprocess.run(
                [str(compiler_exe), "--cfg-phi", str(phi_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(phi_emit.returncode, 0, phi_emit.stderr)
            phi_native_object = root / "phi_diamond_sotlas.o"
            phi_native_emit = subprocess.run(
                [str(compiler_exe), "--cfg-phi-object", str(phi_native_object)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(phi_native_emit.returncode, 0, phi_native_emit.stderr)
            self.assertTrue(phi_native_object.read_bytes().startswith(b"\x7fELF"))
            bad_phi_emit = subprocess.run(
                [str(compiler_exe), "--bad-cfg-phi", str(root / "bad_phi_diamond.s")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bad_phi_emit.returncode, 0, "CFG emitter accepted a Phi value from a non-predecessor")
            phi_text = phi_assembly.read_text(encoding="utf-8")
            self.assertIn("movl -16(%rbp), %eax", phi_text)
            self.assertIn("movl -24(%rbp), %eax", phi_text)
            phi_obj = root / "phi_diamond.obj"
            phi_assemble = subprocess.run(
                [str(clang), "-c", str(phi_assembly), "-o", str(phi_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(phi_assemble.returncode, 0, phi_assemble.stderr)
            phi_caller = root / "phi_diamond_caller.c"
            phi_caller.write_text(
                "#include <stdbool.h>\n#include <stdint.h>\n"
                "extern uint32_t phi_diamond(bool);\n"
                "int main(void) { return phi_diamond(true) == 17u && phi_diamond(false) == 29u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            phi_caller_obj = root / "phi_diamond_caller.obj"
            default_toolchain.compile_c_to_obj(phi_caller, phi_caller_obj, opt_level=0)
            phi_exe = root / ("phi_diamond.exe" if os.name == "nt" else "phi_diamond")
            default_toolchain.link_native_binary([phi_obj, phi_caller_obj], phi_exe)
            phi_run = subprocess.run([str(phi_exe)], capture_output=True, text=True, check=False)
            self.assertEqual(phi_run.returncode, 0, phi_run.stderr)
            if sys.platform.startswith("linux"):
                phi_native_exe = root / "phi_diamond_sotlas_native"
                phi_native_link = subprocess.run(
                    [str(clang), str(phi_caller), str(phi_native_object), "-o", str(phi_native_exe)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(phi_native_link.returncode, 0, phi_native_link.stderr)
                phi_native_run = subprocess.run(
                    [str(phi_native_exe)], capture_output=True, text=True, check=False,
                )
                self.assertEqual(phi_native_run.returncode, 0, phi_native_run.stderr)
            phi_loop_assembly = root / "phi_loop.s"
            phi_loop_emit = subprocess.run(
                [str(compiler_exe), "--cfg-phi-loop", str(phi_loop_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(phi_loop_emit.returncode, 0, phi_loop_emit.stderr)
            self.assertIn("jmp .Lphi_loop_bb2", phi_loop_assembly.read_text(encoding="utf-8"))
            phi_loop_obj = root / "phi_loop.obj"
            phi_loop_assemble = subprocess.run(
                [str(clang), "-c", str(phi_loop_assembly), "-o", str(phi_loop_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(phi_loop_assemble.returncode, 0, phi_loop_assemble.stderr)
            phi_loop_caller = root / "phi_loop_caller.c"
            phi_loop_caller.write_text(
                "#include <stdint.h>\nextern uint32_t phi_loop(void);\n"
                "int main(void) { return phi_loop() == 3u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            phi_loop_caller_obj = root / "phi_loop_caller.obj"
            default_toolchain.compile_c_to_obj(phi_loop_caller, phi_loop_caller_obj, opt_level=0)
            phi_loop_exe = root / ("phi_loop.exe" if os.name == "nt" else "phi_loop")
            default_toolchain.link_native_binary([phi_loop_obj, phi_loop_caller_obj], phi_loop_exe)
            phi_loop_run = subprocess.run(
                [str(phi_loop_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(phi_loop_run.returncode, 0, phi_loop_run.stderr)
            frontend_loop_source = root / "frontend_loop.sotlas"
            frontend_loop_source.write_text(
                "module test::frontend_loop;\n"
                "fn frontend_loop(enabled: bool) -> u32 {\n"
                "  while enabled { continue; }\n"
                "  return 7;\n"
                "}\n",
                encoding="utf-8",
            )
            frontend_loop_assembly = root / "frontend_loop.s"
            frontend_loop_emit = subprocess.run(
                [str(compiler_exe), "--cfg-asm", str(frontend_loop_source), str(frontend_loop_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(frontend_loop_emit.returncode, 0, frontend_loop_emit.stderr)
            self.assertIn("jmp .Lfrontend_loop_bb1", frontend_loop_assembly.read_text(encoding="utf-8"))
            frontend_loop_obj = root / "frontend_loop.obj"
            frontend_loop_assemble = subprocess.run(
                [str(clang), "-c", str(frontend_loop_assembly), "-o", str(frontend_loop_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(frontend_loop_assemble.returncode, 0, frontend_loop_assemble.stderr)
            frontend_loop_caller = root / "frontend_loop_caller.c"
            frontend_loop_caller.write_text(
                "#include <stdbool.h>\n#include <stdint.h>\n"
                "extern uint32_t frontend_loop(bool);\n"
                "int main(void) { return frontend_loop(false) == 7u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            frontend_loop_caller_obj = root / "frontend_loop_caller.obj"
            default_toolchain.compile_c_to_obj(frontend_loop_caller, frontend_loop_caller_obj, opt_level=0)
            frontend_loop_exe = root / (
                "frontend_loop.exe" if os.name == "nt" else "frontend_loop"
            )
            default_toolchain.link_native_binary(
                [frontend_loop_obj, frontend_loop_caller_obj], frontend_loop_exe
            )
            frontend_loop_run = subprocess.run(
                [str(frontend_loop_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(frontend_loop_run.returncode, 0, frontend_loop_run.stderr)
            frontend_break_source = root / "frontend_break.sotlas"
            frontend_break_source.write_text(
                "module test::frontend_break;\n"
                "fn frontend_break(enabled: bool) -> u32 {\n"
                "  while enabled { break; }\n"
                "  return 9;\n"
                "}\n",
                encoding="utf-8",
            )
            frontend_break_assembly = root / "frontend_break.s"
            frontend_break_emit = subprocess.run(
                [str(compiler_exe), "--cfg-asm", str(frontend_break_source), str(frontend_break_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(frontend_break_emit.returncode, 0, frontend_break_emit.stderr)
            frontend_break_obj = root / "frontend_break.obj"
            frontend_break_assemble = subprocess.run(
                [str(clang), "-c", str(frontend_break_assembly), "-o", str(frontend_break_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(frontend_break_assemble.returncode, 0, frontend_break_assemble.stderr)
            frontend_break_caller = root / "frontend_break_caller.c"
            frontend_break_caller.write_text(
                "#include <stdbool.h>\n#include <stdint.h>\n"
                "extern uint32_t frontend_break(bool);\n"
                "int main(void) { return frontend_break(false) == 9u && frontend_break(true) == 9u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            frontend_break_caller_obj = root / "frontend_break_caller.obj"
            default_toolchain.compile_c_to_obj(frontend_break_caller, frontend_break_caller_obj, opt_level=0)
            frontend_break_exe = root / (
                "frontend_break.exe" if os.name == "nt" else "frontend_break"
            )
            default_toolchain.link_native_binary(
                [frontend_break_obj, frontend_break_caller_obj], frontend_break_exe
            )
            frontend_break_run = subprocess.run(
                [str(frontend_break_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(frontend_break_run.returncode, 0, frontend_break_run.stderr)
            nested_loop_source = root / "nested_loop.sotlas"
            nested_loop_source.write_text(
                "module test::nested_loop;\n"
                "fn nested_loop(repeat: bool, stop: bool) -> u32 {\n"
                "  while repeat { if stop { break; } else { continue; } }\n"
                "  return 11;\n"
                "}\n",
                encoding="utf-8",
            )
            nested_loop_assembly = root / "nested_loop.s"
            nested_loop_emit = subprocess.run(
                [str(compiler_exe), "--cfg-asm", str(nested_loop_source), str(nested_loop_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(nested_loop_emit.returncode, 0, nested_loop_emit.stderr)
            nested_loop_text = nested_loop_assembly.read_text(encoding="utf-8")
            self.assertIn("jmp .Lnested_loop_bb1", nested_loop_text)
            nested_loop_obj = root / "nested_loop.obj"
            nested_loop_assemble = subprocess.run(
                [str(clang), "-c", str(nested_loop_assembly), "-o", str(nested_loop_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(nested_loop_assemble.returncode, 0, nested_loop_assemble.stderr)
            nested_loop_caller = root / "nested_loop_caller.c"
            nested_loop_caller.write_text(
                "#include <stdbool.h>\n#include <stdint.h>\n"
                "extern uint32_t nested_loop(bool, bool);\n"
                "int main(void) { return nested_loop(false, false) == 11u && nested_loop(true, true) == 11u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            nested_loop_caller_obj = root / "nested_loop_caller.obj"
            default_toolchain.compile_c_to_obj(nested_loop_caller, nested_loop_caller_obj, opt_level=0)
            nested_loop_exe = root / (
                "nested_loop.exe" if os.name == "nt" else "nested_loop"
            )
            default_toolchain.link_native_binary(
                [nested_loop_obj, nested_loop_caller_obj], nested_loop_exe
            )
            nested_loop_run = subprocess.run(
                [str(nested_loop_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(nested_loop_run.returncode, 0, nested_loop_run.stderr)
            unsupported_loop_source = root / "unsupported_loop.sotlas"
            unsupported_loop_source.write_text(
                "module test::unsupported_loop;\n"
                "fn unsupported_loop(enabled: bool) -> u32 {\n"
                "  while enabled { let item: u32 = 1; }\n"
                "  return 0;\n"
                "}\n",
                encoding="utf-8",
            )
            unsupported_loop = subprocess.run(
                [str(compiler_exe), "--cfg-asm", str(unsupported_loop_source), str(root / "unsupported_loop.s")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unsupported_loop.returncode, 0)
            for operator, setcc in (
                ("==", "sete"), ("!=", "setne"), ("<", "setb"),
                ("<=", "setbe"), (">", "seta"), (">=", "setae"),
            ):
                comparison_source = root / "comparison_target.sotlas"
                comparison_source.write_text(
                    "module test::comparison_target;\n"
                    "fn comparison(left: u32, right: u32) -> u32 { "
                    f"if left {operator} right {{ return 1; }} else {{ return 0; }} }}\n",
                    encoding="utf-8",
                )
                comparison_assembly = root / "comparison_target.s"
                comparison_emit = subprocess.run(
                    [str(compiler_exe), "--cfg-asm", str(comparison_source), str(comparison_assembly)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(comparison_emit.returncode, 0, comparison_emit.stderr)
                self.assertIn(f"{setcc} %al", comparison_assembly.read_text(encoding="utf-8"))

            call_source = root / "external_call_target.sotlas"
            call_source.write_text(
                "module test::external_call_target;\n"
                "fn triple(value: u32) -> u32 { return value * 3 + 1; }\n"
                "fn combine(left: u32, right: u32) -> u32 { return left + right; }\n"
                "fn wrapper(value: u32) -> u32 { return triple(value) + combine(value, 1); }\n",
                encoding="utf-8",
            )
            call_assembly = root / "external_call_target.s"
            call_emit = subprocess.run(
                [str(compiler_exe), "--asm", str(call_source), str(call_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            call_lower = subprocess.run(
                [str(compiler_exe), "--lower", str(call_source)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(call_emit.returncode, 0, f"{call_emit.stderr}\nIR: {call_lower.stdout}")
            bad_call_emit = subprocess.run(
                [str(compiler_exe), "--bad-call", str(call_source), str(root / "bad_call.s")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                bad_call_emit.returncode,
                0,
                "native x86 backend accepted an unresolved Target IR call",
            )
            bad_call_type_emit = subprocess.run(
                [str(compiler_exe), "--bad-call-type", str(call_source), str(root / "bad_call_type.s")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                bad_call_type_emit.returncode,
                0,
                "native x86 backend accepted a non-u32 Target IR call argument",
            )
            call_assembly_text = call_assembly.read_text(encoding="utf-8")
            self.assertIn("movl %eax, %ecx" if os.name == "nt" else "movl %eax, %edi", call_assembly_text)
            self.assertIn("call triple", call_assembly_text)
            self.assertIn("call combine", call_assembly_text)
            call_obj = root / "external_call_target.obj"
            assemble_result = subprocess.run(
                [str(clang), "-c", str(call_assembly), "-o", str(call_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(assemble_result.returncode, 0, assemble_result.stderr)
            call_caller = root / "external_call_target_caller.c"
            call_caller.write_text(
                "#include <stdint.h>\n"
                "extern uint32_t wrapper(uint32_t);\n"
                "int main(void) { return wrapper(14u) == 58u ? 0 : 1; }\n",
                encoding="utf-8",
            )
            call_caller_obj = root / "external_call_target_caller.obj"
            call_exe = root / ("external_call_target_native.exe" if os.name == "nt" else "external_call_target_native")
            default_toolchain.compile_c_to_obj(call_caller, call_caller_obj, opt_level=0)
            default_toolchain.link_native_binary([call_obj, call_caller_obj], call_exe)
            call_run = subprocess.run(
                [str(call_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(call_run.returncode, 0, call_run.stderr)

            call_arity = 4 if os.name == "nt" else 6
            call_names = ["a", "b", "c", "d", "e", "f"][:call_arity]
            call_values = list(range(2, call_arity + 1))
            arity_source = root / "call_arity_target.sotlas"
            arity_source.write_text(
                "module test::call_arity_target;\n"
                f"fn sum_args({', '.join(f'{name}: u32' for name in call_names)}) -> u32 {{ "
                f"return {' + '.join(call_names)}; }}\n"
                "fn forward(value: u32) -> u32 { return sum_args(value, "
                f"{', '.join(str(value) for value in call_values)}); }}\n",
                encoding="utf-8",
            )
            arity_assembly = root / "call_arity_target.s"
            arity_emit = subprocess.run(
                [str(compiler_exe), "--asm", str(arity_source), str(arity_assembly)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(arity_emit.returncode, 0, arity_emit.stderr)
            self.assertEqual(arity_assembly.read_text(encoding="utf-8").count("call sum_args"), 1)
            arity_obj = root / "call_arity_target.obj"
            arity_assemble = subprocess.run(
                [str(clang), "-c", str(arity_assembly), "-o", str(arity_obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(arity_assemble.returncode, 0, arity_assemble.stderr)
            arity_caller = root / "call_arity_target_caller.c"
            arity_result = 14 + sum(call_values)
            arity_caller.write_text(
                "#include <stdint.h>\nextern uint32_t forward(uint32_t);\n"
                f"int main(void) {{ return forward(14u) == {arity_result}u ? 0 : 1; }}\n",
                encoding="utf-8",
            )
            arity_caller_obj = root / "call_arity_target_caller.obj"
            default_toolchain.compile_c_to_obj(arity_caller, arity_caller_obj, opt_level=0)
            arity_exe = root / (
                "call_arity_target_native.exe" if os.name == "nt" else "call_arity_target_native"
            )
            default_toolchain.link_native_binary([arity_obj, arity_caller_obj], arity_exe)
            arity_run = subprocess.run(
                [str(arity_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(arity_run.returncode, 0, arity_run.stderr)

            unsupported_source = root / "unsupported_target.sotlas"
            unsupported_source.write_text(
                "module test::unsupported_target;\n"
                "fn divide(left: u32, right: u32) -> u32 { "
                "return left / right; }\n",
                encoding="utf-8",
            )
            rejected_result = subprocess.run(
                [str(compiler_exe), "--lower", str(unsupported_source)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(rejected_result.returncode, 0, rejected_result.stderr)
            rejected_fields = rejected_result.stdout.strip().splitlines()[0].split("|")
            self.assertEqual(rejected_fields[0], "0")
            self.assertEqual(rejected_fields[1], "2")
            self.assertEqual(rejected_fields[3:], ["0"] * 6 + ["1"])

            default_toolchain.compile_c_to_obj(generated_c, app_obj, opt_level=0)
            default_toolchain.link_native_binary([app_obj], app_exe)
            run_app = subprocess.run(
                [str(app_exe)], capture_output=True, text=True, check=False
            )
            self.assertEqual(run_app.returncode, 0, run_app.stderr)

            cases = (
                (
                    "parser_tree",
                    "module parity::tree;\n"
                    "pub fn add(left: i32, right: i32) -> i32 { return left + right; }\n"
                    "pub fn apply(value: i32) -> i32 { return add(value, 2); }\n",
                    True,
                    False,
                ),
                (
                    "parser_contextual_literals",
                    "module parity::literals;\n"
                    "pub fn enabled() -> bool { return true; }\n"
                    "pub fn ratio() -> f64 { return 3.5; }\n"
                    "pub fn marker() -> i32 { let letter: char = 'x'; return 0; }\n",
                    True,
                    False,
                ),
                (
                    "parser_diagnostic",
                    "module parity::syntax;\n"
                    "pub fn broken() -> i32 { return 1 + ; }\n",
                    False,
                    True,
                ),
                (
                    "parser_missing_semicolon",
                    "module parity::missing_semicolon;\n"
                    "fn run() -> i32 { let value: i32 = 1\nreturn value; }\n",
                    False,
                    True,
                ),
                (
                    "parser_missing_assignment_semicolon",
                    "module parity::missing_assignment_semicolon;\n"
                    "fn run() -> i32 { let mut value: i32 = 1; value = 2\nreturn value; }\n",
                    False,
                    True,
                ),
                (
                    "semantic_duplicate",
                    "module parity::duplicate;\n"
                    "fn run() -> i32 { return 1; }\n"
                    "fn run() -> i32 { return 2; }\n",
                    False,
                    False,
                ),
                (
                    "semantic_unknown_name",
                    "module parity::unknown;\n"
                    "fn run() -> i32 { return missing; }\n",
                    False,
                    False,
                ),
                (
                    "semantic_return_type",
                    "module parity::wrong_type;\n"
                    "fn run() -> i32 { return true; }\n",
                    False,
                    False,
                ),
                (
                    "lex_unterminated_block_comment",
                    "module parity::bad_comment;\n/* never closed",
                    False,
                    True,
                ),
                (
                    "lex_unterminated_string",
                    'module parity::bad_string;\nfn run() -> i32 { return "open; }\n',
                    False,
                    True,
                ),
                (
                    "lex_unterminated_character",
                    "module parity::bad_character_literal;\nfn run() -> i32 { let letter: char = 'x; return 0; }\n",
                    False,
                    True,
                ),
                (
                    "lex_invalid_character",
                    "module parity::bad_character;\n§\n",
                    False,
                    True,
                ),
            )
            for name, source, expected_acceptance, compare_location in cases:
                with self.subTest(case=name):
                    source_path = root / f"{name}.sotlas"
                    native_c = root / f"{name}.c"
                    source_path.write_text(source, encoding="utf-8")
                    try:
                        canonical_c = canonical_compile_source(
                            source, filename=f"{name}.sotlas"
                        )
                        canonical_error = None
                    except Exception as error:
                        canonical_c = None
                        canonical_error = error
                    canonical_accepted = canonical_error is None
                    self.assertEqual(canonical_accepted, expected_acceptance)

                    native_result = subprocess.run(
                        [str(compiler_exe), "--compile", str(source_path), str(native_c)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(native_result.returncode, 0, native_result.stderr)
                    fields = native_result.stdout.strip().split("|")
                    self.assertEqual(len(fields), 3, native_result.stdout)
                    native_size, native_line, native_col = map(int, fields)
                    native_accepted = native_size > 0
                    self.assertEqual(native_accepted, canonical_accepted)

                    if compare_location:
                        self.assertIsNotNone(canonical_error)
                        self.assertEqual(
                            (native_line, native_col),
                            (canonical_error.line, canonical_error.column),
                        )

                    if name == "parser_tree":
                        self.assertTrue(native_c.is_file())
                        reference_module = parse(source, filename=name)
                        names = [function.name for function in reference_module.functions]
                        self.assertEqual(names, ["add", "apply"])
                        self.assertEqual(
                            [len(function.params) for function in reference_module.functions],
                            [2, 1],
                        )

                        # Both pipelines accept the same parsed module, and
                        # their emitted C must expose the same function ABI.
                        for function_name, arity in (
                            ("add", 2),
                            ("apply", 1),
                        ):
                            for code in (native_c.read_text(encoding="utf-8"), canonical_c):
                                signature = next(
                                    (
                                        line.strip()
                                        for line in code.splitlines()
                                        if function_name + "(" in line
                                        and "{" in line
                                    ),
                                    None,
                                )
                                self.assertIsNotNone(
                                    signature, f"missing {function_name} definition"
                                )
                                self.assertEqual(
                                    signature.count(",") + (0 if "()" in signature else 1),
                                    arity,
                                )

    def test_native_token_module_compiles(self):
        token_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "token.sotlas"
        self.assertTrue(token_file.is_file())
        text = token_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(token_file))
        self.assertIn("TokenKind", c_code)
        self.assertIn("Span", c_code)
        self.assertIn("Token", c_code)

    def test_native_lexer_preserves_operator_and_delimiter_spans(self):
        lexer_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "lexer.sotlas"
        text = lexer_file.read_text(encoding="utf-8")
        self.assertIn("pub fn token_from_span", text)
        self.assertIn("tok.span.offset = start_offset;", text)
        self.assertIn("tok.span.length = self.cursor - start_offset;", text)
        self.assertIn(
            "self.token_from_span(TokenKind::Gt, start_line, start_col, start_offset)",
            text,
        )
        self.assertIn(
            "self.token_from_span(TokenKind::Qmark, start_line, start_col, start_offset)",
            text,
        )

    def test_native_lexer_module_compiles(self):
        lexer_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "lexer.sotlas"
        self.assertTrue(lexer_file.is_file())
        text = lexer_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(lexer_file))
        self.assertIn("Lexer", c_code)
        self.assertIn("next_token", c_code)
        self.assertIn("classify_keyword", c_code)

    def test_native_ast_module_compiles(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        self.assertTrue(ast_file.is_file())
        text = ast_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(ast_file))
        self.assertIn("AstKind", c_code)
        self.assertIn("AstNode", c_code)

    def test_native_parser_module_compiles(self):
        parser_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        self.assertTrue(parser_file.is_file())
        text = parser_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(parser_file))
        self.assertIn("Parser", c_code)
        self.assertIn("parse_module", c_code)
        self.assertIn("parse_statement", c_code)
        self.assertIn("node_capacity", c_code)
        self.assertIn("AstNode", c_code)

    def test_native_parser_records_unexpected_token_location_and_rejects_module(self):
        parser_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        text = parser_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(parser_file))
        self.assertIn("pub error_count: usize;", text)
        self.assertIn("pub error_line: u32;", text)
        self.assertIn("pub error_col: u32;", text)
        self.assertIn("self.error_line = tok.span.line;", text)
        self.assertIn("self.error_col = tok.span.col;", text)
        self.assertIn("self.error_count = self.error_count + 1;", text)
        error_check = text.index("if self.error_count != 0")
        self.assertIn("return 0;", text[error_check:])
        self.assertIn("error_line", c_code)
        self.assertIn("error_col", c_code)

    def test_native_parser_persists_allocated_ast_nodes(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub nodes: *mut AstNode;", text)
        self.assertIn("pub node_capacity: usize;", text)
        self.assertIn("*(self.nodes + idx) = AstNode::new(kind, span);", text)
        self.assertIn("self.node_count >= self.node_capacity", text)

    def test_native_ast_links_parent_ownership(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub parent: usize;", ast_text)
        self.assertIn("parent: 0", ast_text)
        self.assertIn("if child_node.parent != 0", parser_text)
        self.assertIn("child_node.parent = parent;", parser_text)
        self.assertIn("*(self.nodes + child) = child_node;", parser_text)

    def test_native_parser_links_module_declarations(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub fn append_child", text)
        self.assertIn("parent_node.first_child = child;", text)
        self.assertIn("current_node.next_sibling = child;", text)
        self.assertIn("let decl_node: usize = self.parse_declaration();", text)
        self.assertIn("self.append_child(mod_node, decl_node)", text)
        self.assertIn("if self.cursor <= before", text)

    def test_native_parser_persists_function_parameters(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("let mut param_mutable: bool = false;", text)
        self.assertIn("let param_node: usize = self.alloc_node(AstKind::ParamDecl", text)
        self.assertIn("self.set_node_text(param_node, param_name)", text)
        self.assertIn("stored_param.int_value = 1;", text)
        self.assertIn("let param_type: usize = self.parse_type_ref(2);", text)
        self.assertIn("self.append_child(param_node, param_type)", text)
        self.assertIn("self.append_child(fn_node, param_node)", text)

    def test_native_parser_persists_function_return_type_slice(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("TypeRef = 27", ast_text)
        self.assertIn("pub fn set_node_text_range", parser_text)
        self.assertIn("let type_node: usize = self.parse_type_ref(3);", parser_text)
        self.assertIn("self.append_child(fn_node, type_node)", parser_text)

    def test_native_parser_persists_function_body_blocks(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub fn parse_block", text)
        self.assertIn("AstKind::Block", text)
        self.assertIn("let stmt_node: usize = self.parse_statement();", text)
        self.assertIn("self.append_child(block_node, stmt_node)", text)
        self.assertIn("let body_node: usize = self.parse_block();", text)
        self.assertIn("self.append_child(fn_node, body_node)", text)

    def test_native_main_emits_parsed_module_tree(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        emitter_text = emitter_file.read_text(encoding="utf-8")
        main_text = main_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_module", emitter_text)
        self.assertIn("module_node.kind != AstKind::Module", emitter_text)
        self.assertIn("node.kind == AstKind::Import", emitter_text)
        self.assertIn("node.kind == AstKind::FnDecl", emitter_text)
        self.assertIn("self.emit_function(child)", emitter_text)
        self.assertIn("if !emitter.emit_module(module_node)", main_text)

    def test_native_main_fails_closed_on_parser_failure(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        text = main_file.read_text(encoding="utf-8")
        self.assertIn("let module_node: usize = p.parse_module();", text)
        self.assertIn("if module_node == 0", text)

    def test_native_parser_persists_local_mutability_and_type(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("let mut is_mutable: bool = tok.kind == TokenKind::KwVar;", text)
        self.assertIn("self.match_token(TokenKind::KwMut)", text)
        self.assertIn("stored_node.int_value = 1;", text)
        self.assertIn("pub fn parse_type_ref", text)
        self.assertIn("let type_node: usize = self.parse_type_ref(1);", text)
        self.assertIn("self.append_child(let_node, type_node)", text)

    def test_native_parser_persists_loop_jump_statements(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("BreakStmt = 28", ast_text)
        self.assertIn("ContinueStmt = 29", ast_text)
        self.assertIn("tok.kind == TokenKind::KwBreak", parser_text)
        self.assertIn("AstKind::BreakStmt", parser_text)
        self.assertIn("tok.kind == TokenKind::KwContinue", parser_text)
        self.assertIn("AstKind::ContinueStmt", parser_text)

    def test_native_parser_persists_defer_payload_ast(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("DeferStmt = 26", ast_text)
        self.assertIn("tok.kind == TokenKind::KwDefer", parser_text)
        self.assertIn("AstKind::DeferStmt", parser_text)
        self.assertIn("payload_node = self.parse_expression_statement();", parser_text)
        self.assertIn("AstKind::AssignStmt", parser_text)
        self.assertIn("AstKind::ExprCall", parser_text)
        self.assertIn("AstKind::ExprBinary", parser_text)
        self.assertIn("self.append_child(defer_node, payload_node)", parser_text)

    def test_native_ast_retains_source_slices_for_emission(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        parser_text = parser_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        main_text = main_file.read_text(encoding="utf-8")
        self.assertIn("node.str_offset = tok.span.offset;", parser_text)
        self.assertIn("node.str_len = tok.span.length;", parser_text)
        self.assertIn("alloc_text_node(AstKind::ExprIdent, tok)", parser_text)
        self.assertIn("alloc_text_node(AstKind::ExprLiteral, tok)", parser_text)
        self.assertIn("pub source: *const u8;", emitter_text)
        self.assertIn("pub fn write_source_slice", emitter_text)
        self.assertIn("len > self.source_len - offset", emitter_text)
        self.assertIn("source_len: usize", emitter_text)
        self.assertIn("p.node_count", main_text)

    def test_native_emitter_can_serialize_defer_payload_ast(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub nodes: *const AstNode;", text)
        self.assertIn("pub fn emit_expression", text)
        self.assertIn("AstKind::ExprBinary", text)
        self.assertIn("AstKind::ExprCall", text)
        self.assertIn("pub fn emit_statement_payload", text)
        self.assertIn("AstKind::AssignStmt", text)
        self.assertIn("pub fn emit_defer_payload", text)
        self.assertIn("node.kind != AstKind::DeferStmt", text)

    def test_native_emitter_can_lower_deferred_block_payload(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("let payload_index: usize = node.first_child;", text)
        self.assertIn("let payload: AstNode = unsafe", text)
        self.assertIn("payload.kind == AstKind::Block", text)
        self.assertIn("return self.emit_braced_block(payload_index);", text)
        self.assertIn("return self.emit_statement_payload(payload_index);", text)

    def test_native_emitter_collects_block_defers_in_lifo_order(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_defer_chain_lifo", text)
        self.assertIn(
            "self.emit_defer_chain_lifo(node.next_sibling)",
            text,
        )
        self.assertIn("return self.emit_defer_payload(index);", text)
        self.assertIn("pub fn emit_block_exit_defers", text)
        self.assertIn("block.kind != AstKind::Block", text)
        self.assertIn(
            "return self.emit_defer_chain_lifo(block.first_child);",
            text,
        )
        recurse_at = text.index("self.emit_defer_chain_lifo(node.next_sibling)")
        emit_at = text.index("return self.emit_defer_payload(index);", recurse_at)
        self.assertLess(recurse_at, emit_at)

    def test_native_emitter_shares_function_exit_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_function_exit_defers", text)
        self.assertIn("let mut child_on_path: usize = exit_index;", text)
        self.assertIn("let mut parent_index: usize = exit_node.parent;", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("return self.emit_function_exit_defers(return_index);", text)

    def test_native_emitter_collects_only_active_return_defers(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_defer_prefix_lifo", text)
        self.assertIn("if index == stop_before", text)
        self.assertIn("pub fn emit_scope_defers_before", text)
        self.assertIn("stop.parent != block_index", text)
        self.assertIn("pub fn emit_function_exit_defers", text)
        self.assertIn("let mut child_on_path: usize = exit_index;", text)
        self.assertIn("let mut parent_index: usize = exit_node.parent;", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("parent_node.kind == AstKind::FnDecl", text)
        self.assertIn("pub fn emit_return_scope_defers", text)
        self.assertIn("return_node.kind != AstKind::ReturnStmt", text)
        self.assertIn(
            "return self.emit_function_exit_defers(return_index);",
            text,
        )

    def test_native_emitter_collects_loop_jump_defers_until_while(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_loop_jump_scope_defers", text)
        self.assertIn("jump.kind != AstKind::BreakStmt", text)
        self.assertIn("jump.kind != AstKind::ContinueStmt", text)
        self.assertIn(
            "self.emit_scope_defers_before(parent_index, child_on_path)",
            text,
        )
        self.assertIn("parent_node.kind == AstKind::WhileStmt", text)
        self.assertIn("A loop jump outside a loop is structurally invalid", text)

    def test_native_emitter_fails_closed_before_result_abi_exists(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("node.kind == AstKind::TryExpr", text)
        self.assertIn("self.try_context_returns_result(index)", text)
        self.assertIn("Until Result<T,E> has a native C11 ABI", text)
        self.assertIn("if self.type_ref_is_result(type_index)", text)
        self.assertIn("Never leak the Sotlas", text)

    def test_native_result_u64_i32_preserves_err_zero(self):
        abi_file = ROOT / "include" / "sotlas" / "sotlas_abi.h"
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        abi_text = abi_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_RESULT_U64_I32_DEFINED", abi_text)
        self.assertIn("bool is_ok;", abi_text)
        self.assertIn("uint64_t ok;", abi_text)
        self.assertIn("int32_t err;", abi_text)
        self.assertIn("SotlasResultU64I32", emitter_text)
        self.assertIn(".payload.ok", emitter_text)
        self.assertIn(".payload.err", emitter_text)
        self.assertIn(".is_ok", emitter_text)

    def test_native_emitter_uses_stable_result_u64_abi(self):
        abi_file = ROOT / "include" / "sotlas" / "sotlas_abi.h"
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        abi_text = abi_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("SOTLAS_RESULT_U64_DEFINED", abi_text)
        self.assertIn("SotlasResultU64", abi_text)
        self.assertIn("pub fn type_ref_is_result_u64_i32", emitter_text)
        self.assertIn('"Result<u64,i32>"', emitter_text)
        self.assertIn('return self.write_str("SotlasResultU64I32", 18);', emitter_text)
        self.assertIn("SOTLAS_RESULT_U64_DEFINED", emitter_text)

    def test_native_emitter_recognizes_result_try_context(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn type_ref_is_result", text)
        self.assertIn('self.source_slice_equals(typ.str_offset, 6, "Result", 6)', text)
        self.assertIn("return close == 62;", text)
        self.assertIn("pub fn try_context_returns_result", text)
        self.assertIn("node.kind != AstKind::TryExpr", text)
        self.assertIn("self.find_enclosing_function(try_index)", text)
        self.assertIn("self.find_function_return_type(fn_index)", text)
        self.assertIn("return self.type_ref_is_result(type_index);", text)

    def test_native_emitter_lowers_result_ok_err_constructors(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn source_slice_equals_compact", text)
        self.assertIn("pub fn result_constructor_kind", text)
        self.assertIn('"Result::ok"', text)
        self.assertIn('"Result::err"', text)
        self.assertIn('"Result::Ok"', text)
        self.assertIn('"Result::Err"', text)
        self.assertIn("pub fn emit_result_u64_constructor", text)
        self.assertIn('"(SotlasResultU64I32){ .is_ok = true, .payload.ok = "', text)
        self.assertIn('"(SotlasResultU64I32){ .is_ok = false, .payload.err = "', text)
        self.assertIn("self.emit_result_u64_constructor(ret.first_child)", text)
        self.assertIn("node.kind == AstKind::ExprPath", text)

    def test_native_emitter_captures_return_before_defer_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_enclosing_function", text)
        self.assertIn("pub fn find_function_return_type", text)
        self.assertIn("pub fn emit_c_type", text)
        self.assertIn("pub fn emit_return_statement", text)
        self.assertIn('" __sotlas_return_value = "', text)
        self.assertIn("self.emit_expression_for_type(ret.first_child, type_index)", text)
        self.assertIn("self.emit_return_scope_defers(return_index)", text)
        self.assertIn('"return __sotlas_return_value;', text)
        capture_at = text.index("self.emit_expression_for_type(ret.first_child, type_index)")
        cleanup_at = text.index(
            "self.emit_return_scope_defers(return_index)",
            capture_at,
        )
        final_return_at = text.index(
            "return __sotlas_return_value;",
            cleanup_at,
        )
        self.assertLess(capture_at, cleanup_at)
        self.assertLess(cleanup_at, final_return_at)

    def test_native_emitter_supports_function_prototypes(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("let body_index: usize = self.find_function_body(fn_index);", text)
        self.assertIn('return self.write_str(");\\n", 3);', text)
        prototype_at = text.index('return self.write_str(");\\n", 3);')
        body_at = text.index("return self.emit_braced_block(body_index);", prototype_at)
        self.assertLess(prototype_at, body_at)

    def test_native_emitter_lowers_function_signature_and_body(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_function_body", text)
        self.assertIn("pub fn emit_parameter", text)
        self.assertIn("param.kind != AstKind::ParamDecl", text)
        self.assertIn("self.emit_c_type(type_index)", text)
        self.assertIn("pub fn emit_function", text)
        self.assertIn("self.find_function_return_type(fn_index)", text)
        self.assertIn("node.kind == AstKind::ParamDecl", text)
        self.assertIn("self.emit_parameter(child)", text)
        self.assertIn("self.find_function_body(fn_index)", text)
        self.assertIn("return self.emit_braced_block(body_index);", text)

    def test_native_emitter_literal_write_lengths_match(self):
        import ast
        import re

        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        pattern = re.compile(r'write_str\(("(?:\\.|[^"\\])*"),\s*(\d+)\)')
        mismatches = []
        for match in pattern.finditer(text):
            literal = ast.literal_eval(match.group(1))
            declared = int(match.group(2))
            if len(literal) != declared:
                mismatches.append((literal, declared, len(literal)))
        self.assertEqual(mismatches, [])

    def test_native_emitter_lowers_result_try_statement(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_try_statement", text)
        self.assertIn("try_node.kind != AstKind::TryExpr", text)
        self.assertIn("self.try_call_returns_result_u64_i32(try_index)", text)
        self.assertIn("SotlasResultU64I32 __sotlas_try_value = ", text)
        self.assertIn("self.emit_function_exit_defers(try_index)", text)
        self.assertIn('"return __sotlas_try_value;', text)
        self.assertIn("node.kind == AstKind::TryExpr", text)
        self.assertIn("return self.emit_try_statement(index);", text)

    def test_native_emitter_lowers_direct_result_try_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn find_module_function_by_name", text)
        self.assertIn("pub fn try_call_returns_result_u64_i32", text)
        self.assertIn("pub fn try_context_returns_result_u64_i32", text)
        self.assertIn("pub fn emit_try_let_statement", text)
        self.assertIn('"SotlasResultU64I32 __sotlas_try_"', text)
        self.assertIn('".is_ok) {\\n"', text)
        self.assertIn("self.emit_function_exit_defers(let_index)", text)
        self.assertIn('"return __sotlas_try_"', text)
        self.assertIn('".payload.ok;\\n"', text)
        self.assertIn(
            "return self.emit_try_let_statement(index, type_index, init_index);",
            text,
        )

    def test_native_emitter_inferrs_u64_from_result_try_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_try_let_u64_statement", text)
        self.assertIn("type_node.kind == AstKind::TryExpr", text)
        self.assertIn(
            "return self.emit_try_let_u64_statement(index, type_index);",
            text,
        )
        self.assertIn("uint64_t ", text)
        self.assertIn('";\\nif (!__sotlas_try_"', text)
        self.assertIn(
            "return self.emit_try_let_u64_statement(let_index, try_index);",
            text,
        )

    def test_native_emitter_lowers_result_constructor_local_initializer(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn(
            "self.type_ref_is_result_u64_i32(type_index)",
            text,
        )
        self.assertIn(
            "self.result_constructor_kind(init_index) != 0",
            text,
        )
        self.assertIn(
            "self.emit_result_u64_constructor(init_index)",
            text,
        )

    def test_native_emitter_lowers_typed_local_declarations(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_let_statement", text)
        self.assertIn("node.kind != AstKind::LetStmt", text)
        self.assertIn("type_node.kind != AstKind::TypeRef", text)
        self.assertIn("self.emit_c_type(type_index)", text)
        self.assertIn("self.write_source_slice(node.str_offset, node.str_len)", text)
        self.assertIn("let init_index: usize = type_node.next_sibling;", text)
        self.assertIn("self.emit_expression_for_type(init_index, type_index)", text)
        self.assertIn("return self.emit_let_statement(index);", text)

    def test_native_emitter_lowers_while_body_as_lexical_scope(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_while_statement", text)
        self.assertIn("node.kind != AstKind::WhileStmt", text)
        self.assertIn("self.emit_expression(cond_index)", text)
        self.assertIn("return self.emit_braced_block(body_index);", text)
        self.assertIn("node.kind == AstKind::WhileStmt", text)
        self.assertIn("return self.emit_while_statement(index);", text)

    def test_native_emitter_lowers_if_else_blocks(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_braced_block", text)
        self.assertIn("pub fn emit_if_statement", text)
        self.assertIn("node.kind != AstKind::IfStmt", text)
        self.assertIn("self.emit_expression(cond_index)", text)
        self.assertIn("self.emit_braced_block(then_index)", text)
        self.assertIn("else_node.kind == AstKind::Block", text)
        self.assertIn("else_node.kind == AstKind::IfStmt", text)
        self.assertIn("return self.emit_if_statement(else_index);", text)
        self.assertIn("return self.emit_if_statement(index);", text)

    def test_native_emitter_lowers_unsafe_as_nested_lexical_block(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_unsafe_block", text)
        self.assertIn("node.kind != AstKind::UnsafeBlock", text)
        self.assertIn("body.kind != AstKind::Block", text)
        self.assertIn("return self.emit_braced_block(body_index);", text)
        self.assertIn("pub fn emit_braced_block", text)
        self.assertIn("self.emit_block_normal_exit(block_index)", text)
        self.assertIn("node.kind == AstKind::UnsafeBlock", text)
        self.assertIn("return self.emit_unsafe_block(index);", text)

    def test_native_emitter_runs_block_defers_after_normal_statements(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_normal_statement", text)
        self.assertIn("node.kind == AstKind::DeferStmt", text)
        self.assertIn("pub fn emit_block_normal_exit", text)
        self.assertIn("while stmt != 0", text)
        self.assertIn("self.emit_normal_statement(stmt)", text)
        self.assertIn("return self.emit_block_exit_defers(block_index);", text)
        walk_at = text.index("while stmt != 0")
        cleanup_at = text.index(
            "return self.emit_block_exit_defers(block_index);",
            walk_at,
        )
        self.assertLess(walk_at, cleanup_at)

    def test_native_block_loop_jump_stops_path_after_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn emit_loop_jump_statement", text)
        self.assertIn("self.emit_loop_jump_scope_defers(jump_index)", text)
        self.assertIn('return self.write_str("break;\\n", 7);', text)
        self.assertIn('return self.write_str("continue;\\n", 10);', text)
        self.assertIn("stmt_node.kind == AstKind::BreakStmt", text)
        self.assertIn("stmt_node.kind == AstKind::ContinueStmt", text)
        self.assertIn("return self.emit_loop_jump_statement(stmt);", text)
        jump_branch = text.index("stmt_node.kind == AstKind::BreakStmt")
        ordinary_emit = text.index("self.emit_normal_statement(stmt)", jump_branch)
        self.assertLess(jump_branch, ordinary_emit)

    def test_native_block_return_stops_fallthrough_and_duplicate_cleanup(self):
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("stmt_node.kind == AstKind::ReturnStmt", text)
        self.assertIn("return self.emit_return_statement(stmt);", text)
        self.assertIn("Only a fallthrough path reaches the normal lexical cleanup", text)
        return_branch = text.index("stmt_node.kind == AstKind::ReturnStmt")
        statement_emit = text.index("self.emit_normal_statement(stmt)", return_branch)
        fallthrough_cleanup = text.index(
            "return self.emit_block_exit_defers(block_index);",
            statement_emit,
        )
        self.assertLess(return_branch, statement_emit)
        self.assertLess(statement_emit, fallthrough_cleanup)

    def test_native_parser_keeps_nested_generic_type_ranges(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("pub fn parse_type_ref", text)
        self.assertIn("let mut angle_depth: i64 = 0;", text)
        self.assertIn("kind == TokenKind::Lt", text)
        self.assertIn("kind == TokenKind::Gt", text)
        self.assertIn("kind == TokenKind::Shr", text)
        self.assertIn("angle_depth != 0", text)
        self.assertIn("self.parse_type_ref(1)", text)
        self.assertIn("self.parse_type_ref(2)", text)
        self.assertIn("self.parse_type_ref(3)", text)

    def test_native_parser_persists_qualified_expression_paths(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("ExprPath = 31", ast_text)
        self.assertIn("self.match_token(TokenKind::DColon)", parser_text)
        self.assertIn("let path_node: usize = self.alloc_node(AstKind::ExprPath", parser_text)
        self.assertIn("self.set_node_text_range(path_node, tok, path_end)", parser_text)
        self.assertIn("callee_node = path_node;", parser_text)
        self.assertIn("self.append_child(call_node, callee_node)", parser_text)

    def test_native_parser_persists_try_propagation_expression(self):
        ast_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "ast.sotlas"
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        ast_text = ast_file.read_text(encoding="utf-8")
        parser_text = parser_file.read_text(encoding="utf-8")
        self.assertIn("TryExpr = 30", ast_text)
        self.assertIn("pub fn parse_postfix_expression", parser_text)
        self.assertIn("self.match_token(TokenKind::Qmark)", parser_text)
        self.assertIn("AstKind::TryExpr", parser_text)
        self.assertIn("self.append_child(try_node, expr)", parser_text)
        self.assertIn("return self.parse_postfix_expression();", parser_text)

    def test_native_parser_and_emitter_support_unary_expressions(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        emitter_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        )
        parser_text = parser_file.read_text(encoding="utf-8")
        emitter_text = emitter_file.read_text(encoding="utf-8")
        self.assertIn("pub fn parse_unary_expression", parser_text)
        self.assertIn("AstKind::ExprUnary", parser_text)
        self.assertIn("self.parse_unary_expression()", parser_text)
        self.assertIn("pub fn emit_unary_operator", emitter_text)
        self.assertIn("node.kind == AstKind::ExprUnary", emitter_text)
        self.assertIn("self.emit_unary_operator(node.int_value)", emitter_text)

    def test_native_parser_persists_nested_statement_tree(self):
        parser_file = (
            ROOT / "bootstrap" / "sotlas" / "native_compiler" / "parser.sotlas"
        )
        text = parser_file.read_text(encoding="utf-8")
        self.assertIn("self.append_child(let_node, val_node)", text)
        self.assertIn("self.append_child(ret_node, expr_node)", text)
        self.assertIn("self.append_child(unsafe_node, body_node)", text)
        self.assertIn("self.append_child(clinch_node, body_node)", text)
        self.assertIn("self.append_child(clinch_node, revert_node)", text)
        self.assertIn("self.append_child(if_node, cond_node)", text)
        self.assertIn("self.append_child(if_node, then_node)", text)
        self.assertIn("self.append_child(if_node, else_node)", text)
        self.assertIn("self.append_child(while_node, cond_node)", text)
        self.assertIn("self.append_child(while_node, body_node)", text)

    def test_native_sema_module_compiles(self):
        sema_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "sema.sotlas"
        self.assertTrue(sema_file.is_file())
        text = sema_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(sema_file))
        self.assertIn("SymbolKind", c_code)
        self.assertIn("Sema", c_code)
        self.assertIn("check_system_privilege", c_code)

    def test_native_emitter_c_module_compiles(self):
        emitter_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "emitter_c.sotlas"
        self.assertTrue(emitter_file.is_file())
        text = emitter_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(emitter_file))
        self.assertIn("CEmitter", c_code)
        self.assertIn("write_byte", c_code)
        self.assertIn("emit_header", c_code)

    def test_native_main_module_compiles(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        self.assertTrue(main_file.is_file())
        text = main_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(main_file))
        self.assertIn("sotlas_native_compile", c_code)
        self.assertIn("sotlas_native_compile_diagnostic", c_code)
        self.assertIn("g_token_buffer", c_code)
        self.assertIn("g_ast_node_buffer", c_code)
        self.assertIn("AST_NODE_BUFFER_CAPACITY", c_code)
        self.assertIn("if !lex.is_at_end()", text)
        self.assertIn("CEmitter", c_code)

    def test_native_compiler_exposes_parser_error_line_and_column(self):
        main_file = ROOT / "bootstrap" / "sotlas" / "native_compiler" / "main.sotlas"
        text = main_file.read_text(encoding="utf-8")
        c_code = compile_source(text, str(main_file))
        self.assertIn("pub fn sotlas_native_compile_diagnostic(", text)
        self.assertIn("error_line: *mut u32", text)
        self.assertIn("error_col: *mut u32", text)
        self.assertIn("*error_line = p.error_line", text)
        self.assertIn("*error_col = p.error_col", text)
        self.assertIn("sotlas_native_compile_diagnostic(", c_code)
        self.assertIn("sotlas_native_compile(", text)


if __name__ == "__main__":
    unittest.main()
