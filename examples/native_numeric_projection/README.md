# CPU numeric projection

This example runs a small row-major f32 projection, residual addition, scale
and dot product using Sotlas CPU kernels. It checks `[30.0, 12.0]` and exits 42.
It does not load a model or dispatch to a GPU/NPU.

Create this project layout, using the runtime module from this checkout:

```text
src/main.sotlas                         <- main.sotlas in this directory
src/sotlas/runtime/tensor_cpu.sotlas     <- runtime/native/tensor_cpu.sotlas
```

With a native compiler rebuilt with numeric place updates:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build projection src src/main.sotlas
./projection
```

Use `--build-win projection.exe` on Windows or `--build-mac projection` on
Intel macOS with the same source arguments. After obtaining the native seed,
this path requires no Python, generated C, host compiler or external linker.
The [contract](../../docs/native_numeric_projection.md) explains caller-owned
buffer lifetimes, shape and overlap checks, arithmetic and accelerator limits.
