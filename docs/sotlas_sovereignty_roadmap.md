# Sotlas Sovereignty Roadmap

**Status:** active implementation track  
**Started:** 2026-10-03 (America/Fortaleza)  
**Green baseline at track start:** `7162167dec6fd5fa0a216121b147335d222e43f1` / CI #1063

## Goal

The long-term goal is for the normal Sotlas development and execution path to no
longer require C or Python. Sotlas should be able to compile applications,
kernels, runtimes, libraries and eventually its own compiler through
Sotlas-owned frontend, IR, machine backend, object writer and linker stages.

This does **not** mean deleting the current C11 and Python Stage-0 paths before
parity. They remain bootstrap and differential-oracle implementations until the
native route proves the same or stronger contracts. No test may be weakened,
skipped or bypassed to accelerate this transition.

The intended end state is:

```text
Sotlas source
    -> Sotlas-written lexer/parser/sema
    -> Sotlas-owned canonical IR
    -> Sotlas-owned Target IR
    -> Sotlas-owned machine backend
    -> Sotlas-owned object writer
    -> Sotlas-owned linker / image builder
    -> apps / libraries / kernels / firmware
```

Python and C may remain optional development/reference tools after the normal
path stops depending on them, but they are not part of the sovereignty target.

## Migration rules

1. Stage 0 remains trusted only as a bootstrap and parity oracle while Stage 1
   is incomplete.
2. New native stages must consume explicit data contracts rather than Python
   dictionaries, C structs used only as glue, or product-specific shortcuts.
3. C11 remains a portability/reference backend until native output has execution
   parity for the same subset.
4. The machine backend must fail closed on unsupported instructions, ABIs,
   layouts and object features.
5. Kernel and application work share the same language/backend primitives; the
   compiler must not gain Baken- or application-specific bypasses.
6. A milestone is promoted only with positive, negative, end-to-end and CI
   evidence appropriate to its scope.
7. The final removal of Python/C from the normal installed path happens only
   after Stage 1 -> Stage 2 fixed-point evidence and clean-install native tests.

## Sovereignty milestones

| Milestone | Objective | State |
|---|---|---|
| **SV0** | Recover a green cross-platform baseline before sovereignty work | ✅ CERTIFIED (`7162167d`, CI #1063) |
| **SV1** | Define backend-neutral Target IR in Sotlas, independent of C/Python containers | 🟡 IN PROGRESS |
| **SV2** | Lower the Sotlas-written native frontend AST/sema subset into native Target IR | ⬜ PENDING |
| **SV3** | Feed native Target IR into the Sotlas-owned x86-64 backend for scalar functions | ⬜ PENDING |
| **SV4** | Native CFG, calls, aggregates, ownership/effects and ABI parity required by real apps | ⬜ PENDING |
| **SV5** | Sotlas-owned object emission and freestanding/native linking for supported targets | ⬜ PENDING |
| **SV6** | Compile a real application and the minimal kernel without the C11 backend | ⬜ PENDING |
| **SV7** | Build the Sotlas compiler Stage 1 from Sotlas sources using Stage 0 | ⬜ PENDING |
| **SV8** | Stage 1 builds Stage 2 with deterministic fixed-point/equivalence gates | ⬜ PENDING |
| **SV9** | Make the native compiler/backend the normal installed path; Python/C become optional legacy/reference tooling | ⬜ PENDING |

## SV1 contract

The first native Target IR representation lives under
`bootstrap/sotlas/native_compiler/backend/target_ir.sotlas`.

Its design deliberately avoids host-language maps and strings for SSA identity.
Values and blocks use stable numeric identifiers. Variable-sized instruction
inputs are represented as ranges into flat operand/phi/target tables. Functions
and blocks similarly reference flat instruction ranges. Source-facing names are
represented as source slices, which keeps the representation usable in hosted
and barecore environments without requiring a string runtime.

The initial opcode vocabulary mirrors the existing checked Target IR boundary:
stack allocation, load/store, integer constants, arithmetic, compare, phi,
calls, system operations, branches, returns and semantic-only ownership/state
operations. This is a representation contract, not yet a claim that the
Sotlas-written frontend lowers all of those operations.

### SV1 exit criteria

- [x] Target IR types and opcodes are represented in Sotlas source.
- [x] SSA values and block references do not depend on host-language objects.
- [x] variadic operands/phi inputs/targets have flat-table contracts.
- [x] semantic-only operations remain explicit instead of disappearing before backend selection.
- [x] the contract has no dependency on the legacy C emitter.
- [ ] native AST/sema lowering creates this IR.
- [ ] differential tests compare native Target IR with canonical Stage-0 Target IR.
- [ ] the Sotlas-owned machine backend consumes the native representation.

## Next implementation slice

`SV2a` will lower the smallest executable native-frontend subset into this
Target IR: integer scalar parameters, integer constants, `add/sub/mul`, direct
returns and one basic block. The result must be deterministic and fail closed on
any AST form outside that subset. Once differential parity is established, the
slice will be handed directly to the x86-64 Sotlas-owned backend rather than to
`emitter_c.sotlas`.
