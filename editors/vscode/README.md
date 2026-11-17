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

- **Native SDK projects**:
  - Select an installed x86-64 SDK and create a console project in an empty directory.
  - Check, build and run with the Sotlas-written native compiler. No Python, C compiler or external linker is required after obtaining the seed.
  - Report native compiler errors in Problems, including UTF-8 byte-column conversion to editor UTF-16 positions.
  - A failed build preserves the old executable and does not run it.

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
  - `Sotlas: Build Workspace` (`sotlas.build`)
  - `Sotlas: Check Active File` (`sotlas.check`)
  - `Sotlas: Format Active File` (`sotlas.format`)
  - `Sotlas: Open Studio` (`sotlas.studio`)
  - `Sotlas: Start REPL` (`sotlas.repl`)
  - `Sotlas: Emit WebAssembly (.wat)` (`sotlas.dumpWasm`)
  - `Sotlas: Restart Language Server` (`sotlas.restartServer`)

---

## Requirements

For native projects, install the matching Linux x86-64, Windows x86-64 or Intel macOS SDK and select it with **Sotlas: Select Native SDK**. The compiler and its runtime sources come from that SDK. VS Code itself remains an editor dependency; it is not part of the compiler bootstrap.

The existing reference profile remains the default for compatibility. Its commands use the separately installed `sotlas` toolchain; backend/tool requirements depend on that installation. Native selection does not change the global reference-toolchain settings.

The local structural hints work without the compiler. Compiler checks and the
optional LSP report an error when the configured compiler cannot be started.

---

## Settings

| Setting | Default | Description |
| :--- | :--- | :--- |
| `sotlas.compilerPath` | `"sotlas"` | Path to the executable Sotlas compiler binary. |
| `sotlas.toolchain` | `"reference"` | `reference` command syntax or the `native` SDK command profile. |
| `sotlas.nativeSdkPath` | empty | Installed SDK used for new project sources. Select Native SDK sets this for an existing project. |
| `sotlas.nativeSourceRoot` | `"src"` | Source directory relative to the workspace folder. |
| `sotlas.nativeEntry` | `"src/main.sotlas"` | Entry for native build/run. Check uses the active saved source. |
| `sotlas.nativeOutput` | `"build/app"` | Executable under the workspace build directory; Windows appends `.exe`. |
| `sotlas.nativeRunArguments` | `[]` | Program arguments passed directly to the process, without a shell. |

## Start a native console project

1. Install the SDK and the VSIX from the same fully green development workflow.
2. Run **Sotlas: Select Native SDK** and select the SDK directory containing `sdk.json` and `bin`.
3. Run **Sotlas: Create Native Console Project** and choose an empty directory. Selecting an SDK in an empty workspace leaves that directory empty until project creation.
4. Choose **Open Project** when offered, or keep the current folder if it is the one just created. Open `src/main.sotlas`.
5. Run **Sotlas: Check Active File**, **Sotlas: Build Workspace**, then **Sotlas: Run Native Project**. The sample prints `Hello from Sotlas!` in the terminal.

The generated project copies the SDK runtime sources and a console I/O adapter
for the current host. Existing project directories are rejected rather than
overwritten. The SDK path is machine-specific; selecting a new SDK does not
silently replace a project's copied runtime or platform adapter.

Native check saves the active file. Build/run save open source files in the
selected source directory. Run builds first and launches a process task only
after success; source edits during compilation require another build. Compiler
output is available in the Sotlas channel. These are explicit compiler commands,
not automatic semantic checking while typing or a native LSP implementation.

Native formatting, REPL, Studio, WebAssembly and LSP are not provided by this
SDK command profile; the extension explains that limit rather than invoking
incompatible commands. Kernel images use the SDK kernel scripts. Local
structural hints and the optional reference LSP retain their separate scope.

---

## Installation

The preview extension is not published to a marketplace yet. From a terminal, build a local VSIX:

```sh
cd editors/vscode
npm install
npm run compile
npx @vscode/vsce package
```

Install the generated `.vsix` from the VS Code Extensions menu using **Install from VSIX...**.

### Validate the installed package

Before sharing a preview build, run the extension unit tests and the isolated VSIX smoke test:

```sh
npm test
npm run test:vsix
```

The smoke test installs the VSIX into a temporary VS Code profile, activates it
against a small Sotlas workspace, and checks that compiler diagnostics appear
with their source location. The runtime version is pinned in
`test/vscode-version.json` (currently 1.141.0). CI caches that exact runtime;
each smoke test still installs the generated VSIX into a fresh profile.
Transient network failures receive up to three download attempts with backoff.
Install, activation and diagnostic failures are not retried or skipped.
Update the version file deliberately when validating a newer VS Code release.
To run it offline on Windows with an existing VS Code installation,
set `SOTLAS_VSCODE_CLI`, `SOTLAS_VSCODE_EXECUTABLE`, and
`SOTLAS_VSCODE_CLI_SCRIPT` to the installed `Code.exe` and its
`resources/app/out/cli.js`, then run `npm run test:vsix`.

Set `SOTLAS_NATIVE_SDK` to an installed native SDK directory to run the native
VSIX smoke scenario. It creates a project through the installed extension,
compiles and executes the real program, verifies native ownership diagnostics
after Unicode text, confirms that a failed build cannot execute a stale image,
and checks error clearing and existing-directory preservation. CI runs this
scenario on the three SDK hosts. Linux uses a virtual display.

---

## License

Distributed under the Apache 2.0 License with LLVM Exception.  
Copyright (c) 2026 Hiago Pinho and the Sotlas project contributors.
