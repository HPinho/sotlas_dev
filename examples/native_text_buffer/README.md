# Caller-backed UTF-8 report buffer

Build a 551-byte report in a 1024-byte local buffer, append a Unicode scalar,
edit a value, reject a split scalar, truncate and append a view of the buffer
itself. A defer clears the used bytes before return. Expected exit status: **42**;
the executable prints no output and uses fixed input fixtures.

After rebuilding a native compiler from SV8.99 sources:

```sh
sotlas-native --check-build build/native-selfhost/src examples/native_text_buffer/main.sotlas
sotlas-native --build build/text-buffer build/native-selfhost/src examples/native_text_buffer/main.sotlas
./build/text-buffer
```

On Windows use `--build-win` and an `.exe` output name. The generated source
root includes the runtime modules. Compilation, import resolution and linking
use the native Sotlas compiler after obtaining the seed.

See [UTF-8 buffers](../../docs/native_utf8_buffer.md) for storage lifetimes,
alias rules, failure behavior and the distinction from allocated strings.
