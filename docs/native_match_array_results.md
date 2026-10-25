# Native contextual array results

`match` and conditional expressions can produce fixed arrays for explicitly typed
local initializers, inline record fields and enum array-payload arguments. The
destination supplies the element type and count; the native compiler checks every
arm before publishing an artifact.

```sotlas
pub fn main_entry()->u32 {
    let selected:[u32;2]=match true {
        true=>[20,22],
        false=>[0;2]
    };
    return match selected { [first,last]=>first+last };
}
```

## Result values

- Branches accept compatible stored arrays, array-valued record fields, element
  lists and one-evaluation repetition. Supported existing global array storage
  can be copied under its native access rules.
- Scalars cover Boolean, signed/unsigned integers and F32/F64. Pointer-free POD
  record arrays preserve nominal record identity and recursively copy fields.
- `if flag { ... } else { ... }` selects an array with the same contextual shape.
  Matches and conditionals can nest in result branches. Only the selected path
  evaluates its initializer; lists preserve order and repetition evaluates once.
- Value blocks can declare locals, yield array values and run the existing
  structured statements/defer paths. In typed local initializers, early return
  uses the enclosing function ABI. A branch that returns does not fabricate an
  array value on the live successor; an all-returning match leaves no live join.
- Matching a payload or an array can supply an array result. Typed captures and
  guards retain their existing scope and first-match semantics.

## Copies and cleanup

The selected value is populated in independent inline storage. Later mutations
of a source array do not affect the result. A value-block tail is copied before
LIFO deferred cleanup, so a deferred mutation of the source cannot change the
already selected result.

Array-valued fields are staged before being written at their actual aligned
field offset. The same operation works inside a POD record returned through the
existing aggregate ABI. Enums retain their private tagged layout and store the
selected array in the declared payload slot.

Owner-consuming calls used to compute scalar elements still participate in
branch-sensitive ownership analysis. Moves on disjoint arms are accepted;
use of moved or maybe-moved owners is rejected. This does not make the arrays
resource-owning containers or add automatic destruction.

## Bounds and exclusions

- Array results contain 1â€“256 elements and at most 4096 bytes of POD storage.
  Existing layout/field, CFG, local, stack, nesting and 64-row budgets apply.
- Incompatible counts, element types, record identities and invalid arms are
  rejected even when a condition is a known literal. Matches remain exhaustive;
  conditions/guards remain Boolean under their existing native rules.
- A typed local or declared inline field/payload provides context. Internal
  parameters/returns now supply context through the
  [value-array ABI](native_value_array_abi.md), including direct returned-array
  subjects and local inference from call signatures. General inferred array
  expressions, direct reassignment, slices and resource elements remain separate
  work. Foreign and independently compiled array signatures remain unsupported.
- Canonical Stage-0/C11 user-program support, ARC/drop and broader Flow/ownership
  migration are not certified by this native block.

## Evidence

- `tests/test_sotlas_native_match_array_results.py`: 20 tests for scalar/record
  shapes, source copies, nesting, branch evaluation, repeat/list order, guards,
  value blocks, early returns, LIFO cleanup, ownership, nominal types and bounds.
- `tests/native/match_profile/array_result*.sotlas`: shared rebuilt Stage 3 driver
  execution and negative gates with located errors/output preservation.
- [Public match example](../examples/native_match_values/main.sotlas).

## Local validation

Local validation: 241 native match tests and 61 shared rebuilt Stage 3 driver
cases pass on each Windows/Linux host. All 20 new array-result tests also pass
against the rebuilt native seeds, including payload/array subjects and copied
results. Another 233 focused frontend, parser, semantic, bootstrap and docs tests
pass through the hosted bootstrap route. Native Stage 2/3 images are identical
within each host. The exact Windows original-module CI gate passes, including
calculator, GUI and UI-model gates. Public-example object and ELF/PE/Mach-O outputs
match across hosts; Windows/Linux images execute with exit 42. New GitHub CI and
actual Intel macOS execution remain pending.

