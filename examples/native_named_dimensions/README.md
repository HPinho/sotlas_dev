# Named constant array dimensions

This native program uses one module constant for each capacity, then reuses it
in array types, repetition, function results, enum payloads and runtime calls.
It constructs a fixed pool from typed metadata, writes and releases a value,
closes the pool, and destructures an inline array payload. Success exits with 42.

Stage the runtime modules `managed.sotlas` and `pool.sotlas` from `runtime/native`
under `src/sotlas/runtime/`, and copy this program to `src/main.sotlas`:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build dimensions src src/main.sotlas
./dimensions
```

Use `--build-win dimensions.exe` on Windows or `--build-mac dimensions` on
Intel macOS. A compiler rebuilt with named-dimension support is required.
See the [contract](../../docs/native_named_dimensions.md).
