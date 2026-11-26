# Sotlas native terminal SDK

This preview contains a native x86-64 compiler, its original Sotlas sources,
native runtime modules, a terminal calculator, a JSON configuration application,
a Windows graphical calculator and 101 executable/rejection/fault contract tests
written in Sotlas. UI model and Unicode tests run on every CLI target; Windows
also runs hidden-window rendering/cleanup tests and builds the GUI executable.
Seven native kernel profiles, their original sources and cross-host image build
scripts are included. Linux QEMU boot checks are separate from hosted examples.
The CPU tensor library also provides row reductions and row-vector broadcasts;
`examples/native_tensor_rows` demonstrates preprocessing with caller-owned
storage. See `docs/native_tensor_ops.md` for shape, alias and numerical rules.
Caller-backed CSV reading/writing and an inventory round-trip example are
included in `examples/native_csv`; see `docs/native_csv.md` for quoting,
line-ending, byte-preservation and buffer contracts.
SDK verification also builds `csv-normalize` (`csv-normalize.exe` on Windows)
for converting CSV files through standard input and output. Usage and exit
codes are in `examples/native_csv/README.md`.

The compiler builds and links the bundled examples and rebuilds itself after
receiving this seed. These operations do not invoke Python, a C compiler or an
external linker. Packaging and test orchestration use Bash or PowerShell and
ordinary OS utilities. Producing the initial seed still has a separate Stage-0
reference path; this SDK does not claim full language parity or global removal
of that path.

## Install

Candidate bundles are attached to the
[main workflow](https://github.com/HPinho/sotlas_dev/actions) as
`sotlas-terminal-sdk-linux-x64`, `sotlas-terminal-sdk-windows-x64` and
`sotlas-terminal-sdk-macos-x64`. Use the artifacts from the same fully green
run. They are CI candidates, not published stable releases.

For a versioned preview, download the matching `sotlas-sdk-*-x64` archive and
`sotlas-preview.vsix` from the same [GitHub prerelease](https://github.com/HPinho/sotlas_dev/releases). The release's
`SHA256SUMS.txt` lists the archive and extension hashes. CI downloads retain
their individual `.sha256` files.

Use a bundle matching Linux x86-64, Windows x86-64 or Intel macOS. Compare the
archive's SHA-256 with its line in `SHA256SUMS.txt` for a prerelease or with its
`.sha256` file for a CI artifact, then extract it. Windows can use
`Get-FileHash -Algorithm SHA256 ARCHIVE`; Linux can use `sha256sum ARCHIVE`;
macOS can use `shasum -a 256 ARCHIVE`. The
installer verifies every bundled file and the target before copying to a fresh
directory. Checksums detect corruption; they are not publisher signatures.
No administrator privileges, registry edits or global PATH changes are needed.

The installed `sdk.json` identifies the SDK version, build source revision,
platform and SHA-256 of the bundled compiler. The version comes from the project
metadata at packaging time. Local builds may show `local` as their revision.
The installer checks the compiler fingerprint against the extracted executable.
Older format-1 bundles remain installable with their original file checksums.
CI verifies the separate archive checksum before extracting the candidate.
Windows SDK verification runs the GUI lifecycle check in a hidden native
window. It closes and recreates the window with an active paint and clip
region, then checks that process GDI and USER object counts stay stable.

Linux and Intel macOS (run from the extracted bundle directory):

```bash
bash packaging/install-sdk.sh "$PWD" "$HOME/sotlas-sdk"
bash "$HOME/sotlas-sdk/scripts/verify_sdk.sh" "$HOME/sotlas-sdk-check" --rebuild
```

Windows (run from the extracted ZIP directory):

```powershell
& ./packaging/install-sdk.ps1 . "$HOME/sotlas-sdk"
& "$HOME/sotlas-sdk/scripts/verify_sdk.ps1" "$HOME/sotlas-sdk-check" -Rebuild
```

Choose fresh output directories. Verification copies source projects outside
the SDK, checks and compiles the calculator/configuration examples, executes
their success and error paths, runs the installed Sotlas tests, then reconstructs
Stage 2 and Stage 3 and requires byte identity. Reports are in the output
directory; the contract runner also writes JUnit. The calculator executable is
`calculator` (`calculator.exe` on Windows). Enter one expression per line;
EOF ends the session. `configuration` exits with code 42 on success.
On Windows, launch `ui-main.exe` from the verification output for the graphical
calculator. It uses Windows desktop drawing services and adaptive grid layout; see
`examples/graphical_calculator/README.md` and `docs/native_ui_snapshots.md`.
Keyboard editing, a visible caret and horizontal scrolling of long expressions
are described in `docs/native_ui_editing.md`.
The calculator adapts to the client area and preserves its model while too
small to show controls; see `docs/native_ui_layout.md` for its size/grid limits.

## Use in VS Code

For editor-based console projects, see `docs/native_vscode_sdk.md`. Install
the VSIX from the same prerelease or CI run, select this SDK, then create/check/build/run
through the native extension commands. The extension is a separate artifact.

## Build a kernel

The installed SDK can generate all seven documented kernel profiles. From its
directory, use `bash scripts/build_kernel.sh "$PWD/bin/sotlas-native" /fresh/output --foundation`,
or PowerShell `./scripts/build_kernel.ps1 ./bin/sotlas-native.exe C:/fresh/output -KernelProfile foundation`.
See `docs/native_kernel_sdk.md` for fresh-directory rules, QEMU boot commands,
rejection checks, artifacts and platform limits. QEMU is optional for image
generation and is not bundled. Linux/WSL is the boot certification environment.

## Compile a project

The SDK verifier creates a working `src` tree containing the runtime namespace
`sotlas/runtime` and both example projects. From that output directory:

```bash
/path/to/sotlas-sdk/bin/sotlas-native --check-build src src/calculator/main.sotlas
/path/to/sotlas-sdk/bin/sotlas-native --build calculator src src/calculator/main.sotlas
./calculator
```

On Intel macOS use `--build-mac`; on Windows use `--build-win`, the compiler
`bin/sotlas-native.exe` and an `.exe` output path. Paths containing spaces must
be quoted. The compiler resolves source modules below the supplied source root.
Runtime allocation and I/O use OS services; operating systems remain runtime
dependencies. See `docs/native_seed_workflow.md` for the bounded compiler
contract and `docs/native_json.md` for JSON limits.

## Scope and updates

This is a native SDK candidate with a bounded Windows GUI example, not complete
GUI/kernel/accelerator release certification. Automatic ARC, general generics, package-manager parity and full
frontend parity are separate work. Follow the support evidence attached to the
candidate. Install updates beside the old SDK in a fresh directory; select the
new compiler path after verification. Rollback means selecting the previous
directory. Sources, examples and tests remain in the bundle for inspection.

Development: [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev).
License: see `LICENSE`.
