# Integrated native Bare Metal foundation (x86-64)

**Maturity:** native integration candidate, pending its own complete CI.

This end-to-end profile demonstrates one Sotlas-built ring-0 kernel executing
the already bounded and separately tested low-level APIs **together**:
Multiboot handoff and initramfs, interrupt dispatch and PIT, physical pages,
supervisor virtual memory, the page-backed heap, POD vectors, a word map,
and persistent UTF-8 text. It does not expand the accepted language grammar
or claim a general-purpose operating system.

## Compile and boot

```sh
bash scripts/build_kernel.sh /path/to/sotlas-native build/kernel-foundation --foundation --run
```

Use a fresh build directory, a reconstructed native Linux x86-64 compiler
and QEMU. The script stages original Sotlas runtime sources and a small
CPIO `newc` initramfs. Following the native seed, the compiler's check,
object emission and owned freestanding linker do not invoke Python, an
external C compiler or a system linker.

`--foundation` is exclusive with the existing specialized kernel profiles.
It retains the module's fixed QEMU-safe basename even when the build
directory contains spaces. The emulator must return guest status **42**
(QEMU `isa-debug-exit` process status **85**) and emit all three complete
serial markers:

```text
SOTLAS: foundation initramfs and VM OK
SOTLAS: foundation IRQ and data OK
SOTLAS: foundation reclaim and ownership OK
```

## Bounded execution contract

Before installing the VM root, the workload checks
[owned page claims](native_owned_pages.md). It forwards `sole` claims,
uses `whisper` byte access and verifies deferred reclamation across ordinary
return, early return and loop exits. The original page count must be restored
after each probe.

The heap probes also use [owned buffers](native_owned_buffers.md). They
transfer claims through growth, shrinking and a failed resize, check that
deferred cleanup restores the used-byte count, and repeat with timer
interrupts allocating from the same heap.

1. Initialize COM1, the IDT/PIC and boot memory allocator; install a
   new 4-KiB page-table root. A CPU without NX is rejected by this profile;
   the dedicated `--vm` gate verifies the unchanged allocation state.
2. Read `etc/boot.cfg` from a reserved Multiboot module and parse its
   final decimal field as `42`, rejecting a nonexistent file. The archive
   stays borrowed and immutable while consumed.
3. Allocate one physical page, map it writable at `0x40000000`, check
   alias visibility, protect it read-only and later unmap it before release.
   A duplicate mapping fails; the frame is never released while mapped.
4. Open an eight-page heap with caller-owned metadata and construct a POD
   vector, a dynamic word map and heap-backed UTF-8 text in one kernel.
   Copy bytes from the boot configuration into text and reject an obsolete
   revision-bound view after mutation.
5. Install a PIT callback that performs a checked heap allocation/write/
   release while the main routine updates vector and map storage. Mainline
   collection operations hold IF clear, because the current heap borrowing
   contract is single-processor and not SMP-safe.
6. Verify the values, number of vector entries and map counts; reject
   premature heap closure with live children; close every collection,
   then the heap; unmap and release the physical page. Page-table reclamation
   and cleanup must restore the physical free count to the value **after**
   the VM root's three deliberately retained pages were installed.
   The boot module must remain available.

The VM root is **not** destroyed: the bootstrap low identity map and kernel
still use it. That lower 1-GiB mapping remains writable/executable. No
system-wide W^X, automatic ARC, compiler-proven pointer provenance,
user-mode address spaces, TSS/IST, scheduler, SMP or device drivers are claimed.

## CI evidence and release gate

`tests/native_kernel_gate.py` checks the emitted kernel's image structure,
interrupt ABI, deterministic relinking, rejected entry signatures, rejected
hosted-syscall objects and the preservation of existing output on failures.
The Linux Stage 3 gate additionally boots the image in QEMU with 64, 32 and
128 MiB RAM, checking the serial markers and process exit. Windows and Intel
macOS Stage 3 gates cross-build and inspect the same profile.

The standalone boot, interrupt, physical-memory, heap, collections and VM
gates remain active rather than being replaced by this combined test.
No green status is attributed to the new profile until its own CI succeeds.

**Starting certified baseline:** `a25653517a9ce1dff27712ba71e836cfb94edabd`,
[CI #42850078780](https://github.com/HPinho/sotlas_dev/actions/runs/42850078780)
(all 19 jobs green).

## Next language milestone

With this bounded Bare Metal foundation certified, shift the main
development effort back to the native Sotlas compiler: source-level ownership
of page/heap resources, lifetime and escape checking for slices and raw
borrows, bounded resource-bearing aggregate cleanup, negative semantic
diagnostics and Stage 2/3 reconstruction. Keep the integrated foundation
as an executable, non-regression target for those changes.
