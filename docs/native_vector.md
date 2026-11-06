# Heap-backed POD vectors

`runtime/native/vector.sotlas` provides a dynamic sequence over the native
Sotlas heap. It supports geometric growth with exact-capacity fallback, append,
insertion, removal, replacement, checked reads, shrinking, clear and close.
The implementation runs in native applications and in the kernel.

`native_vector_replace` performs an atomic element-range splice: deletion,
insertion and replacement share one preflight and commit. It supports aliased
initialized sources through a temporary snapshot and can shrink without growing
capacity. It also backs the [dynamic UTF-8 text owner](native_heap_text.md).

## Elements and ownership

Initialize a stable `NativeVector` descriptor with `native_vector_empty()`,
then call `native_vector_open(descriptor, heap, stride, alignment)`. Element
stride is a positive byte size through 4096. Alignment is a power of two through
4096 and must divide the stride. Counts and indices are in elements; byte
multiplication is checked before allocation or movement.

This is a byte-layout API for trivially copied POD elements, not language-level
generics or a container for resources needing retain/release or destructors.
Examples include bytes, u64 values and plain records with caller-validated
layout. The descriptor must remain outside the heap's backing buffer, control
record and metadata. Its storage and the heap must outlive the vector and all
views. Do not copy live descriptors, reset their revisions, modify their public
fields or release/resize their internal allocation through the heap API.

Opening an empty vector allocates no bytes. Growth resizes its allocation;
allocation failure preserves length, capacity, contents, storage handle and
revision. Self-insertion snapshots initialized source elements before growth
or shifting. If the snapshot cannot be allocated, the insertion fails without
changing the vector. The snapshot is released on both success and failure.
Pointers into uninitialized capacity are refused as insertion sources.

External input and output pointers must describe accessible memory and must
not alias the vector descriptor or allocator control/metadata. Checked reads
also reject destinations overlapping the vector's own allocation, so reading
a view cannot silently mutate it. Raw pointer provenance remains the caller's
responsibility.

## Views and mutations

`native_vector_view(descriptor, first, count)` creates a checked non-owning
view. `native_vector_read(view, offset, destination, count)` checks the view's
revision and element range before copying bytes. A stale view is rejected
before payload access.

Successful insertion, removal, set, capacity changes, nonempty clear and close
invalidate previous views. No-op reserve, empty insertion/removal, already-empty
clear and already-tight shrink preserve them. Revision exhaustion refuses
further mutations; close can still release storage and permanently retire the
descriptor. Reopening a normally closed descriptor advances its revision and
does not revive old views.

Clear removes logical elements while retaining capacity. Shrink reduces capacity
to length; an empty shrink returns its allocation. Close clears and releases
the allocation. Raw aliases are invalid after growth, shrink or close, and must
not be retained across mutations. Logical removal does not promise secure
erasure of discarded bytes.

## Kernel use

Build the executable word-sequence example with:

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-collections --collections --run
```

Use a current native Linux compiler, QEMU x86-64 and a fresh output directory.
Compiler operations run with host tools absent from PATH.

The example opens a page-backed heap and borrows its native allocation context
using `native_kernel_heap_borrow`. That borrow is refused if the caller's IF
was set. Every collection operation and view access using this context must run
with interrupts disabled; restore the saved IF afterwards. Keep the heap open
and close all collections before it. This is the explicit collection-adapter
exception to using only the higher-level kernel heap API.

The guest appends 2000 u64 values while timer interrupts allocate independent
temporary buffers between collection operations. It removes a range, inserts
and self-appends values, checks the resulting sum, rejects stale/out-of-bounds
views and overflow, shrinks, then closes the vector and returns the heap's
physical pages. Interrupt serialization is for one processor; there is no SMP
lock or automatic ownership cleanup.

## Validation

`tests/test_sotlas_native_vector.py` executes native growth, self-insertion,
capacity/snapshot failure, exact-capacity fallback, u64 layout, range/overflow
checks, descriptor overlap, terminal revisions, stale storage and view tests.
A 500-operation edit sequence is compared after every mutation with an
independent fixed-array model.

The Stage 3 kernel fixtures build the imported collection project on Windows,
Linux and Intel macOS. Linux QEMU runs the same image with 32, 64 and 128 MiB.
Local Windows/Linux native execution is verified separately; platform CI for
the new commit remains required.
