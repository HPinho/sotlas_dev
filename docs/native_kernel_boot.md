# Native x86-64 kernel boot

This delivery connects a native Sotlas compiler, owned ELF linker, owned boot
image emitter and a kernel that actually boots under QEMU. A kernel object's
privileged operations cannot be linked as a hosted Linux, Windows or macOS
application.

## Build and boot

The [example](../examples/native_kernel_boot/README.md) has a reproducible
`scripts/build_kernel.sh NATIVE_COMPILER FRESH_DIRECTORY --run` path. It checks
the imported `barecore` project, compiles an ELF64 object and invokes:

```sh
sotlas-native --link-kernel kernel.o kernel.elf kernel_main
```

The same command emits the image on Windows and Intel macOS; execution in the
automated gate uses Linux QEMU TCG. Compilation and linking run with host build
tools absent from PATH. Bash copies sources and invokes executables; no Python,
generated C, assembler or external linker participates after obtaining a seed.

The kernel runs at ring 0. It verifies the Multiboot memory handoff, BSS zeroing,
initialized static data, stack locals, calls, records, arrays, f64 arithmetic,
UART I/O and writes/reads physical VGA text memory. Serial markers and an explicit
QEMU exit code are required; successful object emission alone does not pass.

## Image and entry ABI

The [Multiboot v1 contract](https://www.gnu.org/software/grub/manual/multiboot/html_node/Machine-state.html)
supplies EAX magic `0x2badb002` and EBX physical info address in protected mode.
The image is an ELF32 loader container with two PT_LOAD segments:

| Range | Purpose |
| --- | --- |
| `0x100000..0x120000` | Startup, GDT, three page-table pages and reserved stack |
| `0x101000..0x104000` | PML4, PDPT and a 512-entry page directory |
| `0x110000..0x120000` | 64 KiB stack; initial RSP `0x120000` |
| `0x400000` onward | Owned ELF64 kernel image, including zero-filled BSS |

The startup disables maskable interrupts, clears the direction flag, checks
long mode and SSE2, identity-maps the first GiB with 2 MiB pages, installs its
GDT, enables PAE and long mode, and initializes x87/MXCSR. RSP is 16-byte aligned
before calling the kernel. The magic and info address arrive as U32 values in
EDI and ESI. The required signature is `fn kernel_main(magic:u32,info:u32)->u32`;
the actual entry symbol name is selected by the command. An ABI manifest must
attest a defined function with that exact scalar signature. A returning kernel
enters a CLI/HLT loop.

The emitter bounds the linked file and its memory extent (at most 32 MiB for
the kernel segment), validates its single-segment ELF64 layout and preserves
the native addresses. It rejects malformed objects, wrong entry signatures,
missing symbols, unsupported relocations and hosted syscall objects before
opening the destination. Repeated links are deterministic. General
freestanding linking and boot-specific image validation are separate checks.

## Privileged native operations

Bodyless declarations with these reserved names lower to typed SystemOp IDs
32 through 35, and require an explicit `unsafe` call:

| Declaration | Instruction/result |
| --- | --- |
| `sotlas_x86_out8(port:u16,value:u8)->i64` | OUT DX, AL; returns zero |
| `sotlas_x86_in8(port:u16)->i64` | IN AL, DX; returns zero-extended byte |
| `sotlas_x86_out32(port:u16,value:u32)->i64` | OUT DX, EAX; returns zero |
| `sotlas_x86_halt()->i64` | HLT; returns zero if resumed |

The `@extern(C)` declaration spelling uses the existing scalar declaration
syntax; these names do not resolve to C functions. IR validation independently
checks argument types, counts and result metadata. The object carries a bare
operation flag, rejected by hosted executable linkers. The kernel linker rejects
Linux/Darwin syscall flags; it does not silently turn OS calls into hardware I/O.

`runtime/native/kernel_x86.sotlas` provides a bounded-poll COM1 UART helper,
checked Multiboot memory-field access and halt support. The explicit
`native_kernel_qemu_exit` helper is an emulator test protocol, not a hardware
shutdown API. QEMU's [debug-exit implementation](https://github.com/qemu/qemu/blob/v10.2.0/hw/misc/debugexit.c)
reports `(value << 1) | 1`. Do not combine the test with `-no-shutdown`: recent
QEMU versions implement this device using a shutdown request.

## Closure and further kernel work

The closed capability is building and booting this native x86-64 kernel path,
with executable acceptance, rejection and CI boot gates. This is not a complete
operating system or a complete firmware/bootloader implementation. A Multiboot
loader supplies the initial protected-mode handoff (QEMU's direct kernel loader
in the test). BIOS disk boot sectors, UEFI firmware services, secure boot,
TSS/IST emergency stacks, SMP, a general allocator, device drivers and
physical-machine certification are separate deliverables. The basic example
leaves interrupts disabled; [the interrupt profile](native_kernel_interrupts.md)
adds a linked Sotlas dispatcher, IDT, exception returns and PIC/PIT timer
execution. The initial low identity map is not a memory-protection design.

The older graphical source in `bootstrap/sotlas/kernel/main.sotlas` is retained
as a historical integration experiment; it is not the entry used by this gate.
The executable example above is the supported evidence for native kernel boot.

## Earlier boot delivery verification

The records below describe the boot/compatibility delivery before the interrupt
extension. Current compiler and image evidence is recorded in the
[interrupt contract](native_kernel_interrupts.md).

CI #1346 exposed a regression: the generic freestanding ELF linker is also
used by Mach-O payload conversion, so its new bare-metal-only flag restriction
rejected valid Darwin objects. The dedicated `--link-kernel` command now enforces
the kernel OS-flag boundary; the shared raw-entry linker retains its original
contract. The startup instruction bytes are emitted as fixed words that the
legacy C oracle can represent, preserving that optional bootstrap gate.
Object verification recognizes the new bare-metal bit and still rejects unknown
bits. The kernel integration gate rejects both Linux and Darwin syscall inputs.

- The original delivery passed 154 related instruction, IR, migration,
  platform-linking, structured-CFG and AST self-host tests, plus 21 example/phase
  inventory tests. CI subsequently exposed the compatibility failures above.
- The regression repair passed 19 selected Mach-O, legacy Stage 1/2/3
  fixed-point and privileged-instruction tests, plus the updated object-flag
  test. The full Darwin driver fixture constructed its Mach-O compiler on
  Windows; actual macOS execution remains a CI responsibility.
- The repaired native compiler also cross-built the complete Darwin compiler
  directly from original Sotlas sources with host tools absent from PATH.
- Original-source native rebuilds preserved strict Stage 2/3 byte identity on
  Windows (`5c2ba975a671...`) and Linux/WSL (`4ff548bc5c82...`) after the repair.
- Both final Stage 3 compilers passed the imported kernel project, image and
  rejection gates. They emitted byte-identical boot images (SHA-256
  `1ef8fdf7b48c4c3a8fe3fde75451ed8c3dfc66aa8044ae77a40ece46759e8faf`).
- The Linux build script booted that image under QEMU 10.2 TCG, produced all
  three required markers and completed with guest result 42 / QEMU exit 85.
- CI now requires the emulator boot in the Linux matrix's native Stage 3
  fixture; Windows and Intel macOS validate image generation and rejection.
  Full CI certification of this commit is pending.
