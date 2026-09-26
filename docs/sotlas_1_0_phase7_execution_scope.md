# Sotlas 1.0 — Phase 7 Execution Domains Scope

**Updated:** 2026-09-26
**Status:** COMPLETE for the Sotlas 1.0 target-configuration contract

## Certified contract

The compiler accepts a closed set of x86-64 and AArch64 triples for Linux,
Windows, Darwin, and freestanding ELF. Target resolution returns the selected
triple, ABI identifier, pointer width, endianness, CPU, normalized CPU features,
and LLVM data layout. Unknown triples, architecture-incompatible features, and
unknown feature names fail closed. Feature dependencies are normalized before
the target is passed to LLVM or Clang.

The CLI accepts `--target` and repeatable `--cpu-feature`. LLVM IR preserves
the target triple, layout, CPU, and features. `@target_feature` requirements
are preserved in SIR and LLVM rejects a target that lacks them. C11 rejects
function-specific feature requirements until it can honor them equivalently.
The x86-64/AArch64 presets have tests for ABI/layout identifiers and object
format distinctions (ELF, COFF, Mach-O).

## Release boundary

This completes Sotlas 1.0's execution-target configuration and fail-closed
contract. It does not claim a complete platform ABI certification, native
execution on every triple, or a Sotlas SIMD language. SIMD intrinsics,
multiversion dispatch, CPU feature detection at runtime, custom calling
conventions, register constraints/clobbers, and heterogeneous domain lowering
remain post-1.0 work. A target accepted by the configuration model is not by
itself proof that a host toolchain can emit or run its artifact.

## CI gate

`test_sotlas_llvm.py` checks target normalization, feature dependencies and
rejection, LLVM IR attributes, target reports, C11 fail-closed behavior, and
target-specific Clang arguments. This gate certifies configuration semantics;
backend-specific executable matrices are owned by their respective backend
milestones.
