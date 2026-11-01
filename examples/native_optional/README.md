# Optional values and checked text lookup

The example finds a configuration separator, propagates a missing index with
`?`, checks cleanup on both paths and parses the present value. Invalid input
is checked separately from a valid search that returns `None`. Success exits 42.

Copy `results.sotlas`, `text.sotlas` and `optional.sotlas` from `runtime/native`
to `src/sotlas/runtime/`, and this program to `src/main.sotlas`. Use a native
compiler rebuilt with Some/None propagation:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build optional src src/main.sotlas
./optional
```

Use `--build-win optional.exe` on Windows or `--build-mac optional` on Intel
macOS. See [the contract](../../docs/native_optional.md) for supported forms,
borrowed input preconditions and the distinction between absence and failure.
