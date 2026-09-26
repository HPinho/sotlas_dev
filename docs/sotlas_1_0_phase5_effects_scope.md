# Sotlas 1.0 — Phase 5 Effects Scope

**Updated:** 2026-09-26
**Status:** COMPLETE within the bounded Sotlas 1.0 contract

## Contract

Source and canonical SIR effect inference classify direct and transitive effects
over recursive call graphs. The closed vocabulary is `alloc`, `blocking`,
`async`, `io`, `sync`, `unsafe`, `volatile`, `system`, `ffi`, and
`unknown_call`. Unmapped calls remain `unknown_call` and retain their names;
declared contracts cannot erase an inferred effect or an unresolved call.

`@realtime` rejects allocation, blocking, async, I/O, synchronization, FFI, and
unknown calls transitively. Inline assembly carries `unsafe` and `volatile`.
SIR summaries preserve inferred/declaration evidence and are revalidated before
backend gates.

The canonical C11 production route automatically applies its target contract
before emission. It rejects `async` because there is no suspension runtime and
rejects `unknown_call` because an unresolved symbol has no checked ABI/effect
boundary. An explicit `extern "C"` declaration provides a typed FFI boundary
and infers the `ffi` effect; other unresolved calls remain rejected. Other modeled synchronous effects can be
lowered to C11; this does not claim that a target supplies the corresponding
runtime or hardware resource.

LLVM and the legacy SIR C11 emitter validate `BackendEffectContract` against
fresh SIR summaries. LLVM has a conservative target default; callers can pass a
target-specific contract. The legacy SIR C11 API requires an explicit contract
for this validation path. Neither API implies a runtime is linked or available.

## Verification

- Direct, transitive, recursive, unresolved, and declared effects are tested.
- Malformed and incomplete source contracts fail before C11 emission.
- C11 rejects async and unresolved calls before producing output; modeled host
  I/O and explicit FFI contracts have positive checks.
- `@realtime` rejects every restricted effect transitively, including locks and
  FFI; unmapped runtime names fail closed as unknown calls.
- SIR and backend contracts are tested for accepted and rejected capabilities,
  deterministic diagnostics, and missing summaries.
- Source-to-C11 effect checks run in the full test suite and dedicated CI gate.

## Deferred beyond Sotlas 1.0

- Async suspension/resumption and async runtime integration.
- Target-provided runtime and hardware resource discovery; C11 uses the
  conservative built-in contract and LLVM callers provide capabilities.
- A complete catalog of third-party runtime symbols. Uncatalogued names remain
  unknown and cannot cross the C11 production boundary without an explicit FFI
  declaration.
- Broad per-domain runtime/backend end-to-end matrices.

These are explicit limits of the 1.0 contract, not implicit effect permissions.
