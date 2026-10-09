# Native Linux compiler

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

## Native self-build

The self-build input concatenates these production sources in order:

1. `token`, `ast`, `lexer`, `parser`, `sema`
2. `backend/target_ir`, `backend/lower_scalar`, `backend/x86_64_scalar`
3. `native_driver/linux.sotlas`

Remove their top-level import declarations after concatenation: every dependency
is already included once. The current file driver explicitly rejects imports
instead of silently pretending to resolve them. This merged source is a build
input; it is not a second implementation of the compiler.

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

This closes a native self-build for the current compiler-source subset. Native
module/project loading, full language parity, installed distribution and
Windows/macOS native drivers remain open.

## Kernel interface

Reserved bodyless scalar declarations named `sotlas_linux_read`,
`sotlas_linux_write`, `sotlas_linux_open` and `sotlas_linux_close` lower to a
validated `SystemOp`. The existing C ABI syntax describes the scalar boundary;
these calls do not bind libc symbols. The backend emits Linux x86-64 syscalls
0, 1, 2 and 3 directly and preserves negative kernel error returns as `i64`.
Other declarations continue to use ordinary external-call linking. The Linux
process-entry ABI has a dedicated ELF note flag; it cannot be selected by
supplying arbitrary constant entry arguments or a freestanding target.
