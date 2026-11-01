# Native array iteration

The batch processor combines named array capacities, explicitly tagged results,
postfix `?`, record arrays, by-value iteration and deferred cleanup. It sums the
enabled readings, verifies independent mutable item copies, and checks cleanup
on success, `continue` and a propagated input error. Success exits with 42.

Copy `runtime/native/results.sotlas` to `src/sotlas/runtime/results.sotlas`
and this program to `src/main.sotlas`. Use a native compiler rebuilt with array
iteration support:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build batch src src/main.sotlas
./batch
```

Use `--build-win batch.exe` on Windows or `--build-mac batch` on Intel macOS.
See the [iteration contract](../../docs/native_array_iteration.md) for limits.
