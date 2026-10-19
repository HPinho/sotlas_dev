# Native match release profile

This document fixes the executable native match scope for the current preview.
It is not a claim that the full master language, payload enums or all ownership
domains have native implementations. Changes to those foundations will require
new integration gates even after this profile passes CI.

| Capability | Current implementation | Evidence |
| --- | --- | --- |
| Statement/expression forms | Shared ordered decision chain; subject evaluated once | Match-value and frontend closure suites |
| Scalar subjects | Signed/unsigned integers, Boolean and nominal payload-free enums | Width, coverage and enum gates |
| Patterns | Literal/module constants, `_`, scoped identifier bindings, closed/open integer ranges | Match closure suite |
| Guards | Eligible patterns only, ordered fallthrough, no coverage from guards | Guard-order and guarded-binding gates |
| Scalar results | Integers, Boolean and floats with typed arms | Match-value width and rejected-arm gates |
| Enum results | Same nominal enum in every returning arm and typed destination | Return/argument/inference and mismatch gates |
| Record results | Pointer-free POD records, including nested fields/arrays; independent storage | Record-copy and nominal-layout gates |
| Value blocks | Locals, supported statements, tail values and enclosing function returns | Block scope and early-return gates |
| Defer | Tail captured before LIFO cleanup; enclosing cleanup on early return | Deferred mutation and trace gates |
| Limits | 64 arms plus existing source/CFG/IR/frame/nesting limits | Capacity and negative gates |

## Dependencies that remain open

- Payload enums need native layout, constructors, value transfer and destruction
  before destructuring patterns and payload bindings can be certified.
- Ownership-bearing match values need the broader native ownership merge and
  runtime cleanup contract; this delivery keeps their rejection explicit.
- Standalone arrays/slices, pointer provenance and resource-bearing aggregates
  need their corresponding native value/ABI contracts.
- Canonical Stage-0/C11 parity is a separate gate from native execution.
- Intel macOS execution and release-platform certification require their actual
  runners; cross-host Mach-O generation alone is insufficient.

The profile is maintained in [the match contract](native_match_values.md), with
local build/test evidence in [the sovereignty roadmap](sotlas_sovereignty_roadmap.md).
