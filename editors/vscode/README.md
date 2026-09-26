# Sotlas for Visual Studio Code & Open VSX

Preview editor support for Sotlas source files (`.sotlas`, `.sth`). The checked-in
compiler contract is documented in the [development repository](https://github.com/HPinho/sotlas_dev).

Sotlas is a systems-language preview focused on an explicitly bounded compiler
contract. Hardware runtime support, general-purpose CFG lowering, and several
advanced examples remain experimental or planned.

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

- **Local structural hints**:
  - Checks delimiters and selected declaration patterns while editing.
  - These hints are not the Sotlas parser or type checker. Use **Sotlas: Check Active File** to run the configured compiler for authoritative diagnostics.
- **Symbol Navigation and Outline**:
  - Full navigation tree in the editor's *Outline* panel and quick symbol picker (`Ctrl+Shift+O` / `Cmd+Shift+O`).
- **Hover Documentation**:
  - Short descriptions for selected Sotlas keywords.
- **Comprehensive Syntax Highlighting**:
  - Control flow: `discern`, `match`, `if`, `guard`, `defer`, etc.
  - Architecture & Declarations: `register`, `forge`, `enclave`, `fn`, `trapfn`, `struct`, `mesh`, `barecore`, `typealias`.
  - Topology Pointers & Physical Safety: `*rawphys`, `*virtmap`, `*portwire`, `*dmazone`, `*voidzero`.
  - Bit & Register Operators: `.slit[lo..hi]`, `.notch[n]`, `.strand[len]`.
  - Native Freestanding SIMD Types: `f32x4`, `f32x8`, `f64x2`, `f64x4`, `u8x16`, `u8x32`, `i32x4`, `i32x8`, `i64x2`, `i64x4`.
  - Hardware Effects & Concurrency: `pulse`, `probe`, `clinch`, `rebound`, `quarantine`.
- **Optional compiler LSP**:
  - Can be enabled with `sotlas.enableExternalLsp` when the installed compiler provides `sotlas lsp --stdio`.
  - Completion, compiler diagnostics, and navigation depend on that server; the extension's local structural hints do not provide those guarantees.
- **Integrated Developer Tools & Commands**:
  - `Sotlas: Build Current Package` (`sotlas.build`)
  - `Sotlas: Check Active File` (`sotlas.check`)
  - `Sotlas: Format Current File` (`sotlas.format`)
  - `Sotlas: Open Sotlas Studio (Browser)` (`sotlas.studio`)
  - `Sotlas: Start Interactive REPL` (`sotlas.repl`)
  - `Sotlas: Emit WebAssembly (.wat)` (`sotlas.dumpWasm`)
  - `Sotlas: Restart Language Server (LSP)` (`sotlas.restartServer`)

---

## Requirements

Compiler commands require a Sotlas toolchain installation and a working C compiler for native builds. For the current preview, install the toolchain using the instructions in the [main README](https://github.com/HPinho/sotlas_dev#-quickstart-verified-preview-subset), then ensure `sotlas` is accessible in your `PATH`.

The local structural hints work without the compiler. Compiler checks and the
optional LSP report an error when the configured compiler cannot be started.

---

## Settings

| Setting | Default | Description |
| :--- | :--- | :--- |
| `sotlas.compilerPath` | `"sotlas"` | Path to the executable Sotlas compiler binary. |

---

## Installation

The preview extension is not published to a marketplace yet. From a terminal, build a local VSIX:

```sh
cd editors/vscode
npm install
npm run compile
npx @vscode/vsce package
```

Install the generated `.vsix` from the VS Code Extensions menu using **Install from VSIX...**. Marketplace installation will be documented when a preview package is published.

---

## License

Distributed under the Apache 2.0 License with LLVM Exception.  
Copyright (c) 2026 Hiago Pinho and the Sotlas project contributors.
