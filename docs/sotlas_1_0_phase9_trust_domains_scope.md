# Sotlas 1.0 — Phase 9 Trust Domains Scope

**Updated:** 2026-09-26  
**Status:** COMPLETE for explicit FFI boundary classification and call rules

## Certified contract

The trust analyzer classifies checked `@extern(C)` declarations as `trusted`,
`unsafe`, or `isolated`, validates explicit annotations when requested, and
rejects malformed annotations or trust labels on non-foreign functions. FFI
declarations require the `ffi` effect. The canonical SIR preserves the foreign
symbol, C convention, trust label, effects, and required caller context.

Every foreign call requires a `@system` function. A declaration marked
`@trust(unsafe)` or `@unsafe` also requires an explicit `unsafe` block at its
call site. Pointer values crossing FFI preserve foreign provenance and raw
pointer operations remain subject to unsafe checks. Tests cover both rejected
and accepted call paths and confirm the metadata survives into SIR.

## Release boundary

Trust labels record and enforce source-level boundary policy; `trusted` is an
explicit programmer assertion. `isolated` is always reported as unverified.
Sotlas 1.0 does not claim a sandbox, capability revocation, process isolation,
or a security proof for foreign code. Those require concrete target/runtime
mechanisms. Foreign wrapper policy beyond the checked call-context rules is
deferred.

## CI gate

CI runs the foreign boundary/effect preservation tests and unsafe FFI call-site
tests. The gate rejects missing or malformed declarations and checks both
allowed and forbidden contexts.
