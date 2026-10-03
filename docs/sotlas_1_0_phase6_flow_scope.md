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

For compiled SIR CFG execution, `lower_flow_to_cfg` lowers copy-safe scalar
plans into topologically ordered SIR `CallInst`s plus a certificate that keeps
the canonical dependency layers. `execute_flow_cfg` revalidates the CFG,
function signatures, effects, call provenance, and stage schedule before
interpreting stage bodies. Independent stages run concurrently through the
existing scheduler; dependent stages receive only committed producer outputs.
End-to-end tests start from Sotlas Flow source and verify stage outputs and
overlap of independent stages. The compatibility APIs
`lower_serial_flow_to_cfg` and `execute_serial_flow_cfg` continue to enforce a
strict serial schedule. The SIR interpreter supports straight-line
integer and boolean bodies plus scalar branches, comparisons, `phi` joins, and
loop backedges. It validates the CFG through Target IR before execution and
rejects unreachable blocks, unsupported instructions, and unsupported types.
The interpreter checks for cooperative cancellation at every block entry and
between instructions. A one-million block-visit limit bounds non-terminating
cycles. Its signed
arithmetic rejects values outside the declared type range;
the language-wide signed overflow contract remains open.

For plans whose stage functions are proven pure and use signed or unsigned
integer scalars, `f32`, `f64`, `bool`, or plain `@repr(C)` records whose fields
recursively use those scalars or explicitly represented nested records, the C11 backend emits a
C-callable entrypoint named
`sotlas_flow_<module>_<flow>`. It calls stages in certified dependency order and
returns the final stage result. A companion
`sotlas_flow_<module>_<flow>_outputs` entrypoint writes every stage result to
caller-provided typed output pointers and returns 0 if any pointer is null. Both
entrypoints execute in native tests, including a graph with independent
stages. Sotlas callers declare the exact generated symbol with
`@extern(C)` and call it from an `@system` function. A dedicated Flow invocation
syntax is not available yet.

The backend also emits
`sotlas_flow_<module>_<flow>_cancelable`. It accepts an optional host callback,
context pointer, optional cancelled-stage output, and the same stage-output
pointers. It returns `0` on success, `1` for a null output pointer, and `2` when
the callback requests cancellation. The callback is polled immediately before
each stage in certified topological order; the reported stage index is
zero-based. Stage outputs are copied to caller memory only after every stage
completes, so cancellation leaves those outputs unchanged. A native C caller
test covers cancellation between stages and the success path.

Record payloads, including explicitly represented nested records, are passed
and returned by value. Records with pointers,
arrays, bit-fields, packed/aligned layouts, register unions, ownership domains,
or nested records without an explicit C representation fail closed. This
currently integrates value types and dependencies, but not owner transfer or
cleanup across Flow stages.

An additional `_dispatch` ABI lets a C host provide one executor callback for
the checked stage schedule. Each callback receives the zero-based stage index,
the stable stage name, the canonical result type, ordered dependency type
names, dependency values as read-only pointers, the input count, and a pointer
to the stage output value. Callback status `0` means success; any nonzero
value is reported as wrapper status `3`, with the original callback value written to
`stage_status` and the stage index written to `stopped_stage`. Wrapper status
`1` means an output pointer is null, `2` means cancellation, and `4` means no
executor was supplied. As with `_cancelable`, caller outputs are committed only
after every stage succeeds. The callback is responsible for implementing the
stage associated with each checked index; the compiler does not prove callback
equivalence to the Sotlas function body. This host/provider ABI accepts the
validated scalar and plain-record representations above; it is not a built-in
GPU/NPU backend.

This initial native path serializes accepted DAGs in deterministic dependency
order, including plans with independent stages. It rejects unsupported types,
contracts, system/foreign functions, method calls, and global access (including
access through directly called helpers). The source effect pass does not yet
classify global reads and writes, so the C11 gate checks that case syntactically
and conservatively. The host scheduler remains the only path that runs the
checked source stage bodies with structured stage-failure and cooperative
cancellation propagation. Direct native entrypoints are restricted to
proven-pure scalar or plain-record stages; their cancellation hook cannot
interrupt a running stage. `_dispatch` delegates stage bodies to a caller-supplied executor,
which is not verified against the source implementation. Native entrypoints do
not add parallel scheduling or asynchronous execution.

## Verification

- Graph names, edges, cycles, deterministic parallel layers, worker limits,
  immutable dependency inputs, stable results, failure, and cancellation are
  covered by runtime tests.
- Source parsing, typing, effect reconciliation, SIR plan validation, tamper
  rejection, and flow-report serialization are covered.
- Tests lower source-derived SIR plans into actual call CFGs, execute them via
  the scheduler, and verify outputs, real overlap between independent stages,
  and fail-closed behavior for effectful functions and resource-bearing
  ownership values. A C11 native test executes a linear chain of `sole
  @repr(C)` records, including nested trivial owners, rejects records with a
  destructor, and
  confirms cancellation before publication leaves caller outputs unchanged.
  Source-derived stage tests
  verify branch selection and scalar `phi` joins; a loop-carried `phi` test
  executes through the scheduler. Cancellation interrupts an executing loop
  stage at a block boundary, and a non-terminating CFG hits its visit cap.
- Native C11 entrypoint execution is tested with C and Sotlas callers; positive
  tests include independent stages in a DAG. Negative tests check unsupported
  types and global access before emission. The executable scalar SIR CFG
  accepts parallel layers in the host scheduler; native C11 entrypoints still
  use serial deterministic dependency order. C integration tests verify
  `_cancelable` and `_dispatch` success,
  cancellation, stage-failure status propagation, stage indices, and unchanged
  caller outputs on non-success paths.
- The full suite includes dedicated source, SIR, CFG, runtime, and C11 boundary
  tests.

## Deferred beyond Sotlas 1.0

- Native C11 parallel scheduling and dedicated source syntax for Flow invocation
  (the explicit ABI declaration path is supported).
- Ownership transfer, cleanup, and lifetime-bearing values in executable CFG
  or across native Flow stages. Plain ownership-free C-layout records and
  nested trivial linear `sole @repr(C)` records without cleanup obligations are
  supported in the bounded C11 value path; resource-bearing owners remain
  deferred.
- Source-verified stage failure semantics, ownership, cleanup, and general
  effects in native Flow execution. `_dispatch` propagates callback failures,
  reports the stopped stage, and publishes no partial outputs, but it does not
  verify that an external callback matches the checked source body. Direct native
  calls to source stages remain pure scalar calls without a source-level failure
  result.
- Backpressure, retries, distributed scheduling, and graceful interruption of
  a running synchronous C11 stage. The `flow-run --timeout` option terminates
  its isolated runner process and publishes no partial outputs; it does not
  unwind the stage's C stack or run language-level cleanup.
- Arbitrary CFG semantics beyond the validated scalar instruction subset,
  ownership-bearing source CFG, and general Flow unwind/defer integration.

These restrictions are validated fail-closed and define the supported 1.0
subset.
