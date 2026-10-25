# Native match values

This example uses `match` as a value in a variable initializer and function
returns. Closed/open integer ranges, scoped bindings, guards and exhaustive enum
subjects select numeric, nominal enum and POD record results. One arm uses local
bindings and a tail value. A measurement enum carries a record and scalar payload;
guards read positional bindings. Another function selects an exclusive POD value.
An envelope adds nested variant patterns and a literal field filter before a guard.
The executable exits with status 42 and prints no text.

With a rebuilt Linux x86-64 native compiler:

```sh
build/native-selfhost/sotlas-native --check examples/native_match_values/main.sotlas
build/native-selfhost/sotlas-native examples/native_match_values/main.sotlas build/match-values
./build/match-values
```

On Windows use the Windows native compiler and an `.exe` output name. Exit 42
is the expected result even if the shell treats a nonzero status as failure.
This requires a seed rebuilt with payload matching and exclusive match support.

See [the native match-value contract](../../docs/native_match_values.md) for
coverage, evaluation order and result types, and the
[payload contract](../../docs/native_match_payloads.md) for layout and ownership limits.

Root and nested alternative patterns use |; parentheses group choices. The
example combines fallback variants into one source arm. Alternatives share
binding names/types and evaluate the source guard once, even if they overlap.
See [the alternative-pattern contract](../../docs/native_match_alternatives.md)
for coverage, cleanup and the 64-row distribution bound.

The example also destructures Classification by field name and selects an F32
interval. See [named fields and float patterns](../../docs/native_match_named_float.md)
for shorthand, rest markers, signed zero, NaNs and the current POD layout bound.

## Inline payload arrays

The example also constructs `Samples::Values([21;2])`, reads its exclusive POD
owner through a `whisper` parameter, then transfers the owner to a consuming
function. Arrays live directly inside the enum, with no wrapper record.
`Samples::Values([first,last])` now destructures its two elements directly.
See [inline array patterns](../../docs/native_match_array_patterns.md) for exact
lengths, prefix/suffix rest, coverage and the supported POD limits.

`sample_window` matches a stored array directly with `[first,..,last]`.
[Array subjects](../../docs/native_match_array_subjects.md) explain whole-array
bindings, receiver evaluation and snapshots across guard fallthrough.

`selected_samples` initializes a typed array from a `match` result and then
destructures that array. See [contextual array results](../../docs/native_match_array_results.md)
for conditional expressions, field/payload contexts and cleanup behavior.

`make_samples` returns an array that `sum_samples` accepts by value and matches.
See the [internal value-array ABI](../../docs/native_value_array_abi.md) for
independent argument copies, hidden return storage and the foreign ABI exclusion.

`read_owned_samples` borrows an owned array through `direct`; `move_owned_samples`
then consumes and returns it. The native checker rejects using the original
binding after that transfer. See [array ownership and resource batches](../../docs/native_owned_arrays_and_resources.md).

`replace_samples` replaces a parameter array from a match, then swaps its elements
with a complete right-hand snapshot. See [whole-array assignment](../../docs/native_array_assignment.md)
for mutable destinations, globals, evaluation order and moved-owner reinitialization.
