# Owned kernel heap buffers

`kernel_owned_heap.sotlas` connects variable-sized heap allocations to the
native `sole` and `whisper` contracts. It uses the existing page-backed
kernel heap, generation checks and interrupt-safe operations.

```sotlas
fn use_buffer(heap:*mut NativeKernelHeap)->u32 {
    let first:sole NativeOwnedBuffer=native_kernel_buffer_acquire(heap,8,8,true);
    if !native_kernel_buffer_succeeded(first) {
        native_kernel_buffer_close(first);
        return 1;
    }
    let resized:sole NativeOwnedBuffer=native_kernel_buffer_resize(first,32,16,true);
    let okay:bool=native_kernel_buffer_succeeded(resized);
    defer native_kernel_buffer_close(resized);
    if !okay { return 2; }
    return 42;
}
```

Import `sotlas::runtime::kernel_owned_heap::*` and keep the issuing
`NativeKernelHeap` at a stable, readable address for the lifetime of its
buffers. Open the heap before acquisition. An allocation failure returns an
invalid owner with `succeeded=false`; closing that owner is harmless.

## Operations and transfer

- `native_kernel_buffer_acquire` accepts a positive size, power-of-two
  alignment up to 4096, and an optional zero-fill request.
- `native_kernel_buffer_read` and `native_kernel_buffer_write` borrow a
  `whisper` owner. They check generation, bounds and the issuing heap, with
  IF saved and disabled through the copy. Input and output ranges must remain
  readable or writable as required by the underlying heap copy contract.
- `native_kernel_buffer_length` returns zero for an invalid claim.
  `native_kernel_buffer_succeeded` reports the outcome of acquisition or
  the most recent resize, independently of whether the allocation is live.
- `native_kernel_buffer_resize` consumes its input and returns a new owner.
  Success preserves the common prefix, optionally zeroes a growing tail, and
  gives the allocation a fresh generation. Failure returns the original live
  allocation and bytes with `succeeded=false`. Keep and eventually close
  the returned owner on either outcome.
- `native_kernel_buffer_release` consumes its owner and returns whether
  release succeeded. Its `clear` argument requests clearing the live range.
  `native_kernel_buffer_close` consumes the owner, requests clearing, and
  returns `void` for deferred cleanup.

The compiler rejects use of the original binding after resize or release.
Registering `defer native_kernel_buffer_close(owner)` transfers the owner
into cleanup and makes the binding unavailable immediately. Cleanup follows
the [native deferred ownership contract](native_owned_pages.md).

## Heap lifetime

Claims carry the heap descriptor's identity, slot and allocation generation.
Treat their fields as opaque. The current native profile permits deliberate
construction of scalar descriptors, so generation checking does not establish
provenance for forged claims.

The heap refuses closure while any allocation remains live. Its descriptor
and slot metadata must outlive every buffer, including deferred cleanup.
Do not copy, reset or move a live heap descriptor. The native compiler does
not yet prove that relationship or handle general pointer escapes. Buffers
use explicit consuming cleanup, and the adapter is for one bootstrap CPU.

## Execution evidence

The [integrated kernel](native_kernel_foundation.md) tests growth, shrinking,
prefix preservation, zero-filled extension, failed resize, out-of-bounds
copies, invalid allocation, explicit release and refusal to close a heap with
live buffers. It checks the used-byte count after ordinary return, early
return, loop backedge, break and continue.

The same probes run with the PIT enabled while its callback allocates from
the shared heap. Production frontend gates reject use after release, use
after resize and reassignment after deferred capture through both
`--check-build` and `--build-obj`. The QEMU gate covers 32, 64 and 128 MiB
RAM. Windows and Intel macOS gates emit and inspect the same image.
