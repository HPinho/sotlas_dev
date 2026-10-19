# Native match expressions

The native parser and CFG accept scalar `match` values in initializers,
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
Each selected arm stores its scalar result before a shared join loads the value.
There is no new backend opcode or Python evaluator for match values.

Expressions reuse native statement-match validation: integer widths, Boolean
and payload-free enum subjects, literal/constant patterns, bounded integer
ranges, duplicate/overlap rejection and exhaustive coverage. An unguarded `_`
must be last. Guarded arms do not prove coverage, and the final arm cannot be
guarded. Complete Boolean/enum matches retain the existing invalid-value guard.

## Result profile

Results are typed integers, Booleans or floats. The enclosing expected type
is used when available; otherwise a known first-arm type or a Boolean literal
can determine the result. Untyped integer literals retain the native U32 default.
Use explicit type annotations for signed/float/narrow literal results.

Each arm is a single expression separated by commas; the final comma is optional.
Nested match and conditional values are accepted. Statement blocks with local
bindings, return/break/continue and block-tail values are not added. Parenthesize
a match when needed as an operand or inside a lazy Boolean expression.

Aggregate, pointer and enum-valued results are rejected in this profile. Captures
of owned/domain-qualified bindings are rejected before lowering, including a
scalar projection from an owner. This deliberately leaves owned branch merges,
payload patterns/bindings and resource cleanup for a separate contract. It does
not restrict those existing capabilities in ordinary statement matches.

Arm count is bounded to 64, with the existing CFG, IR, stack and nesting limits.
Match expressions are runtime values; module constant/static evaluation is not
expanded here. The Stage-0/C11 path is not asserted to accept this native syntax.

## Evidence

`tests/test_sotlas_native_match_values.py` executes original source and tests
single subject evaluation, lazy arms/guards, nested matches, ranges, enum and
Boolean coverage, typed results, loops, defer, capacity and rejected forms.
The [example](../examples/native_match_values/README.md) is executed by the suite.
Existing frontend/Target IR tests and native self-builds check compatibility.
