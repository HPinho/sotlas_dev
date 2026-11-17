# Native virtual-memory kernel

This Sotlas example exercises 4 KiB supervisor mappings, read-only/NX faults,
unmap/remap behavior, MMIO bounds and page-table reclamation. It retains the
bootstrap identity map and does not implement userspace, SMP or system-wide
W^X. See the [VM contract](../../docs/native_kernel_vm.md) for entry, lifetime
and protection limits.

From the repository or installed SDK root, with a native Linux x86-64 seed:

```bash
bash scripts/build_kernel.sh /path/to/sotlas-native /fresh/kernel-vm --vm --run
```

QEMU x86-64 and `timeout` are required for `--run`; omit it to emit an image
on Linux or Intel macOS. On Windows:

```powershell
& ./scripts/build_kernel.ps1 ./bin/sotlas-native.exe C:/fresh/kernel-vm -KernelProfile vm
```

Each command requires a fresh output directory. Compilation/linking use the
native compiler with host build tools absent from PATH. The Linux boot script
requires guest return 42 / QEMU exit 85 and both VM serial checkpoints. The
[installed SDK guide](../../docs/native_kernel_sdk.md) describes all seven
kernel profiles and the separate basic/foundation boot certification gate.
