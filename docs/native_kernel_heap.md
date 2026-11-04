# A page-backed heap in Sotlas

The native kernel can allocate variable-sized buffers from a physical page
reservation, resize them while preserving their bytes, release them individually
and return the reservation to the page allocator when the heap closes.

The implementation is in `runtime/native/heap.sotlas` and
`runtime/native/kernel_heap.sotlas`. It uses the existing Sotlas memory-move
routine and physical page allocator. There is no generated C, foreign allocator
or host runtime in the kernel's allocation path.

## Build and run

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-heap --heap --run
```

Use a current native Linux compiler, Bash, QEMU x86-64 and a fresh output
directory. Compilation and linking run with host tools absent from PATH. The
guest must produce three serial markers and an explicit success exit.

The [example](../examples/native_kernel_heap/main.sotlas) reserves eight pages
and supplies 128 metadata slots. It grows a buffer around a live neighbor,
checks preserved bytes and a zeroed tail, rejects an oversized resize without
losing the old allocation, then performs 3000 allocation/resize/release cycles
with PIT interrupts enabled. The timer handler also allocates, writes and frees
buffers. Finally the guest exhausts the heap, rejects an out-of-bounds write,
closes the heap, checks that all eight pages returned, and reopens it while
rejecting an old handle.

The integration gate boots the same image with 32, 64 and 128 MiB of RAM. Native
Windows and Intel macOS Stage 3 fixtures also compile and inspect the image;
the Linux fixture executes it in QEMU.

## Portable allocation API

`NativeHeap` manages a caller-owned buffer and a separate array of
`NativeHeapSlot` records. The control record, metadata and payload must be
writable, disjoint and remain at stable addresses. Initialize the control once
with `native_heap_empty()`, then call `native_heap_open`. All storage and raw
pointer arguments must refer to accessible memory supplied by the caller.

- `native_heap_allocate`: a positive byte size, power-of-two alignment from 1
  through 4096, and optional zero-initialization.
- `native_heap_calloc`: checked count/stride multiplication and zeroed bytes.
- `native_heap_resize`: a fresh handle on success; preserved prefix bytes and
  optional zeroing of an expanded tail. Failure preserves the old handle,
  length and bytes. Even a successful same-size resize changes the generation.
- `native_heap_read` / `native_heap_write`: generation and allocation-bound
  checks before an overlap-safe copy. Raw source/destination memory remains the
  caller's responsibility. `native_heap_address` provides a raw borrow.
- `native_heap_release`: optional clearing, then individual reuse of the hole.
  Duplicate or stale release fails.
- `native_heap_close`: refuses live allocations. A later open preserves the
  allocation sequence, so old handles do not become valid again.

Handles are allocation identities, not independent reference-counted owners.
Copies share the same allocation. Successful resize invalidates earlier handles
and all raw aliases to the old allocation, even if its address stays unchanged.
Release and close also invalidate raw aliases. Do not reset the sequence,
overwrite initialized control records, mutate metadata, or duplicate live
descriptors. These APIs do not prove pointer provenance or replace language-level
ownership analysis.

The allocator searches for aligned holes among live intervals. Adjacent freed
intervals become one available hole without an explicit coalescing pass. Resize
can reuse its own interval and does not require an extra metadata slot. There
are at most 4096 slots; byte capacity and slot capacity can exhaust separately.
The used-byte count excludes alignment gaps and does not promise a contiguous
allocation of `capacity-used` bytes. Search is bounded by the slot count and
can take quadratic work; this is not a real-time allocator.

## Kernel lifecycle

Create a `NativeKernelHeap` using `native_kernel_heap_empty()` at a stable
address and supply exclusively owned slot storage to
`native_kernel_heap_open(descriptor, slots, slot_count, page_count)`. Initialize
the [physical allocator](native_kernel_memory.md) first. A failed heap open
does not retain pages. The entire descriptor is checked against metadata and
the acquired page range.

Kernel allocation, calloc, resize, read/write, release and close save and disable
interrupts, then restore the caller's IF state. Operations verify that the
handle belongs to this heap and that its physical reservation is still live.
Close requires no live buffers and releases the backing pages exactly once.
Do not manipulate the descriptor's internal heap or release its page span
through the lower-level APIs while it is open.

The page reservation is fixed at open time; it does not expand automatically.
The caller selects its size and metadata count. This is a single-processor
kernel API, without SMP locking or automatic ARC/drop integration. Copying and
zeroing execute inside the interrupt-disabled operation; callers must account
for their size and the search cost when choosing interrupt-time work. Raw
payload accesses are not synchronized by the allocator after it returns.

## Validation

`tests/test_sotlas_native_heap.py` covers actual alignment, adjacent and separated
holes, exhaustion of bytes and slots, overlapping relocation, failed resize,
checked copies, metadata overlap, generation exhaustion and close/reopen. Its
mixed workload checks every live byte and every pair of live intervals after
each of 2000 mutations. These cases execute as native programs.

`tests/native_kernel_gate.py --heap --run` exercises the physical backing and
timer handler, checks deterministic image emission and retains entry/interrupt
ABI rejection tests. The delivery also reruns the existing boot, interrupt and
physical-memory profiles. Local execution is evidence for this profile; the
new commit still needs platform CI before release certification.
