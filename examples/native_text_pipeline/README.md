# Native text pipeline

Process `COUNT = 20` as UTF-8 text: split the key/value, trim ASCII whitespace,
normalize the key, parse a checked integer, add 22 and construct `total=42`.
The executable also checks malformed numbers, a missing separator, overflow,
cleanup on every return and Unicode boundary rejection. It exits with **42**
and prints no output. Inputs are fixed fixtures, not interactive input.

After rebuilding the native compiler from SV8.98 sources, its generated `src`
tree contains both runtime modules:

```sh
sotlas-native --check-build build/native-selfhost/src examples/native_text_pipeline/main.sotlas
sotlas-native --build build/text-pipeline build/native-selfhost/src examples/native_text_pipeline/main.sotlas
./build/text-pipeline
```

On Windows, use `--build-win` and an `.exe` output name. Compilation, imports and
linking run through the Sotlas-written native compiler after obtaining a seed.
No Python, C compiler or external linker is launched by that path.

[Native text](../../docs/native_text.md) documents the fixed 256-byte capacity,
UTF-8 rules, checked operations, error offsets and remaining string/slice work.
