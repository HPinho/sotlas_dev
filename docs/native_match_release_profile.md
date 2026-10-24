# Native match release profile

This document fixes the executable native match scope for the current preview.
It is not a claim that the full master language or all ownership
domains have native implementations. Changes to those foundations will require
new integration gates even after this profile passes CI.

| Capability | Current implementation | Evidence |
| --- | --- | --- |
| Statement/expression forms | Shared ordered decision chain; subject evaluated once | Match-value and frontend closure suites |
| Subjects | Signed/unsigned integers, Boolean, F32/F64, nominal enums, bounded POD records and stored fixed arrays | Width, float, record, array, coverage and enum gates |
| Patterns | Literal/module constants, `_`, scoped identifier bindings, closed/open integer ranges | Match closure suite |
| Alternatives | Root/nested `|`, grouping, equal binding sets/types, first-match binding selection and one guard evaluation per source arm | Alternative-pattern suite and rebuilt Stage 3 fixtures |
| Named fields | Reordered fields, renaming, shorthand, `..`, nested records and independent inline array captures | Named/float suite, 512 record coverage unions and Stage 3 fixtures |
| Float patterns | IEEE equality, numeric intervals, signed-zero equivalence, explicit NaN fallback and width-specific rounding | F32/F64 boundary, NaN/infinity and overlap tests |
| Guards | Eligible patterns only, ordered fallthrough, no coverage from guards | Guard-order and guarded-binding gates |
| Scalar results | Integers, Boolean and floats with typed arms | Match-value width and rejected-arm gates |
| Enum results | Same nominal enum in every returning arm and typed destination | Return/argument/inference and mismatch gates |
| Record results | Pointer-free POD records, including nested fields/arrays; independent storage | Record-copy and nominal-layout gates |
| Contextual array results | Typed local initializers and declared inline fields/payloads select POD arrays via match/conditionals; independent copies and pre-cleanup tails | Array-result execution, shape, nominal type, ownership and defer gates |
| Value blocks | Locals, supported statements, tail values and enclosing function returns | Block scope and early-return gates |
| Defer | Tail captured before LIFO cleanup; enclosing cleanup on early return | Deferred mutation and trace gates |
| Payload enums | Private tagged layout; scalar, POD record and inline scalar/record array fields; constructors, internal parameters/returns and match results | Payload construction, ABI, copy, array and nested enum tests |
| Owned subjects | Read named exclusive/whisper/direct POD bindings through an independent snapshot without consuming the owner | Array-payload ownership, guard, move and defer tests |
| Array elements | Exact lists, prefix/suffix rest, typed captures, scalar filters, alternatives and named POD record elements in inline arrays | Array-pattern suite, independent coverage oracle and rebuilt Stage 3 fixtures |
| Destructuring | Nested positional variants, immutable bindings, ignored fields and scalar field filters; bindings available to eligible guards | Nested pattern, scope, arity, guard and rejection tests |
| Combination coverage | Exact union of current Boolean/integer/enum field patterns and nested sum/product patterns; guards excluded | Independent Boolean/interval oracles, integer extrema and Cartesian-hole gates |
| Exclusive results | Branch-sensitive exclusive POD moves, value-block yields and `MAYBE_MOVED` joins | Match ownership suite |
| Limits | 64 distributed decision rows plus existing source/CFG/IR/frame/nesting limits | Exact-boundary and negative gates |

## Dependencies that remain open

- Resource-bearing enum fields require the broader runtime/drop contract.
  Payload fields currently support scalars, pointer-free POD records and bounded
  inline arrays. See [the array payload contract](native_match_array_payloads.md).
- Forward aggregate layout dependencies and enums embedded in earlier record
  layouts remain explicitly rejected.
- Named fields and floats are implemented under
  [their native contract](native_match_named_float.md). Pattern forms in this
  release profile are complete; resource payload/runtime integration is next.
- Shared/resource match values require integrated ARC/drop generation. Exclusive
  POD moves and arm joins are implemented; they do not establish general ARC.
- Standalone fixed arrays support [subject matching](native_match_array_subjects.md).
  General array parameters/returns, slices, pointer provenance and resource-bearing
  aggregates still need their corresponding native value/ABI contracts.
- Canonical Stage-0/C11 parity is a separate gate from native execution.
- Intel macOS execution and release-platform certification require their actual
  runners; cross-host Mach-O generation alone is insufficient.

The profile is maintained in [the match contract](native_match_values.md), with
local build/test evidence in [the sovereignty roadmap](sotlas_sovereignty_roadmap.md).
