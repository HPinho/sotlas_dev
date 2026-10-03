# Self-hosting migration

Sotlas is not ready to remove Python from its toolchain. The current native
compiler is written in Sotlas and its executable has no Python runtime
dependency, but Python still builds and coordinates the bootstrap. The native
compiler also emits C and relies on a C toolchain and a C driver for operating
system services.

## Current boundary

| Component | Current implementation | Migration status |
|---|---|---|
| Production frontend and CLI | Python | Stage 0 |
| Bootstrap compiler sources | Sotlas lexer, parser, semantic checks, and C emitter | Stage 1 preview |
| Bootstrap build orchestration | Python | Stage 0 dependency |
| Native executable and OS/file services | Sotlas output plus a C driver | Transitional |
| Native code generation | C11 emitted by Sotlas | Transitional |

The Stage 1 compiler can compile Sotlas programs without starting Python once
it has been built. The `selfhost` command now builds Stage 2, asks the Stage 2
executable to emit the compiler again, and requires the Stage 1 and Stage 2 C
artifacts to be byte-identical before reporting success. A native integration
test exercises that command and checks the artifacts directly.

Building Stage 1 still uses the Python compiler, and Python still coordinates
the bootstrap. This fixed point validates only the checked-in `sotlas_lite`
subset; it does not establish full frontend parity or prove that Python can be
removed from production builds.

## Sotlas-owned assembly preview

The canonical CLI exposes the experimental x86-64 SysV machine backend:

```sh
sotlas compile source.sotlas --emit-asm --backend sotlas-x86_64 --target x86_64-unknown-linux-gnu
```

This path lowers checked Sotlas source through Target IR and emits
Intel-syntax assembly without invoking LLVM or compiling intermediate C. It
currently supports a gated subset, including signed and unsigned scalar
comparisons. Signed arithmetic remains rejected until Sotlas defines its
overflow modes.

For that same subset, `--emit-obj --backend sotlas-x86_64` sends the generated
assembly directly to the configured assembler driver (`--cc`) and writes a
native object without generating or compiling C. This removes C from this
artifact path, but still depends on an external assembler and the compiler
frontend is still Python. Kernel-only privileged operations are not yet
lowered by this machine backend, except the initial interrupt-control slice
described below.

The machine backend lowers source calls to `__cli()` and `__sti()` directly to
the x86 instructions when the containing function declares
`@system(cpu.interrupts)`. It also lowers `__outb(port, value)` and
`__inb(port)` to `out dx, al` and `in al, dx` when the containing function
declares `@system(io.port)`. These initial port operations accept values passed
through scalar function parameters; computed arguments and the 16-bit and
32-bit port variants remain unsupported by this backend. The authority fact,
operand types, result type, and capability are carried into Target IR and
checked again before instruction selection. Tests inspect the assembly and do
not execute privileged instructions in the host process. MSR access and
interrupt-state queries still use the C11 reference lowering and are not yet
supported by the Sotlas-owned machine backend.

This backend is implemented in the Python compiler today, so it is not yet part
of the Sotlas-written Stage 1/2 compiler. Linking, debug information, and
runtime services remain separate work. The command is an early step toward a
Sotlas-owned code generation path, not a claim that the compiler is self-hosted
or C-free.

## First parity slice

The Stage 1 lexer in `bootstrap/sotlas/sotlas_lite/lexer.sotlas` counts columns
through line and block comments. Its native conformance test compares token
text, class, line, and column with the Python lexer. The native compiler lexer
also reports unterminated block comments, strings, and character literals,
rejects unsupported bytes, preserves source spans, and classifies the
single-character bitwise operators.

The native compiler integration test now differentially checks a documented
subset against the canonical Python frontend. It compares acceptance for a
small parser and semantic corpus, checks exact locations for parser and lexer
errors, and compares parsed function names, parameter counts, and emitted C
function arities for valid inputs. This corpus is evidence for that subset; it
does not establish full parser or semantic parity.

Recent regression hardening keeps boolean, floating-point, and character
literal tokens valid in primary expressions. Missing semicolons in local
declarations and assignments now retain the unexpected token location. The
differential corpus covers those accepted literal contexts, malformed
character literals, and both missing-semicolon paths.

## Promotion gates

1. **Initial subset validated:** compare Stage 1 and Python lexer behavior for
   shared tokens and source positions; native malformed comments, strings,
   characters, and unsupported bytes fail closed. Full token and Unicode
   policy parity remains open.
2. **Initial subset validated:** compare parser acceptance, function names,
   parameter counts, C function arities, and exact syntax error locations.
   Full tree-shape and diagnostic-message parity remain open.
3. **Initial subset validated:** compare semantic acceptance and rejection for
   duplicate declarations, unknown names, and return type mismatches.
   Ownership and target-profile parity remain open.
4. Replace the C-emitting path with a stable Sotlas IR and native object path.
5. Move filesystem, process, and platform services behind documented Sotlas
   interfaces and replace the C driver incrementally.
6. Build Stage 1 from Stage 0, then Stage 2 from Stage 1; compare artifacts and
   behavior reproducibly on supported hosts. The `selfhost` command enforces
   byte-identical Stage 1/Stage 2 C output on the host running the command;
   cross-platform release coverage is still required.
7. Remove Python from normal builds only after those gates pass on every
   supported platform. Keep Python as a recovery bootstrap until the new path
   has independent release coverage.
