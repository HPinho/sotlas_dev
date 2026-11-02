# Composing native Result errors

The report example parses `20::22`, propagates a shared nominal error through
different success types and returns 42. It also checks invalid digit positions,
overflow, explicit destination tags and cleanup on every report path.

Copy `results.sotlas`, `text.sotlas`, `optional.sotlas` and `parse.sotlas`
from `runtime/native` to `src/sotlas/runtime/`, and this program to
`src/main.sotlas`. Use a native compiler rebuilt with error composition:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build report src src/main.sotlas
./report
```

Success exits 42. Use `--build-win report.exe` on Windows or
`--build-mac report` on Intel macOS. See the [contract](../../docs/native_error_composition.md)
for supported error types, diagnostics and borrowed-input preconditions.
