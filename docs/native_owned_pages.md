# Owned physical pages

The native kernel offers scalar page claims that participate in Sotlas
ownership checking. Allocate a `sole NativeOwnedPages` with
`native_kernel_pages_acquire(count, alignment, zero)`. Transfer it through
`sole` parameters and returns, and borrow it through `whisper` parameters
for checked byte access.

```sotlas
fn write_answer()->u32 {
    let owner:sole NativeOwnedPages=native_kernel_pages_acquire(1,1,true);
    if !native_kernel_owned_pages_store(owner,0,42) {
        native_kernel_owned_pages_close(owner);
        return 1;
    }
    let answer:u32=native_kernel_owned_pages_load(owner,0);
    defer native_kernel_owned_pages_close(owner);
    return answer;
}
```

The byte helpers validate the allocation generation and offset while IF is
clear. Load returns 256 for an invalid claim or offset. Allocation failure
returns an invalid owner; closing it is harmless. Explicit
`native_kernel_owned_pages_release(owner)` consumes the claim and reports
whether release succeeded.

## Transfer to deferred cleanup

A direct deferred call returning `void` can consume qualified POD owners.
Registration moves each consuming argument into cleanup. The original
binding becomes unavailable immediately, while its storage remains reserved
until the deferred call runs. Reading, moving, closing again, mutating or
reassigning that binding is rejected. Use borrowed accesses before registering
the cleanup.

Cleanup executes in LIFO order on lexical exit, early return, loop backedge,
`break` and `continue` along the supported structured paths. A conditional
capture contributes a moved state to the branch merge. Argument computations
retain the existing effect checks. [Cleanup call blocks](native_cleanup_blocks.md)
can group observers and consumers. Consuming methods and consuming calls
returning a value remain outside this contract.

## Runtime boundaries

Initialize the kernel physical allocator before acquiring pages. The API uses
the existing single-processor allocator and its first-GiB physical map.
Treat descriptor fields as opaque and obtain claims through acquisition.
The current native profile exposes scalar record fields, so deliberate
construction of duplicate descriptors can bypass the source-level claim
discipline. Generation checks reject stale releases.

A raw address from `native_kernel_owned_pages_address` remains subject to
the caller's alias and lifetime obligations. Remove all virtual mappings and
stop using raw aliases before release. These operations do not establish
general pointer lifetimes or automatically destroy arbitrary aggregates.

## Verification

The integrated [kernel foundation](native_kernel_foundation.md) transfers page
claims through calls and returns, borrows for checked access, and verifies the
free-page count after ordinary return, early return, backedge, break and
continue. It also covers explicit release and invalid allocation.
The gate rejects use after release, use after deferred capture, and
reassignment through both `--check-build` and `--build-obj`.

`tests/test_sotlas_native_deferred_ownership.py` executes delayed LIFO
cleanup and multi-owner calls, and tests rejected reads, duplicate moves,
mutations, branch merges and incompatible defer forms.
