# Dynamic UTF-8 report

This program builds heap-owned text, formats U64_MAX, changes a prefix, reads a
four-byte Unicode scalar through a checked view and releases its allocation.
Native success returns 42. The same API generates a visible report in the
[kernel collection example](../native_kernel_collections/README.md).

For a native Linux compiler, prepare a fresh project directory:

```sh
mkdir -p build/heap-text-demo/src/sotlas/runtime
cp examples/native_heap_text/main.sotlas build/heap-text-demo/src/main.sotlas
for module in results managed text unicode utf8_buffer heap vector heap_text; do
    cp "runtime/native/$module.sotlas" "build/heap-text-demo/src/sotlas/runtime/$module.sotlas"
done
build/native/sotlas-native --build build/heap-text-demo/app build/heap-text-demo/src build/heap-text-demo/src/main.sotlas
build/heap-text-demo/app
echo $? # 42
```

Windows and Intel macOS use the corresponding `--build-win` and `--build-mac`
commands with the same project sources. See the [API contract](../../docs/native_heap_text.md)
for explicit ownership, byte/scalar indices and view invalidation.
