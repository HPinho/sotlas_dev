# Sotlas 1.0 — Phase 5 Effects Scope

**Atualizado em:** 2026-09-26
**Status:** 🟡 IN PROGRESS
**Último baseline verde certificado:** `33e60d8` — CI #586 `success`

## SIR effect summaries

`EffectInferencePass` records direct and transitive effects for each SIR
function. The current effect vocabulary is `alloc`, `blocking`, `async`, `io`,
`sync`, `unsafe`, `volatile`, `system`, and `unknown_call`. Calls to known
functions propagate effects through recursive call graphs to a fixed point.
Unresolved callees conservatively contribute `unknown_call` and are preserved
by name in the summary. When SIR is built from a checked source module, source
direct/transitive facts, unresolved callee names, and the declared contract
are attached to matching SIR functions. Inference combines these facts with
effects visible in lowered instructions and rechecks the declared contract.

`SIRFunction.declared_effects` can carry an explicit SIR contract. The pass
rejects unknown effect names and contracts that omit an inferred effect.
Summaries are attached to the `SIRModule` and each function. The normal SIR
pass manager runs effect inference before hardware interrupt validation.

Interrupt handlers reject transitive `alloc` and `blocking` operations,
`AwaitInst`, and unresolved calls. The diagnostic for a known forbidden call
preserves the call chain.

## Source contracts (release subset)

The canonical production checker accepts `@effects(...)`, infers direct and
transitive effects over local recursive calls, and attaches deterministic
source summaries to the checked module. Classified low-level builtins and
inline assembly carry conservative effects; unmapped external calls are
`unknown_call`. Explicit contracts that omit inferred effects fail before C11
lowering. Phase 1 copies each source summary into its corresponding typed
function, and canonical SIR construction carries the facts into its functions
for inference and contract revalidation. Backend contracts remain open. This
starter contract does not yet model all runtime/FFI names.

## Verifications

- direct and transitive summary propagation through mutually recursive calls;
- deterministic summaries and idempotent repeated analysis;
- unresolved calls remain explicitly unknown;
- incomplete declared contracts fail;
- interrupt paths reject async and unresolved external calls;
- interrupt diagnostics preserve the transitive path to forbidden allocation.

## Blockers de 1.0

- [x] SIR-level direct/transitive effect inference;
- [x] recursive call-graph fixed point;
- [x] conservative classification of unresolved calls;
- [x] validation of explicit SIR effect contracts;
- [x] source syntax, effect inference and canonical checker contract validation;
- [x] per-function source summary propagation into the Typed AST;
- [x] propagation into canonical SIR and revalidation of declared contracts;
- [ ] backend contract integration;
- [ ] effects for `@realtime`, async suspension, locks, FFI, and all runtime calls;
- [x] source tests and a phase-specific release gate for the subset;
- [ ] broad domain/runtime/backend end-to-end matrix.

## Limites

The current pass is SIR analysis and does not make source-level effect
declarations `SUPPORTED`. The builtin name map is a starter contract; an
unmapped call is unknown and remains conservative. Runtime behavior and target
ABI effects still need explicit modeling.
