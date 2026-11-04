# Kernel heap

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-heap --heap --run
```

Use a current native Linux compiler and a fresh build directory. QEMU boots a
Sotlas kernel that allocates and resizes buffers, preserves data on failure,
handles heap allocations from timer interrupts, and returns its physical pages
after all buffers are released.

See the [heap API and limits](../../docs/native_kernel_heap.md). The reservation
size is explicit, and allocation is for one processor with manual resource
ownership.
