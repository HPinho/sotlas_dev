# Dynamic collections in the kernel

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-collections --collections --run
```

The kernel grows a u64 sequence, inserts/removes elements, self-appends data,
checks views and sums, then releases its vector, heap and physical pages.
Timer interrupts allocate temporary buffers between serialized vector calls.

Use a current native Linux compiler and a fresh output directory. See the
[vector contract](../../docs/native_vector.md) for element layout, borrow rules
and view invalidation. POD byte layouts do not implement language generics or
automatic cleanup of resource-bearing elements.
