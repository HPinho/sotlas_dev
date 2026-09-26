# Sotlas 1.0 — Phase 10 Guarantees Scope

**Updated:** 2026-09-26
**Status:** COMPLETE for scalar preconditions, flow proofs, and postconditions

## Preconditions

Functions with verified bodies may declare boolean `requires` predicates over
scalar parameters. Calls with evaluable constant arguments are proven or
rejected statically. Dynamic calls preserve source-stable proof evidence in
SIR; exact branch facts and supported integer interval implications can prove
some dynamic calls. Assignment or potentially mutating calls invalidate local
refinements conservatively. Calls without a static proof retain a runtime
entry guard in C11. External declarations without a checked body are rejected
for this contract.

## Postconditions

The supported `ensures` subset covers numeric and boolean scalar results and
immutable scalar parameters. The C11 backend evaluates the result once, runs
active defers, checks the predicate on each return path, and aborts when the
postcondition fails. SIR preserves the contract. Native tests cover successful
and failing return values, parameter-dependent predicates, and boolean results.

`contract-report` emits deterministic JSON separating static proofs from
runtime precondition and postcondition guards. CI tests both the compiler
contracts and report output.

## Release boundary

The expression evaluator is intentionally bounded to supported scalar
expressions. General theorem proving, arbitrary symbolic refinement, contracts
over mutable state or heap, `guarantee` declarations, and aggregate safety
reports are not part of this 1.0 contract. Unsupported forms fail closed;
those extensions remain post-1.0 work.

## CI gate

CI runs positive and negative frontend checks, native runtime guard tests, and
the CLI report test. The gate verifies constant proofs, flow refinements,
invalidation after mutation, SIR evidence, and runtime enforcement.
