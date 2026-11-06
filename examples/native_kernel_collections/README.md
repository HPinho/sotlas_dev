# Dynamic collections in the kernel

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-collections --collections --run
```

The kernel grows a u64 sequence, inserts/removes elements, self-appends data,
checks views and sums, then releases its vector, heap and physical pages.
Timer interrupts allocate temporary buffers between serialized vector calls.

It also builds a growing UTF-8 report, formats the smallest i64 value, rejects
an edit inside a multibyte scalar and releases the text before closing the heap.
See the [text contract](../../docs/native_heap_text.md).

A [dynamic u64 map](../../docs/native_word_map.md) counts 6000 numeric tokens
across 257 keys, verifies the histogram, removes an entry and compacts the table.
Timer handlers use the same heap between serialized operations. Map storage is
released before the final text report and heap/page cleanup.

Use a current native Linux compiler and a fresh output directory. See the
[vector contract](../../docs/native_vector.md) for element layout, borrow rules
and view invalidation. POD byte layouts do not implement language generics or
automatic cleanup of resource-bearing elements.
