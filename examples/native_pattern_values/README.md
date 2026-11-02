# Native readings with explicit defaults

The example parses `20`, `22` and `bad` into reading records. Invalid input
uses the caller's default while preserving its parse error. It sums with checked
arithmetic, verifies cleanup and exits 42.

Copy `results.sotlas`, `text.sotlas`, `optional.sotlas` and `parse.sotlas`
from `runtime/native` to `src/sotlas/runtime/`, and this program to
`src/main.sotlas`. Use a native compiler rebuilt with value-producing if-let:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build readings src src/main.sotlas
./readings
```

Use `--build-win readings.exe` on Windows or `--build-mac readings` on Intel
macOS. See the [contract](../../docs/native_pattern_values.md) for supported
values, block syntax and ownership limits.
