# Native tensor preprocessing

This complete Sotlas program applies per-feature offsets and scales to two
three-feature samples, computes per-sample means/maxima and projects the
transformed samples with the existing CPU matrix-vector kernel. It uses
caller-owned stack storage throughout. It does not allocate, print output or
invoke Python, a C compiler or an external linker after receiving a native seed.

The expected transformed rows are `[0, 0, 0]` and `[15, 30, 60]`. Their means
are `0` and `35`, maxima are `0` and `60`, and projection scores are `0` and
`-45`. Exit code zero means every result matched; codes 1–6 identify a failed
kernel or result check in `main.sotlas`.

From the repository root, stage the two runtime modules and the original source
under a fresh source directory. On Linux:

```bash
mkdir -p build/tensor-rows-src/sotlas/runtime
cp runtime/native/tensor_cpu.sotlas runtime/native/tensor_ops.sotlas build/tensor-rows-src/sotlas/runtime/
cp examples/native_tensor_rows/main.sotlas build/tensor-rows-src/main.sotlas
/path/to/sotlas-native --check-build build/tensor-rows-src build/tensor-rows-src/main.sotlas
/path/to/sotlas-native --build build/tensor-rows build/tensor-rows-src build/tensor-rows-src/main.sotlas
./build/tensor-rows
```

Use `--build-win build/tensor-rows.exe` on Windows or `--build-mac build/tensor-rows`
on Intel macOS; the remaining source-root and entry arguments are unchanged.
The [tensor operations contract](../../docs/native_tensor_ops.md) defines
shapes, aliases, empty inputs, status codes and floating-point behavior.
These are serial CPU kernels, with no GPU/NPU dispatch or performance claim.
