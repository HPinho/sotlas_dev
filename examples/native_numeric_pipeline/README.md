# Native numeric pipeline

Parse two decimal inputs, add with an overflow check, propagate a structured
error with `?`, then format and parse the result. The same executable verifies
invalid input, overflow, a destination that is too short and LIFO cleanup on
both success and failure. It exits with **42** and prints no output.

Rebuild a native compiler from SV8.97 sources first. Its generated `src` tree
contains the runtime modules required by this example:

```sh
sotlas-native --check-build build/native-selfhost/src examples/native_numeric_pipeline/main.sotlas
sotlas-native --build build/numeric-pipeline build/native-selfhost/src examples/native_numeric_pipeline/main.sotlas
./build/numeric-pipeline
```

On Windows, use `--build-win` and an `.exe` output name. These commands use the
native import resolver, machine-code generator and linker. After obtaining the
seed, the native build path does not start Python, a C compiler or a host linker.

The input strings are fixed test data; this is not an interactive calculator.
The library accepts explicit byte ranges and returns error kind/offset values.
See [native result propagation](../../docs/native_result_propagation.md) for
the concrete result schema, numeric APIs and current boundaries.
