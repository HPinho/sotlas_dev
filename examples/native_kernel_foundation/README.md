# A Bare Metal foundation built and executed in Sotlas

The [kernel source](main.sotlas) combines physical page allocation,
virtual memory protection, a page-backed heap, UTF-8 text, dynamically
sized collections, timer interrupts and a configuration file from an
immutable Multiboot CPIO module. It tests the interfaces as one program
rather than as disconnected API probes.

From the repository root, with a native Linux x86-64 Sotlas compiler
that already passed Stage 2/3 reconstruction:

```sh
bash scripts/build_kernel.sh /path/to/sotlas-native build/kernel-foundation --foundation --run
```

Use a **fresh** output directory; the script rejects replacing an existing
build. It builds a module list, checks the Sotlas program, writes a native
object, links a Multiboot kernel, and boots it under QEMU. Success is QEMU
exit **85** for guest return **42**, with three named serial checkpoints.
A missing module, invalid mapping, failed heap operation, stale view,
missing interrupt or leaked page causes a different guest exit.

[Scope and evidence](../../docs/native_kernel_foundation.md) describes
the exact contracts and limitations. This is a single-bootstrap-processor,
ring-0 integration gate rather than a complete OS.
