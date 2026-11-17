# Kernel development from the installed native SDK

The native SDK includes the original kernel examples, runtime modules and
build scripts. Its native compiler checks the Sotlas sources, emits an owned
ELF64 object and links a Multiboot image without Python, generated C, a C
compiler, an assembler or an external linker after receiving the seed.

Image generation supports the advertised Linux x86-64, Windows x86-64 and
Intel macOS compiler hosts. Boot execution in this gate uses Linux QEMU TCG.
QEMU is an emulator dependency, not a compiler/linker dependency or a bundled
part of the SDK. These images are integration examples, not a complete OS or
physical-machine certification.

## Build a profile

From the installed SDK directory, using fresh output paths:

```bash
bash scripts/build_kernel.sh "$PWD/bin/sotlas-native" "$HOME/sotlas-kernel" --foundation
```

Windows, from the installed SDK directory:

```powershell
& ./scripts/build_kernel.ps1 ./bin/sotlas-native.exe "$HOME/sotlas-kernel" -KernelProfile foundation
```

| Profile | POSIX option | Sotlas example |
|---|---|---|
| Basic boot | no profile option | `examples/native_kernel_boot` |
| Interrupts | `--interrupts` | `examples/native_kernel_interrupts` |
| Physical memory | `--memory` | `examples/native_kernel_memory` |
| Heap | `--heap` | `examples/native_kernel_heap` |
| Collections | `--collections` | `examples/native_kernel_collections` |
| Virtual memory | `--vm` | `examples/native_kernel_vm` |
| Integrated foundation | `--foundation` | `examples/native_kernel_foundation` |

PowerShell uses the profile name in the first column's corresponding source
suffix: `boot`, `interrupts`, `memory`, `heap`, `collections`, `vm`, `foundation`.
Each build writes `src`, `kernel.o` and `kernel.elf`; memory/foundation also
produce a deterministic `boot-module.bin`. Existing output directories are
rejected. Compilation and linking run with host build tools absent from PATH.

## Boot and verify

Install QEMU x86-64 and the `timeout` utility on Linux, then add `--run`:

```bash
bash scripts/build_kernel.sh "$PWD/bin/sotlas-native" "$HOME/sotlas-kernel-boot" --foundation --run
```

Success requires guest return **42**, QEMU exit **85**, and all three expected
serial checkpoints in `serial.log`. A timeout, missing marker or different
exit status fails verification. The command uses QEMU's Multiboot loader,
64 MiB RAM and TCG, with no display. It does not install a bootloader on a disk.
Module filenames are passed as fixed relative names inside the build directory
so QEMU's own initrd command-line parser handles directories containing spaces.
Windows users can copy the resulting image/module to Linux, or use the Linux
SDK inside WSL; do not pass a Windows seed Linux source paths.

To verify the complete installed kernel delivery:

```bash
bash scripts/verify_kernel_sdk.sh "$PWD/bin/sotlas-native" "$HOME/sotlas-kernel-check" --boot
```

On Intel macOS omit `--boot`. On Windows:

```powershell
& ./scripts/verify_kernel_sdk.ps1 ./bin/sotlas-native.exe "$HOME/sotlas-kernel-check"
```

This builds all seven profiles, checks deterministic relinking, and requires
four invalid links to fail while preserving a valid output image: wrong entry
ABI, hosted syscall, missing entry and malformed object. Linux `--boot` executes
the basic and integrated foundation profiles. Reports include `summary.md`,
`images.sha256`, rejection diagnostics and serial logs for the two booted
profiles. The other five profiles are emitted here; their broader execution
evidence remains in the existing per-profile kernel gates.

## Preview examples and ownership claims

| Example | Exercised contract | Storage/resource responsibility |
|---|---|---|
| Terminal calculator | Parsing, arithmetic, recoverable input errors and OS I/O | Caller-backed bounded buffers; no claim of automatic ARC |
| Windows calculator | Validated scene snapshots, keyboard editing, adaptive grids and drawing | Session-owned item/text storage, explicit OS paint/window cleanup |
| Kernel foundation | Privileged machine operations, Multiboot, page/VM/heap integration, IRQs and immutable boot data | Tracked page handles, checked views and explicit reclamation under the profile's interrupt rules |

The same frontend/backend builds these examples. The kernel linker rejects
hosted syscalls rather than silently treating OS calls as hardware operations.
The [boot contract](native_kernel_boot.md) defines entry ABI, memory ranges,
reserved intrinsic names and rejection rules. The
[foundation contract](native_kernel_foundation.md) defines its runtime limits.
General ownership/lifetime parity, SMP, scheduling, userspace, UEFI and hardware
drivers are separate work.

CI attaches images/logs as `sotlas-kernel-sdk-linux`, `sotlas-kernel-sdk-windows`
and `sotlas-kernel-sdk-macos`. Use artifacts from a fully green run matching the
SDK revision; checksums identify bytes and do not provide publisher signatures.
Missing QEMU affects boot verification; it does not prevent image generation.
