# VS Code with the native Sotlas SDK

The extension supports a native hosted-project workflow alongside the existing
reference compiler commands. Use an x86-64 VS Code extension host and an SDK
matching Linux, Windows or Intel macOS. Download `sotlas-preview.vsix` and the
matching native SDK archive from the same [GitHub prerelease](https://github.com/HPinho/sotlas_dev/releases),
or use the `sotlas-vscode-preview` and SDK artifacts from the same successful
[main CI run](https://github.com/HPinho/sotlas_dev/actions/workflows/ci.yml).
Install the VSIX with **Extensions: Install from VSIX** and install the SDK using
its checked installer. No marketplace or organization publication is implied.

## Create and use a project

Run **Sotlas: Select Native SDK**, then **Sotlas: Create Native Console Project**.
Choose an empty directory; existing files are preserved. Open the resulting
project and `src/main.sotlas`. The commands are:

| Command | Native behavior |
|---|---|
| Check Active File | Save the active file and run `--check-build ROOT FILE` |
| Build Workspace | Save open project sources and build the configured entry with the host's native executable target |
| Run Native Project | Build first, then launch the executable in a process task with terminal I/O |
| Select Native SDK | Validate SDK format/host/compiler/runtime and configure the current project, or remember the choice for project creation |
| Create Native Console Project | Copy runtime sources and the host console adapter; write source and project settings into an empty directory |

The sample prints `Hello from Sotlas!` and exits successfully. Sources are below
`src`; the output is `build/app` (`build/app.exe` on Windows). Source paths,
including spaces, are passed as distinct arguments without shell expansion.
The generated adapter targets the current OS; selecting a different SDK does
not overwrite project sources or make that adapter cross-platform automatically.

Existing projects can select the native profile through workspace settings:

```json
{
  "sotlas.toolchain": "native",
  "sotlas.compilerPath": "/absolute/path/to/sdk/bin/sotlas-native",
  "sotlas.nativeSdkPath": "/absolute/path/to/sdk",
  "sotlas.nativeSourceRoot": "src",
  "sotlas.nativeEntry": "src/main.sotlas",
  "sotlas.nativeOutput": "build/app",
  "sotlas.nativeRunArguments": []
}
```

On Windows select `bin/sotlas-native.exe`; the selection command writes the
appropriate absolute path. Imports must resolve below the configured source
root, including the copied `sotlas/runtime` tree. These settings are not a new
package manager or an implementation of general separate module compilation.
Kernel images continue to use the [kernel SDK scripts](native_kernel_sdk.md).

## Diagnostics and execution

Compiler errors keep their file, line and reported cause. Native UTF-8 byte
columns are mapped to the UTF-16 positions expected by the editor, including
text containing supplementary scalars. A successful check clears old compiler
diagnostics; local structural hints remain separate and are not the parser or
type checker. An edited open buffer does not receive stale compiler markers.

A failed build does not run the previous executable. Output stays below the
workspace build directory; source-file output collisions are rejected. If open
sources change during a build, run requires another build. Compiler/program
execution requires workspace trust. Selecting an SDK does not change the
global reference-toolchain configuration or write project settings into the
SDK root. Creating a project does not overwrite a nonempty directory.

The reference profile remains the default for existing users. Its optional LSP
is separate from native commands. Formatting, Studio, REPL, WebAssembly and
native LSP are outside this command profile and are explicitly unavailable
there. This is not frontend parity or a claim of automatic live semantic checks.

## Validation and closure

Unit gates cover host SDK checks, source/output plans, path boundaries, project
creation/preservation and Unicode columns. The installed VSIX smoke uses a real
native SDK: select it in an empty workspace, create a project, check/build/run,
reject use after move, report its Unicode-positioned diagnostic, preserve the
old executable without running it, clear fixed diagnostics and reject an
occupied project directory. The reference diagnostic smoke remains required.

The runner is pinned to `@vscode/test-electron` 3.1.0 for the current macOS
application bundle layout. A platform-independent fixture checks its executable
resolution. Native smoke paths use VS Code URI normalization so Windows drive
letter case does not turn a successful SDK selection into a test failure.

The native SDK matrix installs the VSIX from the same revision and runs this
scenario on each advertised host. Local evidence and complete CI certification
are recorded in the [preview roadmap](preview_launch_roadmap.md). Native builds
require neither Python, a C compiler nor an external linker after the seed;
the editor and its extension runtime remain separate tooling dependencies.
