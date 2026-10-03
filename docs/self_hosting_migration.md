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
   behavior reproducibly on supported hosts.
7. Remove Python from normal builds only after those gates pass on every
   supported platform. Keep Python as a recovery bootstrap until the new path
   has independent release coverage.
