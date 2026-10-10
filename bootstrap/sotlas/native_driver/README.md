# Native compiler drivers

`linux.sotlas` is a Linux x86-64 compiler driver written in Sotlas. It reads
source files, runs the production frontend and Target IR lowerer, writes ELF
objects and links executable images. File operations use kernel syscalls;
the generated compiler has no ELF interpreter or dynamic C runtime.

## Initial seed

Build the current hosted Stage 1 producer once, then use its native object
writer and linker to create the seed:

```sh
./build/sotlas_stage1 --compile-obj \
  bootstrap/sotlas/native_driver/linux.sotlas build/linux_driver.o
./build/sotlas_stage1 --link-exe \
  build/linux_driver.o build/sotlas-native sotlas_linux_main
```

The initial producer still uses the hosted bootstrap. The resulting seed's
compilation and self-build paths do not invoke Python, Clang, a C emitter or
an external linker.

## Compile files

```sh
./build/sotlas-native input.sotlas output
./build/sotlas-native input.sotlas output.o --object
./output
```

Executable input uses `main_entry() -> u32`. `--compiler` selects the checked
`sotlas_linux_main(argc: u64, argv: *const *const u8) -> u32` process ABI, which
receives the kernel's actual argument vector. Unknown options are rejected.

Input must be smaller than 1 MiB. Source storage reserves another MiB for
synthetic symbols. Compiler tables are bounded and exhausted buffers fail
closed. Output is created only after frontend, lowering and linking succeed;
an I/O failure during writing can leave a partial file. Newly created outputs
use mode 0755; existing files retain their permissions.

String literals share a pool of 65,536 decoded bytes, including NUL terminators,
and at most 512 symbols per compilation. Exhausting either limit rejects
lowering before output is opened. Literals are never truncated to fit the pool,
and every accepted string address has a data-symbol relocation.

## Experimental Windows executable output

```sh
./build/sotlas-native input.sotlas output.exe --windows
./build/sotlas-native --build-win output.exe /path/to/source-root /path/to/entry.sotlas
```

The native Linux compiler can cross-compile PE32+ executables for Windows x64.
The writer and linker are Sotlas source. They resolve the existing internal
object format, retain the internal SysV calling convention and emit a Win64
startup bridge importing `KERNEL32.dll!ExitProcess`. No C compiler or external
linker is used after the Linux seed is available. The entry takes no parameters;
its low 32 result bits become the process exit code.

Calls, strings, pointer arrays and zero-initialized globals are covered by
execution tests. Unrecognized foreign symbols and Linux system operations are
rejected. Object platform flags record actual Linux SystemOps; matching bytes
inside integer immediates are accepted. Input must carry the Sotlas entry ABI
note. The image uses a fixed base and currently has writable executable
sections; ASLR, separate memory protections, unwind tables, general Win64 FFI
and macOS output remain open.

## Native Windows compiler

`windows.sotlas` runs the same Lexer, Parser, Sema, Target IR and x86 backend as
the Linux driver. Its file adapters call Win32 APIs directly. Given a seed,
compilation and native Stage 2/3 generation require no Python or C tooling.
The Linux bundle includes its original source and can build the seed:

```sh
./bin/sotlas-native --build-win sotlas-native.exe ./src ./src/sotlas/compiler/windows_driver.sotlas
```

On Windows, executable output defaults to PE32+:

```powershell
.\sotlas-native.exe --check .\main.sotlas
.\sotlas-native.exe .\main.sotlas .\application.exe
.\sotlas-native.exe --build-cc .\stage2.exe .\src .\src\sotlas\compiler\windows_driver.sotlas
.\stage2.exe --build-cc .\stage3.exe .\src .\src\sotlas\compiler\windows_driver.sotlas
```

The driver supports single files, the bounded explicit/resolved project modes,
source discovery and checks. `--object` writes the internal ELF object format.
The argv adapter handles Windows spaces, quotes and backslashes, with at most
67 arguments and 4,095 bytes per argument. Paths use the Windows ANSI code page;
full Unicode paths and environment argument expansion are outside this profile.
The same one-megabyte source and bounded compiler tables apply.

