# Native fixed-array match subjects

Stored fixed arrays can be the subject of a native statement or expression
`match`. Wrapping the array in an enum or record is no longer necessary.
The implementation is in the Sotlas semantic checker and native lowering.

```sotlas
pub fn main_entry()->u32 {
    let values:[u32;3]=[20,99,22];
    return match values {
        [first, .., last]=>first+last
    };
}
```

## Executable scope

- Explicitly typed local arrays, existing global array storage and array-valued
  fields are accepted under their native access rules. Parenthesized/unsafe
  source forms retain their existing syntax and checks.
- Fields of supported internal record results work directly. The receiver of
  `match make().items` is evaluated once before the array snapshot is created.
  Nested fields and fields of captured POD records retain their nominal types.
- Elements are the supported Boolean, integer and F32/F64 scalars or pointer-free
  POD records. Exact lists, prefix/suffix rest, ranges, alternatives and record
  elements reuse [the array pattern contract](native_match_array_patterns.md).
- A whole-subject binding such as `all=>all[0]+all[1]` is an immutable array
  value with its element type/count preserved. It can initialize an existing
  compatible inline array field or be matched again. Checked indexing retains
  its runtime bounds operation.
- Array captures extracted from payloads can also become subjects of nested
  matches. Original alternative trees and normalized decision rows resolve the
  same subject type.

## Snapshots and guards

The compiler copies the entire semantic contents of the subject before testing
arms, including elements skipped by a sparse pattern. Whole-subject bindings
receive their own complete copy before a guard. Scalar captures are values;
record element captures also use independent storage.

A guard that changes the original array through an unsafe alias cannot change
the snapshot inspected by later arms. A guard that changes its whole-array
capture cannot change that snapshot either. Alternatives still evaluate their
source guard once. Scope, immutable bindings, ownership checks, early returns,
loop edges and LIFO deferred cleanup use the existing native rules.

Coverage proves unions of element products against the declared array type.
Guards do not establish coverage. Float numeric intervals leave a path for NaNs.
Scalar/enum patterns cannot accidentally match the internal decision placeholder
used for an array subject; they are explicitly rejected.

## Bounds and remaining work

The subject contains 1â€“256 elements and occupies at most 4096 bytes. One complete
storage layout is shared by compatible array types; sparse pattern views remain
separate. Both use the existing 32 layout and 256 field budgets. Stack, local,
pattern-depth and 64-row limits remain in force and fail before publication.

This does not add general array parameters/returns, array-valued temporary
subjects, untyped array-literal subjects, slices, resource elements, ARC or drop
glue. [Contextual array results](native_match_array_results.md) now allow typed
locals and declared inline fields/payloads to select arrays before matching them.
Existing scalar/record result ABIs remain unchanged. Borrowed record fields
are copied as POD values; no borrowed array escapes through a new array ABI.
Canonical Stage-0/C11 user-program support remains a separate gate.

## Evidence

- `tests/test_sotlas_native_match_array_subjects.py`: 22 tests covering scalar
  widths, records, fields, one-evaluation receivers, whole captures, guard
  mutation, alternatives, shadowing, nested matches, floats, loops, cleanup,
  bounds and explicit rejections.
- All 512 two-Boolean rectangle unions are checked against an independent set
  oracle for standalone array subjects.
- `tests/native/match_profile/array_subject*.sotlas` run through the shared rebuilt
  Stage 3 driver gate, including located errors and previous-output preservation.
- [Public example](../examples/native_match_values/main.sotlas).

## Local validation

Local validation: 221 match tests and 57 shared rebuilt Stage 3 driver cases
pass on each Windows/Linux host. Another 235 focused frontend, parser, semantic,
bootstrap and documentation tests passed during this block; the final 22 new
subject tests also pass through the hosted bootstrap route. Final native Stage
2/3 images are identical within each host. The exact Windows original-module
CI gate passes with the final sources and fixtures, including calculator, GUI
and UI-model gates. Public-example object and ELF/PE/Mach-O outputs match across
hosts; Windows/Linux images execute with exit 42. New GitHub CI and actual Intel
macOS execution remain pending.

