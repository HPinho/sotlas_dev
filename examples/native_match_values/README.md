# Native match values

This example uses `match` as a value in a variable initializer and function
returns. Integer ranges, a guard and an exhaustive enum subject select numeric
results. The executable exits with status 42 and prints no text.

With a rebuilt Linux x86-64 native compiler:

```sh
build/native-selfhost/sotlas-native --check examples/native_match_values/main.sotlas
build/native-selfhost/sotlas-native examples/native_match_values/main.sotlas build/match-values
./build/match-values
```

On Windows use the Windows native compiler and an `.exe` output name. Exit 42
is the expected result even if the shell treats a nonzero status as failure.
This requires a seed rebuilt with match-expression support.

See [the native match-value contract](../../docs/native_match_values.md) for
coverage, evaluation order, result types and excluded payloads.