### Windows platform imports

The native PE backend resolves these reserved `@extern(C)` names to KERNEL32
through a SysV-to-Win64 bridge. Parameter count and machine types are checked
before object emission. Pointee validity and buffer bounds remain the caller's
responsibility at this raw API boundary.

| Sotlas name | Win32 API | Machine parameters | Result |
|---|---|---|---|
| `sotlas_windows_exit` | ExitProcess | u32 | void |
| `sotlas_windows_get_command_line` | GetCommandLineA | none | pointer |
| `sotlas_windows_create_file` | CreateFileA | pointer, u32, u32, pointer, u32, u32, u64 | u64 |
| `sotlas_windows_read_file` | ReadFile | u64, pointer, u32, pointer, pointer | u32 |
| `sotlas_windows_write_file` | WriteFile | u64, pointer, u32, pointer, pointer | u32 |
| `sotlas_windows_close_handle` | CloseHandle | u64 | u32 |
| `sotlas_windows_get_std_handle` | GetStdHandle | u32 | u64 |
| `sotlas_windows_get_last_error` | GetLastError | none | u32 |

The bridge follows the [Microsoft x64 calling convention](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention),
including register mapping, shadow space and stack arguments. The I/O gates
exercise [WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)
and seven-argument [CreateFileA](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)
with actual Windows file round trips.

## Check source without writing artifacts

```sh
./build/sotlas-native --check input.sotlas
./build/sotlas-native --check-build /path/to/source-root /path/to/entry.sotlas
```

Both commands use the same lexer, parser, semantic checker, Target IR lowerer
and native object validator as compilation. The object is validated in memory;
no output file is opened. A successful check is silent and returns zero. Errors
use the existing stage-specific exit codes. `--check-build` discovers glob
imports and validates their dependency graph using the same rules as `--build`.

Checking targets the declared native object profile, so a library without an
executable entry can pass. It does not prove executable linking, resolve foreign
symbols, or claim parity with every feature of the canonical hosted frontend.
Use executable compilation to validate the entry and linker contract.

## Explicit multi-file builds (SV8.21a)

The Linux native driver also accepts a bounded list of source files. The
compiler joins them in the supplied order with newline separators, runs the
same lexer/parser/sema/lowerer, and emits one object or linked ELF executable:

```sh
./build/sotlas-native --project build/app.elf math.sotlas app.sotlas
./build/sotlas-native --project-object build/app.o math.sotlas app.sotlas
./build/app.elf
```

Pass dependencies before users and keep symbol names unambiguous. This initial
flat-source profile **does not resolve imports**: source files containing
`import` still fail with exit code 12, even if a target appears in the
explicit file list. Only syntactically valid, import-free modules are joined;
the driver never silently drops or rewrites dependency declarations. A
`--project-compiler` variant selects the dedicated compiler entry ABI, but
does not automatically merge or resolve the compiler's own imports. This is
not yet native package/module loading or release bootstrap closure.

At least two input files and at most 64 are accepted. The combined source
(including separators) remains under the original 1 MiB limit; each file must
be nonempty. The second MiB remains reserved for synthetic symbols.
Missing files, invalid options, oversized/invalid sources and unresolved
imports fail before opening the output path. Successful object output is
byte-for-byte equal to compiling the exact newline-joined input with the
existing hosted producer. Native Linux tests execute the linked project with
no external tools on PATH and verify that failure preserves an old output
artifact. The regular one-file invocation and the Stage 2/Stage 3 generation
path are unchanged.

The implementation keeps single-file reading, explicit multi-file reading, and
the common native frontend/object/link pipeline in separate Sotlas functions.
This isolates the ELF link call from nested project input loops and preserves
the identical compiler core and fail-before-output contract for both modes.
The Linux regression suite exercises all three project modes' argument bounds
and empty-source rejection without modifying an existing artifact.

## Bounded native module resolution (SV8.21b1)

The opt-in Linux-only flags `--project-resolve`, `--project-resolve-object` and
`--project-resolve-compiler` accept the same output and 2–64 explicitly
supplied source files as the earlier project modes:

