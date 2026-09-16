# Changelog

All notable changes to the "Sotlas Programming Language" extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-09-16

### Fixed
- **Marketplace Documentation Hotfix**:
  - Removed internal source compilation and packaging commands from the store README.
  - Added clean, user-friendly editor installation instructions (`ext install hiagopinho.sotlas`).
  - Polished marketplace presentation and styling for VS Code Marketplace and Open VSX Registry.

---

## [0.5.0] - 2026-09-16

### Added
- **Hardware MMIO Registers**:
  - Full syntax highlighting for declarative hardware registers (`register Reg: u32 { field: lo..hi; }`).
  - Native document symbol / outline tree support for `register` declarations.
  - Rich hover documentation explaining deterministic bitfield mapping, zero-cost inlined accessors, and atomic volatile semantics.
- **Native Freestanding SIMD Vector Types**:
  - Syntax highlighting for floating-point SIMD types: `f32x4`, `f32x8`, `f64x2`, `f64x4`.
  - Syntax highlighting for unsigned integer SIMD types: `u8x16`, `u8x32`.
  - Syntax highlighting for signed integer SIMD types: `i32x4`, `i32x8`, `i64x2`, `i64x4`.
- **Comptime & Generics Enhancements**:
  - Syntax highlighting and hover tooltips for comptime `mould` blocks and static `probe` assertions.
  - Support for `typealias` keyword in syntax grammar.
- **Language Server Protocol (LSP)**:
  - Official integration with the `sotlas lsp --stdio` compiler command.

### Changed
- Translated full extension description, README, and documentation to English for international marketplace distribution.
- Updated extension schema and dependencies to latest VS Code engine targets.

---

## [0.4.5] - 2026-09-15

### Added
- **Hardware Typestate Support**:
  - Semantic highlighting and phantom type checking for driver lifecycle states (e.g., `Device<Detached>`, `Device<Attached>`, `Device<Active>`).
- **Const Generics**:
  - Syntax highlighting and parser support for constant generic parameters (`forge<T, const N: usize>`).
- **DMA Barriers & Fences**:
  - Highlighting for `*dmazone` topology pointers and hardware memory fence intrinsics (`dma_fence()`, `dma_barrier()`).
- **Island Confinement**:
  - Visual diagnostic markers for strict domain confinement violations.

---

## [0.4.0] - 2026-09-14

### Added
- **Topology Pointer Highlighting**:
  - Dedicated storage type styling for `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, and `*voidzero`.
- **Hardware Effect Keywords**:
  - Syntax rules for `trapfn`, `clinch`, `revert`, `quench`, `gate`, and `emit`.
- **Bitwise & Register Accessors**:
  - Highlighting for bit slicing (`.slit[lo..hi]`), bit testing (`.notch[n]`), and endianness byte swapping (`.strand[len]`).

---

## [0.3.0] - 2026-09-10

### Added
- **Initial Public Release**:
  - Zero-dependency real-time TypeScript diagnostics engine (unbalanced braces, unclosed strings, missing semicolons, type mismatches).
  - Full document symbol outline navigation (`Ctrl+Shift+O` / `Cmd+Shift+O`).
  - Rich hover tooltips for Sotlas ownership keywords (`sole`, `co-owned`, `island`, `whisper`, `direct`).
  - Icon theme with official Sotlas branding.
  - Automatic language configuration (comment toggling, auto-closing brackets, indentation rules).
