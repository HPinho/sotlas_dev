# Native x86-64 exceptions and timer interrupts

The kernel path now links a Sotlas interrupt dispatcher, builds an IDT and
machine entry stubs, installs the table, configures the legacy interrupt
controller and receives PIT timer interrupts. The
[executable kernel](../examples/native_kernel_interrupts/README.md) validates
exception frames, return state and repeated hardware timer delivery in QEMU.

```sh
bash scripts/build_kernel.sh /path/to/sotlas-native build/irq-kernel --run --interrupts
```

This command uses the Linux native compiler on Linux/WSL. It requires QEMU and
`timeout` for execution. Compilation and image generation run with host build
tools absent from PATH after obtaining the native seed.

## Dispatcher and image contract

A kernel opts in by defining:

```sotlas
pub fn kernel_interrupt(vector:u32,error:u64,frame:*mut u64)->u32 {
    // Handle the interrupt, then return to the interrupted code.
    return 0;
}
```

The linker verifies the defined symbol's machine ABI: U32, U64, Pointer -> U32.
The frame pointer convention is a writable array of five CPU words: RIP, CS,
RFLAGS, RSP and SS. The handler's U32 return value is ignored. Raw frame access
requires `unsafe`; the pointer is borrowed from the interrupted stack and must
not escape. A wrong callback signature is rejected before publishing an image.
An external declaration without a definition is not an installed dispatcher.

The owned linker resolves the callback's actual address. The image emitter
builds all 256 present DPL-0 interrupt gates and corresponding entry stubs:

| Physical address | Purpose |
| --- | --- |
| `0x100320` | Ten-byte IDTR descriptor, limit 4095 |
| `0x100330` | `IRQ1` capability marker |
| `0x104000..0x105000` | IDT: 256 sixteen-byte entries |
| `0x105000..0x107000` | 256 fixed-size vector entry stubs |
| `0x107000` | Common saved-state entry/return code |

The boot segment contains 32 KiB of file data; the embedded ELF64 kernel begins
at file offset 36864, retaining its native physical address at 4 MiB. Kernels
without the dispatcher retain the basic image layout and have no IRQ marker.
The installer returns false for that image, instead of loading an empty IDT.

CPU error-code vectors 8, 10–14, 17, 21, 29 and 30 preserve the hardware error
word. Other stubs supply zero. Every stub supplies its vector number, then
branches to common code. The common entry saves all fifteen general-purpose
registers, aligns the stack, saves x87/MMX/SSE state with FXSAVE64, clears DF and
calls Sotlas with the normalized vector/error/frame arguments. It restores the
saved state, removes the vector/error words and executes IRETQ. The return
restores the interrupted flags and stack. These conventions follow the
[Intel system-programming contract](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-system-programming-manual-325384.pdf).

## Runtime API

| Function | Behavior |
| --- | --- |
| `native_kernel_interrupts_install()` | Install IDTR and remap/mask both PICs; leave IF clear; reject missing image support or repeat installation |
| `native_kernel_interrupts_disable()` | Save RFLAGS and clear IF |
| `native_kernel_interrupts_restore(flags)` | Restore only the saved IF bit |
| `native_kernel_timer_start(hz)` | Configure PIT channel 0 and unmask IRQ0; accept 19–1000 Hz |
| `native_kernel_timer_interrupt(vector,error)` | Handle IRQ0, update the counter and issue EOI; return false for other vectors |
| `native_kernel_timer_read()` | Read the aligned U64 tick count with interrupts disabled, restoring the caller's IF |
| `native_kernel_timer_wait(count)` | Wait for 1–10000 ticks using STI/HLT/CLI; preserve caller IF; return zero if stopped or the count is invalid |
| `native_kernel_timer_stop()` | Mask IRQ0 and stop counter updates; preserve caller IF |

PIT divisors use integer `1193182 / hz`, so actual frequency is quantized.
Waiting blocks on real hardware delivery; an absent timer can block indefinitely.
The emulator test enforces an external timeout. Unsigned tick differences handle
counter wrap. The interrupt gate keeps IF clear during the dispatcher; the timer
hook must be called from that context. PIC EOI is required for subsequent ticks.

Typed unsafe machine operations add IDs 36–41 to the existing SystemOp family:
IRQ-save/CLI, STI, LIDT, INT3, load-DS and STI/HLT/CLI. They return I64, retain the
bare-metal object flag and are rejected by hosted linkers. LIDT takes a raw
descriptor pointer and load-DS takes U16. IRQ-save returns the saved RFLAGS;
the other operations return zero after normal completion. Existing OS syscall
IDs and Mach-O conversion retain their contracts.

## Execution evidence and scope

The example exercises a real INT3 twice, with IF clear and set, and a real #GP
with error code 24 from an invalid DS selector. Its handler verifies the faulting
opcode, advances RIP by the two-byte instruction and returns with IRETQ. It then
receives repeated PIT IRQs, checks caller IF restoration, executes floating-point
work while timer delivery is enabled, stops the timer and verifies stopped waits.
The handler also performs f64 arithmetic, exercising the FPU state save/restore.
Both required serial markers and QEMU exit 85 are necessary for a passing test.

The gate also validates every IDT entry and stub, deterministic output, rejected
callback ABIs and unchanged existing output on rejection. The Linux matrix runs
the QEMU test through the reconstructed native Stage 3 compiler; Windows and
Intel macOS validate image generation. Native instruction tests enforce unsafe
boundaries and exact machine signatures. The legacy C-oracle bootstrap and
Mach-O compatibility remain regression gates.

This is a single-bootstrap-processor, ring-0, legacy PIC/PIT implementation.
The kernel owns its exception policy and stack budget. There is no TSS/IST
emergency stack, user-mode transition, APIC/SMP dispatch, AVX/XSAVE context,
scheduler or general device-driver registration in this contract. The basic
boot image's 64 KiB stack and executable low identity map remain in effect.

## Local verification

Native instruction, unsafe-boundary and signature tests passed, as did the
legacy C-oracle fixed point and Mach-O compatibility group. All 21 example and
phase-inventory tests passed. Original-source native rebuilds preserved strict
Stage 2/3 identity on Windows (`0e8978e7573e...`) and Linux (`727d66894ebc...`).
The complete original-source Darwin compiler also cross-built without host tools.

Both final native Stage 3 compilers passed image generation, deterministic
re-linking and rejected handler ABI/syscall cases. Their output was identical
across hosts for each profile:

| Image | SHA-256 |
| --- | --- |
| Basic boot | `a9cac9aef120c24073d3668dca7a8e39fcbdb0dcfaa4c151b524c67f5576d3b1` |
| Interrupts/timer | `7786d7a46a95a69e94ebfd466999fb436bdf5d265bc4d391c1a11e3eecffef65` |

Both images booted under Linux QEMU TCG and returned the required exit code
and serial markers. The interrupt run additionally checked invalid frequencies,
invalid wait counts, duplicate installation, stopped waits and caller IF state.
Full platform CI for this commit remains pending.