```sh
./build/sotlas-native --project-resolve build/app.elf app.sotlas math.sotlas
./build/sotlas-native --project-resolve-object build/app.o app.sotlas math.sotlas
./build/sotlas-native --project-resolve-compiler build/stage2 \
  bootstrap/sotlas/native_compiler/{token,ast,lexer,parser,sema}.sotlas \
  bootstrap/sotlas/native_compiler/backend/{target_ir,lower_scalar,x86_64_scalar}.sotlas \
  bootstrap/sotlas/native_driver/linux.sotlas
```

The opt-in resolved modes use a separate exact ASCII-byte decoder without
introducing additional CLI string literal relocations into the native image.
Legacy flat-project modes dispatch first through the previously certified
entry path; unknown calls with five or more argv entries reach the isolated
resolver helper, and invalid suffixes fail without opening the output file.

All inputs must begin with exactly one explicit `module path;` declaration.
Imports are currently restricted to contiguous `import path::*;` declarations.
The native lexer reads each original source and builds a bounded module-name
index and dependency graph. Missing module names, duplicate modules/imports,
self imports, cyclic graphs, unsupported aliases and nested imports fail with
exit code 12 before any output file is opened. A stable topological sort chooses
the earliest ready source from the caller's list and emits the ordered source
stream with *only verified import tokens* removed. No Python, C emitter, host
linker, host module resolver or build-time concatenation is invoked by either
native compiler generation.

Imports expose current flat compiler symbols: **this does not yet implement
qualified namespace isolation or visibility rules**. The original `--project`
commands retain their exact behavior and continue to reject every import.
The 1 MiB combined-input bound and synthetic-symbol reservation remain.
General native package resolution and separate per-module linking remain
outside this profile.

The resolver uses one-element static scratch slots for parsed token spans
and the emitted source length. This is an intentionally non-reentrant
single-compilation-per-process interface: the current native lowerer cannot
yet lower helper calls passing several independent address-taken local scalar
out-parameters. The import graph and input limits remain unchanged.

