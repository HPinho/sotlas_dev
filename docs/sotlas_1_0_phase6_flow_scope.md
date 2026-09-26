# Sotlas 1.0 — Phase 6 Flow Scope

**Updated:** 2026-09-26
**Status:** COMPLETE within the bounded Sotlas 1.0 contract

## Contract

The canonical frontend parses and type-checks named Flow stages and explicit
dependencies. It rejects invalid references, cycles, unresolved stages,
signature mismatches, and effect/ownership shapes outside the declared subset.
The typed plan is reconciled with canonical SIR signatures, effect summaries,
and dependency provenance before execution.

The local graph scheduler executes independent stages concurrently, limits
workers, provides only direct dependency outputs through immutable maps, and
returns outputs in stable source order. Failure or cancellation prevents later
stages from starting and joins work already running. Cooperative cancellation
is observed between stages or by bindings that inspect the supplied token; the
runtime does not forcibly interrupt synchronous work.

For compiled SIR CFG execution, `lower_serial_flow_to_cfg` lowers strictly
serial plans with copy-safe scalar values into certified SIR `CallInst`s.
`execute_serial_flow_cfg` revalidates that CFG, function signatures, effects,
call provenance, and serial schedule before interpreting stage bodies and
dispatching them through the scheduler. End-to-end tests start from Sotlas Flow
source and verify stage outputs. Pure integer and boolean stage bodies are the
supported executable subset.

The C11 production backend explicitly rejects source Flow until it has an
ownership-aware lowering into its scheduler contract. This rejection is tested
and is part of the 1.0 backend boundary.

## Verification

- Graph names, edges, cycles, deterministic parallel layers, worker limits,
  immutable dependency inputs, stable results, failure, and cancellation are
  covered by runtime tests.
- Source parsing, typing, effect reconciliation, SIR plan validation, tamper
  rejection, and flow-report serialization are covered.
- Tests lower source-derived SIR plans into actual call CFGs, execute them via
  the scheduler, and verify outputs and fail-closed behavior for parallel CFG,
  effectful functions, and ownership-bearing values.
- C11's unsupported-Flow diagnostic is checked before code emission.
- The full suite includes dedicated source, SIR, CFG, runtime, and C11 boundary
  tests.

## Deferred beyond Sotlas 1.0

- Executable parallel SIR CFGs; declarative Flow and the host graph scheduler
  already support parallel execution.
- Ownership, cleanup, and non-scalar/lifetime-bearing values in executable CFG.
- Native C11 scheduler lowering for source Flow; the backend rejects it
  explicitly until that contract exists.
- Backpressure, retries, distributed scheduling, timeouts, and forced
  interruption of running synchronous functions.
- Arbitrary source CFG and general Flow unwind/defer integration.

These restrictions are validated fail-closed and define the supported 1.0
subset.
