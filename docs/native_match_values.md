# Native match expressions

The native parser and CFG accept `match` values in initializers,
assignments, returns, call arguments, calculations and conditions.

```sotlas
fn classify(value:u8)->u32 {
    return match value {
        0..=9 if value < 5 => 20,
        0..=9 => 21,
        10..=255 => 22
    };
}
pub fn main_entry()->u32 { return classify(5)+classify(10)-1; }
```

## Evaluation and coverage

The subject is evaluated once and kept as an SSA value across the decision
chain. Patterns are tried in source order. A guard runs only after its pattern
matches; a false guard proceeds to the next arm. Only the selected arm value
executes. Every arm is still lowered/type-checked, including unselected arms.
Each selected arm stores its scalar result, or copies its complete POD record,
before the shared join. A value block captures its tail before executing defers.
There is no new backend opcode or Python evaluator for match values.

Expressions reuse native statement-match validation: integer widths, Boolean
and payload-free enum subjects, literal/constant patterns, bounded integer
ranges, duplicate/overlap rejection and exhaustive coverage. Ranges include
`..end`, `..=end`, `start..` and `..`, bounded by the subject's actual integer
type. Empty, overflowing, reversed and overlapping intervals are rejected.
An unguarded `_`
must be last. Guarded arms do not prove coverage, and the final arm cannot be
guarded. Complete Boolean/enum matches retain the existing invalid-value guard.

## Result profile

Results are typed integers, Booleans or floats. The enclosing expected type
is used when available; otherwise a known first-arm type or a Boolean literal
can determine the result. Untyped integer literals retain the native U32 default.
Use explicit type annotations for signed/float/narrow literal results.

Payload-free enum results preserve nominal identity across arms and typed lets,
returns, assignments and internal call arguments. Mixing unrelated enums or
silently assigning an enum result to an integer is rejected. An explicit cast
remains a separate operation. Pointer-free POD records can be returned by value;
their fields and array fields are copied into independent result storage.

Arms accept expressions or blocks with local declarations, ordinary statements
and a final value without a semicolon. A block that provably returns from the
enclosing function needs no tail value. Defers execute in LIFO order after the
tail is captured, or on early return with the enclosing cleanup. Internal loops
use their normal control flow. Cross-expression break/continue targets are not
provided; those forms fail closed. Nested match and conditional values are
accepted. Parenthesize a match when needed as an operand or in lazy Boolean code.

An identifier pattern that is not a module constant binds the scalar subject
immutably in that arm's guard/body. It can shadow an outer name but cannot escape
to a sibling arm or the surrounding scope. An unguarded binding is a catch-all
and must be last; a guarded binding contributes no coverage. Existing module
constants continue to mean value patterns.

Raw pointer results and pointer/resource-bearing record results remain rejected.
Exclusive POD captures and results use independent arm analysis, live-path joins
and the existing move checks. Guards may borrow owners but cannot consume them.
Value blocks preserve defer reservations and capture results before cleanup.
Payload enums now have native constructors, internal aggregate transfer and
positional pattern bindings; see [the payload contract](native_match_payloads.md).
General resource cleanup, ARC and named-field patterns remain separate
dependencies. Nested/refutable positional patterns have symbolic sum/product
coverage: complete combinations need no total fallback. See the payload contract
for the declared domains, proof algorithm and independent coverage oracles.

Root and nested `|` alternatives share a body and source-level guard under
[the alternative-pattern contract](native_match_alternatives.md).
The distributed decision-row count is bounded to 64, with the existing CFG, IR,
stack and nesting limits.
Match expressions are runtime values; module constant/static evaluation is not
expanded here. The Stage-0/C11 path is not asserted to accept this native syntax.

## Evidence

`tests/test_sotlas_native_match_values.py` executes original source and tests
single subject evaluation, lazy arms/guards, nested matches, ranges, enum and
Boolean coverage, typed results, loops, defer, capacity and rejected forms.
The [example](../examples/native_match_values/README.md) is executed by the suite.
Existing frontend/Target IR tests and native self-builds check compatibility.
`tests/test_sotlas_native_match_closure.py` covers bindings, open ranges, nominal
enum results, POD aggregate copies, value-block scope, LIFO/captured-value order,
early return and explicit exclusions. See the [release profile](native_match_release_profile.md)
for the closure matrix and remaining dependencies.