The Linux gates validate out-of-order imported project execution, native/hosted
object identity for an explicitly normalized reference source, error paths
preserving existing output, and Stage 1→2→3 fixed point from the nine original
production module files. This profile is certified by
[CI #1167](https://github.com/HPinho/sotlas_dev/actions/runs/38037420665) for
`3782ff133b4c9e952f7bcb8fa8f188feb6c39b29`. The new check commands require their
own CI certification.

## Discover imported files

```sh
./build/sotlas-native --build output /path/to/source-root /path/to/entry.sotlas
./build/sotlas-native --build-obj output.o /path/to/source-root /path/to/entry.sotlas
./build/sotlas-native --build-cc stage2 /path/to/source-root /path/to/compiler-entry.sotlas
```

Glob imports are discovered by the production lexer. `foo::bar` resolves to
`SOURCE_ROOT/foo/bar.sotlas`; the existing graph verifier rejects duplicate
modules, missing imports, cycles, aliases and malformed paths before output is
opened. Comments and strings are never interpreted as imports. Discovery uses
a queue of at most 64 paths, each shorter than 4,096 bytes, and the existing
one-megabyte combined source limit. Module visibility and import aliases are
still outside the native profile.

## Install a native seed bundle

```sh
python packaging/native_linux.py --output dist/sotlas-native-linux-x64
tar -xzf dist/sotlas-native-linux-x64.tar.gz
bash sotlas-native-linux-x64/install-native.sh sotlas-native-linux-x64 /path/to/install
```

The packager uses build-time Python and the initial producer. The extracted
bundle contains a static native compiler, its eight core Sotlas modules and
the Linux and Windows driver sources in
namespace layout under `src/`, documentation and SHA-256 checksums. Installation
uses Bash and ordinary system utilities; Python, Clang and a C compiler are not
required. The installer verifies the payload before writing and refuses an
existing destination. The archive has deterministic order, timestamps and
permissions. CI builds, installs and uploads this Linux bundle independently of
the existing Python distribution.

The installed compiler can discover and rebuild its own source tree:

```sh
INSTALL/bin/sotlas-native --build-cc stage2 INSTALL/src INSTALL/src/sotlas/compiler/linux_driver.sotlas
./stage2 --build-cc stage3 INSTALL/src INSTALL/src/sotlas/compiler/linux_driver.sotlas
cmp stage2 stage3
```

## Explicit native self-build

The self-build input concatenates these production sources in order:

1. `token`, `ast`, `lexer`, `parser`, `sema`
2. `backend/target_ir`, `backend/lower_scalar`, `backend/x86_64_scalar`
3. `native_driver/linux.sotlas`

Remove top-level import declarations after concatenation, since every dependency
is already included once. Single-file compilation rejects imports. Use `--build`
to discover dependencies directly from the original module files. The merged
source remains an alternative input for the same compiler implementation.

```sh
./build/sotlas-native compiler_merged.sotlas build/stage2 --compiler
./build/stage2 compiler_merged.sotlas build/stage3 --compiler
cmp build/stage2 build/stage3
```

`tests/test_sotlas_native_linux_driver.py` creates this merged input,
compares native and hosted-producer objects, requires Stage 2 and Stage 3 to be
byte-for-byte identical, and executes a program compiled by Stage 3. These
execution tests run with `PATH` pointing to an empty directory. Windows and
macOS compile and link the seed as a cross-target ELF artifact; Linux x86-64
executes the generation chain. WSL can execute the same local artifacts.

This closes a native self-build for the current compiler-source subset. Bounded
glob-module discovery and a Linux seed bundle are available. Broader module
visibility/package semantics, full language parity, general Windows ABI coverage
and the macOS native driver remain open.

## Kernel interface

Reserved bodyless scalar declarations named `sotlas_linux_read`,
`sotlas_linux_write`, `sotlas_linux_open` and `sotlas_linux_close` lower to a
validated `SystemOp`. The existing C ABI syntax describes the scalar boundary;
these calls do not bind libc symbols. The backend emits Linux x86-64 syscalls
0, 1, 2 and 3 directly and preserves negative kernel error returns as `i64`.
Other declarations continue to use ordinary external-call linking. The Linux
process-entry ABI has a dedicated ELF note flag; it cannot be selected by
supplying arbitrary constant entry arguments or a freestanding target.

## Experimental Intel macOS output

Native Linux and Windows drivers can discover a project and emit a static
Intel Mach-O image without a host compiler or external linker:

```sh
sotlas-native --build-mac app.macho SOURCE_ROOT SOURCE_ROOT/probe/main.sotlas
```

The supported entry contract is `pub fn main_entry() -> u32`. The writer
requires a recorded zero-argument ABI, resolves its internal ELF object, maps
strings and zero-filled BSS, and emits a kernel startup through `LC_UNIXTHREAD`.
The startup exits with the entry's low 32-bit scalar return value. Legacy object
ABI notes record arity rather than the full return-type schema; they do not
make arbitrary entry signatures interchangeable.

Reserved bodyless adapters lower directly to Darwin kernel operations:

```sotlas
@extern(C) fn sotlas_darwin_open(path: *const u8, flags: u64, mode: u64) -> i64;
@extern(C) fn sotlas_darwin_read(fd: u64, data: *mut u8, count: u64) -> i64;
@extern(C) fn sotlas_darwin_write(fd: u64, data: *const u8, count: u64) -> i64;
@extern(C) fn sotlas_darwin_close(fd: u64) -> i64;
```

Errors are normalized to negative `i64` errno values. Linux and Darwin use
different file flags; adapters do not translate flags across platforms.
The final writer rejects Linux operations, Windows imports, unresolved foreign
symbols and unsupported entry arity before opening the output file.

This profile is experimental: cross-build parity is tested locally on Linux
and Windows, and Intel macOS execution is a CI gate. Apple Silicon, Rosetta,
code signing, ASLR, dynamic libraries, separate payload permissions and a
native macOS compiler file driver remain outside its contract. The initial
payload segment is RWX; startup is RX. The hosted distribution remains
necessary for canonical features outside the native compiler-source subset.
