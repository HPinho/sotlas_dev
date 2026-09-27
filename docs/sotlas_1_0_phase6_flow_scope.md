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

For serial plans whose stage functions are proven pure and use signed or
unsigned integer scalars or `bool`, the C11 backend emits a C-callable entrypoint named
`sotlas_flow_<module>_<flow>`. It calls stages in certified dependency order and
returns the final stage result. Native C and Sotlas callers execute this
entrypoint in tests. Sotlas callers declare the exact generated symbol with
`@extern(C)` and call it from an `@system` function. A dedicated Flow invocation
syntax is not available yet.

This initial native path rejects parallel plans, unsupported types, contracts,
system/foreign functions, method calls, and global access (including access
through directly called helpers). The source effect pass does not yet classify
global reads and writes, so the C11 gate checks that case syntactically and
conservatively. The host scheduler remains the only path with structured
failure/cancellation propagation.

## Verification

- Graph names, edges, cycles, deterministic parallel layers, worker limits,
  immutable dependency inputs, stable results, failure, and cancellation are
  covered by runtime tests.
- Source parsing, typing, effect reconciliation, SIR plan validation, tamper
  rejection, and flow-report serialization are covered.
- Tests lower source-derived SIR plans into actual call CFGs, execute them via
  the scheduler, and verify outputs and fail-closed behavior for parallel CFG,
  effectful functions, and ownership-bearing values.
- Native C11 entrypoint execution is tested with a C caller; negative tests
  check parallel plans, unsupported types, and global access before emission.
- The full suite includes dedicated source, SIR, CFG, runtime, and C11 boundary
  tests.

## Deferred beyond Sotlas 1.0

- Executable parallel SIR CFGs; declarative Flow and the host graph scheduler
  already support parallel execution.
- Ownership, cleanup, and non-scalar/lifetime-bearing values in executable CFG.
- A native scheduler, parallel execution, and dedicated source syntax for Flow
  invocation (the explicit C11 ABI declaration path is supported).
- Ownership, cleanup, stage errors/cancellation, and general effects in native
  Flow execution.
- Backpressure, retries, distributed scheduling, timeouts, and forced
  interruption of running synchronous functions.
- Arbitrary source CFG and general Flow unwind/defer integration.

These restrictions are validated fail-closed and define the supported 1.0
subset.
