# Native development from a Sotlas seed

The compiler implementation used here lives in
`bootstrap/sotlas/native_compiler/*.sotlas` and its backend modules. Platform
drivers in `bootstrap/sotlas/native_driver/` perform file I/O directly through
the supported operating-system boundary. `@extern(C)` on a reserved Win32
declaration describes its ABI; it does not invoke a C compiler.

## Rebuild and exercise the compiler

Windows x64:

```powershell
.\scripts\build_native.ps1 -Seed C:\seeds\sotlas-native.exe -OutputDirectory .\build\native-check
```

Linux x86-64 or Intel macOS:

```bash
bash scripts/build_native.sh /path/to/sotlas-native ./build/native-check
```

Supply a trusted, compatible native file-driver seed for the host. Existing
output directories are refused. The scripts stage unchanged source files in
their namespace layout; the native compiler discovers their imports. This is
not typed separate-module compilation: the driver still combines source input
internally.

The workflow:

1. Uses the seed to compile Stage 2 from the original compiler modules.
2. Uses Stage 2 to compile Stage 3 from the same modules.
3. Requires byte identity between these two generations.
4. Runs the rebuilt compiler's native self-test.
5. Checks and builds the config parser with the Sotlas text runtime.
6. Executes the parser, requiring exit status 42.
7. Requires ownership rejection from both check and compilation, and verifies
   that a rejected compilation preserves the previous executable.

All compiler/application invocations receive a `PATH` without host tools.
The scripts use PowerShell/Bash and ordinary file utilities for staging and
comparison. They have no Python, pip, C compiler or external-linker invocation,
including fallback branches. No compiler behavior is implemented in these
scripts.

## What changed

The previous `build_native.bat` and `build_native.sh` searched for a C compiler
even when a compiler executable existed. They also invoked Python to produce a
hosted bootstrap and used older `selfhost`/C-output commands. Those mandatory
branches have been removed from these entry points.

This does not remove the Python reference compiler, its test infrastructure,
packager or the initial hosted producer. They still have distinct users. Seed
production and distribution remain separate work. The workflow does not prove
whole-language parity, remove operating-system dependencies, or certify foreign
ABI coverage beyond the native profile.

## Continue using the result

On Windows, `build/native-check/sotlas-native.exe` checks source with `--check`
and compiles `input.sotlas output.exe`. On Unix the result is
`build/native-check/sotlas-native`; use `input.sotlas output` and execute the
result. Application entry is `pub fn main_entry() -> u32`.

The parser example reads embedded test records, not a user-supplied file. It
demonstrates runtime imports, borrowed text, records, loops, checked parsing and
native execution. File/argument handling is provided by the platform drivers,
not by that example.

## Local validation (2026-10-15)

The complete PowerShell workflow passed on Windows x64. The complete shell
workflow passed on Linux x86-64 through WSL, using a Linux seed cross-built by
the native Windows compiler. Both required generation identity, self-test,
example execution and negative ownership checks. Existing-directory rejection
and preservation also passed on Windows. Bash and PowerShell syntax checks
passed. Intel macOS execution and the remote CI were not run for this change.

The first current Windows seed was prepared with an existing hosted producer
executable; that preparation is not claimed as a fully independent initial
bootstrap. The successful rebuild workflows themselves used only native seeds.
