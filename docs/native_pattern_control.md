# Native pattern control and checked field iteration

The native frontend supports statement-level `if let` and `while let`:

```sotlas
enum Item { End, Value(u32) }

fn read(item: Item) -> u32 {
    if let Item::Value(number) = item {
        return number;
    } else {
        return 0;
    }
}
```

`if let` evaluates its subject once and selects a scoped pattern branch.
An omitted else is an empty branch. Else blocks, ordinary `else if` and
`else if let` can be combined. Bindings exist only in the selected body;
they shadow outer names and are immutable snapshots.

`while let` evaluates a fresh subject before each iteration. A failed pattern
ends that loop. The subject is not evaluated again when `break` or `return`
exits the body. `continue` executes active iteration defers before reevaluating
the subject. Nested loops retain their own jump targets; an `if let` does not
introduce a loop target. A `?` operand can return before a new iteration starts.
Lexical defers execute in LIFO order on all supported structured exits.

## Patterns and boundaries

The constructs reuse native match decisions, nominal checks and POD payload
snapshots: enum variants, nested payloads, named record fields, fixed-array
patterns, literals, constants, bounded ranges, floats and alternatives with
compatible bindings. Qualified POD sources follow the existing match reading
contract: reading an exclusive owner does not consume it. Unavailable owners
and pointer/resource payload graphs remain rejected. This is not automatic
resource destruction or general borrow checking.

A bare capture or `_` as the entire condition is rejected; use `let` or `loop`
for those forms. Expression-valued `if let`, mutable pattern bindings,
`while let ... else`, pattern guards and chained conditions are not introduced.
Unreachable-code diagnostic parity remains a separate frontend task; this
package does not claim a new exhaustive semantic pass over unreachable match
patterns. The optional legacy C11 emitter is outside this native contract.

The parser normalizes each decision to a statement match with a reserved
fallback binding. Its `let` spelling cannot collide with a user identifier.
A conditional loop is a structured while containing that decision and a
failure break. No new IR opcode or alternate pattern engine is used.

Scalar-returning calls with supported aggregate parameters now select the
structured ABI path too. This includes calls nested directly in arithmetic
return expressions, without requiring an artificial branch or local binding
in the caller. Existing aggregate layouts and foreign-ABI gates still apply.

## Checked split cursor

`runtime/native/text_split.sotlas` provides allocation-free field iteration
using these concrete types:

| Type/API | Meaning |
| --- | --- |
| `NativeByteRange` | Byte offset and byte count; carries no pointer |
| `NativeRangeOption` | Some(range), or None after iteration ends |
| `NativeSplitCursor` | Offset and finished flag; passed by value |
| `NativeSplitResult` | Status, optional field, next cursor and numeric error |
| `native_split_open()` | Initial cursor, at byte zero |
| `native_split_next(source, delimiter, cursor)` | Checked nonoverlapping byte-delimiter search |

Success has status zero. A present field includes the next cursor. The final
field sets `next.finished`; another call yields successful None. Empty input
contains one empty field. Leading, repeated and trailing delimiters preserve
empty fields. Delimiters may contain multiple bytes or NUL; offsets are byte
positions, not Unicode character indices. Matching is nonoverlapping.

Invalid slice shape, an empty delimiter or an offset beyond the source returns
status/error kind 7, None and the unchanged cursor. Bounds are checked even for
a finished cursor. Callers must inspect status to distinguish an error from
successful exhaustion. Source and delimiter must remain the same throughout
one traversal; the cursor does not track source identity or mutation. Borrowed
storage must be readable for each call. Shape checks do not prove provenance
or lifetime. Returned ranges need the original source to obtain a byte view.

The implementation reuses checked optional lookup and its text-search routine.
It adds no allocator or hidden host call. The older mutable byte cursor APIs in
`text.sotlas` retain their existing interface and behavior.

## Example and evidence

The [field-sum example](../examples/native_pattern_control/main.sotlas) reads
`10::12::::20::`, preserves its five fields, skips empty values, parses numbers
and verifies one cleanup per iteration before returning 42. Invalid delimiters
remain errors. It is included in each native rebuilt-driver platform gate for
imported check/build, object emission, linking, execution and ELF/PE/Mach-O output.

Focused cases are in `tests/test_sotlas_native_pattern_control.py` and
`tests/test_sotlas_native_text_split.py`. They cover scope, snapshots, alternatives,
structured exits, nominal/type/ownership rejection and cursor boundaries.
Full platform CI certification for this candidate remains pending.

### Local checks

The final sources passed 33 new hosted-harness tests and 134 focused native
tests per Windows/Linux producer. The latter include the new cases plus
optional propagation, fixed-array iteration, recursive/named/float patterns,
match ownership and tagged results. Separately, 86 structured CFG tests and
19 public-inventory checks passed; the generated phase matrix stayed consistent.

The imported field-sum application passed check, object generation, direct
build and execution with exit 42 on Windows and Linux, with host tools absent
from PATH. The two producers emitted byte-identical object, ELF, PE and Mach-O
files. Actual Mach-O execution remains a macOS CI responsibility.

Original-source rebuilds completed with host tools absent from PATH and strict
Stage 2/3 byte equality on each host. The focused native runs used Stage 2;
the resulting Stage 3 images are identical. Compiler SHA-256 values:

- Windows: `3b06cc0f3adda6aee48064d11e718e32cfcc41b1f5cf1a0be7801c7ea401f5dd`
- Linux: `f9f145843e2864b827bcd84a6c693c3a0dfc36ca64ac6c6c54234e568c5e4832`

These checks certify local behavior within the declared native profile. They
do not complete generic frontend parity, automatic ARC or independent packaging.
