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
it has been built. Building that executable still uses the Python compiler and
a native C toolchain. The existing fixed-point check compares Stage 1 and
Stage 2 compiler output; it does not prove that the Python bootstrap can be
removed.

## First parity slice

The self-hosted lexer in `bootstrap/sotlas/sotlas_lite/lexer.sotlas` now counts
columns through line and block comments. A native conformance test compiles the
Sotlas lexer, runs it, and compares token text, class, line, and column with the
Python lexer for a shared source sample. This keeps the current bootstrap
usable while the native frontend grows against observable behavior.

## Promotion gates

1. Expand shared lexer cases to cover the full supported token subset, malformed
   input, Unicode policy, and source spans.
2. Compare parser trees and diagnostics for a documented source subset.
3. Compare semantic acceptance and rejection, including ownership and target
   profile rules.
4. Replace the C-emitting path with a stable Sotlas IR and native object path.
5. Move filesystem, process, and platform services behind documented Sotlas
   interfaces and replace the C driver incrementally.
6. Build Stage 1 from Stage 0, then Stage 2 from Stage 1; compare artifacts and
   behavior reproducibly on supported hosts.
7. Remove Python from normal builds only after those gates pass on every
   supported platform. Keep Python as a recovery bootstrap until the new path
   has independent release coverage.
