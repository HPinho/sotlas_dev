# Phase 1 Semantic Core Status

**Status: CERTIFIED**  
**Maturity: ISOLATED_PHASE1**  
**Certification date:** 2026-09-20

This gate certifies the isolated Phase-1 semantic core exposed by
`compiler/sotlas_compile/phase1_pipeline.py`. It is intentionally narrower
than Sotlas' project-wide `SUPPORTED` maturity contract and is **not a claim
of full language production support**.

## Certified scope

The certified path composes the canonical `bootstrap.check` frontend with the
isolated Phase-1 Typed AST and ownership passes without replacing or mutating
the production checker.

The gate covers:

- canonical declaration freezing into semantic types;
- structured function-body typing;
- contextual integer literals and constant-range validation;
- explicit numeric type mismatch rejection;
- raw-pointer and safe-reference compatibility boundaries;
- null contextualization restricted to raw pointers;
- assignment, return, direct-call, method-call and function-field contracts;
- struct-literal shape and field-type validation;
- scalar numeric, equality, shift and unary operator domains;
- lexical `unsafe` requirements for raw-pointer access and arithmetic;
- immutable-reference write protection and mutable-borrow requirements;
- function-pointer signature preservation in the Typed AST;
- sole ownership facts and the isolated Phase-1 ownership analysis.

## Certification invariants

The certification remains valid only while the repository reality gates and
the full CI matrix stay green.

In particular:

1. `typed_ast.MATURITY` remains `ISOLATED_PHASE1`.
2. `TypedModule` and `Phase1ModuleSnapshot` use the same maturity constant.
3. The obsolete `DECLARATIONS_ONLY` marker does not return to the canonical
   Typed AST.
4. The legacy permissive `assignable()` helper is not called by the canonical
   Phase-1 semantic path.
5. `bootstrap.check` remains the production checker invoked before the
   isolated Typed AST and ownership snapshot.

## Non-claims

This certification does not promote the whole language, backend, SIR,
toolchain, standard library, or every documented Sotlas feature to
`SUPPORTED`. Those subsystems retain their own maturity gates and must be
proven independently.
