# Conditional cleanup

Owner-capturing `defer` blocks accept `if`, `else if`, `else` and
nested blocks. The native compiler uses the same branch-sensitive ownership
analysis as ordinary structured code.

```sotlas
defer {
    if close_buffer_first {
        buffer.close();
        pages.close();
    } else {
        pages.close();
        buffer.close();
    }
}
```

## Execution and capture

Conditions run during cleanup. They read the current values of captured
locals and parameters, so changing an ordinary boolean flag after registration
can change which branch executes. Calls inside the chosen branch run in source
order. Separate deferred actions retain LIFO order.

The compiler checks every branch at registration. It merges moved states
before checking the next cleanup statement. Reading an owner after either
branch consumed it, closing it twice on a possible path, or consuming a
borrowed owner is rejected.

An owner consumed in any branch becomes moved or maybe-moved at registration.
Its storage remains reserved until cleanup. Subsequent reads, moves and
reassignments are rejected even if a runtime condition would skip consumption.
An unexecuted branch adds no implicit release. Write each required release
on all paths, as in the example above.

An owner that the cleanup only observes remains available under the existing
deferred borrow contract. After an inner cleanup scope ends, its reservations
are released. The same structured lowering handles ordinary exit, early return,
loop backedge, `break` and `continue`.

## Checked subset

Conditions use the existing argument-effect proof. Literals, locals,
parameters, scalar owner fields and helpers proved effect-free are accepted.
A condition cannot consume an owner or mutate state through a call.

Cleanup calls keep their existing checks for argument effects, borrowing and
consumption. A call that transfers a qualified owner must return `void`.
Assignments, declarations, loops, nested defers and control transfers inside
owner-capturing cleanup blocks remain outside this contract.
Each block has at most 128 statements, with bounded nesting.

## Verification

`tests/test_sotlas_native_conditional_cleanup.py` checks both branch orders,
LIFO, late condition evaluation, nested blocks, else-if chains, read-only
conditions over owners, early returns and loop jumps. Negative tests cover
maybe-moved reads, double release, reassignment after capture, nonvoid
consumption and effectful conditions.

The [kernel foundation](native_kernel_foundation.md) conditionally closes
page and buffer claims in different orders. It verifies page counts and heap
usage after every path, including timer-enabled execution, with 32, 64 and
128 MiB RAM. Invalid programs fail through both `--check-build` and
`--build-obj`.
