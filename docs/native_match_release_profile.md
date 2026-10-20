# Native match release profile

This document fixes the executable native match scope for the current preview.
It is not a claim that the full master language or all ownership
domains have native implementations. Changes to those foundations will require
new integration gates even after this profile passes CI.

| Capability | Current implementation | Evidence |
| --- | --- | --- |
| Statement/expression forms | Shared ordered decision chain; subject evaluated once | Match-value and frontend closure suites |
| Scalar subjects | Signed/unsigned integers, Boolean and nominal payload-free enums | Width, coverage and enum gates |
| Patterns | Literal/module constants, `_`, scoped identifier bindings, closed/open integer ranges | Match closure suite |
| Alternatives | Root/nested `|`, grouping, equal binding sets/types, first-match binding selection and one guard evaluation per source arm | Alternative-pattern suite and rebuilt Stage 3 fixtures |
| Guards | Eligible patterns only, ordered fallthrough, no coverage from guards | Guard-order and guarded-binding gates |
| Scalar results | Integers, Boolean and floats with typed arms | Match-value width and rejected-arm gates |
| Enum results | Same nominal enum in every returning arm and typed destination | Return/argument/inference and mismatch gates |
| Record results | Pointer-free POD records, including nested fields/arrays; independent storage | Record-copy and nominal-layout gates |
| Value blocks | Locals, supported statements, tail values and enclosing function returns | Block scope and early-return gates |
| Defer | Tail captured before LIFO cleanup; enclosing cleanup on early return | Deferred mutation and trace gates |
| Payload enums | Private tagged layout; scalar and POD record fields; constructors, internal parameters/returns and match results | Payload construction, ABI, copy and nested enum tests |
| Destructuring | Nested positional variants, immutable bindings, ignored fields and scalar field filters; bindings available to eligible guards | Nested pattern, scope, arity, guard and rejection tests |
| Combination coverage | Exact union of current Boolean/integer/enum field patterns and nested sum/product patterns; guards excluded | Independent Boolean/interval oracles, integer extrema and Cartesian-hole gates |
| Exclusive results | Branch-sensitive exclusive POD moves, value-block yields and `MAYBE_MOVED` joins | Match ownership suite |
| Limits | 64 distributed decision rows plus existing source/CFG/IR/frame/nesting limits | Exact-boundary and negative gates |

## Dependencies that remain open

- Resource-bearing enum fields require the broader runtime/drop contract.
  Payload fields currently support scalars and pointer-free POD records.
- Forward aggregate layout dependencies and enums embedded in earlier record
  layouts remain explicitly rejected.
- Named-field/record destructuring and float equality patterns remain outside
  the implemented pattern syntax. Root/nested alternatives and grouping are
  implemented under [their binding and guard contract](native_match_alternatives.md).
- Shared/resource match values require integrated ARC/drop generation. Exclusive
  POD moves and arm joins are implemented; they do not establish general ARC.
- Standalone arrays/slices, pointer provenance and resource-bearing aggregates
  need their corresponding native value/ABI contracts.
- Canonical Stage-0/C11 parity is a separate gate from native execution.
- Intel macOS execution and release-platform certification require their actual
  runners; cross-host Mach-O generation alone is insufficient.

The profile is maintained in [the match contract](native_match_values.md), with
local build/test evidence in [the sovereignty roadmap](sotlas_sovereignty_roadmap.md).
