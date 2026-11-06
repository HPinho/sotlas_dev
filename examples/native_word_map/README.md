# Native token histogram

This program counts 5000 numeric tokens across 61 distinct keys with a dynamic
map. It verifies every frequency, sums the iteration results, closes the map
and releases the heap. Native success returns 42.

With a native Linux compiler, use a fresh project directory:

```sh
mkdir -p build/word-map-demo/src/sotlas/runtime
cp examples/native_word_map/main.sotlas build/word-map-demo/src/main.sotlas
for module in managed heap word_map; do
    cp "runtime/native/$module.sotlas" "build/word-map-demo/src/sotlas/runtime/$module.sotlas"
done
build/native/sotlas-native --build build/word-map-demo/app build/word-map-demo/src build/word-map-demo/src/main.sotlas
build/word-map-demo/app
echo $? # 42
```

Windows and Intel macOS use `--build-win` and `--build-mac` with the same
project. The [map contract](../../docs/native_word_map.md) describes explicit
ownership, capacity and cursor invalidation. The kernel version is part of
the [collection example](../native_kernel_collections/README.md).
