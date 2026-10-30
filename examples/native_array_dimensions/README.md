# Constant array dimensions

The native compiler evaluates literal arithmetic in fixed-array dimensions and
repetition counts. This example composes record arrays, inline scalar arrays,
an enum payload, function return and a match. Success exits with 42.

Use a native compiler rebuilt with dimension-expression support:

```sh
sotlas-native --check examples/native_array_dimensions/main.sotlas
sotlas-native examples/native_array_dimensions/main.sotlas dimensions
./dimensions
```

On Windows choose an `.exe` output filename. See the
[contract and limits](../../docs/native_array_dimensions.md).
