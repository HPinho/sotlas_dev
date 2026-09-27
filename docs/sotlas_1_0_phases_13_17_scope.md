# Sotlas 1.0 — Phases 13–17 Release Scope

**Updated:** 2026-09-26  
**Status:** COMPLETE for the certified subsets listed below

These phases close the Sotlas 1.0 contracts they can support end to end. The
percentages in the implementation status refer to these bounded contracts;
they do not claim that every construct in the architectural roadmap is
implemented.

## Phase 13 — Transactions

Canonical SIR Flow effects require an explicit `reversible`,
`compensatable`, or `irreversible` policy. A compensatable policy requires a
present handler with a compatible signature. Audit results report blockers
and reverse dependency-layer order. The sequential reference executor validates
the reconciled Flow, policy, and callable bindings before invoking a stage;
when a later stage fails it compensates completed stages in reverse order and
retains the original and rollback errors. Parallel schedules fail closed.

No atomicity is promised for external effects. The executor cannot undo an
effect performed by the stage that itself failed. Snapshots, verified inverse
operations, crash recovery, and concurrent journals remain future work.

## Phase 14 — Intent

The programmatic planner deterministically checks preferred and fallback
canonical SIR Flows against forbidden effects and unavailable stages, recording
why each candidate was selected or rejected. Both execution APIs revalidate
the plan and canonical Flow before calling selected stages. Caller-provided
bindings are checked before execution.

Declarative source syntax, inferred functional goals, typed guarantees, and
Ownership-integrated scheduler execution remain future work. The 1.0 interface
is an explicit planning API and makes no claim to infer programmer intent.

## Phase 15 — Canonical SIR subset

The checked source pipeline carries supported function bodies and the
implemented Ownership placements, Effects summaries, foreign trust metadata,
contract evidence, and Flow plans into canonical SIR. Flow plans are checked
against function signatures, argument provenance, dependencies, schedules,
and Effects before relevant analyses or execution consume them. Tampered plans
fail closed.

The `sir-report` command emits deterministic `sotlas.sir-report.v1` JSON with
function signatures, block operation inventories, CPU requirements, validated
Flow names, and aggregate counts. This is an inventory of the checked SIR
subset, not a promise that the prototype SIR dump is a stable serialization
format or that arbitrary source bodies lower to SIR.

## Phase 16 — Native machine backend

The certified scalar and structured-control subset lowers from source through
SIR directly to LLVM IR, then to host assembly, relocatable objects, or native
executables without C as an intermediate language. Covered cases include
direct scalar returns, immutable scalar locals that alias a same-typed
parameter, immutable explicitly typed integer locals initialized from literals,
selected integer arithmetic/comparisons, conditional
branches/phi values, one unsigned counter/accumulator loop lowered with
loop-carried `phi` nodes, and verified native caller interoperability. The loop
is compiled to an object and executed through a native C caller. Unsupported
instructions/domains fail before artifact emission. Functions that fall through
the prototype SIR generator's body-lowering fallback are now identified in SIR
inspection output and rejected by the LLVM source path before writing an IR,
object, or executable artifact; the prototype dump remains available for
inspection only.

LLVM supplies instruction selection, register allocation, ABI lowering, and
object emission for this 1.0 path. Sotlas does not yet provide its own machine
backend. Complete ABI lowering, a Sotlas register allocator, general mutable
loop-body CFG and aggregate support, unwind metadata, and execution coverage
for every target remain future milestones.

## Phase 17 — Tooling

The 1.0 CLI has deterministic JSON reports for target configuration, checked
Flow plans, function contracts, and canonical SIR inventory. Each report is
derived from the corresponding validated source/SIR pipeline, rejects invalid
input without emitting partial JSON, and has a CLI regression test. Assembly
emission is available for the certified LLVM subset and rejects unsupported
forms. A backend test also feeds the source-generated unsigned loop CFG through
Target IR lowering, phi-edge liveness, and the inspection-only register preview;
these analyses do not yet feed LLVM code generation.

Interactive Domain/State/Authority views, a causal debugger, safety explorer,
register-allocation and ABI/stack visualization, and source-to-instruction
mapping remain post-1.0 work.

## CI gates

CI covers transactional and Intent Flow behavior, canonical SIR validation,
LLVM object/executable emission, and deterministic CLI reports. These gates
validate the bounded 1.0 contracts above; they do not certify the deferred
features listed in each phase.
