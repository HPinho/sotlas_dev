# Kernel physical memory

Build and run the Sotlas page allocator on QEMU:

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-memory --memory --run
```

Use a fresh output directory and a native Linux compiler rebuilt from current
sources. The guest discovers RAM, allocates aligned page spans, checks zeroed
reuse and stale handles, exhausts usable memory, and preserves a boot module.
A PIT interrupt handler allocates and releases pages during the test.

See the [memory contract](../../docs/native_kernel_memory.md) for reservations,
API preconditions, platform gates and the single-processor scope.
