# Native inline array patterns

Fixed arrays inside enum payloads and POD record fields can be matched element
by element. The Sotlas-written parser, semantic checker and lowering implement
these patterns; execution uses the owned native object writer and linker.

```sotlas
enum Packet { Empty, Samples([u32;3]) }

fn read(value:whisper Packet)->u32 {
    return match value {
        Packet::Samples([20, .., last])=>20+last,
        Packet::Samples([..])=>0,
        Packet::Empty=>0
    };
}

pub fn main_entry()->u32 {
    let value:sole Packet=Packet::Samples([20, 99, 22]);
    return read(value);
}
```

## Pattern forms

- `[a, b]` requires exactly two elements. Captures are immutable and preserve
  the declared element type. `_` ignores one element.
- `[first, .., last]` selects a prefix and suffix. One unbound `..` may appear
  at the beginning, middle or end, ignoring zero or more elements. `[..]`
  matches every value of the declared fixed array type.
- Each explicit element accepts the existing scalar literals, typed constants,
  numeric intervals, grouping and alternatives. POD record elements accept
  named record patterns and nested field patterns, including inline arrays.
- `..` immediately followed by a comma or closing bracket is the rest marker.
  Use `(..)` for an unbounded numeric interval in one element. `..42` and
  `..=42` remain numeric intervals without extra parentheses.
- Alternatives must bind the same names and types. Expansion keeps the existing
  64 decision-row limit and one guard evaluation per source arm.

An exact pattern with the wrong number of elements, an overfull prefix/suffix,
duplicate rest marker, duplicate name or mismatched element type is rejected.
`[value; count]` remains expression repetition, not pattern syntax. Rest does not
create a slice or bind the skipped elements.

## Coverage and evaluation

Coverage uses the physical offsets and declared types of selected elements.
It proves unions of Cartesian products, including prefix/suffix projections;
independent coverage of each element is insufficient. Ignored elements need no
constraints. Guards never establish coverage. Float intervals leave NaNs for
a capture/fallback, and signed-zero equality follows the float pattern contract.

The subject is evaluated once and copied into its existing independent POD
snapshot. Element tests run only after enclosing enum tags match. Captures are
populated before guards; record captures get independent storage. A false guard
continues with the preserved snapshot. Lexical scope, moved/maybe-moved checks,
owned subject reads and LIFO deferred cleanup retain their existing rules.

## Bounds and exclusions

This block covers arrays embedded in accepted POD records and tagged payloads.
Standalone array subjects, slices, multidimensional arrays and resource elements
remain outside this contract. It does not add ARC or generated destructors.

Arrays retain the 1â€“256 element and 4096-byte container bounds. The compiler
creates layout views for explicitly selected elements only, sharing views with
the same element type, array length and prefix/suffix shape. These views consume
the existing 32 layout and 256 field slots. Reaching a capacity rejects the
program before an artifact is published. A view never changes a stored value's
layout or ABI. A 256-element array matched as `[first, .., last]` needs only two
selected-element slots. Pattern depth, local/frame and CFG limits still apply.

The canonical Stage-0/C11 frontend has separate support gates. New GitHub CI
and actual Intel macOS execution remain certification gates for this change.

## Evidence

- `tests/test_sotlas_native_match_array_patterns.py`: all scalar widths, exact
  and rest patterns, record/nested array fields, typed captures, alternatives,
  guards, scopes, owned subjects, loops, defer and rejection cases.
- All 512 unions of two-Boolean rectangles are checked against an independent
  set oracle. Separate three-element projections test actual suffix offsets.
- The 256-element sparse view and IEEE NaN runtime/fallback paths execute.
- `tests/native/match_profile/array_pattern*.sotlas`: shared rebuilt Stage 3
  driver cases, including located errors and previous-output preservation.
- [Public match example](../examples/native_match_values/main.sotlas).

## Local validation

Local validation: 199 native match tests and 52 shared rebuilt Stage 3 driver
cases pass on each Windows/Linux host. The 20 new array-pattern tests also pass
through the hosted bootstrap route. Another 212 frontend/parser/bootstrap/docs
tests pass, as does the exact Windows original-module CI gate with calculator,
GUI and UI-model checks. Final native Stage 2/3 images are byte-identical within
each host; reconstruction runs without host tools after obtaining a refreshed
seed for the OS adapters added online. The final sources also pass canonical
bootstrap validation. The public example object and ELF/PE/Mach-O images match
across hosts, and the Windows/Linux images execute with exit 42. GitHub CI and
actual Intel macOS execution remain pending.

