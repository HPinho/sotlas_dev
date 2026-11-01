# Checked field iteration

This native example sums `10::12::::20::` to 42. It preserves empty fields,
uses `while let` to extract field ranges, skips empty fields with `continue`
and checks that each iteration executes its deferred cleanup. Invalid input
is checked separately from normal exhaustion.

Copy `results.sotlas`, `text.sotlas`, `optional.sotlas` and `text_split.sotlas`
from `runtime/native` to `src/sotlas/runtime/`, and this program to
`src/main.sotlas`. Use a native compiler rebuilt with pattern control:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build field-sum src src/main.sotlas
./field-sum
```

Success exits 42. Use `--build-win field-sum.exe` on Windows, or
`--build-mac field-sum` on Intel macOS. The source uses the same frontend and
runtime modules on all three targets. See [the contract](../../docs/native_pattern_control.md)
for accepted syntax, byte-range semantics and borrowed-storage preconditions.
