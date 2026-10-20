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
