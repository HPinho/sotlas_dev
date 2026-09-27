# High-Level Language and Self-Hosting Roadmap

**Status:** design roadmap; the milestones below are not current support claims.

Sotlas can grow toward expressive application code, explicit systems control,
portable compute, and a compiler written in Sotlas. Those goals depend on a
shared typed representation and reproducible tests; adding surface syntax before
those contracts exist would widen the gap between what parses and what runs.

## Current implementation boundary

The installed production frontend is the Python package under `compiler/`. Its
canonical source pipeline checks Sotlas and emits the supported C11 subset. The
checked SIR and direct LLVM backend cover smaller, separately gated subsets.
`sotlas bootstrap` builds and checks the existing Sotlas-lite compiler project,
but it does not rebuild the production compiler from its own source. Python is
therefore still required by the production compiler and package tooling.

LLVM currently supplies instruction selection, register allocation, ABI
lowering, and object emission on the direct LLVM route. Sotlas does not yet have
its own machine backend or register allocator. Emitting host assembly through
LLVM is not the same as Sotlas owning an assembly language or code generator.

Flow has a canonical typed plan, SIR plan, a host reference scheduler, and an
interpreter for pure scalar stages. The checked subset now forwards boolean
results between stages. Source Flow still fails closed at native C11 lowering;
there is no native Flow scheduler, physical device provider, GPU/NPU dispatch,
or hardware synchronization contract.

## High-level language milestones

1. **Make common programs pleasant to write.** Improve modules and imports,
   generic data structures, exhaustive enum handling, structured errors, tests,
   and package workflows. Each addition needs a typed-AST contract and examples
   that compile and run through an installed toolchain.
2. **Keep low-level control explicit.** Preserve ownership, effects, unsafe
   boundaries, layout, and FFI facts through the typed AST and SIR. High-level
   libraries should use those same rules instead of bypassing them.
3. **Make Flow useful on CPU first.** Define typed inputs and outputs, dependency
   rules, effects, failure propagation, cancellation, and ownership of values
   between stages. Lower a serial scalar subset to native code and execute it
   against the reference interpreter before widening parallel execution.
4. **Add portable devices behind a provider boundary.** Specify buffers,
   dimensions, formats, transfers, synchronization, failure, cancellation, and
   fallback before selecting a hardware API. A backend must report unavailable
   devices clearly. The first accelerator should be a narrow end-to-end vertical
   slice with documented hardware prerequisites and CPU-vs-device comparisons.
5. **Grow the standard library with the language.** Prioritize strings, slices,
   collections, files, errors, and I/O. Every public API should say who owns and
   frees memory, how mutation works, and how allocation or I/O failure appears.

## Self-hosting milestones

1. **Freeze a bootstrap boundary.** Keep the current production compiler as
   Stage 0 while writing Sotlas modules for the lexer, parser, AST, type checker,
   and diagnostics. Treat the existing Sotlas-lite project as an experimental
   bootstrap, not as the replacement compiler.
2. **Reach useful language coverage.** The Sotlas compiler must parse and compile
   its own real source modules, including imports, errors, collections, and the
   ownership/effect forms used by the compiler itself.
3. **Build Stage 1 with Stage 0.** Run the new native compiler over the same
   compiler sources and test programs. Compare diagnostics, typed facts, emitted
   SIR, and executable behavior on an agreed corpus.
4. **Prove a fixed point.** Stage 1 must build Stage 2, and Stage 2 must produce
   byte-identical deterministic artifacts or pass a documented semantic
   equivalence check. Repeat this in clean Linux, Windows, and macOS jobs.
5. **Remove Python from the compiler path only after parity.** Make the native
   compiler the normal installed compiler only after clean-install tests use it
   without Python. Python may remain optional for development scripts until
   separate native replacements exist.

## Sotlas-owned machine code milestones

1. Stabilize a backend-neutral machine IR with verified types, ownership,
   effects, control flow, and source locations.
2. Specify target data layout and calling conventions, then implement one
   architecture/ABI pair with instruction selection and register allocation.
3. Add relocations, object writing, debug information, and unwind metadata with
   native caller tests before adding another target.
4. Compare generated programs against LLVM and the C11 route for the shared
   subset. Keep LLVM as the practical production backend until the Sotlas-owned
   backend passes those differential and toolchain gates.

“Modern assembly” can mean both a readable low-level source language and a
Sotlas-owned machine backend. These are distinct projects. A useful first design
should decide whether the immediate need is safer inline assembly, a portable
low-level IR, or direct target-specific assembly; it should not claim a machine
backend while LLVM performs that work.

## Promotion gates

A milestone moves from design to preview only when its source contract,
positive and negative tests, backend behavior, native execution, diagnostics,
and support-matrix entry are all present. Hardware-specific claims additionally
need an available physical device in CI or a clearly labeled manual hardware
gate. The phase evidence matrix is maintained in
[`phase_gate_matrix.md`](phase_gate_matrix.md).
