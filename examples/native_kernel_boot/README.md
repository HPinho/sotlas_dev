# Boot a native Sotlas kernel

From the repository root on Linux x86-64 or WSL, with a native compiler rebuilt
with `--link-kernel`:

```sh
bash scripts/build_kernel.sh /absolute/path/to/sotlas-native build/my-kernel --run
```

Use a fresh output directory. QEMU (`qemu-system-x86_64`) and `timeout` are
required for `--run`. Without that option, the script only builds `kernel.elf`.
Once a seed is available, kernel compilation and image generation do not use
Python, a C compiler, an assembler or an external linker. QEMU runs the machine;
it does not compile the program.

Successful boot prints:

```text
SOTLAS: kernel entered
SOTLAS: memory, stack, data, SSE OK
SOTLAS: VGA OK
```

The guest explicitly sends 42 to QEMU's debug-exit device. QEMU exits 85; the
script requires that status and all three serial markers. A timeout, crash,
missing marker or different exit code fails the gate.

The image contains a Multiboot v1 protected-mode startup that transitions to
x86-64, initializes page tables, stack and floating-point state, and calls
`kernel_main(magic:u32, info:u32)->u32`. The kernel validates the handoff and
memory, checks BSS/data and native arithmetic, performs UART I/O and writes
physical VGA text memory. Read the [ABI and image contract](../../docs/native_kernel_boot.md)
before replacing the example with your own kernel.
