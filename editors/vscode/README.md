# Sotlas for Visual Studio Code & Open VSX

Official extension support for the **Sotlas** programming language (`.sotlas`, `.sth`).

**Sotlas** is a modern, safe, and expressive general-purpose and systems programming language — engineered with infinite possibilities, from the lowest level (bare-metal, monolithic kernels/microkernels, drivers, and embedded systems) to high-level applications (game engines, command-line tools, network services, and desktop apps).

<p align="left">
  <a href="https://sotlas.org"><strong>🌐 Website</strong></a> &bull;
  <a href="https://sotlas.org/docs"><strong>📖 Documentation</strong></a> &bull;
  <a href="https://sotlas.org/playground"><strong>⚡ Interactive Playground</strong></a> &bull;
  <a href="https://sotlas.org/community"><strong>👥 Community</strong></a> &bull;
  <a href="https://github.com/Sotlas/sotlas"><strong>🐙 GitHub (Core)</strong></a> &bull;
  <a href="https://github.com/Sotlas/vscode-sotlas"><strong>🔌 GitHub (Extension)</strong></a>
</p>

---

## Key Features

- **Real-Time Native Diagnostics (Zero Dependencies)**:
  - Red squiggles for syntax errors (unbalanced braces/parentheses/brackets, unclosed strings, missing semicolons, incorrect types).
  - Yellow squiggles for code warnings and structural best practices.
  - Works out of the box on 100% of platforms (Windows, Linux, macOS) upon installation, without requiring Python or external binaries.
- **Symbol Navigation and Outline**:
  - Full navigation tree in the editor's *Outline* panel and quick symbol picker (`Ctrl+Shift+O` / `Cmd+Shift+O`).
- **Rich Hover Documentation (Tooltips)**:
  - In-depth conceptual explanations for language keywords (`sole`, `co-owned`, `rawphys`, `barecore`, `quarantine`, `discern`, `guard`, `register`, `mould`, etc.).
- **Comprehensive Syntax Highlighting**:
  - Control flow: `discern`, `match`, `if`, `guard`, `defer`, etc.
  - Architecture & Declarations: `register`, `forge`, `enclave`, `fn`, `trapfn`, `struct`, `mesh`, `barecore`, `typealias`.
  - Topology Pointers & Physical Safety: `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, `*voidzero`.
  - Bit & Register Operators: `.slit[lo..hi]`, `.notch[n]`, `.strand[len]`.
  - Native Freestanding SIMD Types: `f32x4`, `f32x8`, `f64x2`, `f64x4`, `u8x16`, `u8x32`, `i32x4`, `i32x8`, `i64x2`, `i64x4`.
  - Hardware Effects & Concurrency: `pulse`, `probe`, `clinch`, `rebound`, `quarantine`.
- **Integrated Language Server Protocol (LSP)**:
  - Smart autocomplete for keywords, registers, types, and standard library functions.
  - Hover tooltips with type signatures and documentation.
  - Automatic code formatting (*Format Document*).
  - Go to Definition (*Go to Definition*).
- **Integrated Developer Tools & Commands**:
  - `Sotlas: Build Current Package` (`sotlas.build`)
  - `Sotlas: Check Types & Syntax` (`sotlas.check`)
  - `Sotlas: Format Current File` (`sotlas.format`)
  - `Sotlas: Open Sotlas Studio (Browser)` (`sotlas.studio`)
  - `Sotlas: Start Interactive REPL` (`sotlas.repl`)
  - `Sotlas: Emit WebAssembly (.wat)` (`sotlas.dumpWasm`)
  - `Sotlas: Restart Language Server (LSP)` (`sotlas.restartServer`)

---

## Requirements

To enable the Language Server (LSP) and compiler commands, install the official Sotlas toolchain and ensure `sotlas` is accessible in your `PATH`:

```powershell
# On Windows (PowerShell):
irm https://raw.githubusercontent.com/Sotlas/sotlas/main/packaging/install.ps1 | iex
```

```bash
# On Linux / macOS:
curl -fsSL https://raw.githubusercontent.com/Sotlas/sotlas/main/packaging/install.sh | bash
```

---

## Settings

| Setting | Default | Description |
| :--- | :--- | :--- |
| `sotlas.compilerPath` | `"sotlas"` | Path to the executable Sotlas compiler binary. |

---

## Installation

Install directly from your editor:

1. Open **VS Code**, **VSCodium**, or **Cursor**.
2. Press `Ctrl+P` (or `Cmd+P` on macOS) and enter:
   ```text
   ext install sotlas-lang.sotlas
   ```
   *Or simply search for **Sotlas** in the Extensions sidebar (`Ctrl+Shift+X`).*

---

## License

Distributed under the Apache 2.0 License with LLVM Exception.  
Copyright (c) 2026 Hiago Pinho and the Sotlas project contributors.
