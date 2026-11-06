# Physical pages for the native kernel

The kernel can discover usable RAM from a Multiboot v1 memory map and allocate
4096-byte physical pages. The allocator, boot-map reader and interrupt-safe
kernel adapter are written in Sotlas. The native compiler emits and links the
kernel without generated C, an assembler or an external linker.

## Run the example

With a rebuilt native Linux compiler, Bash and QEMU x86-64 installed:

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-memory --memory --run
```

Choose a fresh output directory. The script checks the imported project,
emits its object, links the boot image and boots QEMU TCG with 64 MiB RAM.
Compiler commands run with host tools absent from PATH. The script supplies a
small boot module so the guest can verify that allocation never overwrites it.
An explicit guest success exit and all four serial markers are required.

The [example](../examples/native_kernel_memory/main.sotlas) exercises:

- aligned contiguous allocation, writes and zero-initialized reuse;
- exact-span release, double-release rejection and generation checks;
- allocation from a timer handler while the main kernel also uses the allocator;
- exhaustion, failed allocation and reuse after exhaustion;
- writes to every allocated page while retaining the boot module unchanged.

The integration gate repeats the same image with 32 and 128 MiB RAM. It also
checks image structure, deterministic linking and rejection of incorrect entry
and interrupt ABIs. Windows and Intel macOS Stage 3 fixtures build and inspect
the same profile; guest execution runs in Linux QEMU.

## Allocation contract

`runtime/native/pages.sotlas` manages caller-provided metadata. `NativePages`
must start as `native_pages_empty()` at a stable address. State bytes and
generation words must be writable, disjoint from the control record, and remain
exclusively owned and accessible for its lifetime. The API does not establish
pointer provenance or authenticate caller-forged metadata.

`native_pages_open` starts with all pages reserved. Before sealing, configuration
can offer complete pages or reserve every page touched by an interval. Overlap
does not double-count free pages. `native_pages_import_map` first validates the
entire variable-length map, then offers type-1 intervals and reserves every
other type, regardless of record order. Invalid maps publish no free pages.
Maps are limited to 64 KiB and 1024 entries; record extensions are skipped.

After `native_pages_seal`, the map is immutable. Allocation accepts a positive
page count and a power-of-two page alignment. It returns an invalid span if no
contiguous run fits. A release must match the current head, complete length and
generation; partial, interior, stale and duplicate releases fail. Generation
exhaustion refuses further allocations rather than wrapping. Handles identify
allocations; copying one does not create another ownership claim.

## Kernel handoff and reservations

`runtime/native/kernel_memory.sotlas` uses the first GiB identity map installed
by the native boot image. Available memory above that limit is not allocated.
The owned image emitter writes a version-1 `MEM1` descriptor at physical
`0x100340`: magic/version, kernel start, kernel end including BSS, and mapped
limit. Older images without that descriptor are rejected.

Initialization requires the Multiboot magic, a readable aligned handoff and a
valid memory map. It reserves low memory through the kernel's actual end,
including allocator metadata, startup stack, page tables and IDT. It also
reserves the handoff, map storage, module descriptors, module payloads, command
line and bootloader/module strings. At most 256 modules and 4096 bytes per
retained string are accepted. Malformed input leaves allocation unavailable.
A completed initialization cannot be repeated. Failure after metadata has been
opened leaves it unusable and is a boot failure, rather than a reset operation.

The bootloader must supply readable RAM pointers and must not overlap the loaded
kernel with its handoff structures. Bounds checks cannot establish that a
physical address contains RAM. Other optional firmware/debug tables are not
retained by this adapter; copy or reserve any such data before using it after
initialization. The underlying record layout follows the
[Multiboot v1 boot information format](https://www.gnu.org/software/grub/manual/multiboot/html_node/Boot-information-format.html).

Allocation metadata updates save and disable interrupts, then restore the
caller's IF state. Zeroing happens after an allocation is committed. The kernel
adapter accepts releases only from its own allocator. It is for a single
bootstrap processor: payload aliases remain the caller's responsibility and
there is no SMP lock, general heap, virtual-memory mapper or automatic drop
integration in this profile.

## Verification

`tests/test_sotlas_native_pages.py` executes native positive and negative cases
for alignment, fragmentation, reservations, generations, metadata overlap,
map extensions, interval overflow and malformed maps. `tests/native_kernel_gate.py`
connects the runtime to the original-source Stage 3 fixtures and QEMU boots.
The fixture deliberately keeps spaces in its temporary build path. QEMU's
Multiboot module parser interprets whitespace inside `-initrd` values, even
when the shell passes one quoted argument. Both the build script and additional
RAM-size checks therefore launch QEMU from the build directory and pass the
fixed `boot-module.bin` basename. Image paths remain absolute.
Local Windows/Linux rebuilds retain strict Stage 2/3 identity; platform CI is
still required before certifying the new commit.
