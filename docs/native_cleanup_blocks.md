# Consuming cleanup blocks

The native compiler accepts a deferred sequence of calls that reads qualified
POD owners and transfers them to direct `void` cleanup functions.

```sotlas
defer {
    native_kernel_owned_pages_load(pages,0);
    native_kernel_buffer_close(buffer);
    native_kernel_owned_pages_close(pages);
}
```

The block's calls execute in source order. Separate deferred actions execute
in LIFO order. The example can inspect its page claim before closing it.
Reading it after its close in the same block is rejected.

## Capture and scope

Registration checks every argument and simulates reads and transfers in call
order. A consumed owner becomes unavailable to subsequent source statements
immediately. Its original local storage is reserved until cleanup. Reading,
moving, mutating or reassigning that binding while it is captured is rejected.

An owner that the block only borrows remains readable under the existing
deferred observer contract, and cannot be moved before cleanup. A reservation
from a separate earlier defer also prevents consumption by a later defer.

Once an inner scope has finished its cleanup, a moved mutable binding can
receive a new owner. Conditional capture participates in the existing moved
and maybe-moved branch merges. The supported structured cleanup paths include
ordinary scope exit, return, loop backedge, `break` and `continue`.

## Accepted block contents

Owner-capturing blocks contain at most 128 call statements. A call that
consumes an owner must be a resolved call returning `void`. Direct calls,
[consuming methods and associated functions](native_consuming_methods.md) are
accepted. Borrowing
observers retain their existing result and receiver contracts.

The existing checks for argument effects still apply. Assignments, local
declarations, nested control flow, nested defers and
consuming calls returning a value are rejected in owner-capturing blocks.
These rules allow cleanup sequencing without introducing general closures.

Physical claims and heap buffers remain subject to their runtime contracts.
Keep heap descriptors alive and remove raw aliases or virtual mappings before
releasing their backing resources.

## Verification

`tests/test_sotlas_native_deferred_ownership.py` checks delayed execution,
read-before-consume ordering, LIFO, inner-scope rebinding, ordinary and early
returns, loop backedges and jumps. Negative cases cover duplicate consumption,
read-after-consume, use after capture, reassignments and unsupported statements.

The [integrated kernel](native_kernel_foundation.md) groups page and heap
buffer cleanup, checks their contents before release, and verifies both free
pages and heap usage after each path. The same probes run with PIT interrupts
allocating from the shared heap. Its frontend gate rejects invalid captures
through both `--check-build` and `--build-obj`.
