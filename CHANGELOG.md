# Sotlas Language Changelog

All notable changes to the Sotlas programming language and compiler will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-09-16

### Added
- **First-Class Hardware MMIO Registers (`register`)**:
  - Declarative register syntax: `register Reg: BackingType { field: lo..hi; }`.
  - Compile-time validation: bit width verification against backing unsigned integers (`u8`, `u16`, `u32`, `u64`), automatic bitfield overflow detection, and illegal overlap rejection.
  - Zero-cost volatile code generation: static inline getters/setters (`Name_get_field` and `Name_set_field`) with automatic bit shifting and masking.
  - Volatile pointer read-modify-write: modifying fields via topology pointers (`ptr.field = val`) produces safe volatile read, mask, and volatile store operations without macros.
- **Native Freestanding SIMD Vector Primitives**:
  - Vector types: `f32x4`, `f32x8`, `f64x2`, `f64x4`, `u8x16`, `u8x32`, `i32x4`, `i32x8`, `i64x2`, `i64x4`.
  - Standard arithmetic operator overloading (`+`, `-`, `*`, `/`) with compile-time vector dimension and type verification.
  - Freestanding C11 code emission using portable GCC/Clang vector attributes (`__attribute__((vector_size(N)))`).
- **Official CLI Language Server (`sotlas lsp`)**:
  - Built-in `sotlas lsp [--stdio]` subcommand connecting the unified driver to editor extensions.
- **VS Code & Open VSX Extension 0.5.0**:
  - Full syntax highlighting, outline navigation, and hover documentation for `register`, `mould`, and SIMD types.
  - Complete English documentation and changelog integration.

---

## [0.4.5] - 2026-09-15

### Added
- **Hardware Typestate System**:
  - Strict compile-time lifecycle state transitions for driver development (`Device<Detached> -> Device<Attached> -> Device<Active>`).
  - Phantom type verification in call sites preventing invalid operations in uninitialized hardware states.
- **Const Generics (`forge<T, const N: usize>`)**:
  - Fixed-capacity buffers, DMA rings, and descriptor tables with zero runtime heap allocation.
  - Compile-time dimensional type safety.
- **Comptime `mould` Blocks & Static `probe` Assertions**:
  - In-source static evaluation of constant expressions and memory layout intrinsics (`span_of<T>()`, `stride_of<T>()`, `align_of<T>()`).
  - Static assertion failures reject compilation with clear diagnostic messages.
- **Strict `island` Execution Confinement**:
  - Prevention of accidental reference or pointer escaping from isolated execution domains without explicit `handover`.
- **DMA Barriers & Memory Fences**:
  - Intrinsic `dma_fence()`, `dma_barrier()`, and sequential consistency fences for `*dmazone` transfers.

---

## [0.4.0] - 2026-09-14

### Added
- **Soundness & Ownership Verification**:
  - Flow-sensitive CFG dataflow analysis tracking `sole`, `whisper`, and `handover` transitions across branching paths.
  - Prevention of use-after-move, conflicting mutable borrows, and invalid aliases.
- **Hardware Effect System**:
  - Hardware interrupt handlers (`trapfn`), critical sections (`clinch` / `revert`), memory synchronization (`quench`, `gate`), and inline assembly (`emit`).
- **Topology Pointers**:
  - First-class pointer topology qualification: `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, and `*voidzero`.

---

## [0.3.0] - 2026-09-10

### Added
- Initial public release of Visual Studio Code & Open VSX official extension.
- Real-time native TypeScript diagnostics, outline navigation, and rich hover tooltips.

---

## [0.2.0] - 2026-08-25

### Added
- Sotlas Intermediate Representation (SIR) in Static Single Assignment (SSA) form.
- Freestanding C11 code generator (`codegen_c.py`).

---

## [0.1.0] - 2026-08-01

### Added
- Initial compiler frontend: lexer, recursive descent parser, and AST data structures.
