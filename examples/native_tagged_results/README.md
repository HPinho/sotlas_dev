# Tagged results and native propagation

This program combines a concrete `Ok/Err` enum, postfix `?`, checked parsing,
checked addition and lexical cleanup. It verifies success, an invalid byte with
its exact offset, overflow and cleanup on every return. Success exits with 42.

Copy `runtime/native/results.sotlas` to `src/sotlas/runtime/results.sotlas`
and this program to `src/main.sotlas`. Use a native seed rebuilt with tagged
result propagation:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build tagged-results src src/main.sotlas
./tagged-results
```

Use `--build-win tagged-results.exe` on Windows or `--build-mac tagged-results`
on Intel macOS. See [the supported contract](../../docs/native_tagged_results.md).
